@echo off
setlocal
set "APP=%~dp0dist\VoiceThoughtCapture\VoiceThoughtCapture.exe"
if not exist "%APP%" (
  echo Voice Thought Capture is not packaged yet.
  echo Ask the setup maintainer to run build.bat first.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcuts.ps1"
