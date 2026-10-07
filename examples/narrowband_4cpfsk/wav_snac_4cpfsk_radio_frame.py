"""Experimental SNAC radio frame v2: information bits and stock GNU Radio framing.

Custom code only packs 84 payload bits, 8 control bits and CRC-12. FEC, bit
repacking and sync multiplexing use GNU Radio blocks, just as in the GRC.
"""
import argparse
import json
import operator
import wave
from pathlib import Path

import numpy as np

PAYLOAD_BITS = 84
INFORMATION_BITS = 104
CODED_BITS = 208
FRAME_SYMBOLS = 112
POLYNOMIALS = [109, 79]  # GNU Radio bit-mask convention, positive = no inversion.
INTERLEAVER_ROWS, INTERLEAVER_COLS = 16, 13
WHITENING_MASK, WHITENING_SEED, WHITENING_LEN = 0x21, 0x1ff, 8
# GNU Radio inserts feedback at bit index 8: this is a nine-bit register.
# Experimental fixed word: two occurrences of each dibit; not an acquisition claim.
SYNC_DIBITS = (0, 3, 1, 0, 2, 1, 3, 2)  # 00 11 01 00 10 01 11 10 = 0x349e


def wav_transmission_info(filename, repeat_count=5):
    """Validate the same PCM input contract as the existing SNAC WAV example."""
    repeats = operator.index(repeat_count)
    if repeats < 1:
        raise ValueError('repeat_count must be an integer >= 1 (total number of plays)')
    with wave.open(str(filename), 'rb') as wav:
        if wav.getframerate() != 24000 or wav.getnchannels() != 1 or wav.getcomptype() != 'NONE':
            raise ValueError('Use an uncompressed 24000 Hz mono PCM WAV')
        if wav.getsampwidth() not in (1, 2, 3, 4) or wav.getnframes() < 1:
            raise ValueError('WAV must contain nonempty 8/16/24/32-bit integer PCM')
        samples = wav.getnframes()
    total = samples*repeats
    return dict(input_path=str(Path(filename).resolve()), wav_samples=samples, repeat_count=repeats,
                total_audio_samples=total, frame_count=(total+2047)//2048,
                audio_seconds=total/24000, final_frame_audio_samples=(total-1)%2048+1)


def checked_bits(bits, size=None):
    values = np.asarray(bits)
    if values.ndim != 1 or not np.all((values == 0) | (values == 1)):
        raise ValueError('Expected a one-dimensional array of bits (0 or 1)')
    if size is not None and len(values) != size:
        raise ValueError(f'Expected {size} bits, got {len(values)}')
    return values.astype(np.uint8)


def integer_bits(value, width):
    value = operator.index(value)
    if not 0 <= value < (1 << width):
        raise ValueError(f'Value must fit in {width} bits')
    return np.array([(value >> i) & 1 for i in range(width-1, -1, -1)], dtype=np.uint8)


def crc12(bits):
    """CRC-12/DECT parameters: poly=0x80f, init=0, no reflection/xorout.

    Feed exactly the supplied bits MSB first; there is no byte alignment padding.
    Check value for ASCII '123456789' is 0xf5b. Append register MSB first.
    """
    register = 0
    for bit in checked_bits(bits):
        feedback = ((register >> 11) & 1) ^ int(bit)
        register = (register << 1) & 0xfff
        if feedback:
            register ^= 0x80f
    return register


def pack_information(payload, sequence=0, flags=0):
    """Return 104 unpacked bits: payload[84], sequence[6], flags[2], CRC[12]."""
    payload = checked_bits(payload, PAYLOAD_BITS)
    body = np.concatenate([payload, integer_bits(sequence, 6), integer_bits(flags, 2)])
    return np.concatenate([body, integer_bits(crc12(body), 12)])


def random_information(frame_count, seed=12345, start_sequence=0, flags=0):
    """Finite frame bank; sequence increments modulo 64, seed controls payload only."""
    frame_count = operator.index(frame_count)
    if frame_count < 1:
        raise ValueError('frame_count must be positive')
    integer_bits(start_sequence, 6)
    integer_bits(flags, 2)
    rng = np.random.default_rng(seed)
    payloads = rng.integers(0, 2, (frame_count, PAYLOAD_BITS), dtype=np.uint8)
    return np.concatenate([pack_information(payload, (start_sequence+i) % 64, flags)
                           for i, payload in enumerate(payloads)])


def encoder_object():
    from gnuradio import fec
    return fec.cc_encoder_make(INFORMATION_BITS, 7, 2, POLYNOMIALS,
                               0, fec.CC_TAILBITING, False)


