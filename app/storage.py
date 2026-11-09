from __future__ import annotations

import os
import wave
from datetime import datetime
from pathlib import Path

import numpy as np


def append_thought(note_file: Path, text: str, captured_at: datetime | None = None) -> None:
    thought = text.strip()
    if not thought:
        raise ValueError("Refusing to append an empty transcription.")
    timestamp = captured_at or datetime.now()
    note_file.parent.mkdir(parents=True, exist_ok=True)
    entry = f"## {timestamp:%Y-%m-%d %I:%M %p}\n\n{thought}\n\n---\n\n"
    with note_file.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(entry)
        handle.flush()
        os.fsync(handle.fileno())


def save_recovery_wav(file_path: Path, samples: np.ndarray, sample_rate: int = 16000) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    mono = np.asarray(samples, dtype=np.float32).reshape(-1)
    pcm = (np.clip(mono, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(file_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm.tobytes())


def save_recovery_text(file_path: Path, text: str, captured_at: datetime | None = None) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = captured_at or datetime.now()
    with file_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"Captured {timestamp:%Y-%m-%d %I:%M %p}\n\n{text.strip()}\n\n---\n\n")
        handle.flush()
        os.fsync(handle.fileno())
