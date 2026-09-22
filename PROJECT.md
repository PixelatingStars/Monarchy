# Monarchy project brief

Last updated: 2026-09-21

## Purpose

Monarchy is a local Sol's RNG autosniper for Omarchy Linux. It watches server
links in the selected Radiant Notifier Discord channel, joins through Sober,
and runs either a biome monitor or a selective Jester-shop buyer.

A separate Windows Edition now lives in
`/home/pixelatingstars/Work/Monarchy/windows`. It does not modify or share
runtime state with the installed Omarchy edition. It provides a Tkinter
dashboard, Chromium extension, native Roblox protocol launching, Windows
process/window/input support, bundled-build support, Rich Presence biome
monitoring, and a biome-only workflow. Shop automation, Fish Macro, and
biome-item automation are intentionally deferred on Windows.

Windows v0.3.0 adds official Discord desktop-app monitoring through Microsoft
UI Automation, with the Chromium extension retained as a fallback. It reads
only Discord's exposed accessibility names and selected-channel state; it does
not extract credentials, inspect process memory, inject code, or modify the
Discord client. The listener baselines links already visible when monitoring
starts, then forwards only newly exposed supported links through the same
validation, biome classification, and deduplication path used by the browser
extension. Channel identification fails closed when Discord exposes neither a
supported channel in its window title nor a selected accessible channel.

After launching a Roblox server, the Windows edition focuses the Roblox window
and uses Roblox UI Navigation (`backslash`, Down, Enter, `backslash`) to
activate Play. It makes at most three attempts, eight seconds apart, and still
requires OCR confirmation of the in-game Roll control within the existing
90-second watchdog before biome monitoring proceeds.

Windows v0.3.1 hardens this step against Windows foreground-lock behavior. It
temporarily attaches the Monarchy thread to the Roblox and current foreground
input queues, restores and raises Roblox, requests keyboard focus, then verifies
Roblox is truly foreground before sending any navigation keys. Each key is
logged individually, and an unsuccessful focus handoff is reported as a failed
attempt rather than silently claiming input was sent.

Windows v0.3.2 standardizes the platform branding throughout the Windows
source, dashboard, runtime messages, and documentation as `Windows Edition`.
The dashboard subtitle is now
`Sol's RNG autosniper • Windows Edition` followed by the app version.

The Windows portable dashboard is versioned and checks the latest GitHub
release at `PixelatingStars/Monarchy` on startup. Newer semantic-version tags
produce an Update banner. Install downloads the portable ZIP plus its SHA-256
asset, verifies it, preserves the adjacent `data` directory, replaces program
files only after the running process exits, and restarts Monarchy. Public
releases need no credentials. Windows v0.3.3 removes the former authenticated
update option, its settings UI, and all credential-handling code. Automatic
updates now support public GitHub releases only.

Windows v0.3.4 removes the deferred Jester mode, purchasing workflow,
calibration controls, target-item settings, and Jester channel classification.
The Windows app is biome-only. Its dashboard is redesigned to closely mirror
the Omarchy edition with the existing Monarchy header and crown-panel artwork,
a dark purple sidebar, Dashboard/Biomes/Settings/Logs pages, status and target
cards, a supported-biome list, runtime, and activity logs. Fish and Jester pages
remain intentionally absent until those features are ported later.

Windows v0.3.5 fixes Hell-channel rejection caused by competing Discord window
titles. Once the desktop accessibility watcher or browser extension reports a
selected channel, that channel remains authoritative through link submission;
the listener no longer re-scans all visible Discord-titled windows and
overwrites Hell with a stale Corruption or other channel. Regression tests
require both Hell and Corruption links to remain accepted and correctly
targeted.

Windows v0.2.1 adds a small purple crown beside the purple MONARCHY dashboard
heading as the first end-to-end updater test. A GitHub Actions Windows workflow
builds portable artifacts on demand and, for `v*` tags matching `APP_VERSION`,
creates the release and uploads the ZIP plus SHA-256 file automatically.
The workflow explicitly creates `.venv` with the Python 3.12 interpreter from
`actions/setup-python`; invoking the generic Windows `py -3` launcher on a
hosted runner selected its preinstalled Python 3.14 instead, whose runner image
lacked the Tcl/Tk runtime required by the portable build.

