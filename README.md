# Voice Thought Capture

Voice Thought Capture is a Windows system-tray app for recording a thought on demand, transcribing it locally, and appending the result to a Markdown file. It does not record continuously.

## Features

- Start and finish a recording with a configurable global hotkey or the tray menu.
- Stop automatically after a configurable period of silence or a maximum recording time.
- Transcribe English and Bengali on the local computer with CPU-based Whisper models.
- Append timestamped, UTF-8 entries without changing earlier notes.
- Save recovery audio or transcript files if capture, transcription, or note writing fails.

## Requirements

- 64-bit Windows.
- Python 3.14 and the Windows Python Launcher (`py`) to install dependencies and build from source.
- A microphone and internet access on first launch to download the speech models. The models use about 1 GB of disk space combined.

## Install and build from source

From the project folder, run:

1. `setup_dependencies.bat` to create `.venv314` and install the pinned dependencies.
2. `build.bat` to package the app into `dist\VoiceThoughtCapture`.
3. `setup.bat` to create Desktop and Start Menu shortcuts.

You can also run the source app with `.venv314\Scripts\python.exe launcher.py`. The app creates its default settings file at `config\settings.json` the first time it starts. That local file is intentionally excluded from version control.

## Use

1. Start the app from the Desktop shortcut or run `start.bat`.
2. Find its icon in the Windows notification area.
3. Press **Ctrl + Alt + N** to begin speaking.
4. Press the hotkey again to finish, or pause for the configured silence interval. A maximum recording duration also applies.
5. Wait for the **Thought saved** notification.

By default, notes are saved to `Documents\VoiceThoughtCapture\THOUGHTS.md` for the current Windows user. The app appends each new entry and preserves earlier entries.

To stop, right-click the tray icon and choose **Stop application**, or run `stop.bat`. Use `restart.bat` or `status.bat` for the corresponding actions. Startup with Windows is optional and off by default; run `enable_startup.bat` only if you want it.

## Settings

After the first launch, stop the app and edit `config\settings.json`, then restart it. The file supports settings for the hotkey and fallbacks, note destination, microphone selection, silence detection, model cache, and CPU thread count. The app does not configure cloud sync for the note file.

## Speech recognition

The app uses `Systran/faster-whisper-small` for general language detection and English, and routes Bengali audio to `sha1779/Faster_BengaliRegionalASR`. Both models run locally after download. Bengali and English read-speech fixtures are included for tests; recognition of mixed-language speech can vary with accent, noise, speaking pace, and which language dominates.

## Privacy and local data

Recording starts only after the user presses the hotkey or selects the tray action. Audio is processed locally; the app does not upload recordings or notes. First launch downloads model files from Hugging Face. Captured audio normally stays in memory. If processing or saving fails, recovery audio or text may be written under `data\recovery`; logs are written under `logs`. These folders can contain sensitive information and are ignored by Git.

## Tests

Run the existing test suite with:

```powershell
.venv314\Scripts\python.exe -m unittest discover -s tests -v
```

The transcription tests use the included Google FLEURS samples and real speech models. If the models are not already cached, those tests may download roughly 1 GB of model data. Fixture attribution is in `tests\fixtures\ATTRIBUTION.txt`.

## Project files

- `app/` — tray app, hotkey handling, audio capture, transcription, and note storage.
- `assets/` — application icon.
- `tests/` — unit and speech-recognition tests plus attributed public fixtures.
- `requirements.txt` — pinned Python dependencies.
- `setup_dependencies.bat`, `build.bat`, `setup.bat` — source setup, packaging, and shortcut setup.
- `THIRD_PARTY_NOTICES.txt` — third-party code, model, and fixture notices.

Build output, bundled environments, local settings, recordings, notes, logs, and other generated or private data are not part of the source release.