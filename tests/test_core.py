import sys
import unittest
import tempfile
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from gr_snac_core.codec import chunk_size, prepare_audio, validate_levels, statistics


class CoreTests(unittest.TestCase):
    def test_chunk_durations(self):
        for ms in (80, 100, 120, 160, 200, 250, 500, 1000, 123.45):
            self.assertEqual(chunk_size(ms), round(24 * ms))
        for bad in (0, -1, float("nan"), float("inf"), 0.00001):
            with self.assertRaises(ValueError):
                chunk_size(bad)

    def test_audio_validation_and_clipping(self):
        np.testing.assert_array_equal(prepare_audio([-2, .25, 2]), [-1, .25, 1])
        for audio in ([], [float("nan")], [float("inf")], [[0, 1]]):
            with self.assertRaises(ValueError):
                prepare_audio(audio)

    def test_tokens_and_actual_bitrate(self):
        levels = validate_levels([[0, 4095], [2, 3, 4], [1]])
        self.assertTrue(all(x.dtype == np.uint16 for x in levels))
        self.assertEqual(statistics(levels, 12000), dict(tokens=[2, 3, 1], total_tokens=6,
                                                       raw_bits=72, bitrate=144))
        for bad in ([[0]], [[], [1], [2]], [[-1], [1], [2]],
                    [[4096], [1], [2]], [[1.2], [1], [2]], [[[1]], [1], [2]]):
            with self.assertRaises(ValueError):
                validate_levels(bad)

    def test_wav_conversion_no_normalization(self):
        from scipy.io import wavfile
        from gr_snac_core.wav import read_wav, write_wav
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "audio.wav"
            wavfile.write(path, 48000, np.full((4800, 2), 8192, dtype=np.int16))
            audio, rate = read_wav(path)
            self.assertEqual(rate, 48000)
            self.assertEqual(len(audio), 2400)
            np.testing.assert_allclose(audio[30:-30], .25, atol=.001)
            write_wav(path, audio)
            out_rate, out = wavfile.read(path)
            self.assertEqual(out_rate, 24000)
            self.assertEqual(out.shape, (2400,))
            wavfile.write(path, 24000, np.array([0, 128, 255], dtype=np.uint8))
            audio, _ = read_wav(path)
            np.testing.assert_allclose(audio, [-1, 0, 127 / 128])


if __name__ == "__main__":
    unittest.main()