The Windows portable build stores all mutable state in a `data` directory next
to the executable. Distribution packages must exclude that directory's
contents so logs, calibration, and personal settings are never shared. The
Windows build script bundles Tesseract and produces
`dist/Monarchy-Windows-Portable.zip`; source runs require Tesseract on PATH.
The builder explicitly copies and validates Python's Tcl/Tk runtime under the
PyInstaller `_internal` directory. This prevents packaged startup failures
reporting that `_tcl_data` was not found when automatic discovery misses it.

This file is the durable context for future sessions. Read it before modifying
Monarchy and update it when the implementation or requirements change.

## Installed files

- Dashboard: `/home/pixelatingstars/.local/share/radiant-biome-autosniper/ui.py`
- Dashboard side artwork: `/home/pixelatingstars/.local/share/radiant-biome-autosniper/assets/throne-panel.png`
- Original throne side artwork backup: `/home/pixelatingstars/.local/share/radiant-biome-autosniper/assets/throne-panel-original.png`
- Listener: `/home/pixelatingstars/.local/share/radiant-biome-autosniper/listener.py`
- Browser extension: `/home/pixelatingstars/.local/share/radiant-biome-autosniper/extension/`
- Dashboard launcher: `/home/pixelatingstars/.local/bin/radiant-biome-autosniper`
- Play navigation: `/home/pixelatingstars/.local/bin/radiant-click-play`
- Biome monitor: `/home/pixelatingstars/.local/bin/radiant-monitor-biome`
- Jester buyer: `/home/pixelatingstars/.local/bin/radiant-jester-autobuy`
- Fish macro: `/home/pixelatingstars/.local/bin/radiant-fish-macro`
- Keybind controller: `/home/pixelatingstars/.local/bin/monarchy-control`
- User service: `/home/pixelatingstars/.config/systemd/user/radiant-biome-autosniper.service`
- Crash-alert watcher override: `/home/pixelatingstars/Work/Monarchy/omarchy-crash-watch-autodismiss`
- Crash-alert service drop-in: `/home/pixelatingstars/.config/systemd/user/omarchy-crash-watch.service.d/override.conf`
- Active mode: `/home/pixelatingstars/.config/monarchy/mode`
- Calibration: `/home/pixelatingstars/.config/monarchy/calibration.json`
- Jester item selection: `/home/pixelatingstars/.config/monarchy/jester-targets.json`
- Fishing settings: `/home/pixelatingstars/.config/monarchy/fishing.json`
- Channel state: `/home/pixelatingstars/.local/state/monarchy/channel.json`
- Persistent activity log: `/home/pixelatingstars/.local/state/monarchy/activity.log`
- Hyprland bindings: `/home/pixelatingstars/.config/hypr/bindings.lua`
- Managed Monarchy bindings: `/home/pixelatingstars/.config/hypr/monarchy-bindings.lua`
- Keybind selection: `/home/pixelatingstars/.config/monarchy/keybinds.json`

## Startup rules

- Opening the Monarchy dashboard leaves the listener and any active workflow
  running.
- The user service is enabled and configured for continuous operation. User
  lingering starts it at boot without requiring an interactive login.
- Dashboard Start or F1 starts the listener.
- Dashboard Stop or F2 stops the listener and active child automation.
- Stop also closes Sober, whose Flatpak process runs in a separate systemd
  scope. Starting around an already-running Sober session restores the matching
  workflow monitor instead of leaving the listener permanently locked.
- The service uses `Restart=always` with a three-second restart delay once
  started.

## Modes and channel filtering

Modes are mutually exclusive.

- Jester mode accepts links only when the selected Discord channel is Jester.
- Entering Jester mode requires two dashboard activations within five seconds,
  preventing a single stray or click-through event from interrupting an
  unattended biome-hunting session. Returning to Biome mode remains immediate.
- Biome mode accepts only the selected supported biome channel.
- Supported biome channels: Corruption, Dreamspace, Glitch/Glitched,
  Cyberspace, Singularity, and Hell.
- The Quakagen `biome-spawner` channel is supported as a mixed BIOME-mode
  source. Monarchy derives the target from each `BIOME Started` embed and
  accepts only Corruption, Dreamspace, Glitch/Glitched, Cyberspace,
  Singularity, or Hell; all other biome embeds are ignored.
- Unsupported channels and mode mismatches must be ignored.
- The listener independently reads the live Discord window title every second;
  it does not depend solely on browser-extension channel metadata.
- The dashboard shows selected-channel state as MATCHED or BLOCKED.

## Link selection and handoff

- Always prefer the newest visible, unhandled link. Rendered player counts are
  logged when recognizable but do not affect link selection.
