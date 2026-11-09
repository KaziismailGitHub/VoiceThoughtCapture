@echo off
set "APP=%~dp0dist\VoiceThoughtCapture\VoiceThoughtCapture.exe"
if exist "%APP%" start "" "%APP%" --restart
