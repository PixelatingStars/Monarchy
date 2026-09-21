#!/usr/bin/env python3
"""Monarchy for Windows Edition.

Portable local listener, dashboard, Roblox launcher, biome watcher, and guarded
Jester buyer. Windows-only integrations are imported lazily so the source can
still be syntax-checked on another platform.
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
from difflib import SequenceMatcher
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

APP_VERSION = "0.3.2"
GITHUB_REPOSITORY = "PixelatingStars/Monarchy"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
UPDATE_CREDENTIAL = "Monarchy/GitHubUpdates"
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
    "mode": "BIOME",
    "jester_enabled": False,
    "close_roblox_on_stop": True,
    "points": {
        "inventory": [33, 516], "items_tab": [1268, 334],
        "inventory_search": [1095, 365], "merchant_teleporter": [850, 475],
        "teleporter_use": [678, 579], "dialogue_skip": [1055, 810],
        "jester_open": [618, 942], "stock_1": [963, 718],
        "stock_2": [1154, 718], "stock_3": [1344, 718],
        "stock_4": [1534, 718], "stock_5": [1724, 718],
        "set_max": [1338, 614], "purchase": [1178, 661],
    },
    "targets": {name: True for name in (
        "LUCKY POTION", "SPEED POTION", "HEAVENLY POTION", "POTION OF BOUND"
    )},
}


def github_token() -> str:
    """Read the private-release token without placing it in portable data."""
    try:
        import win32cred
        value = win32cred.CredRead(UPDATE_CREDENTIAL, win32cred.CRED_TYPE_GENERIC)["CredentialBlob"]
        return value.decode("utf-16-le") if isinstance(value, bytes) else str(value)
    except Exception:
        return ""


def save_github_token(token: str) -> None:
    import win32cred
    win32cred.CredWrite({
        "Type": win32cred.CRED_TYPE_GENERIC,
        "TargetName": UPDATE_CREDENTIAL,
        "UserName": "PixelatingStars",
        "CredentialBlob": token,
        "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
    }, 0)


def validate_github_token(token: str) -> str:
    """Confirm a token belongs to the owner and can see Monarchy releases."""
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
               "User-Agent": f"Monarchy/{APP_VERSION}", "X-GitHub-Api-Version": "2022-11-28"}
    with urllib.request.urlopen(urllib.request.Request("https://api.github.com/user", headers=headers),
                               timeout=10) as response:
        account = json.load(response)
    login = str(account.get("login", ""))
    if login.casefold() != "PixelatingStars".casefold():
        raise ValueError(f"token belongs to {login or 'an unknown account'}, not PixelatingStars")
    with urllib.request.urlopen(urllib.request.Request(f"{GITHUB_API}/releases/latest", headers=headers),
                               timeout=10) as response:
        json.load(response)
    return login


def github_request(url: str, accept="application/vnd.github+json"):
    headers = {"Accept": accept, "User-Agent": f"Monarchy/{APP_VERSION}",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
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
        for key in ("mode", "jester_enabled", "close_roblox_on_stop"):
            if key in saved:
                result[key] = saved[key]
        for section in ("points", "targets"):
            if isinstance(saved.get(section), dict):
                result[section].update(saved[section])
    return result


def save_settings(settings: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


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
    for label in ("JESTER", MIXED_CHANNEL, "CORRUPTION", "DREAMSPACE", "GLITCHED",
                  "GLITCH", "CYBERSPACE", "SINGULARITY", "HELL"):
        if label in source:
            name = "GLITCH" if label == "GLITCHED" else label
            return name, "JESTER" if name == "JESTER" else "BIOME"
    return None


def channel_from_text(text: str):
    source = text.upper()
    for label in ("JESTER", MIXED_CHANNEL, "CORRUPTION", "DREAMSPACE", "GLITCHED",
                  "GLITCH", "CYBERSPACE", "SINGULARITY", "HELL"):
        if label in source:
            name = "GLITCH" if label == "GLITCHED" else label
            return name, "JESTER" if name == "JESTER" else "BIOME"
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


def activate_play_with_ui_navigation(window) -> None:
    """Activate the landing-screen Play button through Roblox UI Navigation."""
    import pyautogui
    if not focus_window(window):
        raise RuntimeError("Windows did not give foreground focus to Roblox")
    log("play", "Roblox foreground focus confirmed")
    for label, key, delay in (("UI Navigation toggle", "\\", .35),
                              ("Down", "down", .35),
                              ("Enter", "enter", .5),
                              ("UI Navigation exit", "\\", 0)):
        log("play", f"sending {label}")
        pyautogui.press(key)
        if delay:
            time.sleep(delay)


def wait_for_roll(timeout=90):
    deadline = time.monotonic() + timeout
    next_navigation = 0.0
    navigation_attempts = 0
    while time.monotonic() < deadline:
        window = roblox_window()
        if window and "ROLL" in ocr_region(window, (620, 875, 720, 205), 11):
            return window
        now = time.monotonic()
        if window and navigation_attempts < 3 and now >= next_navigation:
            navigation_attempts += 1
            log("play", f"UI Navigation attempt {navigation_attempts}/3")
            try:
                activate_play_with_ui_navigation(window)
            except Exception as error:
                log("play", f"UI Navigation attempt failed: {error}")
            next_navigation = time.monotonic() + 8
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

    def mode(self):
        return str(load_settings().get("mode", "BIOME")).upper()

    def update_channel(self, name, kind):
        self.channel = (name, kind)
        detected = discord_title_channel()
        if detected:
            self.channel = detected
        mode = self.mode()
        valid = (mode == "JESTER" and self.channel == ("JESTER", "JESTER")) or (
            mode == "BIOME" and self.channel[1] == "BIOME" and
            self.channel[0] in BIOMES | {MIXED_CHANNEL}
        )
        CHANNEL_FILE.write_text(json.dumps({"name": self.channel[0], "kind": self.channel[1],
            "mode": mode, "matchesMode": valid}, indent=2), encoding="utf-8")
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
        detected = discord_title_channel()
        if detected:
            channel, kind = detected
        if channel == MIXED_CHANNEL and requested in BIOMES:
            biome = requested
        elif channel in BIOMES:
            biome = channel
        else:
            biome = "CORRUPTION"
        if kind == "UNSUPPORTED" or kind != self.mode():
            log("listener", f"ignored link; channel={channel}, mode={self.mode()}")
            return 204
        if kind == "JESTER" and not load_settings().get("jester_enabled"):
            log("listener", "ignored Jester link; Windows Jester automation is disabled")
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
                if not initialized:
                    self.discord_desktop_seen.update(
                        parsed[0] for payload in candidates if (parsed := parse_link(payload["url"]))
                    )
                    initialized = True
                    log("discord", "desktop message baseline captured; watching for new links")
                    time.sleep(0.75)
                    continue
                for payload in candidates:
                    parsed = parse_link(payload["url"])
                    if not parsed or parsed[0] in self.discord_desktop_seen:
                        continue
                    status = self.submit_link(payload)
                    if status in (202, 208, 409):
                        self.discord_desktop_seen.add(parsed[0])
            except Exception as error:
                if available_logged:
                    log("discord", f"desktop monitoring unavailable: {error}")
                    available_logged = False
            time.sleep(0.75)

    def launch(self, candidate):
        link_id, uri, biome, kind, players = candidate
        self.seen.add(link_id)
        log("listener", f"joining {link_id}; target={kind}:{biome}; players={players}")
        notify("Monarchy", f"New {'Jester' if kind == 'JESTER' else biome.title()} link detected")
        if roblox_running():
            close_roblox()
        os.startfile(uri)  # noqa: S606 - registered Roblox protocol is intentional
        worker = jester_workflow if kind == "JESTER" else biome_workflow
        threading.Thread(target=worker, args=(biome,), daemon=True).start()

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
        log("listener", f"ready on 127.0.0.1:{PORT} in {self.mode()} mode")
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


def fuzzy_word(text, expected, threshold=.75):
    words = re.sub(r"[^A-Z ]", " ", text.upper()).split()
    return any(SequenceMatcher(None, expected, word).ratio() >= threshold for word in words)


def jester_workflow(_target):
    settings = load_settings()
    if not settings.get("jester_enabled"):
        return
    log("jester", "started; waiting for playable Roblox window")
    window = wait_for_roll()
    if not window:
        log("jester", "Roll screen not reached; closing Roblox")
        close_roblox()
        return
    import pyautogui
    focus_window(window)
    points = settings["points"]

    def click(name, pause=.25):
        _, x, y, width, height = window
        rx, ry = points[name]
        pyautogui.click(round(x + rx * width / 1920), round(y + ry * height / 1080))
        time.sleep(pause)

    click("inventory")
    time.sleep(1)
    if "INVENTORY" not in ocr_region(window, (450, 260, 1050, 570)):
        log("jester", "Inventory did not open; aborting")
        close_roblox()
        return
    click("items_tab")
    time.sleep(6)
    click("inventory_search")
    pyautogui.hotkey("ctrl", "a")
    pyautogui.write("Merchant Teleporter")
    time.sleep(1)
    rx, ry = points["merchant_teleporter"]
    tile = ocr_region(window, (max(0, rx - 110), max(0, ry - 90), 220, 180))
    if not fuzzy_word(tile, "TELEPORTER") or "POTION" in tile or "PATION" in tile:
        log("jester", f"SAFETY ABORT: teleporter tile not verified; OCR={tile[:180]}")
        close_roblox()
        return
    click("merchant_teleporter")
    time.sleep(1.5)
    description = ocr_region(window, (460, 590, 340, 220))
    safe = (fuzzy_word(description, "MERCHANT") and
            (fuzzy_word(description, "TELEPORTS") or fuzzy_word(description, "TELEPORTER")) and
            "POTION" not in description and "PATION" not in description)
    if not safe:
        log("jester", f"SAFETY ABORT: description not verified; OCR={description[:180]}")
        close_roblox()
        return
    click("teleporter_use")
    time.sleep(1.5)
    pyautogui.press("e")
    time.sleep(.5)
    for _ in range(12):
        click("dialogue_skip", .04)
    confirmed = False
    for _ in range(4):
        click("jester_open")
        text = ocr_region(window, (820, 300, 1050, 470), 11)
        if ("JESTER" in text and "SHOP" in text) or "PURCHASE" in text:
            confirmed = True
            break
        for _ in range(4):
            click("dialogue_skip", .04)
    if not confirmed:
        log("jester", "shop not confirmed; no stock touched")
        close_roblox()
        return
    enabled = {name for name, value in settings["targets"].items() if value}
    for slot in range(1, 6):
        click(f"stock_{slot}")
        time.sleep(.85)
        header = ocr_region(window, (1080, 350, 760, 100))
        matched = next((name for name in enabled if SequenceMatcher(None, name, header).ratio() >= .7 or name in header), None)
        if not matched:
            log("jester", f"slot {slot} ignored; OCR={header[:100]}")
            continue
        click("set_max")
        time.sleep(1.25)
        click("purchase")
        log("jester", f"purchase attempted: {matched.title()}")
    time.sleep(2)
    close_roblox()


class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Monarchy — Windows Edition")
        self.geometry("920x620")
        self.minsize(760, 520)
        self.configure(bg="#090817")
        self.server = MonarchyServer(lambda: self.after(0, self.refresh))
        self.settings = load_settings()
        self.mode_var = tk.StringVar(value=self.settings["mode"])
        self.jester_var = tk.BooleanVar(value=bool(self.settings["jester_enabled"]))
        self.status_var = tk.StringVar()
        self.channel_var = tk.StringVar()
        self.private_update_var = tk.StringVar(
            value="Private updates: connected" if github_token() else "Private updates: not connected"
        )
        self.available_update = None
        self.build_ui()
        self.refresh()
        self.after(1000, self.periodic)
        self.after(1500, self.check_for_updates)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#090817")
        style.configure("TLabel", background="#090817", foreground="#eeeaff", font=("Segoe UI", 11))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 27), foreground="#b9a7ff")
        root = ttk.Frame(self, padding=28)
        root.pack(fill="both", expand=True)
        title_row = ttk.Frame(root)
        title_row.pack(anchor="w")
        ttk.Label(title_row, text="MONARCHY", style="Title.TLabel").pack(side="left")
        ttk.Label(title_row, text="♛", style="Title.TLabel",
                  font=("Segoe UI Symbol", 21)).pack(side="left", padx=(9, 0), pady=(4, 0))
        ttk.Label(root, text=f"Sol's RNG autosniper • Windows Edition • v{APP_VERSION}").pack(anchor="w", pady=(0, 12))
        self.update_banner = ttk.Frame(root, padding=10)
        self.update_text = ttk.Label(self.update_banner, text="")
        self.update_text.pack(side="left")
        self.update_button = ttk.Button(self.update_banner, text="Install", command=self.install_update)
        self.update_button.pack(side="right", padx=(18, 0))
        card = ttk.Frame(root, padding=18)
        card.pack(fill="x")
        ttk.Label(card, textvariable=self.status_var, font=("Segoe UI Semibold", 15)).grid(row=0, column=0, sticky="w")
        ttk.Label(card, textvariable=self.channel_var).grid(row=1, column=0, sticky="w", pady=(5, 12))
        ttk.Button(card, text="Start", command=self.server.start).grid(row=2, column=0, sticky="w")
        ttk.Button(card, text="Stop", command=self.server.stop).grid(row=2, column=1, sticky="w", padx=8)
        options = ttk.LabelFrame(root, text=" Settings ", padding=16)
        options.pack(fill="x", pady=20)
        ttk.Label(options, text="Mode").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(options, text="Biome", value="BIOME", variable=self.mode_var,
                        command=self.save).grid(row=0, column=1, padx=8)
        ttk.Radiobutton(options, text="Jester", value="JESTER", variable=self.mode_var,
                        command=self.save).grid(row=0, column=2, padx=8)
        ttk.Checkbutton(options, text="Enable calibrated Jester automation",
                        variable=self.jester_var, command=self.toggle_jester).grid(row=1, column=0, columnspan=3,
                                                                                  sticky="w", pady=12)
        ttk.Button(options, text="Open data folder", command=lambda: os.startfile(DATA_DIR)).grid(row=2, column=0, sticky="w")
        ttk.Button(options, text="Open extension folder", command=lambda: os.startfile(APP_DIR / "extension")).grid(row=2, column=1, columnspan=2, sticky="w", padx=8)
        ttk.Button(options, text="Calibrate Jester", command=self.open_calibration).grid(row=3, column=0, sticky="w", pady=(10, 0))
        private_update_label = "Reconnect private updates" if github_token() else "Connect private updates"
        self.private_update_button = ttk.Button(options, text=private_update_label,
                                                command=self.connect_private_updates)
        self.private_update_button.grid(row=3, column=1, sticky="w", padx=8, pady=(10, 0))
        ttk.Label(options, textvariable=self.private_update_var).grid(row=3, column=2, sticky="w", pady=(10, 0))
        ttk.Label(root, text="Recent activity").pack(anchor="w")
        self.logs = tk.Text(root, height=12, bg="#111027", fg="#d9d4f5", insertbackground="white",
                            relief="flat", font=("Cascadia Mono", 9), state="disabled")
        self.logs.pack(fill="both", expand=True, pady=(6, 0))

    def connect_private_updates(self):
        token = simpledialog.askstring(
            "Connect private updates",
            "Paste a fine-grained GitHub token for PixelatingStars/Monarchy.\n"
            "It needs read-only Contents access and will be saved in Windows Credential Manager.",
            show="•", parent=self,
        )
        if not token or not token.strip():
            return
        token = token.strip()
        self.private_update_button.configure(state="disabled")
        self.private_update_var.set("Private updates: checking…")

        def worker():
            try:
                login = validate_github_token(token)
                save_github_token(token)
            except urllib.error.HTTPError as error:
                detail = f"GitHub rejected the credential (HTTP {error.code})."
                self.after(0, lambda message=detail: self.private_update_failed(message))
                return
            except Exception as error:
                detail = f"Could not connect private updates: {error}"
                self.after(0, lambda message=detail: self.private_update_failed(message))
                return
            self.after(0, lambda: self.private_update_connected(login))

        threading.Thread(target=worker, daemon=True).start()

    def private_update_connected(self, login):
        self.private_update_button.configure(state="normal", text="Reconnect private updates")
        self.private_update_var.set(f"Private updates: connected as {login}")
        messagebox.showinfo(
            "Private updates connected",
            "The credential is saved in Windows Credential Manager. Monarchy can keep updating after the repository is private.",
        )

    def private_update_failed(self, error):
        self.private_update_button.configure(state="normal")
        self.private_update_var.set("Private updates: not connected")
        messagebox.showerror("Private updates", error)

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
        self.update_banner.pack(fill="x", pady=(0, 12), before=self.update_banner.master.winfo_children()[3])

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

    def save(self):
        self.settings["mode"] = self.mode_var.get()
        self.settings["jester_enabled"] = self.jester_var.get()
        save_settings(self.settings)
        self.refresh()

    def toggle_jester(self):
        if self.jester_var.get():
            answer = messagebox.askyesno("Enable Jester automation?",
                "This sends mouse and keyboard input to Roblox. Enable it only after verifying the 1920x1080 calibration. Continue?")
            if not answer:
                self.jester_var.set(False)
        self.save()

    def open_calibration(self):
        window = roblox_window()
        if not window:
            messagebox.showerror("Calibration", "Open Roblox in a 1920x1080 window first.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Jester calibration")
        dialog.geometry("560x520")
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Open the relevant Roblox screen, then click Capture. You have three seconds to place the pointer over the named control.", wraplength=520).pack(anchor="w", pady=(0, 10))
        canvas = tk.Canvas(frame, bg="#090817", highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        rows = ttk.Frame(canvas)
        rows.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=rows, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def capture(name, label):
            label.configure(text="Move pointer now…")
            dialog.update_idletasks()
            def worker():
                time.sleep(3)
                import pyautogui
                live = roblox_window()
                if not live:
                    self.after(0, lambda: label.configure(text="Roblox not found"))
                    return
                _, x, y, width, height = live
                px, py = pyautogui.position()
                rx = round((px - x) * 1920 / width)
                ry = round((py - y) * 1080 / height)
                if not (0 <= rx <= 1920 and 0 <= ry <= 1080):
                    self.after(0, lambda: label.configure(text="Pointer was outside Roblox"))
                    return
                self.settings["points"][name] = [rx, ry]
                save_settings(self.settings)
                self.after(0, lambda: label.configure(text=f"Saved {rx}, {ry}"))
            threading.Thread(target=worker, daemon=True).start()

        for row, name in enumerate(self.settings["points"]):
            ttk.Label(rows, text=name.replace("_", " ").title(), width=24).grid(row=row, column=0, sticky="w", pady=3)
            status = ttk.Label(rows, text=str(self.settings["points"][name]), width=18)
            status.grid(row=row, column=1, sticky="w")
            ttk.Button(rows, text="Capture", command=lambda n=name, s=status: capture(n, s)).grid(row=row, column=2)

    def refresh(self):
        self.status_var.set("Listener running" if self.server.httpd else "Listener stopped")
        try:
            state = json.loads(CHANNEL_FILE.read_text(encoding="utf-8"))
            self.channel_var.set(f"Discord: {state['name']} • {'MATCHED' if state['matchesMode'] else 'BLOCKED'}")
        except Exception:
            self.channel_var.set("Discord: waiting for desktop app or browser extension")
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