- Supported server-link formats include public-instance Roblox deep links,
  ChromaHub web links, legacy Sol's RNG game URLs with
  `privateServerLinkCode`, and modern Roblox
  `/share?code=…&type=Server` links. Private and share links are deduplicated
  by their opaque server token and launched through the corresponding Roblox
  deep-link form.
- Browser polling interval is 500 ms.
- While Sober is busy, the newest link remains deferred and eligible.
- The listener retains the newest newly discovered deferred link and dispatches
  it itself after Sober exits; re-arming does not depend on Discord submitting
  the link again. Repeated older links from a browser DOM rescan do not replace
  that pending candidate.
- After Sober exits, enforce a five-second handoff cooldown. Requests remain
  deferred during the cooldown so the newest link wins afterward.
- A 90-second home-screen watchdog closes Sober if the playable game screen is
  not reached, then re-arms for the newest link.
- Play activation primarily uses OCR to locate the visible Play label inside
  Sober's lower-left button region and clicks the center of its bounding box.
  It never mouse-clicks when Play was not recognized. UI Navigation is retained as a fallback. Either path
  is successful only after OCR confirms the in-game Roll control; main-menu
  biome presence does not satisfy the playable-screen watchdog.
- Biome start/end decisions are also gated on Roll-screen verification, so a
  biome label changing on the landing menu cannot be mistaken for the end of a
  biome that the player entered.
- The listener records when Sober has appeared during startup, so a short-lived
  Sober crash releases the session immediately rather than waiting out the full
  30-second startup grace period.
- Before launching a replacement Sober session, the listener terminates Play,
  biome-monitor, and Jester helpers left over from the previous session so
  stale retries cannot send input to or close the new window.

## Sober and Play navigation

- Roblox place ID: `15532962292`.
- Sober Flatpak ID: `org.vinegarhq.Sober`.
- Play is activated with a safe OCR-guided mouse click. Roblox UI Navigation
  (backslash, Down, Return, backslash) is the fallback.
- Jester automation waits for OCR detection of the in-game Roll control before
  interacting with inventory.

## Jester purchase requirements

The Jester Sniper page has persistent Enable and Disable controls for these
items. Enabled items are bought at maximum available quantity; disabled items
are ignored. All four default to enabled when no settings file exists:

- Lucky Potion
- Speed Potion
- Heavenly Potion
- Potion of Bound

Never buy or use any other inventory item or Jester stock. In particular,
inventory potions are valuable and must not be activated accidentally.

The shop buyer uses tolerant OCR because the game font produces errors such as
`Heovenly Potion` and `Pation of Bund`. Fuzzy recognition must remain narrowly
restricted to the four approved names.

The buyer checks all five stock tabs once. It waits 1.25 seconds between Set to
Max and Purchase so the quantity update registers.

## Current Jester sequence

1. Wait for Sober and the playable Roll screen.
2. Wait two seconds for the game UI to settle.
3. Open Inventory using the calibrated position.
   If Inventory does not open before its safety timeout, close Sober and re-arm
   for the newest link.
4. Click the calibrated Items tab.
5. Wait six seconds for all inventory items to load.
6. Click the calibrated inventory search field.
7. Type `Merchant Teleporter`.
8. Wait one second for the filtered result.
9. Verify the filtered result visually. `Teleporter` is accepted even when the
   gold word `Merchant` is unreadable in dark biomes. Any `Potion` or `Pation`
   text fails closed.
10. Click the calibrated filtered Merchant Teleporter result.
11. Verify the selected item's left-side description identifies a teleporter
    to the merchant and contains no potion text.
12. Press Use exactly once.
13. Briefly scan the right-side red warning area for a newly created warning.
14. If `There's no merchant spawned. (Event merchant is not counted)` appears,
    close Sober and move to the newest link.
15. About one second after Use, press E to talk to Jester.
16. Rapid-click the calibrated dialogue-skip area 12 times.
17. Click the calibrated Open button.
18. Require OCR confirmation of `Jester's Shop` or shop-only controls before
    touching stock. Retry dialogue skip/Open up to four times.
19. If the shop never confirms, do not check stock; close Sober and re-arm.
20. Inspect five calibrated stock tabs and buy only approved items.
21. Close Sober after the purchase pass so Monarchy can continue.

## Calibration

Calibration is persistent and normally needs to be performed once. Recalibrate
after resolution, scale, window-layout, or major game-UI changes.

Calibrated actions include:

- Inventory sidebar button
- Inventory Items tab
- Inventory search field
- Filtered Merchant Teleporter result
- Teleporter Use button
- Jester dialogue skip area
- Jester Open button
- Shop stock tabs 1 through 5
- Set to Max
- Purchase

