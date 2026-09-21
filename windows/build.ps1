$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) { & .\setup.ps1 }
& .\.venv\Scripts\python.exe -m pip install pyinstaller==6.16.0

# Resolve Tcl/Tk from the base Python installation used by the virtual
# environment. This does not rely on initializing Tkinter during the build.
$PythonBase = [string](& .\.venv\Scripts\python.exe -c "import sys; print(sys.base_prefix)")
$PythonBase = $PythonBase.Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($PythonBase)) {
    throw "Could not locate the Python installation used to build Monarchy."
}
$TclRoot = Join-Path $PythonBase "tcl"
if (-not (Test-Path $TclRoot)) {
    throw "Python's Tcl runtime was not found. Reinstall 64-bit Python from python.org with Tcl/Tk support enabled."
}
$TclSource = Get-ChildItem $TclRoot -Directory | Where-Object {
    $_.Name -like "tcl*" -and (Test-Path (Join-Path $_.FullName "init.tcl"))
} | Select-Object -First 1 -ExpandProperty FullName
$TkSource = Get-ChildItem $TclRoot -Directory | Where-Object {
    $_.Name -like "tk*" -and (Test-Path (Join-Path $_.FullName "tk.tcl"))
} | Select-Object -First 1 -ExpandProperty FullName
if (-not $TclSource -or -not $TkSource) {
    throw "Python's Tcl/Tk runtime was not found. Reinstall 64-bit Python from python.org with Tcl/Tk support enabled."
}

$Tesseract = Join-Path $env:ProgramFiles "Tesseract-OCR"
if (-not (Test-Path (Join-Path $Tesseract "tesseract.exe"))) {
    throw "Tesseract was not found at $Tesseract. Install 64-bit Tesseract OCR before building."
}

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --name Monarchy `
    --add-data "extension;extension" `
    --collect-all winotify monarchy.py

$Internal = Join-Path $PSScriptRoot "dist\Monarchy\_internal"
$TclTarget = Join-Path $Internal "_tcl_data"
$TkTarget = Join-Path $Internal "_tk_data"
New-Item -ItemType Directory -Force $TclTarget, $TkTarget | Out-Null
Copy-Item -Recurse -Force (Join-Path $TclSource "*") $TclTarget
Copy-Item -Recurse -Force (Join-Path $TkSource "*") $TkTarget
if (-not (Test-Path (Join-Path $TclTarget "init.tcl")) -or
    -not (Test-Path (Join-Path $TkTarget "tk.tcl"))) {
    throw "Tcl/Tk runtime validation failed; the portable ZIP was not created."
}

$Portable = Join-Path $PSScriptRoot "dist\Monarchy-Windows-Portable"
New-Item -ItemType Directory -Force $Portable | Out-Null
Copy-Item -Recurse -Force .\dist\Monarchy\* $Portable
Copy-Item -Recurse -Force .\extension (Join-Path $Portable "extension")
Copy-Item -Recurse -Force $Tesseract (Join-Path $Portable "tesseract")
Copy-Item -Force .\README.md $Portable
New-Item -ItemType Directory -Force (Join-Path $Portable "data") | Out-Null
Compress-Archive -Force "$Portable\*" (Join-Path $PSScriptRoot "dist\Monarchy-Windows-Portable.zip")
$Archive = Join-Path $PSScriptRoot "dist\Monarchy-Windows-Portable.zip"
$Hash = (Get-FileHash -Algorithm SHA256 $Archive).Hash.ToLowerInvariant()
Set-Content -Encoding ascii "$Archive.sha256" "$Hash  Monarchy-Windows-Portable.zip"
Write-Host "Built dist\Monarchy-Windows-Portable.zip"
Write-Host "Built dist\Monarchy-Windows-Portable.zip.sha256"
