"""Stock receiver PHY checks, including acquisition and FEC error correction."""
import numpy as np
import json
from pathlib import Path
from gnuradio import analog, blocks, fec, filter, gr, digital
from radio_frame import random_information, make_symbols
from sweep_4cpfsk import modulate
from rx_support import equalizer_taps, acquire


def receive(iq, count):
    tb = gr.top_block()
    source = blocks.vector_source_c(iq.tolist(), False)
    demod = analog.quadrature_demod_cf(32/(np.pi*.25))
    zeros = blocks.vector_source_f([0.]*320, False)
    mux = blocks.stream_mux(gr.sizeof_float, [len(iq), 320])
    eq = filter.fir_filter_fff(1, equalizer_taps())
    out = blocks.vector_sink_f()
    tb.connect(source, demod, (mux, 0))
    tb.connect(zeros, (mux, 1))
    tb.connect(mux, eq, out)
    tb.run()
    values = np.asarray(out.data())
    bits, status = acquire(values, count)
    print('acquisition', len(values), status, flush=True)
    return decode_bits(bits), bits, status


def decode_bits(bits):
    tb = gr.top_block()
    src = blocks.vector_source_b(bits.tolist(), False)
    whitening = digital.additive_scrambler_bb(0x21, 0x1ff, 8, 208, 1, '')
    inter = blocks.matrix_interleaver(gr.sizeof_char, 16, 13, True)
    convert = blocks.uchar_to_float()
    scale = blocks.multiply_const_ff(2)
    offset = blocks.add_const_ff(-1)
    dec = fec.extended_decoder(fec.cc_decoder.make(104, 7, 2, [109, 79], 0, -1, fec.CC_TAILBITING, False), threading=None)
    sink = blocks.vector_sink_b()
    tb.connect(src, whitening, inter, convert, scale, offset, dec, sink)
    tb.run()
    return np.asarray(sink.data(), dtype=np.uint8)


if __name__ == '__main__':
    info = random_information(137, seed=824, start_sequence=60)
    iq = modulate(make_symbols(info), flush_symbols=4)
    recovered, channel, status = receive(iq, 137)
    np.testing.assert_array_equal(recovered, info)
    symbols = make_symbols(info).reshape(-1, 112)[:, 8:].reshape(-1)
    expected = np.stack([symbols >> 1, symbols & 1], axis=1).reshape(-1)
    np.testing.assert_array_equal(channel, expected)
    shifted = np.r_[np.ones(123, dtype=np.complex64), iq]*np.complex64(.37*np.exp(1j*1.23))
    shifted_info, _, shifted_status = receive(shifted, 137)
    np.testing.assert_array_equal(shifted_info, info)
    assert shifted_status['first_sync_sample'] == status['first_sync_sample']+123
    damaged = channel.copy()
    damaged[17::208] ^= 1
    np.testing.assert_array_equal(decode_bits(damaged), info)
    try:
        receive(np.ones_like(iq), 137)
    except ValueError:
        pass
    else:
        raise AssertionError('Constant carrier falsely synchronized')
    from radio_frame import crc12, pack_information
    from rx_tokens import blk as Tokens
    rejected = Tokens(total_samples=2048, start_sequence=60, crc_fn=crc12)
    bad_crc = info[:104].copy()
    bad_crc[3] ^= 1
    rejected.work([bad_crc.reshape(1, 104)], [])
    assert rejected.error is not None and rejected.crc_failures == 1 and rejected.frames == 0
    assert not rejected.eos_sent
    wrong_sequence = Tokens(total_samples=2048, start_sequence=60, crc_fn=crc12)
    wrong_sequence.work([pack_information(info[:84], sequence=61).reshape(1, 104)], [])
    assert wrong_sequence.error is not None and wrong_sequence.frames == 0
    output = Path(__file__).resolve().parent/'results_rx'
    output.mkdir(exist_ok=True)
    (output/'phy_verification.json').write_text(json.dumps(dict(
        frames=137, information_bits=len(info), information_bit_errors=0, channel_bit_errors=0,
        acquisition=status, shifted_acquisition=shifted_status, prefix_samples=123,
        amplitude=.37, phase_radians=1.23, corrected_channel_bit_errors=137,
        no_sync_rejected=True, crc_error_rejected=True, sequence_error_rejected=True), indent=2)+'\n')
    print('PASS: 137 frames, arbitrary 123-sample prefix/phase/gain, one channel error per frame, no-sync/CRC/sequence rejection')