Fishing calibration is stored in the same `calibration.json`. It includes the
VIP-route menu points, Fisherman dialogue and selling controls, cast and result
points, the white minigame-ready pixel, randomized bar-color sample, and the
top-left/bottom-right fishing-bar detection region.

Coordinates are saved in 1920x1080 reference space and scaled to the live Sober
window. Cursor movement uses Hyprland's Lua dispatcher
`hl.dsp.cursor.move({ x = ..., y = ... })`, followed by a tiny ydotool jiggle
so Sober registers the pointer position.

The Calibration page also contains persisted Jester timing controls. They are
stored under the `timings` object in `calibration.json` and apply when the next
Jester automation process starts. The controls cover cursor/click settling,
window and OCR polling, safety timeouts, inventory and Merchant Teleporter
waits, dialogue/shop pacing, stock selection, Set-to-Max/Purchase pacing, and
the final close delay. Sub-second values are supported. The displayed defaults
match the original hard-coded behavior, and deliberately shortening waits can
cause OCR or game inputs to miss.

## Safety behavior

- Teleporter selection fails closed.
- Before Use, verify both the filtered tile and selected-item description.
- Any Potion/Pation text in the teleporter verification regions aborts Use.
- A safety abort logs the OCR, notifies the user, closes Sober, and re-arms.
- Stock controls are never used until the shop-open gate succeeds.
- Purchases require recognized approved-item OCR.

## Fish macro

- The dashboard has a dedicated Fish Macro page with standalone Start/Stop
  controls. Standalone fishing operates on the currently open Sober session and
  does not start the Discord listener or autosniper.
- A persisted Enable/Disable setting controls automatic fishing in every
  supported sniped biome session. It defaults to enabled. Disabling it does not
  disable or otherwise change biome autosniping, and does not prevent manual
  standalone fishing. The legacy `auto_corruption` setting is accepted as a
  fallback when migrating older configurations; new changes use `auto_biome`.
- Automatic fishing starts only after the biome monitor has verified both the
  playable Roll screen and the requested target biome.
- Fishing uses a native Wayland port of FishSol v1.9.9-2's 1920x1080 VIP route:
  reset, travel to Captain Flarg, sell, return to the fishing spot, then cast and
  control the randomized fishing bar. Reference coordinates scale to the live
  Sober window.
- At Captain Flarg, the VIP route waits 0.6 seconds after opening dialogue
  before clicking to skip it, then waits another 0.25 seconds for the `Sell
  fish` option to appear before opening it.
- The helper uses a runtime file lock so standalone and automatic starts cannot
  create concurrent input processes. It releases held movement keys on normal
  exit, SIGTERM, or failure, and stops when Sober closes.
- The helper retries a failed minigame detection once, then reruns VIP pathing.
  It sells and reruns the VIP route every 15 completed fishing cycles by
  default. Fishing activity and failures are written to the shared activity
  log.
- The Fish Macro page has persistent 1–200 numeric controls for fish caught per
  run and sale iterations per Captain Flarg visit. The macro stops cleanly when
  its successful-catch target is reached. Saved values apply on the next run.
- The Fish Macro page has independent persistent toggles for Strange Controller,
  Biome Randomizer, and Biome Selector. They default off and, while the macro is
  active, run immediately when first due and then at FishSol's 21-, 36-, and
  61-minute intervals respectively.
- The Biome Selector target is chosen from Windy, Snowy, Rainy, Heaven, Hell,
  Starfall, Corruption, SandStorm, and Null. The chosen biome is also protected:
  all three item automations skip their use when screen OCR recognizes it as the
  current biome.
- Biome-item inventory automation searches and OCR-verifies the requested item
  in the result tile, using narrowly tolerant matching for game-font errors such
  as `Rondomizer`. Because Sol's RNG does not repeat these item names in the
  selected-item description, it verifies item-specific description phrases
  (natural spawnrate/device, random biome/device, or biome data drive) before
  clicking Use. It fails closed if those phrases are absent or any Potion/Pation
  text is found.
  The current in-game selector is a centered nine-row panel on the full
  1920x1080 game screen, ordered Golden Dune (SandStorm),
  Infernal Flame (Hell), Unknown Void (Null), Corrupt Ruin (Corruption), Abyss
  Curse (Starfall), Chilling Frost (Snowy), Angelic Hymn (Heaven), Raging Gale
  (Windy), and Radiant Storm (Rainy). Monarchy clicks the corresponding fixed
  row, clicks the left-side Confirm button in the resulting `Are you sure?`
  dialog, waits briefly, and clicks the selector's top-right X as a cleanup
  failsafe. Selector calibration and defaults must use full-game coordinates,
  not coordinates relative to a cropped image of the selector panel.
