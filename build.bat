@echo off
setlocal
pushd "%~dp0"
if not exist ".venv314\Scripts\python.exe" (
  echo Project build environment is missing.
  echo Run setup_dependencies.bat first.
  popd
  pause
  exit /b 1
)
".venv314\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name VoiceThoughtCapture --icon "assets\voice_thought_capture.ico" --add-data "assets;assets" --collect-all faster_whisper --collect-all ctranslate2 --collect-all onnxruntime --collect-all sounddevice --collect-all pystray --collect-all av --collect-all huggingface_hub --collect-all tokenizers "launcher.py"
if errorlevel 1 (
  echo Build failed. Check the messages above.
  popd
  pause
  exit /b 1
)
echo Built: dist\VoiceThoughtCapture\VoiceThoughtCapture.exe
popd
