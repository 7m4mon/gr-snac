"""Finite-file receiver parameters, Gaussian equalizer design and sync acquisition.

No transmitted payload, dibit file or RNG state is used for acquisition.
The first receiver intentionally assumes the transmitter sample clock and no CFO.
"""
import json
from pathlib import Path
import numpy as np


def capture_info(iq_path):
    meta = json.loads(Path(str(iq_path)+'.frames.json').read_text())
    if (meta.get('format') != 'snac-radio-experimental-v2' or meta.get('carriers') != 1
            or meta.get('samples_per_symbol') != 32 or meta.get('h') != .25
            or meta.get('bt') != .3 or meta.get('pulse_length') != 4
            or meta.get('sample_rate') != 42000):
        raise ValueError('Receiver requires single-carrier v2, 42 kHz, SPS32, h=.25, BT=.3, L4')
    samples = Path(iq_path).stat().st_size//8
    if Path(iq_path).stat().st_size % 8 or samples < meta['expected_iq_samples']:
        raise ValueError('Incomplete complex64 IQ capture')
    # Extra prefix/suffix samples are allowed for acquisition experiments.
    audio_samples = meta['audio']['total_audio_samples']
    if audio_samples < 1 or (audio_samples+2047)//2048 != meta['frames']:
        raise ValueError('Inconsistent finite audio length')
    return dict(iq_samples=samples, frames=meta['frames'], audio_samples=audio_samples,
                start_sequence=meta['start_sequence'], context_frames=meta.get('context_frames', 2), validation_error='')


def preview_info(iq_path):
    # GRC must remain editable before the first TX capture exists. The acquisition
    # block rejects this placeholder at runtime, before processing any samples.
    try:
        return capture_info(iq_path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return dict(iq_samples=3712, frames=1, audio_samples=2048, start_sequence=0,
                    context_frames=2, validation_error=f'Invalid IQ/metadata: {exc}')


def equalizer_taps():
    """9 symbol-spaced inverse FIR, implemented by stock FIR Filter in GRC.

    Sampled Gaussian frequency pulse is a five-tap ISI channel. Least squares
    approximates its inverse with a four-symbol delay. No received data is fitted.
    """
    from gnuradio import analog, digital
    pulse = np.asarray(digital.cpmmod_bc(analog.cpm.GAUSSIAN, .25, 32, 4, .3).taps())*32
    channel = np.r_[pulse[::32], 0.0]
    convolution = np.zeros((len(channel)+8, 9))
    for i in range(9):
        convolution[i:i+len(channel), i] = channel
    target = np.zeros(len(convolution))
    target[6] = 1
    inverse = np.linalg.lstsq(convolution, target, rcond=None)[0]
    taps = np.zeros(257)
    taps[::32] = inverse
    return taps.tolist()


def finish_receiver(tb):
    """Call after the graph has stopped; close WAV and report actual completion."""
    tb.wav_sink.close()
    errors = [str(e) for e in (tb.acquisition.error, tb.tokens.error, tb.snac_decoder.error) if e is not None]
    saved = int(tb.wav_sink.nitems_read(0))
    complete = (not errors and tb.tokens.eos_sent and tb.snac_decoder.ended
                and saved == tb.capture['audio_samples'])
    record = dict(complete=complete, errors=errors, saved_audio_samples=saved,
                  expected_audio_samples=tb.capture['audio_samples'],
                  accepted_frames=tb.tokens.frames, crc_failures=tb.tokens.crc_failures,
                  sync=tb.acquisition.status, audio_length_source='TX sidecar JSON, not an on-air field')
    Path(tb.wav_path+'.rx.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


def acquire(samples, frame_count):
    """Try 32 sampling phases and exact sync matches at 112-symbol spacing.

    All expected sync words must agree. Rank candidates by distance to the four
    legal levels, then recover the data bits. CRC/FEC run in downstream blocks.
    """
    sync = np.array([0, 3, 1, 0, 2, 1, 3, 2], dtype=np.uint8)
    level_to_dibit = np.array([0, 1, 3, 2], dtype=np.uint8)
    best = None
    for phase in range(32):
        values = np.asarray(samples[phase::32])
        indices = np.clip(np.floor((values+4)/2), 0, 3).astype(np.int32)
        dibits = level_to_dibit[indices]
        if len(dibits) < frame_count*112:
            continue
        windows = np.lib.stride_tricks.sliding_window_view(dibits, 8)
        hits = np.flatnonzero(np.all(windows == sync, axis=1))
        hit_set = set(hits.tolist())
        for start in hits:
            end = start+frame_count*112
            if end > len(dibits) or not all(start+112*i in hit_set for i in range(frame_count)):
                continue
            error = float(np.mean((values[start:end]-(2*indices[start:end]-3))**2))
            if best is None or error < best[0]:
                best = error, phase, int(start), dibits[start:end].copy()
    if best is None:
        raise ValueError('No complete sync chain: truncated capture, clock/CFO error or excessive noise')
    error, phase, start, dibits = best
    data = dibits.reshape(-1, 112)[:, 8:].reshape(-1)
    bits = np.stack([data >> 1, data & 1], axis=1).reshape(-1).astype(np.uint8)
    return bits, dict(sampling_phase=phase, first_sync_symbol=start,
                      first_sync_sample=start*32+phase, sync_frames=frame_count,
                      level_mse=error)
