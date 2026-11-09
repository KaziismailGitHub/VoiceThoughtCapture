from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        # PyInstaller onedir layout: project/dist/AppName/AppName.exe
        return Path(sys.executable).resolve().parents[2]
    return Path(__file__).resolve().parent.parent


ROOT = project_root()
CONFIG_FILE = ROOT / "config" / "settings.json"
LOG_FILE = ROOT / "logs" / "voice_thought_capture.log"
APPDATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "VoiceThoughtCapture"
STATUS_FILE = APPDATA / "status.json"
DEFAULT_NOTE_FILE = Path.home() / "Documents" / "VoiceThoughtCapture" / "THOUGHTS.md"
DEFAULT_MODEL_DIR = APPDATA / "models"

DEFAULTS: dict[str, Any] = {
    "hotkey": "Ctrl+Alt+N",
    "fallback_hotkeys": ["Ctrl+Alt+M", "Ctrl+Shift+F12", "Ctrl+Alt+F11"],
    "notes_file": str(DEFAULT_NOTE_FILE),
    "input_device": None,
    "input_device_name": "",
    "sample_rate": 16000,
    "silence_seconds": 2.0,
    "no_speech_timeout_seconds": 15,
    "silence_threshold_rms": 0.012,
    "max_recording_seconds": 180,
    "min_recording_seconds": 0.9,
    "model": "small",
    "bengali_model": "sha1779/Faster_BengaliRegionalASR",
    "model_cache": str(DEFAULT_MODEL_DIR),
    "compute_type": "int8",
    "cpu_threads": 6,
}


@dataclass(frozen=True)
class Settings:
    hotkey: str
    fallback_hotkeys: tuple[str, ...]
    notes_file: Path
    input_device: int | None
    input_device_name: str
    sample_rate: int
    silence_seconds: float
    no_speech_timeout_seconds: int
    silence_threshold_rms: float
    max_recording_seconds: int
    min_recording_seconds: float
    model: str
    bengali_model: str
    model_cache: Path
    compute_type: str
    cpu_threads: int


def load_settings() -> Settings:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULTS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Settings must be a JSON object.")
    except Exception as exc:
        raise RuntimeError(f"Could not read settings file {CONFIG_FILE}: {exc}") from exc

    merged = {**DEFAULTS, **raw}
    try:
        notes_file = Path(os.path.expandvars(str(merged["notes_file"]))).expanduser()
        model_cache = Path(os.path.expandvars(str(merged["model_cache"]))).expanduser()
        input_device = merged.get("input_device")
        return Settings(
            hotkey=str(merged["hotkey"]),
            fallback_hotkeys=tuple(str(value) for value in merged["fallback_hotkeys"]),
            notes_file=notes_file,
            input_device=None if input_device in (None, "") else int(input_device),
            input_device_name=str(merged.get("input_device_name", "")).strip(),
            sample_rate=max(8000, int(merged["sample_rate"])),
            silence_seconds=max(0.5, float(merged["silence_seconds"])),
            no_speech_timeout_seconds=max(3, int(merged["no_speech_timeout_seconds"])),
            silence_threshold_rms=max(0.001, float(merged["silence_threshold_rms"])),
            max_recording_seconds=max(5, int(merged["max_recording_seconds"])),
            min_recording_seconds=max(0.2, float(merged["min_recording_seconds"])),
            model=str(merged["model"]),
            bengali_model=str(merged["bengali_model"]),
            model_cache=model_cache,
            compute_type=str(merged["compute_type"]),
            cpu_threads=max(1, int(merged["cpu_threads"])),
        )
    except Exception as exc:
        raise RuntimeError(f"Invalid value in {CONFIG_FILE}: {exc}") from exc
