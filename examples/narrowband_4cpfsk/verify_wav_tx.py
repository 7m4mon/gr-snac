"""Real-model WAV -> SNAC -> framed 4CPFSK integration checks (no SDR)."""
import argparse
import json
import os
from pathlib import Path
import threading
import wave

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
import numpy as np
import pmt
from PyQt5 import QtCore, QtWidgets
from gnuradio import blocks
import wav_snac_4cpfsk as flowgraph
from radio_frame import make_symbols, pack_information, wav_transmission_info
from sweep_4cpfsk import modulate


def run_case(app, path, repeats, output, label):
    output.mkdir(parents=True, exist_ok=True)
    os.chdir(output)
    kwargs = dict(input_path=str(path))
    if repeats is not None:
        kwargs['repeat_count'] = repeats
    tb = flowgraph.wav_snac_4cpfsk(**kwargs)
    tb.set_iq_path(str(output/(label+'.cf32')))
    tb.set_dibit_path(str(output/(label+'.dibits')))
    # The status path is a constructor argument of the adapter (no runtime setter).
    tb.token_frames.status_path = str(output/(label+'.audio.json'))
    flowgraph.snippets_main_after_init(tb)
    pcm = blocks.vector_sink_f()
    info = blocks.vector_sink_b()
    messages = blocks.message_debug()
    tb.connect(tb.audio_length, pcm)
    tb.connect(tb.source_0, info)
    tb.msg_connect(tb.snac_encoder, 'codes', messages, 'store')
    tb.start()
    waiter = threading.Thread(target=tb.wait, daemon=True)
    waiter.start()
    loop = QtCore.QEventLoop()
    check = QtCore.QTimer()
    check.timeout.connect(lambda: loop.quit() if not waiter.is_alive() else None)
    check.start(50)
    timeout = QtCore.QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    timeout.start(180000)
    loop.exec_()
    check.stop()
    timeout.stop()
    tb._frame_error_timer.stop()
    finished = not waiter.is_alive()
    tb.stop()
    waiter.join(10)
    assert finished, 'WAV transmitter did not finish after finite input'
    assert tb.token_frames.error is None, str(tb.token_frames.error)
    assert tb.token_frames.eos_received
    tb.iq_file.close()
    tb.dibit_file_0.close()
    with wave.open(str(path), 'rb') as wav:
        assert wav.getsampwidth() == 2  # test fixture contract only
        original = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32)/32768
    np.testing.assert_allclose(pcm.data(), np.tile(original, tb.repeat_count), atol=1e-7)
    assert len(pcm.data()) == tb.total_samples
    assert messages.num_messages() == tb.frame_count+1
    expected_frames = []
    for i in range(tb.frame_count):
        message = messages.get_message(i)
        tokens = []
        for level in range(3):
            tokens.extend(pmt.u16vector_elements(pmt.dict_ref(message, pmt.intern(f'level{level}'), pmt.PMT_NIL)))
        payload = np.array([(int(token) >> bit) & 1 for token in tokens for bit in range(11, -1, -1)], dtype=np.uint8)
        expected_frames.append(pack_information(payload, (tb.start_sequence+i)%64, tb.frame_flags))
    information = np.concatenate(expected_frames)
    np.testing.assert_array_equal(info.data(), information)
    symbols = np.fromfile(tb.dibit_path, dtype=np.uint8)
    np.testing.assert_array_equal(symbols, make_symbols(information))
    iq = np.fromfile(tb.iq_path, dtype=np.complex64)
    assert len(iq) == (tb.frame_count*112+tb.pulse_length)*tb.samples_per_symbol
    np.testing.assert_allclose(iq, modulate(symbols, flush_symbols=tb.pulse_length), atol=1e-5)
    np.testing.assert_allclose(np.abs(iq), 1, atol=1e-5)
    status = json.loads(Path(tb.token_frames.status_path).read_text())
    assert status['eos_received'] and status['audio_samples'] == tb.total_samples
    result = dict(case=label, repeat_count=tb.repeat_count, total_samples=tb.total_samples,
                  frames=tb.frame_count, iq_samples=len(iq), final_frame_samples=tb.wav_info['final_frame_audio_samples'])
    print('PASS: '+json.dumps(result), flush=True)
    tb.close()
    app.processEvents()
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--speech-wav', type=Path)
    args = ap.parse_args()
    speech_wav = args.speech_wav.resolve() if args.speech_wav else None
    output = Path(__file__).resolve().parent/'results_wav_tx'
    output.mkdir(exist_ok=True)
    app = QtWidgets.QApplication([])
    fixture = output/'short.wav'
    samples = (np.sin(2*np.pi*440*np.arange(1001)/24000)*5000).astype('<i2')
    with wave.open(str(fixture), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(samples.tobytes())
    for invalid in [0, -1]:
        try:
            wav_transmission_info(fixture, invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid repeat count accepted')
    cases = [run_case(app, fixture, None, output, 'short_default5'),
             run_case(app, fixture, 1, output, 'short_once')]
    if speech_wav:
        cases.append(run_case(app, speech_wav, None, output, 'speech_default5'))
    (output/'verification.json').write_text(json.dumps(cases, indent=2)+'\n')


if __name__ == '__main__':
    main()