def make_symbols(information):
    """Stock FEC -> interleave -> whiten -> Repack Bits -> sync mux chain.

    The Head removes any extra sync emitted before the mux sees data EOF.
    No custom FEC, bit-pair mapper or scheduler block is used here.
    """
    from gnuradio import blocks, digital, fec, gr
    information = checked_bits(information)
    if len(information) == 0 or len(information) % INFORMATION_BITS:
        raise ValueError('Information must contain complete 104-bit frames')
    count = len(information)//INFORMATION_BITS
    tb = gr.top_block()
    source = blocks.vector_source_b(information.tolist(), False)
    encoder = fec.extended_encoder(encoder_object(), threading=None, puncpat='11')
    interleaver = blocks.matrix_interleaver(gr.sizeof_char, INTERLEAVER_ROWS, INTERLEAVER_COLS, False)
    whitening = digital.additive_scrambler_bb(WHITENING_MASK, WHITENING_SEED,
        WHITENING_LEN, count=CODED_BITS, bits_per_byte=1, reset_tag_key='')
    pairs = blocks.repack_bits_bb(1, 2, '', False, gr.GR_MSB_FIRST)
    sync = blocks.vector_source_b(SYNC_DIBITS, True)
    mux = blocks.stream_mux(gr.sizeof_char, [8, 104])
    head = blocks.head(gr.sizeof_char, count*FRAME_SYMBOLS)
    sink = blocks.vector_sink_b()
    tb.connect(source, encoder, interleaver, whitening, pairs, (mux, 1))
    tb.connect(sync, (mux, 0))
    tb.connect(mux, head, sink)
    tb.run()
    symbols = np.asarray(sink.data(), dtype=np.uint8)
    if len(symbols) != count*FRAME_SYMBOLS:
        raise RuntimeError(f'Incomplete frame output: {len(symbols)} symbols')
    return symbols


def format_metadata():
    return dict(format='snac-radio-experimental-v2', payload_bits=84,
                sequence_bits=6, flags_bits=2, information_bits=104,
                crc=dict(width=12, poly='0x80f', init=0, refin=False, refout=False,
                         xorout=0, check_123456789='0xf5b', protected_bits=92,
                         bit_order='MSB first, no byte padding'),
                fec=dict(k=7, rate='1/2', polys=POLYNOMIALS, mode='CC_TAILBITING',
                         padded=False, coded_bits=208),
                sync_dibits=SYNC_DIBITS, frame_symbols=112, mapping=[-3, -1, 3, 1],
                interleaver=dict(rows=16, cols=13, order='write rows, read columns', frame_bits=208),
                scrambler=dict(type='additive XOR', mask='0x21', seed='0x1ff',
                    gnuradio_len=8, register_bits=9, count=208, bits_per_byte=1,
                    reset='before every coded frame', sync_excluded=True))


def write_capture_metadata(iq_path, frames, seed, sequence, flags, symbol_rate, sps,
                           h, bt, length, spacing, carriers):
    """Record the exact planned finite capture; completion is checked via file length."""
    record = dict(**format_metadata(), frames=frames, seed=seed,
        carrier_seeds=[seed+i for i in range(carriers)], start_sequence=sequence, flags=flags,
        symbol_rate=symbol_rate, samples_per_symbol=sps, sample_rate=symbol_rate*sps,
        h=h, bt=bt, pulse_length=length, channel_spacing=spacing, carriers=carriers,
        frame_duration_seconds=112/symbol_rate, drain_symbols=length,
        expected_iq_samples=(112*frames+length)*sps,
        expected_dibits_per_carrier=112*frames,
        capture_status='planned; a manually interrupted capture may be shorter')
    Path(str(iq_path)+'.frames.json').write_text(json.dumps(record, indent=2)+'\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--frames', type=int, default=704)
    ap.add_argument('--seed', type=int, default=12345)
    ap.add_argument('--sequence', type=int, default=0)
    ap.add_argument('--flags', type=int, default=0)
    ap.add_argument('--output', type=Path, default=Path('framed_4cpfsk.dibits'))
    args = ap.parse_args()
    info = random_information(args.frames, args.seed, args.sequence, args.flags)
    symbols = make_symbols(info)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    symbols.tofile(args.output)
    record = dict(**format_metadata(), frames=args.frames, seed=args.seed,
                  start_sequence=args.sequence, flags=args.flags,
                  first_information_bits=''.join(map(str, info[:104].tolist())),
                  first_frame_dibits=symbols[:112].tolist())
    args.output.with_suffix('.frames.json').write_text(json.dumps(record, indent=2)+'\n')
    print(f'{args.frames} frames, {len(symbols)} dibits -> {args.output}')


if __name__ == '__main__':
    main()
