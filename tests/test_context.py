"""Context must change inference windows, never the output sample timeline."""
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from gr_snac_core.chunks import ContextChunks


class ContextTests(unittest.TestCase):
    def test_exact_samples_for_irregular_calls_and_short_tails(self):
        for length in (1, 2399, 2400, 2401, 5001, 40000):
            for context in (1, 1200, 12000):
                with self.subTest(length=length, context=context):
                    source = np.arange(length, dtype=np.float32)
                    windows = ContextChunks(2400, context, 2048)
                    pieces = []
                    position = 0
                    for start in range(0, length, 317):
                        end = min(start + 317, length)
                        for audio, crop, count in windows.feed(source[start:end], final=end == length):
                            self.assertEqual(int(audio[0]) % 2048, 0)
                            self.assertEqual(int(audio[crop]), position)
                            pieces.append(audio[crop:crop+count])
                            position += count
                        self.assertLessEqual(len(windows.buffer), 2400 + 2*context + 2048)
                    np.testing.assert_array_equal(np.concatenate(pieces), source)

    def test_waits_for_future_context(self):
        windows = ContextChunks(2400, 1200, 2048)
        self.assertEqual(list(windows.feed(np.zeros(3599, np.float32))), [])
        emitted = list(windows.feed(np.zeros(1, np.float32)))
        self.assertEqual([(len(a), crop, count) for a, crop, count in emitted], [(3600, 0, 2400)])


if __name__ == "__main__":
    unittest.main()
