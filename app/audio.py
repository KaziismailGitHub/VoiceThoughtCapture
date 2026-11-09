from __future__ import annotations

import logging
import threading
import time
from typing import Any

import numpy as np
import sounddevice as sd


class AudioCapture:
    def __init__(
        self,
        sample_rate: int = 16000,
        device: int | None = None,
        device_name: str = "",
        silence_seconds: float = 2.0,
        silence_threshold_rms: float = 0.012,
        no_speech_timeout_seconds: int = 15,
        max_seconds: int = 180,
    ) -> None:
        self.sample_rate = sample_rate
        self.device = device
        self.device_name = device_name
        self.silence_seconds = silence_seconds
        self.silence_threshold_rms = silence_threshold_rms
        self.no_speech_timeout_seconds = no_speech_timeout_seconds
        self.max_seconds = max_seconds
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self.done = threading.Event()
        self._stream: sd.InputStream | None = None
        self.started_at = 0.0
        self.last_voice_at = 0.0
        self.speech_detected = False
        self.stop_reason = ""
        self.error: Exception | None = None
        self._finished = False

    def _select_device(self) -> int | None:
        if self.device_name:
            for index, item in enumerate(sd.query_devices()):
                if int(item.get("max_input_channels", 0)) > 0 and self.device_name.casefold() in str(item["name"]).casefold():
                    return index
            raise RuntimeError(f"No microphone matches the configured name: {self.device_name}")
        if self.device is not None:
            item = sd.query_devices(self.device)
            if int(item.get("max_input_channels", 0)) < 1:
                raise RuntimeError(f"Audio device {self.device} has no microphone input.")
            return self.device
        return None

    def start(self) -> None:
        selected = self._select_device()
        self.started_at = time.monotonic()
        self._stream = sd.InputStream(
            device=selected,
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=0,
            callback=self._audio_callback,
        )
        self._stream.start()

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
        if status:
            logging.getLogger("voice_thought_capture").warning("Audio input status: %s", status)
        now = time.monotonic()
        try:
            chunk = np.asarray(indata[:, 0], dtype=np.float32).copy()
            with self._lock:
                if self._finished:
                    return
                self._chunks.append(chunk)
                rms = float(np.sqrt(np.mean(np.square(chunk)))) if chunk.size else 0.0
                if rms >= self.silence_threshold_rms:
                    self.speech_detected = True
                    self.last_voice_at = now
                if now - self.started_at >= self.max_seconds:
                    self.stop_reason = "maximum duration"
                    self.done.set()
                elif self.speech_detected and now - self.last_voice_at >= self.silence_seconds:
                    self.stop_reason = "silence"
                    self.done.set()
                elif not self.speech_detected and now - self.started_at >= self.no_speech_timeout_seconds:
                    self.stop_reason = "no speech"
                    self.done.set()
        except Exception as exc:
            self.error = exc
            self.stop_reason = "audio callback error"
            self.done.set()
            raise sd.CallbackStop from exc

    @property
    def duration(self) -> float:
        if not self.started_at:
            return 0.0
        return max(0.0, time.monotonic() - self.started_at)

    def request_stop(self, reason: str = "hotkey") -> None:
        self.stop_reason = reason
        self.done.set()

    def finish(self) -> np.ndarray:
        with self._lock:
            already_finished = self._finished
            self._finished = True
        if not already_finished and self._stream is not None:
            try:
                self._stream.stop()
            finally:
                self._stream.close()
                self._stream = None
        return self.samples

    @property
    def samples(self) -> np.ndarray:
        with self._lock:
            if not self._chunks:
                return np.empty(0, dtype=np.float32)
            return np.concatenate(self._chunks).astype(np.float32, copy=False)


def list_input_devices() -> list[dict[str, Any]]:
    try:
        devices = sd.query_devices()
        return [
            {"index": index, "name": str(device["name"]), "channels": int(device["max_input_channels"])}
            for index, device in enumerate(devices)
            if int(device["max_input_channels"]) > 0
        ]
    except Exception:
        logging.getLogger("voice_thought_capture").exception("Unable to enumerate audio devices")
        return []
