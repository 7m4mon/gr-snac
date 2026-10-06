#!/usr/bin/env python3
"""Opt-in real model + GNU Radio scheduler integration test; may download weights."""
import os
import sys
import unittest
from pathlib import Path

if os.environ.get("GR_SNAC_MODEL_TESTS") != "1":
    print("SKIP: set GR_SNAC_MODEL_TESTS=1 to download/load real weights and run GNU Radio QA")
    sys.exit(77)

import numpy as np
from gnuradio import gr, blocks
import gnuradio
# Test the checkout without exposing python/snac as upstream's top-level snac.
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
gnuradio.__path__.insert(0, str(root / "gnuradio"))
from gnuradio import snac
from gr_snac_core.codec import Codec, RATE


class RealModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec = Codec(device=os.environ.get("GR_SNAC_TEST_DEVICE", "cpu"))

    def test_model_encode_decode(self):
        for samples in (2400, 4800, 12000, 24000):
            with self.subTest(samples=samples):
                audio = (.1 * np.sin(2 * np.pi * 440 * np.arange(samples) / RATE)).astype(np.float32)
                levels, _ = self.codec.encode(audio)
                self.assertEqual(len(levels), 3)
                for level in levels:
                    self.assertGreater(len(level), 0)
                    self.assertTrue(np.all(level < 4096))
                decoded, _ = self.codec.decode(levels, samples)
                self.assertEqual(len(decoded), samples)
                self.assertTrue(np.isfinite(decoded).all())

    def test_message_stream_scheduler_tail_and_eos(self):
        self._loopback(2)

    def test_one_frame_context_and_compact_recording(self):
        self._loopback(1)

    def _loopback(self, context):
        import threading
        import tempfile
        from gr_snac_core.token_file import read_tokens
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "frames.snac"
        audio = (.1 * np.sin(2 * np.pi * 220 * np.arange(25003) / RATE)).astype(np.float32)
        tb = gr.top_block()
        source = blocks.vector_source_f(audio.tolist(), False)
        device = os.environ.get("GR_SNAC_TEST_DEVICE", "cpu")
        enc = snac.snac_encoder(device=device, total_samples=len(audio), context_frames=context)
        dec = snac.snac_decoder(device=device, context_frames=context)
        recorder = snac.snac_token_file(str(path))
        sink = blocks.vector_sink_f()
        tb.connect(source, enc)
        tb.msg_connect(enc, "codes", recorder, "codes")
        tb.msg_connect(recorder, "codes", dec, "codes")
        tb.connect(dec, sink)
        tb.start()
        waiter = threading.Thread(target=tb.wait, daemon=True)
        waiter.start()
        waiter.join(120)
        timed_out = waiter.is_alive()
        if timed_out:
            tb.stop()
            waiter.join(10)
        self.assertFalse(timed_out, "flowgraph did not terminate after EOS")
        self.assertIsNone(dec.error)
        decoded = np.array(sink.data())
        self.assertEqual(len(decoded), len(audio))
        self.assertTrue(np.isfinite(decoded).all())
        self.assertIsNone(recorder.error)
        records = list(read_tokens(path))
        self.assertEqual(len(records), 13)
        self.assertEqual(sum(meta["audio_samples"] for meta, _ in records), len(audio))
        self.assertEqual(sum(sum(map(len, levels)) for _, levels in records), 13*7)
        self.assertEqual(recorder.writer.report["payload_bytes"], (13*84+7)//8)


if __name__ == "__main__":
    unittest.main()
