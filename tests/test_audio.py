from __future__ import annotations

import time
import unittest
from unittest.mock import Mock, patch

import numpy as np

from app.audio import AudioCapture
from app.config import load_settings
from app.controller import CaptureController
from app.hotkey import parse_hotkey


class AudioTests(unittest.TestCase):
    def test_voice_then_silence_completes_capture(self):
        capture = AudioCapture(silence_seconds=0.02, silence_threshold_rms=0.01)
        capture.started_at = time.monotonic()
        voiced = np.full((320, 1), 0.15, dtype=np.float32)
        capture._audio_callback(voiced, len(voiced), None, None)
        self.assertTrue(capture.speech_detected)
        time.sleep(0.03)
        silence = np.zeros((320, 1), dtype=np.float32)
        capture._audio_callback(silence, len(silence), None, None)
        self.assertTrue(capture.done.is_set())
        self.assertEqual(capture.stop_reason, "silence")
        self.assertGreater(capture.samples.size, 0)

    def test_no_speech_capture_times_out_quickly(self):
        capture = AudioCapture(no_speech_timeout_seconds=3)
        capture.started_at = time.monotonic() - 4
        silence = np.zeros((320, 1), dtype=np.float32)
        capture._audio_callback(silence, len(silence), None, None)
        self.assertTrue(capture.done.is_set())
        self.assertEqual(capture.stop_reason, "no speech")
        self.assertFalse(capture.speech_detected)

    def test_empty_capture_has_no_samples(self):
        capture = AudioCapture()
        self.assertEqual(capture.samples.size, 0)
        self.assertFalse(capture.speech_detected)

    def test_missing_selected_microphone_is_reported(self):
        capture = AudioCapture(device_name="missing microphone")
        with patch("app.audio.sd.query_devices", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "No microphone matches"):
                capture.start()

    def test_controller_reports_stream_open_error_without_crashing(self):
        class MissingDevice:
            def __init__(self, *args, **kwargs):
                pass

            def start(self):
                raise OSError("input device unavailable")

        controller = CaptureController(load_settings())
        with patch("app.controller.AudioCapture", MissingDevice):
            controller.toggle_capture()
        self.assertEqual(controller.state, "ready")
        self.assertIn("Microphone unavailable", controller._queued_notifications[-1][0])

    def test_hotkey_parser_and_validation(self):
        modifiers, key = parse_hotkey("Ctrl+Alt+N")
        self.assertEqual(key, ord("N"))
        self.assertTrue(modifiers & 0x0002)
        self.assertTrue(modifiers & 0x0001)
        with self.assertRaises(ValueError):
            parse_hotkey("N")

    def test_capture_hotkey_during_processing_does_not_start_another_recording(self):
        controller = CaptureController(load_settings())
        controller._state = "processing"
        constructor = Mock()
        with patch("app.controller.AudioCapture", constructor):
            controller.toggle_capture()
        constructor.assert_not_called()

    def test_second_hotkey_stops_active_capture_instead_of_starting_another(self):
        controller = CaptureController(load_settings())
        active = Mock()
        controller._state = "recording"
        controller._capture = active
        constructor = Mock()
        with patch("app.controller.AudioCapture", constructor):
            controller.toggle_capture()
        active.request_stop.assert_called_once_with("hotkey")
        constructor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
