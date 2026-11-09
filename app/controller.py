from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from .audio import AudioCapture
from .config import ROOT, STATUS_FILE, Settings
from .hotkey import GlobalHotkey
from .storage import append_thought, save_recovery_text, save_recovery_wav
from .transcriber import LocalTranscriber


class CaptureController:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.log = logging.getLogger("voice_thought_capture")
        self.transcriber = LocalTranscriber(settings)
        self._lock = threading.RLock()
        self._state = "starting"
        self._capture: AudioCapture | None = None
        self._icon = None
        self._queued_notifications: list[tuple[str, str]] = []
        self._hotkey = GlobalHotkey(settings.hotkey, settings.fallback_hotkeys, self.toggle_capture, self.notify)
        self._processing_done = threading.Event()
        self._processing_done.set()
        self._worker: threading.Thread | None = None
        self._actual_hotkey: str | None = None
        self._write_status()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def _set_state(self, value: str) -> None:
        with self._lock:
            self._state = value
        self._write_status()

    def _write_status(self) -> None:
        try:
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp = STATUS_FILE.with_suffix(".tmp")
            payload = (
                "{\n"
                f'  "pid": {__import__("os").getpid()},\n'
                f'  "state": "{self._state}",\n'
                f'  "hotkey": "{(self._actual_hotkey or self.settings.hotkey).replace(chr(34), "")}",\n'
                f'  "notes_file": "{str(self.settings.notes_file).replace(chr(92), chr(92) * 2).replace(chr(34), "")}"\n'
                "}\n"
            )
            temp.write_text(payload, encoding="utf-8")
            temp.replace(STATUS_FILE)
        except Exception:
            self.log.exception("Could not update status file")

    def set_hotkey(self, value: str | None) -> None:
        self._actual_hotkey = value
        self._write_status()

    def attach_icon(self, icon) -> None:
        self._icon = icon
        pending, self._queued_notifications = self._queued_notifications, []
        for message, title in pending:
            self.notify(message, title)

    def notify(self, message: str, title: str = "Voice Thought Capture") -> None:
        self.log.info("Notification: %s", message)
        icon = self._icon
        if icon is None:
            self._queued_notifications.append((message, title))
            return
        try:
            icon.notify(message, title)
        except Exception:
            self.log.exception("Unable to display tray notification")

    def start(self) -> None:
        self.log.info("Starting capture service. Notes: %s", self.settings.notes_file)
        if self.transcriber.is_cached():
            self.notify("Loading offline speech models...", "Voice Thought Capture")
        else:
            self.notify("Downloading local speech models once (about 1 GB total).", "First-time setup")
        threading.Thread(target=self._warm_model, name="model-warmup", daemon=True).start()
        self._hotkey.start()
        self.set_hotkey(self._hotkey.actual)
        if self._hotkey.actual:
            self.notify(f"Hotkey {self._hotkey.actual} is active while models load.", "Voice Thought Capture")
        else:
            self.notify("No global hotkey is active. Use the tray menu or change settings.", "Hotkey unavailable")

    def _warm_model(self) -> None:
        try:
            self.transcriber.load()
            bengali_ready = True
            try:
                self.transcriber.load_bengali()
            except Exception:
                bengali_ready = False
                self.log.exception("Bengali speech model could not be loaded; English remains available")
            if self.state not in ("recording", "processing"):
                self._set_state("ready")
            if bengali_ready and self._hotkey.actual:
                self.notify(f"Ready. Press {self._hotkey.actual} to capture.", "Voice Thought Capture")
            elif bengali_ready:
                self.notify("Speech models ready. Use the tray menu to capture.", "Voice Thought Capture")
            else:
                self.notify("English model ready; Bengali model could not load. Check internet and the log.", "Model setup")
        except Exception:
            self.log.exception("General speech model could not be loaded")
            self._set_state("model_error")
            self.notify("Speech model failed to load. Check internet, disk space, and the log file.", "Setup error")

    def toggle_capture(self) -> None:
        with self._lock:
            state_before_capture = self._state
            if self._state == "recording" and self._capture is not None:
                self._capture.request_stop("hotkey")
                self.notify("Finishing recording...", "Voice Thought Capture")
                return
            if self._state == "processing":
                self.notify("The previous capture is still being prepared. Please wait.", "Voice Thought Capture")
                return
            capture = AudioCapture(
                sample_rate=self.settings.sample_rate,
                device=self.settings.input_device,
                device_name=self.settings.input_device_name,
                silence_seconds=self.settings.silence_seconds,
                no_speech_timeout_seconds=self.settings.no_speech_timeout_seconds,
                silence_threshold_rms=self.settings.silence_threshold_rms,
                max_seconds=self.settings.max_recording_seconds,
            )
            try:
                capture.start()
            except Exception as exc:
                self.log.exception("Could not start microphone capture")
                self._state = "model_error" if state_before_capture == "model_error" else "ready"
                self._write_status()
                self.notify(
                    "Microphone unavailable. Check Windows microphone privacy and the selected input device.",
                    "Voice Thought Capture",
                )
                return
            self._capture = capture
            self._state = "recording"
            self._write_status()
        self.notify(f"Listening... Press {self._hotkey.actual or self.settings.hotkey} again to finish.", "Voice Thought Capture")
        threading.Thread(target=self._watch_capture, args=(capture,), name="capture-monitor", daemon=True).start()

    def _watch_capture(self, capture: AudioCapture) -> None:
        while not capture.done.wait(0.1):
            pass
        try:
            samples = capture.finish()
        except Exception as exc:
            capture.error = capture.error or exc
            samples = capture.samples
        duration = capture.duration
        with self._lock:
            if self._capture is capture:
                self._capture = None
            if self._state == "recording":
                self._state = "processing"
                self._write_status()
        if capture.error is not None:
            self.log.error("Microphone callback failed: %s", capture.error)
            self._preserve_audio(samples, "capture-error")
            self._set_state("ready")
            self.notify("Microphone error. Any captured audio was saved for recovery.", "Capture problem")
            return
        if duration < self.settings.min_recording_seconds or not capture.speech_detected or samples.size == 0:
            self._set_state("ready")
            self.notify("No speech detected. Hold the microphone closer and try again.", "Voice Thought Capture")
            return
        if capture.stop_reason == "maximum duration":
            self.notify("Maximum recording time reached. Transcribing now.", "Voice Thought Capture")
        else:
            self.notify("Transcribing locally...", "Voice Thought Capture")
        self._processing_done.clear()
        self._worker = threading.Thread(
            target=self._transcribe_and_save,
            args=(samples, datetime.now()),
            name="transcription-worker",
            daemon=True,
        )
        self._worker.start()

    def _recovery_path(self, suffix: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return ROOT / "data" / "recovery" / f"{stamp}_{suffix}"

    def _preserve_audio(self, samples: np.ndarray, suffix: str = "transcription-failed") -> Path | None:
        if samples.size == 0:
            return None
        path = self._recovery_path(suffix).with_suffix(".wav")
        try:
            save_recovery_wav(path, samples, self.settings.sample_rate)
            self.log.error("Recovery audio saved to %s", path)
            return path
        except Exception:
            self.log.exception("Could not save recovery audio")
            return None

    def _transcribe_and_save(self, samples: np.ndarray, captured_at: datetime) -> None:
        try:
            text, language = self.transcriber.transcribe(samples)
            self.log.info("Transcription completed; detected language=%s", language)
            try:
                append_thought(self.settings.notes_file, text, captured_at)
            except Exception:
                self.log.exception("Could not append transcript to the note file")
                text_path = self._recovery_path("unsaved-transcript").with_suffix(".txt")
                try:
                    save_recovery_text(text_path, text, captured_at)
                except Exception:
                    self.log.exception("Could not save recovery transcript")
                self._preserve_audio(samples, "note-write-failed")
                self._set_state("ready")
                self.notify(f"Could not write the note. Recovery copy: {text_path}", "Save problem")
                return
            self._set_state("ready")
            self.notify("Thought saved.", "Voice Thought Capture")
        except Exception:
            self.log.exception("Speech recognition failed")
            path = self._preserve_audio(samples)
            self._set_state("ready")
            if path:
                self.notify(f"Transcription failed; audio saved here: {path}", "Recovery audio saved")
            else:
                self.notify("Transcription failed. Details are in the log file.", "Speech recognition problem")
        finally:
            self._processing_done.set()

    def shutdown(self) -> None:
        self._hotkey.stop()
        with self._lock:
            capture = self._capture
            self._capture = None
        if capture is not None:
            capture.request_stop("application exit")
            try:
                samples = capture.finish()
                if samples.size:
                    path = self._preserve_audio(samples, "app-exit-recording")
                    self.log.info("Unfinished recording preserved to %s", path)
            except Exception:
                self.log.exception("Error stopping recording during shutdown")
        if not self._processing_done.wait(timeout=120):
            self.log.warning("Transcription has not finished after 120 seconds")
        self._set_state("stopped")
        self.log.info("Capture service stopped")
