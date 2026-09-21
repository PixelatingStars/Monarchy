# Monarchy for Windows 11

This is the Windows 11 edition of Monarchy. It receives supported Sol's RNG
server links from either the Windows Discord desktop app or the included
Chromium extension, launches them with the installed Roblox client, monitors
biome sessions, and can run the guarded Jester workflow after per-PC
calibration.

## Requirements

- Windows 11 (64-bit)
- The Roblox desktop client, already signed in
- The Windows Discord desktop app, or Google Chrome/Chromium/Brave/Microsoft
  Edge with the unpacked `extension` folder loaded as a fallback
- Tesseract OCR on `PATH` when running from source
- A 1920x1080 Roblox window for the initial preview build

The portable release bundles Python dependencies and Tesseract OCR. It never
contains the builder's Roblox cookies, Discord credentials, logs, or settings.

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

The app stores settings and logs beside the executable in `data`. Delete that
folder to reset the portable copy.

## Build a portable ZIP

On Windows, double-click `BUILD-PORTABLE.cmd`. When it finishes, Explorer
selects the friend-ready `dist\Monarchy-Windows-Portable.zip` automatically.
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

Portable builds show an update banner, verify the downloaded ZIP against the
published SHA-256 file, preserve the local `data` directory, replace program
files after Monarchy exits, and restart automatically. Public releases require
no credentials. Private releases require a read-only GitHub credential stored
locally in Windows Credential Manager; never embed a token in a build.

### Moving the repository to private

Install v0.2.2 while the repository is still public, then create a fine-grained
personal access token on GitHub for the `PixelatingStars` owner. Limit repository
access to `Monarchy` and grant only read-only **Contents** permission (Metadata
read access is added automatically). In Monarchy, choose **Connect private
updates**, paste the token, and wait for the connected confirmation before
changing the repository visibility. Monarchy validates the account and release
access before saving the token in Windows Credential Manager under
`Monarchy/GitHubUpdates`. Never send or publish the token.

## Safety and limitations

- Jester automation defaults to disabled. Use **Calibrate Jester** for every
  listed control before enabling it.
- Play activation verifies Roblox has foreground focus before sending UI
  Navigation keys. Recent activity records the focus result and every key. A
  `Windows did not give foreground focus to Roblox` failure means another app
  or Windows focus policy retained keyboard input; Monarchy does not send the
  sequence blindly in that state.
- Item selection is OCR-verified and fails closed before pressing Use.
- Only Lucky Potion, Speed Potion, Heavenly Potion, and Potion of Bound can be
  purchased.
- Fish Macro and biome-item automation are not yet included in this Windows
  preview.
- Display scaling and Roblox UI changes can invalidate coordinates. Keep
  Windows scaling at 100% and recalibrate after layout changes.
- Game automation may carry account-enforcement risk. Use it at your own risk.