- For VIP camera setup, positive `ydotool --wheel` movement corresponds to the
  upstream WheelUp action and negative movement corresponds to WheelDown. The
  route deliberately forces the camera fully inward first, then backs it out
  to its usable pathing/click distance, followed by a five-notch inward
  correction before movement begins. Reversing those signs leaves the camera
  fully zoomed in and prevents subsequent UI clicks.

## Logging and diagnostics

All components append timestamped events to `activity.log`. The dashboard Logs
page reads the same persistent file. Logs cover dashboard actions, channel
classification, link decisions, Sober/Play steps, OCR, calibration, teleporter
safety, dialogue/shop steps, stock decisions, purchases, biome monitoring,
timeouts, and errors.

When diagnosing a failure, inspect the latest relevant block with:

```bash
tail -150 /home/pixelatingstars/.local/state/monarchy/activity.log
```

Repeated duplicate/deferred messages should be suppressed per instance so they
do not bury meaningful workflow events.

Six Sober 1.7.1 Flatpak startup crashes are recorded (2026-09-03 08:51,
2026-09-04 23:57, 2026-09-05 05:46 and 08:15, 2026-09-06 16:04, and
2026-09-13 23:40). Each used
a different Sol's RNG server instance URI but produced the same `SEGV_MAPERR`
signature: instruction pointer/address zero, one captured startup thread, and
the stripped `sober`, `libloader.so`, and `libbadcpu.so` modules. The cores have
no usable symbols, so the caller of the null target cannot be identified. The
crashes were not caused by memory pressure and are most consistent with a
recurring Sober startup/URI-loading defect rather than a specific server link
or an Omarchy fault. Monarchy treats short-lived Sober exits as failed sessions
and continues with the newest deferred link.

Omarchy's stock crash watcher sends critical notifications, which the shell
keeps on screen indefinitely. Persistent crash toasts can obstruct Monarchy's
screen reading or input during server joins. A user-service override runs the
project's local watcher variant instead: crash alerts remain dismissible and
clickable for AI diagnosis, use normal urgency, and expire after ten seconds.
Set `OMARCHY_CRASH_TIMEOUT_MS` in the service environment to change that delay.
Other critical notifications are unaffected.

## UI and desktop behavior

- Dashboard pages: Dashboard, Biomes, Jester Sniper, Fish Macro, Calibration,
  Settings, and Logs.
- Every dashboard sidebar entry uses the same white-star icon for a consistent
  navigation style.
- The dashboard's framed right-side card uses an ornate glowing blue-purple
  crown on a dark star field. Its border, quote, ornament, and footer remain in
  the raster asset; the former AI-generated throne scene is retained only in
  `throne-panel-original.png` as a recoverable backup.
- The old Supported Channel Targets dashboard card was removed; statistics sit
  directly below Current Target. The statistics card displays only Runtime.
- Monarchy is a floating, resizable GTK4/Libadwaita window.
- Hyprland edge/corner resize is enabled with a 15-pixel grab area.
- The window remembers its selected size.
- F1 starts Monarchy and F2 stops it by default. These keys were unbound before
  their original assignment.
- The Settings page allows each of four global actions (Monarchy Start/Stop and
  Fish Macro Start/Stop) to use a distinct key from F1 through F10. Defaults
  are F1/F2 for Monarchy and F3/F4 for fishing. Saving rewrites the managed
  `monarchy-bindings.lua`, reloads Hyprland, and displays any config error.
- F6 is otherwise assigned to Easy Autoclicker and F9 to push-to-talk
  dictation. Selecting either in Monarchy explicitly unbinds and overrides its
  prior action; moving the Monarchy action away restores the original binding
  on the next full Hyprland reload.

## Validation after changes

- Python: run `python3 -m py_compile` on changed Python files.
- Shell: run `bash -n` on changed shell scripts.
- Extension: run `node --check` on changed JavaScript and `jq empty` on the
  manifest.
- Hyprland config: run `hyprctl reload` and `hyprctl configerrors`.
- Do not restart an active listener while a Jester workflow is running because
  stopping the unit terminates its child automation.
- Browser-extension changes require reloading/restarting the Discord Chromium
  app before testing.
