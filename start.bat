@echo off
set "APP=%~dp0dist\VoiceThoughtCapture\VoiceThoughtCapture.exe"
if not exist "%APP%" (
  echo Application is not packaged yet. Run build.bat.
  pause
  exit /b 1
)
start "" "%APP%"
