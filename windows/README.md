# Monarchy for Windows Edition

This is the Windows Edition of Monarchy. It receives supported Sol's RNG
server links from either the Windows Discord desktop app or the included
Chromium extension, launches them with the installed Roblox client, monitors
biome sessions, and closes Roblox when the target biome ends.

## Requirements

- Windows Edition (64-bit)
- The Roblox desktop client, already signed in
- The Windows Discord desktop app, or Google Chrome/Chromium/Brave/Microsoft
  Edge with the unpacked `extension` folder loaded as a fallback
- Tesseract OCR on `PATH` when running from source
- A 1920x1080 Roblox window for the initial preview build

The installer and portable release bundle Python dependencies and Tesseract
OCR. They never contain the builder's Roblox cookies, Discord credentials,
logs, or settings.

## Install (recommended)

Download and run `Monarchy-Setup.exe`. It installs for the current Windows user
without an administrator prompt, creates Start Menu and optional desktop
shortcuts, and launches `Monarchy.exe`. The program and installer use Monarchy's
purple crown icon. Settings and logs live under `%LOCALAPPDATA%\Monarchy`, while
program files live under `%LOCALAPPDATA%\Programs\Monarchy`.

## Discord desktop monitoring

Start Monarchy while the supported Discord channel is open in the official
Windows Discord app. Monarchy reads Discord's Windows accessibility tree; it
does not read Discord credentials, inject code, or modify the Discord client.
At startup it records already-visible links as a baseline and acts only on new
links that appear afterward. The selected channel must be exposed in Discord's
window title or accessibility selection state. If the dashboard keeps showing
that it is waiting, use the Chromium extension fallback and report the Discord
version plus the recent Monarchy activity log for compatibility work.

## Run from source

1. Install Python 3.12 or newer.
2. In PowerShell, run `powershell -ExecutionPolicy Bypass -File .\setup.ps1`.
3. Load `extension` as an unpacked browser extension.
4. Install 64-bit Tesseract OCR, then run `.\run-monarchy.cmd`.

Source runs store settings and logs beside the script. Packaged builds store
them in `%LOCALAPPDATA%\Monarchy`. On first launch, an older adjacent portable
`data` folder is migrated automatically. Delete the AppData folder to reset it.

## Build the installer and portable ZIP

On Windows, install Inno Setup 6, then double-click `BUILD-PORTABLE.cmd`. The
build produces the friend-ready `dist\Monarchy-Setup.exe` as well as the legacy
`dist\Monarchy-Windows-Portable.zip` transition package.
The builder also copies and verifies Python's Tcl/Tk runtime so the packaged
dashboard can start on another PC. If Tcl/Tk is missing, reinstall 64-bit
Python from python.org with the Tcl/Tk component enabled, then rebuild.

The equivalent PowerShell command is:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

The result is written under `dist\Monarchy-Windows-Portable`. The build script
expects a local Tesseract installation and copies it into the portable bundle.

## Publishing updates

The dashboard checks the latest GitHub release at `PixelatingStars/Monarchy`
after startup. To publish an update:

1. Increase `APP_VERSION` in `monarchy.py`.
2. Commit and push the change.
3. Push a matching semantic-version tag prefixed with `v`, such as `v0.2.1`.

The `Windows release` GitHub Actions workflow installs the build dependencies,
validates that the tag matches `APP_VERSION`, builds the portable package, and
creates the latest GitHub release with the ZIP and SHA-256 assets. It can also
be run manually to produce downloadable workflow artifacts without publishing
a release.

Packaged builds show an update banner, download `Monarchy-Setup.exe`, verify it
against the published SHA-256 file, close Monarchy, run the installer silently,
and relaunch automatically. The v0.4.0 release also retains a portable ZIP so
older updaters can transition to the installer-aware version. Updates come from
public GitHub releases and do not use credentials.

## Safety and limitations

- Play activation verifies Roblox has foreground focus, OCR-locates the visible
  Play label, moves to its center, pauses for the hover state, and sends a
  sequence of independent activation methods: Windows `SendInput`, the legacy
  Windows mouse API, direct window messages, a native double-click, Enter, and
  Space. It checks for the in-game Roll control between attempts and proceeds
  only after that verification succeeds. It uses the actual window
  dimensions, including 2560×1440, rather than fixed coordinates. A
  duplicate Play attempt is skipped while an existing OCR/click attempt is
  active.
  `Windows did not give foreground focus to Roblox` failure means another app
  or Windows focus policy retained input. Monarchy skips the click when OCR
  does not positively recognize Play.
- Only one biome workflow can own a Roblox session. Pressing Stop cancels its
  timers immediately, discards the deferred link, and prevents an old 90-second
  timeout from closing a newer Roblox session.
- Shop automation, fishing, and biome-item automation are intentionally not
  included in the current biome-focused Windows Edition.
- Display scaling and Roblox UI changes can affect OCR. Keep Windows scaling at
  100% while troubleshooting Play or Roll detection.
- Game automation may carry account-enforcement risk. Use it at your own risk.
