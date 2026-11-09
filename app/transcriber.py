from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

from faster_whisper import WhisperModel

from .config import Settings


class TranscriptionError(RuntimeError):
    pass


class LocalTranscriber:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: WhisperModel | None = None
        self._bengali_model: WhisperModel | None = None
        self._lock = threading.RLock()

    def _cached_path(self, repo_id: str) -> Path | None:
        repo_folder = "models--" + repo_id.replace("/", "--")
        snapshots = self.settings.model_cache / repo_folder / "snapshots"
        candidates = [path.parent for path in snapshots.glob("*/model.bin") if path.is_file()]
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)

    def _repo_cached(self, repo_id: str) -> bool:
        return self._cached_path(repo_id) is not None

    def is_cached(self) -> bool:
        general_repo = f"Systran/faster-whisper-{self.settings.model}"
        return self._repo_cached(general_repo) and self._repo_cached(self.settings.bengali_model)

    def _load_model(self, repo_id: str, model_name: str) -> WhisperModel:
        local_path = self._cached_path(repo_id)
        # Passing the snapshot directory avoids a Hugging Face metadata request on later launches.
        source = str(local_path) if local_path is not None else model_name
        return WhisperModel(
            source,
            device="cpu",
            compute_type=self.settings.compute_type,
            cpu_threads=self.settings.cpu_threads,
            num_workers=1,
            download_root=str(self.settings.model_cache),
        )

    def load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            self.settings.model_cache.mkdir(parents=True, exist_ok=True)
            repo_id = f"Systran/faster-whisper-{self.settings.model}"
            logging.getLogger("voice_thought_capture").info(
                "Loading local %s model from %s", self.settings.model, self.settings.model_cache
            )
            self._model = self._load_model(repo_id, self.settings.model)
            logging.getLogger("voice_thought_capture").info("General speech model is ready")

    def load_bengali(self) -> None:
        if self._bengali_model is not None:
            return
        with self._lock:
            if self._bengali_model is not None:
                return
            self.settings.model_cache.mkdir(parents=True, exist_ok=True)
            logging.getLogger("voice_thought_capture").info(
                "Loading Bengali speech model %s", self.settings.bengali_model
            )
            self._bengali_model = self._load_model(
                self.settings.bengali_model,
                self.settings.bengali_model,
            )
            logging.getLogger("voice_thought_capture").info("Bengali speech model is ready")

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        if audio.size == 0:
            raise TranscriptionError("No audio samples were captured.")
        self.load()
        try:
            general_segments, info = self._model.transcribe(
                audio,
                beam_size=5,
                temperature=0.0,
                language=None,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            language = str(info.language or "unknown")
            segments = general_segments
            if language == "bn":
                self.load_bengali()
                segments, info = self._bengali_model.transcribe(
                    audio,
                    beam_size=5,
                    temperature=0.0,
                    language="bn",
                    vad_filter=True,
                    condition_on_previous_text=False,
                )
            text = "".join(segment.text for segment in segments).strip()
            if not text:
                raise TranscriptionError("The recording did not produce any text.")
            return text, language
        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionError(str(exc)) from exc
