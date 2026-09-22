#!/usr/bin/env python3
"""Monarchy for Windows Edition.

Portable local listener, dashboard, Roblox launcher, and biome watcher.
Windows-only integrations are imported lazily so the source can still be
syntax-checked on another platform.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import messagebox, ttk

APP_VERSION = "0.3.8"
GITHUB_REPOSITORY = "PixelatingStars/Monarchy"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
PLACE_ID = "15532962292"
PORT = 17381
BIOMES = {"CORRUPTION", "DREAMSPACE", "GLITCH", "CYBERSPACE", "SINGULARITY", "HELL"}
MIXED_CHANNEL = "BIOME-SPAWNER"
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
LOG_FILE = DATA_DIR / "activity.log"
CHANNEL_FILE = DATA_DIR / "channel.json"
DEFAULT_SETTINGS = {
    "close_roblox_on_stop": True,
}


def github_request(url: str, accept="application/vnd.github+json"):
    headers = {"Accept": accept, "User-Agent": f"Monarchy/{APP_VERSION}",
               "X-GitHub-Api-Version": "2022-11-28"}
    return urllib.request.Request(url, headers=headers)


def version_key(value: str):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
    return tuple(map(int, match.groups())) if match else None


def latest_update() -> dict | None:
    with urllib.request.urlopen(github_request(f"{GITHUB_API}/releases/latest"), timeout=10) as response:
        release = json.load(response)
    latest = version_key(str(release.get("tag_name", "")))
    current = version_key(APP_VERSION)
    if not latest or not current or latest <= current:
        return None
    assets = {asset["name"]: asset for asset in release.get("assets", [])}
    archive = assets.get("Monarchy-Windows-Portable.zip")
    checksum = assets.get("Monarchy-Windows-Portable.zip.sha256")
    if not archive or not checksum:
        raise ValueError("release is missing the portable ZIP or SHA-256 file")
    return {"version": str(release["tag_name"]).lstrip("v"), "archive": archive["url"],
            "checksum": checksum["url"], "page": release.get("html_url", "")}


def download_asset(url: str, destination: Path) -> None:
    with urllib.request.urlopen(github_request(url, "application/octet-stream"), timeout=60) as response:
        with destination.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)


def stage_update(update: dict) -> Path:
    update_dir = DATA_DIR / "update"
    update_dir.mkdir(parents=True, exist_ok=True)
    archive = update_dir / "Monarchy-Windows-Portable.zip"
    checksum = update_dir / "Monarchy-Windows-Portable.zip.sha256"
    download_asset(update["archive"], archive)
    download_asset(update["checksum"], checksum)
    expected = checksum.read_text(encoding="utf-8").strip().split()[0].lower()
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or actual != expected:
        archive.unlink(missing_ok=True)
        raise ValueError("downloaded update failed SHA-256 verification")
    script = Path(tempfile.gettempdir()) / f"monarchy-update-{os.getpid()}.ps1"
    script.write_text(r'''param([string]$AppDir,[string]$Archive,[int]$ProcessId)
$ErrorActionPreference = "Stop"
Wait-Process -Id $ProcessId -ErrorAction SilentlyContinue
$Stage = Join-Path $env:TEMP ("Monarchy-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Stage | Out-Null
Expand-Archive -Force $Archive $Stage
$Source = $Stage
if (-not (Test-Path (Join-Path $Source "Monarchy.exe"))) {
    $Child = Get-ChildItem $Stage -Directory | Select-Object -First 1
    if ($Child -and (Test-Path (Join-Path $Child.FullName "Monarchy.exe"))) { $Source = $Child.FullName }
}
& robocopy.exe $Source $AppDir /E /XD (Join-Path $Source "data") /R:2 /W:1 | Out-Null
if ($LASTEXITCODE -gt 7) { throw "Could not replace Monarchy files (robocopy exit $LASTEXITCODE)." }
Remove-Item $Stage -Recurse -Force
Start-Process (Join-Path $AppDir "Monarchy.exe")
''', encoding="utf-8")
    return script
PUBLIC_PATTERN = re.compile(
    r"(?:roblox://(?:placeID=|experiences/start\?[^\s]*?placeId=)|"
    r"https?://hewa7798\.github\.io/chromahublink/?\?[^\s]*?placeId=)"
    r"(?P<place>\d+)[^\s]*?gameInstanceId=(?P<instance>[0-9a-f-]{36})", re.I,
)
PRIVATE_PATTERN = re.compile(
    r"https?://(?:www\.)?roblox\.com/games/(?P<place>\d+)(?:/[^?\s]*)?"
    r"\?[^\s]*?privateServerLinkCode=(?P<code>[a-z0-9_-]+)", re.I,
)
SHARE_PATTERN = re.compile(
    r"https?://(?:www\.)?roblox\.com/(?:share|share-links)"
    r"\?[^\s]*?code=(?P<code>[a-f0-9]{32})[^\s]*?type=Server", re.I,
)


def load_settings() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    saved = {}
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        pass
    result = json.loads(json.dumps(DEFAULT_SETTINGS))
    if isinstance(saved, dict):
        if "close_roblox_on_stop" in saved:
            result["close_roblox_on_stop"] = saved["close_roblox_on_stop"]
    return result


_log_lock = threading.Lock()


def log(component: str, message: str) -> None:
    line = f"{datetime.now().astimezone().isoformat(timespec='seconds')} [{component}] {message}"
    with _log_lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")


def notify(title: str, body: str) -> None:
    try:
        from winotify import Notification
        toast = Notification(app_id="Monarchy", title=title, msg=body)
        toast.show()
    except Exception:
        log("notify", f"{title}: {body}")


def parse_link(url: str):
    match = PUBLIC_PATTERN.search(url)
    if match and match.group("place") == PLACE_ID:
        instance = match.group("instance").lower()
        return f"public:{instance}", f"roblox://experiences/start?placeId={PLACE_ID}&gameInstanceId={instance}"
    match = PRIVATE_PATTERN.search(url)
    if match and match.group("place") == PLACE_ID:
        code = match.group("code")
        return f"private:{code.lower()}", f"roblox://placeId={PLACE_ID}&linkCode={code}"
    match = SHARE_PATTERN.search(url)
    if match:
        code = match.group("code").lower()
        return f"share:{code}", f"roblox://navigation/share_links?code={code}&type=Server"
    return None


def roblox_processes():
    import psutil
    names = {"robloxplayerbeta.exe", "windows10universal.exe"}
    found = []
    for process in psutil.process_iter(("name",)):
        try:
            if (process.info["name"] or "").lower() in names:
                found.append(process)
        except (psutil.Error, OSError):
            pass
    return found


def roblox_running() -> bool:
    return bool(roblox_processes())


def close_roblox() -> None:
    import psutil
    processes = roblox_processes()
    for process in processes:
        try:
            process.terminate()
        except (psutil.Error, OSError):
            pass
    _, alive = psutil.wait_procs(processes, timeout=5)
    for process in alive:
        try:
            process.kill()
        except (psutil.Error, OSError):
            pass


def discord_title_channel():
    try:
        import win32gui
        titles = []
        win32gui.EnumWindows(
            lambda hwnd, _: titles.append(win32gui.GetWindowText(hwnd))
            if win32gui.IsWindowVisible(hwnd) else None, None,
        )
        source = " ".join(title.upper() for title in titles if "DISCORD" in title.upper())
    except Exception:
        return None
    for label in (MIXED_CHANNEL, "CORRUPTION", "DREAMSPACE", "GLITCHED",
                  "GLITCH", "CYBERSPACE", "SINGULARITY", "HELL"):
        if label in source:
            name = "GLITCH" if label == "GLITCHED" else label
            return name, "BIOME"
    return None


def channel_from_text(text: str):
    source = text.upper()
    for label in (MIXED_CHANNEL, "CORRUPTION", "DREAMSPACE", "GLITCHED",
                  "GLITCH", "CYBERSPACE", "SINGULARITY", "HELL"):
        if label in source:
            name = "GLITCH" if label == "GLITCHED" else label
            return name, "BIOME"
    return None


def discord_desktop_snapshot():
    """Return accessible Discord text and its selected channel, if exposed."""
    from pywinauto import Desktop
    messages = []
    selected_channel = None
    windows = Desktop(backend="uia").windows(title_re=r"(?i).*discord.*", visible_only=True)
    for window in windows:
        for control in window.descendants():
            try:
                text = (control.element_info.name or "").strip()
            except Exception:
                continue
            if text and len(text) <= 8192:
                messages.append(text)
                try:
                    properties = control.legacy_properties()
                    value = str(properties.get("Value") or "").strip()
                    if value and value != text and len(value) <= 8192:
                        # Chromium exposes a hyperlink's destination here even
                        # when its visible Discord label is shortened.
                        messages.append(f"{text} {value}")
                    if channel_from_text(text) and int(properties.get("State", 0)) & 2:
                        selected_channel = channel_from_text(text) or selected_channel
                except Exception:
                    pass
    return messages, selected_channel


def discord_desktop_candidates(messages, channel):
    """Extract supported links from individual accessibility message blocks."""
    candidates = []
    for text in messages:
        parsed = parse_link(text)
        if not parsed:
            continue
        requested = channel[0]
        if requested == MIXED_CHANNEL:
            upper = text.upper()
            requested = next((biome for biome in BIOMES if biome in upper), "")
            if "GLITCHED BIOME" in upper:
                requested = "GLITCH"
            if not requested:
                continue
        population = re.search(r"(?:^|\D)(\d{1,2})\s*/\s*20(?:\D|$)", text)
        candidates.append({"url": text, "targetBiome": requested,
                           "playerCount": int(population.group(1)) if population else None})
    return candidates


def newest_unseen_desktop_candidate(candidates, known_ids):
    """Mark a scan as seen and return only its newest previously unseen link."""
    unseen = []
    for payload in candidates:
        parsed = parse_link(payload["url"])
        if parsed and parsed[0] not in known_ids:
            unseen.append((parsed[0], payload))
    known_ids.update(link_id for link_id, _payload in unseen)
    return unseen[-1][1] if unseen else None


def roblox_window():
    try:
        import win32gui
        candidates = []
        def visit(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if "ROBLOX" not in title.upper():
                return
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            if right - left > 500 and bottom - top > 400:
                candidates.append((hwnd, left, top, right - left, bottom - top))
        win32gui.EnumWindows(visit, None)
        return max(candidates, key=lambda item: item[3] * item[4]) if candidates else None
    except Exception:
        return None


def focus_window(window) -> bool:
    import win32api
    import win32con
    import win32gui
    import win32process
    hwnd = window[0]
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    attached = []
    try:
        current_thread = win32api.GetCurrentThreadId()
        target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
        foreground = win32gui.GetForegroundWindow()
        foreground_thread = win32process.GetWindowThreadProcessId(foreground)[0] if foreground else 0
        for thread_id in {target_thread, foreground_thread} - {0, current_thread}:
            win32process.AttachThreadInput(current_thread, thread_id, True)
            attached.append(thread_id)
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
        win32gui.SetFocus(hwnd)
    except Exception as error:
        log("play", f"direct foreground handoff failed: {error}")
    finally:
        for thread_id in reversed(attached):
            try:
                win32process.AttachThreadInput(win32api.GetCurrentThreadId(), thread_id, False)
            except Exception:
                pass
    time.sleep(.25)
    foreground = win32gui.GetForegroundWindow()
    try:
        foreground_root = win32gui.GetAncestor(foreground, win32con.GA_ROOT)
    except Exception:
        foreground_root = foreground
    return foreground_root == hwnd


def ocr_region(window, region, psm=6) -> str:
    from PIL import ImageGrab
    import pytesseract
    _, x, y, width, height = window
    rx, ry, rw, rh = region
    box = (
        round(x + rx * width / 1920), round(y + ry * height / 1080),
        round(x + (rx + rw) * width / 1920), round(y + (ry + rh) * height / 1080),
    )
    bundled = APP_DIR / "tesseract" / "tesseract.exe"
    if bundled.exists():
        pytesseract.pytesseract.tesseract_cmd = str(bundled)
    text = pytesseract.image_to_string(ImageGrab.grab(bbox=box, all_screens=True), config=f"--psm {psm}")
    return re.sub(r"\s+", " ", text).strip().upper()


def play_box_from_ocr(data):
    """Return the highest-confidence exact Play word box from Tesseract data."""
    matches = []
    for index, text in enumerate(data.get("text", [])):
        if re.sub(r"[^A-Z]", "", str(text).upper()) != "PLAY":
            continue
        try:
            confidence = float(data["conf"][index])
            box = tuple(int(data[name][index]) for name in ("left", "top", "width", "height"))
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if confidence >= 30 and box[2] > 5 and box[3] > 5:
            matches.append((confidence, box))
    return max(matches, default=(None, None), key=lambda item: item[0])


def activate_play_with_mouse(window) -> bool:
    """OCR-locate and click Play inside the lower-left of the Roblox window."""
    import pyautogui
    from PIL import ImageGrab
    import pytesseract
    if not focus_window(window):
        raise RuntimeError("Windows did not give foreground focus to Roblox")
    log("play", "Roblox foreground focus confirmed")
    _, x, y, width, height = window
    crop_left = x
    crop_top = y + round(height * .5)
    crop_width = max(1, round(width * .45))
    crop_height = max(1, height - (crop_top - y))
    bundled = APP_DIR / "tesseract" / "tesseract.exe"
    if bundled.exists():
        pytesseract.pytesseract.tesseract_cmd = str(bundled)
    image = ImageGrab.grab(
        bbox=(crop_left, crop_top, crop_left + crop_width, crop_top + crop_height),
        all_screens=True,
    )
    data = pytesseract.image_to_data(image, config="--psm 11", output_type=pytesseract.Output.DICT)
    confidence, box = play_box_from_ocr(data)
    if box is None:
        log("play", "Play label was not found by OCR; mouse click skipped")
        return False
    left, top, box_width, box_height = box
    click_x = crop_left + left + box_width // 2
    click_y = crop_top + top + box_height // 2
    log("play", f"clicking OCR-detected Play at {click_x},{click_y} (confidence {confidence:.0f})")
    pyautogui.click(click_x, click_y)
    return True


def wait_for_roll(timeout=90):
    deadline = time.monotonic() + timeout
    next_play_attempt = 0.0
    play_attempts = 0
    while time.monotonic() < deadline:
        window = roblox_window()
        if window and "ROLL" in ocr_region(window, (620, 875, 720, 205), 11):
            return window
        now = time.monotonic()
        if window and play_attempts < 6 and now >= next_play_attempt:
            play_attempts += 1
            log("play", f"OCR-guided Play mouse attempt {play_attempts}/6")
            try:
                activate_play_with_mouse(window)
            except Exception as error:
                log("play", f"Play mouse attempt failed: {error}")
            next_play_attempt = time.monotonic() + 4
        time.sleep(1)
    return None


def current_logged_biome(started_at: float) -> str:
    """Read Roblox Rich Presence, ignoring logs older than this join."""
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    log_dir = local / "Roblox" / "logs"
    try:
        candidates = [path for path in log_dir.glob("*.log") if path.stat().st_mtime >= started_at - 2]
        latest = max(candidates, key=lambda path: path.stat().st_mtime)
        # Roblox logs can be large; only the newest tail is relevant.
        with latest.open("rb") as stream:
            stream.seek(max(0, latest.stat().st_size - 512_000))
            tail = stream.read().decode("utf-8", errors="replace")
        matches = re.findall(r'"largeImage"\s*:\s*\{\s*"hoverText"\s*:\s*"([^"]+)"', tail)
        return matches[-1].upper().strip() if matches else ""
    except (OSError, ValueError):
        return ""


class MonarchyServer:
    def __init__(self, status_callback=lambda: None):
        self.httpd = None
        self.thread = None
        self.status_callback = status_callback
        self.seen = set()
        self.pending = None
        self.active = False
        self.cooldown_until = 0.0
        self.lock = threading.Lock()
        self.channel = ("UNSUPPORTED", "UNSUPPORTED")
        self.discord_desktop_seen = set()

    def update_channel(self, name, kind):
        self.channel = (name, kind)
        valid = self.channel[1] == "BIOME" and self.channel[0] in BIOMES | {MIXED_CHANNEL}
        CHANNEL_FILE.write_text(json.dumps({"name": self.channel[0], "kind": self.channel[1],
            "mode": "BIOME", "matchesMode": valid}, indent=2), encoding="utf-8")
        self.status_callback()
        return valid

    def can_start(self):
        with self.lock:
            if self.active and not roblox_running():
                self.active = False
                self.cooldown_until = time.monotonic() + 5
                log("listener", "Roblox exited; starting 5-second handoff cooldown")
            if self.active or time.monotonic() < self.cooldown_until:
                return False
            self.active = True
            return True

    def submit_link(self, payload):
        parsed = parse_link(str(payload.get("url", "")))
        if not parsed:
            return 400
        link_id, uri = parsed
        requested = str(payload.get("targetBiome", "")).upper()
        channel, kind = self.channel
        if channel == MIXED_CHANNEL and requested in BIOMES:
            biome = requested
        elif channel in BIOMES:
            biome = channel
        else:
            biome = "CORRUPTION"
        if kind != "BIOME" or channel not in BIOMES | {MIXED_CHANNEL}:
            log("listener", f"ignored link; channel={channel}, mode=BIOME")
            return 204
        if link_id in self.seen:
            return 208
        players = payload.get("playerCount")
        candidate = (link_id, uri, biome, kind, players)
        if self.can_start():
            self.launch(candidate)
            return 202
        self.pending = candidate
        log("listener", f"deferred active-session link {link_id}")
        return 409

    def discord_desktop_loop(self):
        available_logged = False
        initialized = False
        baseline_deadline = time.monotonic() + 5
        while self.httpd:
            try:
                messages, selected = discord_desktop_snapshot()
                detected = discord_title_channel() or selected
                if not detected:
                    time.sleep(1)
                    continue
                self.update_channel(*detected)
                if not available_logged:
                    log("discord", "Windows Discord accessibility monitoring active")
                    available_logged = True
                candidates = discord_desktop_candidates(messages, detected)
                if time.monotonic() < baseline_deadline:
                    self.discord_desktop_seen.update(
                        parsed[0] for payload in candidates if (parsed := parse_link(payload["url"]))
                    )
                    time.sleep(0.75)
                    continue
                if not initialized:
                    initialized = True
                    log("discord", "desktop message baseline captured; watching for new links")
                payload = newest_unseen_desktop_candidate(candidates, self.discord_desktop_seen)
                if payload:
                    parsed = parse_link(payload["url"])
                    status = self.submit_link(payload)
                    log("discord", f"newest desktop link handled with HTTP-style status {status}: {parsed[0]}")
            except Exception as error:
                if available_logged:
                    log("discord", f"desktop monitoring unavailable: {error}")
                    available_logged = False
            time.sleep(0.75)

    def launch(self, candidate):
        link_id, uri, biome, kind, players = candidate
        self.seen.add(link_id)
        log("listener", f"joining {link_id}; target={kind}:{biome}; players={players}")
        notify("Monarchy", f"New {biome.title()} link detected")
        if roblox_running():
            close_roblox()
        os.startfile(uri)  # noqa: S606 - registered Roblox protocol is intentional
        threading.Thread(target=biome_workflow, args=(biome,), daemon=True).start()

    def dispatch_loop(self):
        while self.httpd:
            if self.pending and self.can_start():
                with self.lock:
                    candidate, self.pending = self.pending, None
                self.launch(candidate)
            time.sleep(0.25)

    def start(self):
        if self.httpd:
            return
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def finish_response(self, status):
                self.send_response(status)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

            def do_POST(self):
                try:
                    if self.client_address[0] != "127.0.0.1":
                        return self.send_error(404)
                    length = min(int(self.headers.get("Content-Length", "0")), 4096)
                    payload = json.loads(self.rfile.read(length))
                    if self.path == "/channel":
                        owner.update_channel(str(payload.get("name", "UNSUPPORTED")).upper(),
                                             str(payload.get("kind", "UNSUPPORTED")).upper())
                        return self.finish_response(204)
                    if self.path != "/join":
                        return self.send_error(404)
                    status = owner.submit_link(payload)
                    if status == 400:
                        return self.send_error(400)
                    return self.finish_response(status)
                except Exception as error:
                    log("listener", f"request failed: {error}")
                    self.send_error(400)

            def log_message(self, *_):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        threading.Thread(target=self.dispatch_loop, daemon=True).start()
        threading.Thread(target=self.discord_desktop_loop, daemon=True).start()
        log("listener", f"ready on 127.0.0.1:{PORT} in BIOME mode")
        self.status_callback()

    def stop(self):
        if self.httpd:
            server, self.httpd = self.httpd, None
            server.shutdown()
            server.server_close()
        if load_settings().get("close_roblox_on_stop") and roblox_running():
            close_roblox()
        log("listener", "stopped")
        self.status_callback()


def biome_workflow(target):
    started_at = time.time()
    log("biome", f"waiting for playable {target} session")
    window = wait_for_roll()
    if not window:
        log("biome", "Roll screen was not reached within 90 seconds; closing Roblox")
        close_roblox()
        return
    target_words = {"GLITCH": ("GLITCH", "GLITCHED")}.get(target, (target,))
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline and roblox_running():
        biome = current_logged_biome(started_at)
        if any(word == biome for word in target_words):
            log("biome", f"verified target biome {target}")
            break
        time.sleep(2)
    else:
        log("biome", f"target biome {target} was not verified; closing Roblox")
        close_roblox()
        return
    while roblox_running():
        biome = current_logged_biome(started_at)
        if biome and not any(word == biome for word in target_words):
            log("biome", f"{target} ended ({biome} detected); closing Roblox")
            close_roblox()
            return
        time.sleep(1)


class Dashboard(tk.Tk):
    BG = "#080914"
    PANEL = "#10111f"
    CARD = "#121321"
    BORDER = "#2d2942"
    PURPLE = "#bd7cff"
    TEXT = "#f2effa"
    MUTED = "#a6a1b5"

    def __init__(self):
        super().__init__()
        self.title("Monarchy — Windows Edition")
        self.geometry("1240x780")
        self.minsize(980, 650)
        self.configure(bg=self.BG)
        self.server = MonarchyServer(lambda: self.after(0, self.refresh))
        self.status_var = tk.StringVar()
        self.status_help_var = tk.StringVar()
        self.target_var = tk.StringVar(value="Current channel")
        self.detection_var = tk.StringVar(value="Unsupported")
        self.detection_detail_var = tk.StringVar(value="Listener is stopped.")
        self.runtime_var = tk.StringVar(value="00:00:00")
        self.listener_started_at = None
        self.available_update = None
        self.nav_buttons = {}
        self.pages = {}
        self.build_ui()
        self.show_page("Dashboard")
        self.refresh()
        self.after(1000, self.periodic)
        self.after(1500, self.check_for_updates)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 10))

        header = tk.Frame(self, bg=self.BG, height=142, highlightbackground="#252337", highlightthickness=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        try:
            from PIL import Image, ImageTk
            logo = Image.open(APP_DIR / "assets" / "header.png")
            self.logo_image = ImageTk.PhotoImage(logo)
            tk.Label(header, image=self.logo_image, bg=self.BG, bd=0).pack(anchor="w", padx=28, pady=(21, 0))
        except Exception:
            tk.Label(header, text="♛  Monarchy", bg=self.BG, fg=self.PURPLE,
                     font=("Georgia", 34, "bold")).pack(anchor="w", padx=28, pady=(24, 0))
        tk.Label(header, text=f"Autosniper for Sol's RNG.  •  Windows Edition  •  v{APP_VERSION}",
                 bg=self.BG, fg=self.MUTED, font=("Segoe UI", 11)).pack(anchor="w", padx=112, pady=(2, 14))
        tk.Frame(self, bg="#29243f", height=1).pack(fill="x")

        self.update_banner = tk.Frame(self, bg="#26203c", padx=18, pady=9)
        self.update_text = tk.Label(self.update_banner, text="", bg="#26203c", fg=self.TEXT,
                                    font=("Segoe UI Semibold", 10))
        self.update_text.pack(side="left")
        self.update_button = tk.Button(self.update_banner, text="Install", command=self.install_update,
                                       bg="#b8dedd", fg="#071111", activebackground="#d0eeee",
                                       relief="flat", padx=22, pady=4, font=("Segoe UI Semibold", 9))
        self.update_button.pack(side="right")

        self.body = tk.Frame(self, bg=self.BG)
        self.body.pack(fill="both", expand=True)
        sidebar = tk.Frame(self.body, bg="#0d0e1b", width=190,
                           highlightbackground=self.BORDER, highlightthickness=1)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        for name in ("Dashboard", "Biomes", "Settings", "Logs"):
            button = tk.Button(sidebar, text=f"☆  {name}", anchor="w", command=lambda page=name: self.show_page(page),
                               bg="#0d0e1b", fg=self.MUTED, activebackground="#241b3c",
                               activeforeground=self.TEXT, relief="flat", bd=0, padx=22, pady=14,
                               font=("Segoe UI Semibold", 11), cursor="hand2")
            button.pack(fill="x", padx=10, pady=(10 if name == "Dashboard" else 2, 0))
            self.nav_buttons[name] = button

        self.content = tk.Frame(self.body, bg=self.BG)
        self.content.pack(side="left", fill="both", expand=True, padx=16, pady=14)
        self.pages["Dashboard"] = self.build_dashboard_page()
        self.pages["Biomes"] = self.build_biomes_page()
        self.pages["Settings"] = self.build_settings_page()
        self.pages["Logs"] = self.build_logs_page()

    def card(self, parent, **pack_options):
        frame = tk.Frame(parent, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1,
                         padx=16, pady=14)
        frame.pack(**pack_options)
        return frame

    def heading(self, parent, text, size=20):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=self.TEXT,
                        font=("Segoe UI Semibold", size))

    def build_dashboard_page(self):
        page = tk.Frame(self.content, bg=self.BG)
        center = tk.Frame(page, bg=self.BG)
        center.pack(side="left", fill="both", expand=True)
        status = self.card(center, fill="x", pady=(0, 14))
        tk.Label(status, text="STATUS", bg=self.CARD, fg=self.MUTED,
                 font=("Segoe UI Semibold", 9)).grid(row=0, column=0, sticky="w")
        tk.Label(status, textvariable=self.status_var, bg=self.CARD, fg=self.TEXT,
                 font=("Segoe UI Semibold", 21)).grid(row=1, column=0, sticky="w")
        tk.Label(status, textvariable=self.status_help_var, bg=self.CARD, fg=self.MUTED,
                 font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w")
        status.grid_columnconfigure(0, weight=1)
        tk.Button(status, text="▶  Start", command=self.start_listener, bg="#115633", fg="#d4ffe6",
                  activebackground="#177546", relief="flat", padx=34, pady=14,
                  font=("Segoe UI Semibold", 12)).grid(row=0, column=1, rowspan=3, padx=(15, 8))
        tk.Button(status, text="■  Stop", command=self.stop_listener, bg="#5b1b2f", fg="#ffd9e2",
                  activebackground="#76253e", relief="flat", padx=34, pady=14,
                  font=("Segoe UI Semibold", 12)).grid(row=0, column=2, rowspan=3)

        target = self.card(center, fill="x", pady=(0, 14))
        tk.Label(target, text="CURRENT TARGET", bg=self.CARD, fg=self.MUTED,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w")
        tk.Label(target, textvariable=self.target_var, bg=self.CARD, fg=self.PURPLE,
                 font=("Segoe UI Semibold", 18)).pack(anchor="w", pady=(6, 2))
        tk.Label(target, text="DISCORD CHANNEL DETECTION", bg=self.CARD, fg=self.MUTED,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(10, 0))
        tk.Label(target, textvariable=self.detection_var, bg=self.CARD, fg=self.PURPLE,
                 font=("Segoe UI Semibold", 12)).pack(anchor="w", pady=(5, 0))
        tk.Label(target, textvariable=self.detection_detail_var, bg=self.CARD, fg=self.MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

        runtime = self.card(center, fill="x")
        tk.Label(runtime, textvariable=self.runtime_var, bg=self.CARD, fg=self.TEXT,
                 font=("Segoe UI Semibold", 18)).pack()
        tk.Label(runtime, text="Runtime", bg=self.CARD, fg=self.MUTED,
                 font=("Segoe UI", 9)).pack()

        art_frame = tk.Frame(page, bg=self.BG, width=244)
        art_frame.pack(side="right", fill="y", padx=(16, 0))
        art_frame.pack_propagate(False)
        try:
            from PIL import Image, ImageTk
            art = Image.open(APP_DIR / "assets" / "throne-panel.png")
            art.thumbnail((230, 520), Image.Resampling.LANCZOS)
            self.throne_image = ImageTk.PhotoImage(art)
            tk.Label(art_frame, image=self.throne_image, bg=self.BG, bd=0).pack(anchor="n")
        except Exception:
            tk.Label(art_frame, text="♛\n\nAll hail the\nPixelatingStars.", bg=self.CARD,
                     fg=self.PURPLE, font=("Georgia", 18), justify="center", padx=20, pady=80).pack(fill="both")
        return page

    def build_biomes_page(self):
        page = tk.Frame(self.content, bg=self.BG)
        self.heading(page, "Biomes").pack(anchor="w")
        tk.Label(page, text="Monarchy selects the target from the Discord channel currently visible.",
                 bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(5, 8))
        tk.Label(page, text="ACTIVE — biome links only", bg=self.BG, fg=self.PURPLE,
                 font=("Segoe UI Semibold", 17)).pack(anchor="w", pady=(0, 12))
        banner = tk.Frame(page, bg="#115633", padx=14, pady=14)
        banner.pack(fill="x", pady=(0, 12))
        tk.Label(banner, text="Biome Sniper", bg="#115633", fg="#d4ffe6",
                 font=("Segoe UI Semibold", 12)).pack()
        for biome in ("Corruption", "Dreamspace", "Glitch", "Cyberspace", "Singularity", "Hell"):
            row = tk.Frame(page, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1,
                           padx=14, pady=12)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=f"✦  {biome}", bg=self.CARD, fg=self.TEXT,
                     font=("Segoe UI", 10)).pack(anchor="w")
        return page

    def build_settings_page(self):
        page = tk.Frame(self.content, bg=self.BG)
        self.heading(page, "Settings").pack(anchor="w")
        tk.Label(page, text="Biome-only Windows Edition", bg=self.BG, fg=self.MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 18))
        panel = self.card(page, fill="x")
        tk.Label(panel, text="Local files", bg=self.CARD, fg=self.TEXT,
                 font=("Segoe UI Semibold", 13)).pack(anchor="w", pady=(0, 12))
        tk.Button(panel, text="Open data folder", command=lambda: os.startfile(DATA_DIR),
                  bg="#28253a", fg=self.TEXT, activebackground="#39334f", relief="flat",
                  padx=18, pady=9).pack(side="left")
        tk.Button(panel, text="Open browser extension folder", command=lambda: os.startfile(APP_DIR / "extension"),
                  bg="#28253a", fg=self.TEXT, activebackground="#39334f", relief="flat",
                  padx=18, pady=9).pack(side="left", padx=10)
        return page

    def build_logs_page(self):
        page = tk.Frame(self.content, bg=self.BG)
        self.heading(page, "Activity Logs").pack(anchor="w", pady=(0, 10))
        self.logs = tk.Text(page, bg="#0b0c18", fg="#d9d4e7", insertbackground="white",
                            highlightbackground=self.BORDER, highlightthickness=1, relief="flat",
                            font=("Cascadia Mono", 9), state="disabled", padx=10, pady=8)
        self.logs.pack(fill="both", expand=True)
        return page

    def show_page(self, name):
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        for label, button in self.nav_buttons.items():
            selected = label == name
            button.configure(bg="#241b3c" if selected else "#0d0e1b",
                             fg=self.TEXT if selected else self.MUTED)

    def start_listener(self):
        self.server.start()
        if self.listener_started_at is None:
            self.listener_started_at = time.monotonic()
        self.refresh()

    def stop_listener(self):
        self.server.stop()
        self.listener_started_at = None
        self.refresh()

    def check_for_updates(self):
        def worker():
            try:
                update = latest_update()
            except urllib.error.HTTPError as error:
                if error.code not in (401, 403, 404):
                    log("update", f"check failed: HTTP {error.code}")
                return
            except Exception as error:
                log("update", f"check failed: {error}")
                return
            if update:
                self.after(0, lambda: self.show_update(update))
        threading.Thread(target=worker, daemon=True).start()

    def show_update(self, update):
        self.available_update = update
        self.update_text.configure(text=f"Update available: v{update['version']}")
        self.update_banner.pack(fill="x", before=self.body)

    def install_update(self):
        if not self.available_update:
            return
        if not getattr(sys, "frozen", False):
            messagebox.showinfo("Update Monarchy", "Automatic installation is available in the portable EXE build.")
            return
        self.update_button.configure(state="disabled")
        self.update_text.configure(text=f"Downloading v{self.available_update['version']}…")

        def worker():
            try:
                script = stage_update(self.available_update)
            except Exception as error:
                log("update", f"install failed: {error}")
                self.after(0, lambda: self.update_failed(str(error)))
                return
            self.after(0, lambda: self.launch_staged_update(script))
        threading.Thread(target=worker, daemon=True).start()

    def update_failed(self, error):
        self.update_text.configure(text="Update download failed")
        self.update_button.configure(state="normal")
        messagebox.showerror("Monarchy update", error)

    def launch_staged_update(self, script):
        archive = DATA_DIR / "update" / "Monarchy-Windows-Portable.zip"
        subprocess.Popen([
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
            "-AppDir", str(APP_DIR), "-Archive", str(archive), "-ProcessId", str(os.getpid()),
        ], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log("update", f"installing v{self.available_update['version']}; restarting")
        self.destroy()

    def refresh(self):
        running = bool(self.server.httpd)
        self.status_var.set("Running" if running else "Stopped")
        self.status_help_var.set("Watching Discord for biome links." if running else "Press Start to begin autosniping.")
        try:
            state = json.loads(CHANNEL_FILE.read_text(encoding="utf-8"))
            if running:
                name = str(state.get("name", "UNSUPPORTED"))
                matched = bool(state.get("matchesMode"))
                self.target_var.set(name.replace("-", " ").title() if matched else "Current channel")
                self.detection_var.set(name.replace("-", " ").title())
                self.detection_detail_var.set("MATCHED — ready for biome links" if matched else
                                              "BLOCKED — this channel is not a supported biome channel")
            else:
                self.target_var.set("Current channel")
                self.detection_var.set("Unsupported")
                self.detection_detail_var.set("Listener is stopped.")
        except Exception:
            self.target_var.set("Current channel")
            self.detection_var.set("Waiting for Discord" if running else "Unsupported")
            self.detection_detail_var.set("Open a supported channel in Discord." if running else "Listener is stopped.")
        if running and self.listener_started_at is not None:
            elapsed = max(0, int(time.monotonic() - self.listener_started_at))
            self.runtime_var.set(f"{elapsed // 3600:02d}:{elapsed % 3600 // 60:02d}:{elapsed % 60:02d}")
        else:
            self.runtime_var.set("00:00:00")
        try:
            lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
        except OSError:
            lines = []
        self.logs.configure(state="normal")
        self.logs.delete("1.0", "end")
        self.logs.insert("end", "\n".join(lines))
        self.logs.see("end")
        self.logs.configure(state="disabled")

    def periodic(self):
        self.refresh()
        self.after(1000, self.periodic)

    def on_close(self):
        if self.server.httpd:
            if not messagebox.askyesno("Exit Monarchy", "Stop the listener and exit?"):
                return
            self.server.stop()
        self.destroy()


if __name__ == "__main__":
    if os.name != "nt":
        print("Monarchy Windows requires Windows Edition.", file=sys.stderr)
        raise SystemExit(1)
    Dashboard().mainloop()
