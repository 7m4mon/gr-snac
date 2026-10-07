"""Frame-format tests; convolution reference is test-only, never a TX block."""
import unittest
import numpy as np

from radio_frame import (SYNC_DIBITS, crc12, integer_bits, pack_information,
                         random_information, make_symbols)
from sweep_4cpfsk import modulate


def reference_tailbiting(bits):
    # Independent bit-register oracle for the explicitly chosen GNU Radio masks.
    memory = 0
    for bit in bits[-6:]:
        memory = (memory << 1) | int(bit)
    initial = memory
    encoded = []
    for bit in bits:
        register = (memory << 1) | int(bit)
        encoded.extend([(register & 109).bit_count() % 2, (register & 79).bit_count() % 2])
        memory = register & 63
    assert memory == initial
    return np.asarray(encoded, dtype=np.uint8)


def reference_whitening():
    register = 0x1ff
    sequence = []
    for _ in range(208):
        sequence.append(register & 1)
        feedback = ((register >> 0) ^ (register >> 5)) & 1
        register = (register >> 1) | (feedback << 8)
    return np.asarray(sequence, dtype=np.uint8)


def reference_channel_bits(bits):
    return reference_tailbiting(bits).reshape(16, 13).T.reshape(-1) ^ reference_whitening()


class FrameTests(unittest.TestCase):
    def test_crc_catalogue_vector(self):
        bits = np.unpackbits(np.frombuffer(b'123456789', dtype=np.uint8))
        self.assertEqual(crc12(bits), 0xf5b)
        self.assertEqual(crc12(np.r_[bits, integer_bits(0xf5b, 12)]), 0)

    def test_bit_exact_layout_and_error_detection(self):
        payload = np.random.default_rng(7).integers(0, 2, 84, dtype=np.uint8)
        frame = pack_information(payload, sequence=43, flags=2)
        self.assertEqual(len(frame), 104)
        np.testing.assert_array_equal(frame[:84], payload)
        np.testing.assert_array_equal(frame[84:92], integer_bits((43 << 2) | 2, 8))
        self.assertEqual(crc12(frame), 0)
        for bit in range(104):
            damaged = frame.copy()
            damaged[bit] ^= 1
            self.assertNotEqual(crc12(damaged), 0)

    def test_sequence_wrap_and_input_validation(self):
        frames = random_information(4, start_sequence=62).reshape(-1, 104)
        for row, sequence in zip(frames, [62, 63, 0, 1]):
            np.testing.assert_array_equal(row[84:90], integer_bits(sequence, 6))
        for payload in [np.zeros(83), np.full(84, 2), np.zeros((7, 12))]:
            with self.assertRaises(ValueError):
                pack_information(payload)
        for kwargs in [dict(frame_count=0), dict(frame_count=1, flags=4),
                       dict(frame_count=1, start_sequence=64)]:
            with self.assertRaises(ValueError):
                random_information(**kwargs)
        with self.assertRaises(ValueError):
            make_symbols(np.zeros(103, dtype=np.uint8))

    def test_stock_fec_sync_and_scheduler_boundaries(self):
        info = random_information(137, seed=54, start_sequence=61, flags=3)
        frames = make_symbols(info).reshape(-1, 112)
        self.assertEqual(frames.shape, (137, 112))
        for bits, symbols in zip(info.reshape(-1, 104), frames):
            np.testing.assert_array_equal(symbols[:8], SYNC_DIBITS)
            coded = reference_channel_bits(bits).reshape(-1, 2)
            expected = 2*coded[:, 0] + coded[:, 1]
            np.testing.assert_array_equal(symbols[8:], expected)
        # All-zero and all-one information vectors expose polarity/order mistakes.
        for bits in [np.zeros(104, dtype=np.uint8), np.ones(104, dtype=np.uint8)]:
            symbols = make_symbols(bits)
            reference = reference_channel_bits(bits).reshape(-1, 2)
            np.testing.assert_array_equal(symbols[8:], 2*reference[:, 0]+reference[:, 1])

    def test_stock_inverse_and_frame_reset(self):
        from gnuradio import blocks, digital, gr
        info = random_information(137, seed=82).reshape(-1, 104)
        # Repeat a frame to prove the whitening state resets rather than continuing.
        info[1] = info[0]
        symbols = make_symbols(info.reshape(-1)).reshape(-1, 112)
        np.testing.assert_array_equal(symbols[0], symbols[1])
        data = symbols[:, 8:].reshape(-1)
        channel_bits = np.stack([data >> 1, data & 1], axis=1).reshape(-1)
        def undo(values):
            tb = gr.top_block()
            source = blocks.vector_source_b(values.tolist(), False)
            descrambler = digital.additive_scrambler_bb(0x21, 0x1ff, 8, 208, 1, '')
            deinterleaver = blocks.matrix_interleaver(gr.sizeof_char, 16, 13, True)
            sink = blocks.vector_sink_b()
            tb.connect(source, descrambler, deinterleaver, sink)
            tb.run()
            return np.asarray(sink.data(), dtype=np.uint8)
        decoded = undo(channel_bits)
        expected = np.concatenate([reference_tailbiting(row) for row in info])
        np.testing.assert_array_equal(decoded, expected)
        # A single channel error stays one bit after XOR and permutation.
        damaged = channel_bits.copy()
        damaged[215] ^= 1
        self.assertEqual(np.count_nonzero(undo(damaged) != expected), 1)
        # Independently verify that the nine-bit LFSR has period 511.
        state, seen = 0x1ff, set()
        while state not in seen:
            seen.add(state)
            state = (state >> 1) | ((((state >> 0) ^ (state >> 5)) & 1) << 8)
        self.assertEqual(len(seen), 511)
        self.assertEqual(state, 0x1ff)

    def test_framed_waveform_and_final_filter_drain(self):
        symbols = make_symbols(random_information(10))
        iq = modulate(symbols, flush_symbols=4)
        self.assertEqual(len(iq), (10*112+4)*32)
        np.testing.assert_allclose(np.abs(iq), 1, atol=1e-5)
        step = np.angle(iq[1:]*iq[:-1].conj())
        self.assertLess(float(np.max(np.abs(step))), 3*.25*np.pi/32 + .001)
        # L zero-level symbols finish the FIR tail and leave stationary phase.
        self.assertLess(float(np.max(np.abs(step[-16:]))), .001)


if __name__ == '__main__':
    unittest.main(verbosity=2)
