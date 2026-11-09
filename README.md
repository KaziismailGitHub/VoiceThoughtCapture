# VoiceThoughtCapture

On-demand voice capture for Windows with local English and Bengali transcription.

## Problem

Short ideas can be easy to lose while switching tasks. VoiceThoughtCapture provides a quick way to capture speech and save the recognized text as a dated Markdown entry without manually typing it.

## Key features

- Windows notification-area app with a configurable global hotkey and fallback keys.
- Starts recording only when requested; stops on the hotkey, detected silence, or the configured duration limit.
- CPU-based speech recognition using Faster-Whisper, with Bengali audio routed to a Bengali-tuned model.
- Appends timestamped UTF-8 entries while preserving earlier notes.
- Saves recovery audio or text locally when processing or saving fails.

## How it works

The app captures mono microphone audio with `sounddevice`. A Faster-Whisper model detects the language and transcribes general speech; detected Bengali is processed by the configured Bengali model. The transcript is appended to a Markdown file. Model files are downloaded from Hugging Face on first use and cached locally; speech audio and notes are not sent to that service.

## Technology stack

Python, `sounddevice`, NumPy, Faster-Whisper/CTranslate2, `pystray`, Pillow, PyInstaller, and Python `unittest`. The transcription tests use PyAV to read audio fixtures.

## Requirements

- 64-bit Windows and a microphone.
- Python 3.14 with the Windows Python Launcher (`py`) for source setup and packaging.
- Internet access on first launch to download the speech models (about 1 GB combined).

## Installation and setup

From the project folder:

1. Run `setup_dependencies.bat` to create `.venv314` and install dependencies.
2. Optional: run `build.bat` to package the app under `dist\VoiceThoughtCapture`.
3. Optional: run `setup.bat` after building to create Desktop and Start Menu shortcuts.

The app creates its default `config\settings.json` on first launch. This user-specific file is ignored by Git.

## How to run

- From source: `.venv314\Scripts\python.exe launcher.py`
- Packaged build: run `start.bat` after completing the build steps above.

Press **Ctrl + Alt + N** to start a capture, then press it again to finish. A configured silence pause also ends capture automatically. The default note is saved under the current user's `Documents\VoiceThoughtCapture\THOUGHTS.md`. Settings can be changed in `config\settings.json` while the app is stopped.

## Screenshots

No actual application screenshots are included yet. See [`docs/screenshots/README.md`](docs/screenshots/README.md) for instructions on adding genuine screenshots. No mockups are presented as screenshots of the running app.

## Project structure

```text
app/                    Application, audio capture, hotkeys, transcription, storage
assets/                 Application icon
docs/screenshots/       Instructions for adding real screenshots
tests/                 Unit and speech-recognition tests with attributed FLEURS fixtures
build.bat               Package the app
setup_dependencies.bat  Create the Python environment and install dependencies
setup.bat               Create shortcuts for a packaged build
requirements.txt        Pinned Python dependencies
THIRD_PARTY_NOTICES.txt Third-party code, model, and fixture notices
LICENSE                 MIT License
```

## Privacy and local storage

Recording is started by the user and processed locally after model download. The app does not upload captured audio or notes. Notes are stored in the configured Markdown path; the default is in the current user's Documents folder. Model files are cached in the user's local application data. Logs, local settings, and recovery files remain on the computer and may contain sensitive information, so they are excluded from version control.

## Testing

Run the existing suite with:

```powershell
.venv314\Scripts\python.exe -m unittest discover -s tests -v
```

The tests cover audio capture behavior, note storage, and English/Bengali transcription using the included Google FLEURS samples. Transcription tests load the real local speech models and may download them if they are not cached. Fixture attribution is in `tests/fixtures/ATTRIBUTION.txt`.

## Future improvements

- Add Windows CI for the unit tests and build checks.
- Evaluate code-switched English/Bengali speech with a documented test set.
- Provide a signed, downloadable Windows package alongside the source release.

## License

Released under the [MIT License](LICENSE).

## Release

The first stable public release is [VoiceThoughtCapture v1.0.0](https://github.com/KaziismailGitHub/VoiceThoughtCapture/releases/tag/v1.0.0).