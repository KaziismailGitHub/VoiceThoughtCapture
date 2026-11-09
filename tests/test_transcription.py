from __future__ import annotations

import unicodedata
import unittest
from pathlib import Path

import av
import numpy as np

from app.config import ROOT, load_settings
from app.transcriber import LocalTranscriber


def load_mono_16k(file_path: Path) -> np.ndarray:
    container = av.open(str(file_path))
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
    parts = []
    for frame in container.decode(audio=0):
        parts.extend(output.to_ndarray().reshape(-1) for output in resampler.resample(frame))
    if not parts:
        return np.empty(0, dtype=np.float32)
    return np.concatenate(parts).astype(np.float32)


class RealSpeechModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transcriber = LocalTranscriber(load_settings())
        cls.fixtures = ROOT / "tests" / "fixtures"

    def test_english_sample(self):
        audio = load_mono_16k(self.fixtures / "fleurs_en_sample.wav")
        text, language = self.transcriber.transcribe(audio)
        self.assertEqual(language, "en")
        normalized = unicodedata.normalize("NFKC", text).casefold()
        self.assertIn("slow communication channels", normalized)
        self.assertIn("25 to 30", normalized)

    def test_bengali_sample_uses_bengali_script(self):
        audio = load_mono_16k(self.fixtures / "fleurs_bn_sample.wav")
        text, language = self.transcriber.transcribe(audio)
        self.assertEqual(language, "bn")
        self.assertIn("জার্মানির", text)
        self.assertGreater(sum("\u0980" <= char <= "\u09ff" for char in text), 20)


if __name__ == "__main__":
    unittest.main()
