@echo off
setlocal
pushd "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher not found. Install 64-bit Python 3.14 and enable the py launcher.
  popd
  pause
  exit /b 1
)
py -3.14 -m venv ".venv314"
if errorlevel 1 (
  echo Could not create the environment. Confirm that Python 3.14 is installed.
  popd
  pause
  exit /b 1
)
".venv314\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  popd
  pause
  exit /b 1
)
echo Dependencies installed for running and rebuilding the app.
popd