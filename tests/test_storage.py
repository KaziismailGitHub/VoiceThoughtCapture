from __future__ import annotations

import tempfile
import unittest
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

from app.storage import append_thought, save_recovery_wav


class StorageTests(unittest.TestCase):
    def test_append_preserves_old_entries_and_bangla_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            note = Path(directory) / "THOUGHTS.md"
            first = "আগামীকাল Blender-এর আলো নিয়ে কাজ করব."
            second = "Research this in Chrome, তারপর Illustrator-এ apply করব!"
            append_thought(note, first, datetime(2026, 11, 7, 9, 5))
            original = note.read_bytes()
            append_thought(note, second, datetime(2026, 11, 7, 9, 7))

            saved = note.read_text(encoding="utf-8")
            self.assertIn(first, saved)
            self.assertIn(second, saved)
            self.assertIn("2026-11-07 09:05 AM", saved)
            self.assertIn("2026-11-07 09:07 AM", saved)
            self.assertTrue(saved.encode("utf-8").startswith(original))
            self.assertEqual(saved.count("---"), 2)

    def test_empty_transcript_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            note = Path(directory) / "THOUGHTS.md"
            note.write_text("old thought\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                append_thought(note, " \n ")
            self.assertEqual(note.read_text(encoding="utf-8"), "old thought\n")

    def test_recovery_audio_is_valid_pcm_wav(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "recovery.wav"
            samples = np.array([0.0, 0.2, -0.2, 1.0], dtype=np.float32)
            save_recovery_wav(output, samples, 16000)
            with wave.open(str(output), "rb") as captured:
                self.assertEqual(captured.getnchannels(), 1)
                self.assertEqual(captured.getframerate(), 16000)
                self.assertEqual(captured.getnframes(), 4)


if __name__ == "__main__":
    unittest.main()
