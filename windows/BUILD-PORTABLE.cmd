@echo off
setlocal
cd /d "%~dp0"
title Build Monarchy Portable

echo Building Monarchy for Windows...
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
if errorlevel 1 (
  echo.
  echo BUILD FAILED.
  echo Read the error above. If Tesseract is missing, install 64-bit
  echo Tesseract OCR into C:\Program Files\Tesseract-OCR and try again.
  echo.
  pause
  exit /b 1
)

echo.
echo BUILD COMPLETE.
echo Send this file to your friend:
echo %~dp0dist\Monarchy-Windows-Portable.zip
echo.
explorer.exe /select,"%~dp0dist\Monarchy-Windows-Portable.zip"
pause
