import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from gr_snac_core.token_file import TokenWriter, read_tokens, pack12, unpack12
from gr_snac_core.frames import FRAME_MODE


class TokenFileTests(unittest.TestCase):
    def test_compact_frames_pack_across_byte_boundaries_and_preserve_tail(self):
        for frames in (1, 2, 3):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "frames.snac"
                writer = TokenWriter(path)
                original = []
                for index in range(frames):
                    levels = [np.array([0xABC+index]), np.array([0xDEF, index]), np.array([1, 4095, 3, 0x123])]
                    meta = dict(stream_mode=FRAME_MODE, chunk_index=index,
                                audio_samples=17 if index == frames-1 else 2048,
                                encoded_samples=2048, crop_start=0)
                    writer.write(meta, levels)
                    original.append((meta, levels))
                report = writer.finish(True)
                self.assertEqual(report["payload_bytes"], (frames*84+7)//8)
                self.assertEqual(report["steady_token_bitrate_bps"], 984.375)
                restored = list(read_tokens(path))
                self.assertEqual(len(restored), frames)
                for (meta, levels), (new_meta, new_levels) in zip(original, restored):
                    for key in meta:
                        self.assertEqual(meta[key], new_meta[key])
                    for a, b in zip(levels, new_levels):
                        np.testing.assert_array_equal(a, b)
                content = path.read_bytes()
                path.write_bytes(content[:-1])
                with self.assertRaises(ValueError):
                    list(read_tokens(path))

    def test_known_bit_pattern_and_odd_count(self):
        levels = [np.array([0xABC]), np.array([0xDEF]), np.array([0x123])]
        self.assertEqual(pack12(levels), bytes.fromhex("abcdef1230"))
        for a, b in zip(levels, unpack12(pack12(levels), [1, 1, 1])):
            np.testing.assert_array_equal(a, b)

    def test_all_12_bit_values_roundtrip(self):
        levels = [np.arange(4096), np.array([4095, 0]), np.array([16])]
        restored = unpack12(pack12(levels), list(map(len, levels)))
        for a, b in zip(levels, restored):
            np.testing.assert_array_equal(a, b)

    def test_container_roundtrip_crop_size_and_truncation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "audio.snac"
            writer = TokenWriter(path)
            levels = [np.array([0]), np.array([1, 2]), np.array([3, 4, 5, 4095])]
            meta = dict(audio_samples=1000, encoded_samples=2000, crop_start=500, chunk_index=0)
            writer.write(meta, levels)
            report = writer.finish(complete=True)
            self.assertEqual(report["payload_bytes"], 11)
            self.assertEqual(report["file_bytes"], path.stat().st_size)
            self.assertEqual(report["token_bitrate_bps"], 84*24000/1000)
            self.assertEqual(report["file_bitrate_bps"], path.stat().st_size*8*24000/1000)
            records = list(read_tokens(path))
            for key in meta:
                self.assertEqual(records[0][0][key], meta[key])
            for a, b in zip(levels, records[0][1]):
                np.testing.assert_array_equal(a, b)
            content = path.read_bytes()
            for length in (0, 8, len(content)-1, len(content)-25):
                path.write_bytes(content[:length])
                with self.assertRaises(ValueError):
                    list(read_tokens(path))

    def test_manual_stop_is_incomplete(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "audio.snac"
            writer = TokenWriter(path)
            self.assertFalse(writer.finish()["complete"])
            with self.assertRaises(ValueError):
                list(read_tokens(path))


if __name__ == "__main__":
    unittest.main()
