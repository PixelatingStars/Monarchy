@echo off
setlocal
cd /d "%~dp0"
title Build Monarchy Installer

echo Building Monarchy for Windows...
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
if errorlevel 1 (
  echo.
  echo BUILD FAILED.
  echo Read the error above. If Tesseract is missing, install 64-bit
  echo Tesseract OCR and Inno Setup 6, then try again.
  echo.
  pause
  exit /b 1
)

echo.
echo BUILD COMPLETE.
echo Share or install this file:
echo %~dp0dist\Monarchy-Setup.exe
echo.
explorer.exe /select,"%~dp0dist\Monarchy-Setup.exe"
pause
