"""Exercise buffering/PMT/FIFO logic without loading weights or a GNU Radio runtime.

Test doubles deliberately do not claim to verify GNU Radio scheduling; qa_snac.py does that.
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))


class Block:
    def __init__(self, **kwargs):
        self.messages = []
    def message_port_register_out(self, port): pass
    def message_port_register_in(self, port): pass
    def set_msg_handler(self, port, handler): pass
    def message_port_pub(self, port, message): self.messages.append(message)


class FakeCodec:
    def __init__(self, model, device):
        self.model_id, self.device = model, device
    def encode(self, audio):
        return [np.array([len(audio) % 4096], dtype=np.uint16)] * 3, 0.01
    def decode(self, levels, samples):
        return np.full(samples, .25, dtype=np.float32), .01


def load_blocks():
    pmt = types.ModuleType("pmt")
    pmt.intern = pmt.to_pmt = pmt.to_python = lambda x: x
    pmt.make_dict = dict
    pmt.dict_add = lambda d, k, v: {**d, k: v}
    pmt.dict_ref = lambda d, k, default: d.get(k, default)
    pmt.is_dict = lambda d: isinstance(d, dict)
    pmt.PMT_NIL = None
    pmt.init_u16vector = lambda n, values: np.array(values, dtype=np.uint16)
    pmt.is_u16vector = lambda x: isinstance(x, np.ndarray) and x.dtype == np.uint16
    pmt.u16vector_elements = lambda x: x.tolist()
    gnuradio = types.ModuleType("gnuradio")
    gnuradio.gr = types.SimpleNamespace(sync_block=Block)
    spec = importlib.util.spec_from_file_location("snac_blocks_test", ROOT / "python/gnuradio/snac/__init__.py",
                                                 submodule_search_locations=[str(ROOT / "python/gnuradio/snac")])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.dict(sys.modules, pmt=pmt, gnuradio=gnuradio):
        spec.loader.exec_module(module)
        loaded = {key: value for key, value in sys.modules.items()
                  if key.startswith("snac_blocks_test.")}
    sys.modules.update(loaded)
    return module


MODULE = load_blocks()


class BlockTests(unittest.TestCase):
    def setUp(self):
        self.enc_patch = patch.object(sys.modules["snac_blocks_test.snac_encoder"], "Codec", FakeCodec)
        self.dec_patch = patch.object(sys.modules["snac_blocks_test.snac_decoder"], "Codec", FakeCodec)
        self.enc_patch.start()
        self.dec_patch.start()
        self.addCleanup(self.enc_patch.stop)
        self.addCleanup(self.dec_patch.stop)

    def test_irregular_input_tail_eos_fifo(self):
        enc = MODULE.snac_encoder(chunk_ms=100, total_samples=5001)
        for count in (17, 3000, 1984):
            self.assertEqual(enc.work([np.zeros(count, np.float32)], []), count)
        self.assertEqual([m["metadata"].get("audio_samples") for m in enc.messages],
                         [2400, 2400, 201, None])
        self.assertEqual([m["metadata"]["chunk_index"] for m in enc.messages], [0, 1, 2, 3])
        dec = MODULE.snac_decoder()
        self.assertEqual(dec.work([], [np.empty(17, np.float32)]), 0)
        for message in enc.messages:
            dec._handle(message)
        total = 0
        while True:
            output = np.empty(333, np.float32)
            count = dec.work([], [output])
            if count == -1:
                break
            self.assertGreater(count, 0)
            np.testing.assert_array_equal(output[:count], .25)
            total += count
        self.assertEqual(total, 5001)
        self.assertIsNone(dec.error)

    def test_continuous_mode_retains_partial_chunk(self):
        enc = MODULE.snac_encoder(chunk_ms=100)
        enc.work([np.zeros(2410, np.float32)], [])
        self.assertEqual(len(enc.messages), 1)
        self.assertEqual(enc.fill, 10)
        self.assertFalse(enc.ended)

    def test_reject_wrong_model_and_token_type(self):
        from snac_blocks_test.messages import unpack
        enc = MODULE.snac_encoder(total_samples=7)
        enc.work([np.zeros(7, np.float32)], [])
        message = enc.messages[0]
        with self.assertRaises(ValueError):
            unpack(message, "wrong-model")
        message["level1"] = np.array([0], dtype=np.int64)
        with self.assertRaises(ValueError):
            unpack(message, enc.codec.model_id)

    def test_reject_invalid_metadata_and_token_range(self):
        from snac_blocks_test.messages import unpack
        enc = MODULE.snac_encoder(total_samples=7)
        enc.work([np.zeros(7, np.float32)], [])
        original = enc.messages[0]
        for key, value in (("sample_rate", 48000), ("num_levels", 4),
                           ("audio_samples", 0), ("chunk_index", -1),
                           ("chunk_duration_ms", float("nan"))):
            message = {**original, "metadata": {**original["metadata"], key: value}}
            with self.subTest(key=key), self.assertRaises(ValueError):
                unpack(message, enc.codec.model_id)
        message = {**original, "level0": np.array([4096], dtype=np.uint16)}
        with self.assertRaises(ValueError):
            unpack(message, enc.codec.model_id)


if __name__ == "__main__":
    unittest.main()
