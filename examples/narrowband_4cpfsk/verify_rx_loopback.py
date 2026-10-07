"""Real TX/RX GRC loopback: compare tokens and PCM against direct SNAC decode."""
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
from PyQt5 import QtCore, QtWidgets
from gnuradio import blocks
from gnuradio.snac.messages import unpack
from gr_snac_core.frames import FrameDecoder
import wav_snac_4cpfsk as tx_graph
import receive_snac_4cpfsk as rx_graph

ROOT = Path(__file__).resolve().parent


def run(app, tb, errors, timeout_seconds=240):
    tb.start()
    waiter = threading.Thread(target=tb.wait, daemon=True)
    waiter.start()
    loop = QtCore.QEventLoop()
    check = QtCore.QTimer()
    check.timeout.connect(lambda: loop.quit() if not waiter.is_alive() or any(errors()) else None)
    check.start(50)
    timeout = QtCore.QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    timeout.start(timeout_seconds*1000)
    loop.exec_()
    check.stop()
    timeout.stop()
    completed = not waiter.is_alive()
    tb.stop()
    waiter.join(10)
    assert not any(errors()), str(errors())
    assert completed, 'Finite flowgraph did not terminate'


def case(app, wav, repeat, output, label):
    os.chdir(output)
    tx = tx_graph.wav_snac_4cpfsk(input_path=str(wav), repeat_count=repeat)
    iq_path = output/(label+'.cf32')
    tx.set_iq_path(str(iq_path))
    tx.set_dibit_path(str(output/(label+'.dibits')))
    tx.token_frames.status_path = str(output/(label+'.tx.json'))
    tx_graph.snippets_main_after_init(tx)
    sent = blocks.message_debug()
    tx.msg_connect(tx.snac_encoder, 'codes', sent, 'store')
    run(app, tx, lambda: [tx.token_frames.error])
    tx._frame_error_timer.stop()
    tx.iq_file.close()
    tx.dibit_file_0.close()
    assert tx.token_frames.eos_received
    rx = rx_graph.receive_snac_4cpfsk(iq_path=str(iq_path), wav_path=str(output/(label+'.wav')))
    rx_graph.snippets_main_after_init(rx)
    received, pcm, channel = blocks.message_debug(), blocks.vector_sink_f(), blocks.vector_sink_b()
    rx.msg_connect(rx.tokens, 'codes', received, 'store')
    rx.connect(rx.snac_decoder, pcm)
    rx.connect(rx.acquisition, channel)
    # SNAC NoiseBlock draws randomness even in eval mode. Reset only in this
    # comparison test so independent direct and radio decodes use equal noise.
    rx.snac_decoder.codec.torch.manual_seed(24680)
    run(app, rx, lambda: [rx.acquisition.error, rx.tokens.error, rx.snac_decoder.error])
    rx._rx_timer.stop()
    result_status = rx_graph.rx_support.finish_receiver(rx)
    assert result_status['complete'], result_status
    assert rx.tokens.eos_sent and rx.snac_decoder.ended
    assert sent.num_messages() == received.num_messages() == tx.frame_count+1
    oracle = FrameDecoder(rx.snac_decoder.codec, 2)
    rx.snac_decoder.codec.torch.manual_seed(24680)
    direct = []
    for i in range(sent.num_messages()):
        expected_meta, expected_levels = unpack(sent.get_message(i), 'hubertsiuzdak/snac_24khz')
        actual_meta, actual_levels = unpack(received.get_message(i), 'hubertsiuzdak/snac_24khz')
        for key in ('chunk_index', 'stream_mode', 'audio_samples', 'eos'):
            assert expected_meta.get(key) == actual_meta.get(key), (key, i)
        if expected_levels is None:
            assert actual_levels is None
            direct.extend(a for a, _, _ in oracle.finish())
        else:
            for expected, actual in zip(expected_levels, actual_levels):
                np.testing.assert_array_equal(expected, actual)
            direct.extend(a for a, _, _ in oracle.push(expected_meta, expected_levels))
    reference = np.concatenate(direct)
    audio = np.asarray(pcm.data(), dtype=np.float32)
    np.testing.assert_allclose(audio, reference, rtol=0, atol=1e-6)
    assert len(audio) == tx.total_samples
    symbols = np.fromfile(tx.dibit_path, dtype=np.uint8).reshape(-1, 112)[:, 8:].reshape(-1)
    expected_bits = np.stack([symbols >> 1, symbols & 1], axis=1).reshape(-1)
    np.testing.assert_array_equal(channel.data(), expected_bits)
    with wave.open(rx.wav_path, 'rb') as f:
        assert f.getframerate() == 24000 and f.getnchannels() == 1 and f.getnframes() == tx.total_samples
        saved = np.frombuffer(f.readframes(f.getnframes()), dtype='<i2').astype(np.float32)/32768
    np.testing.assert_allclose(saved, np.clip(audio, -1, 32767/32768), rtol=0, atol=2/32768)
    result = dict(case=label, repeats=repeat, frames=tx.frame_count, audio_samples=len(audio),
                  crc_failures=rx.tokens.crc_failures, channel_bit_errors=0, token_errors=0,
                  max_pcm_error=float(np.max(np.abs(audio-reference))), sync=rx.acquisition.status)
    print('PASS: '+json.dumps(result), flush=True)
    tx.close()
    rx.close()
    app.processEvents()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--speech-wav', type=Path)
    args = parser.parse_args()
    speech = args.speech_wav.resolve() if args.speech_wav else None
    output = ROOT/'results_rx'
    output.mkdir(exist_ok=True)
    fixture = output/'input_short.wav'
    with wave.open(str(fixture), 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes((5000*np.sin(2*np.pi*440*np.arange(1001)/24000)).astype('<i2').tobytes())
    app = QtWidgets.QApplication([])
    results = [case(app, fixture, 1, output, 'short_once'), case(app, fixture, 5, output, 'short_five')]
    if speech:
        results.append(case(app, speech, 5, output, 'speech_five'))
    (output/'verification.json').write_text(json.dumps(results, indent=2)+'\n')


if __name__ == '__main__':
    main()
