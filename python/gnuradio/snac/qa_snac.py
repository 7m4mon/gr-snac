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
        import threading
        audio = (.1 * np.sin(2 * np.pi * 220 * np.arange(25003) / RATE)).astype(np.float32)
        tb = gr.top_block()
        source = blocks.vector_source_f(audio.tolist(), False)
        device = os.environ.get("GR_SNAC_TEST_DEVICE", "cpu")
        enc = snac.snac_encoder(device=device, total_samples=len(audio))
        dec = snac.snac_decoder(device=device)
        sink = blocks.vector_sink_f()
        tb.connect(source, enc)
        tb.msg_connect(enc, "codes", dec, "codes")
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


if __name__ == "__main__":
    unittest.main()
