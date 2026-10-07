"""Offscreen smoke check of both GRC-generated Qt applications."""
import os
import importlib
import json
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5 import QtCore, QtWidgets
from narrowband_4cpfsk import narrowband_4cpfsk
from three_carriers import three_carriers
from framed_4cpfsk import framed_4cpfsk
from three_carriers_framed import three_carriers_framed
from radio_frame import make_symbols, random_information
from sweep_4cpfsk import modulate
import numpy as np


def main():
    output = Path(__file__).resolve().parent / 'results_gui'
    output.mkdir(exist_ok=True)
    os.chdir(output)
    app = QtWidgets.QApplication([])
    for cls, spacing in [(narrowband_4cpfsk, 2500), (three_carriers, 2500), (three_carriers, 2000),
                         (framed_4cpfsk, 2500), (three_carriers_framed, 2500),
                         (three_carriers_framed, 2000)]:
        framed = cls in [framed_4cpfsk, three_carriers_framed]
        three = cls in [three_carriers, three_carriers_framed]
        tb = cls(duration_seconds=1) if framed else cls()
        # Equivalent to the GRC main_after_init window-size snippet.
        tb.resize(1200, 900)
        if not framed:
            tb.set_duration_seconds(1)
        tb.set_channel_spacing(spacing)
        filename = output / f'{cls.__name__}_{spacing}.cf32'
        tb.set_iq_path(str(filename))
        if framed:
            tb.set_dibit_path(str(filename.with_suffix('.dibits')))
        importlib.import_module(cls.__module__).snippets_main_after_init(tb)
        tb.start()
        tb.show()
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(1800, loop.quit)
        loop.exec_()
        tb.grab().save(str(filename.with_suffix('.png')))
        tb.stop()
        tb.wait()
        tb.iq_file.close()
        x = np.fromfile(filename, dtype=np.complex64)
        expected_samples = (tb.frame_count*112+tb.pulse_length)*tb.samples_per_symbol if framed else 42000
        assert len(x) == expected_samples, (filename, len(x), expected_samples)
        assert np.isfinite(x).all()
        if not three:
            np.testing.assert_allclose(np.abs(x), 1, atol=1e-5)
        else:
            assert 2.8 < np.mean(np.abs(x)**2) < 3.2
        if framed:
            metadata = json.loads(Path(str(filename)+'.frames.json').read_text())
            assert metadata['expected_iq_samples'] == len(x)
            for i in range(3 if three else 1):
                getattr(tb, f'dibit_file_{i}').close()
                dibits = np.fromfile(tb.dibit_path + (f'.carrier{i}' if three else ''), dtype=np.uint8)
                expected = make_symbols(random_information(tb.frame_count, tb.seed+i,
                                        tb.start_sequence, tb.frame_flags))
                np.testing.assert_array_equal(dibits, expected)
                if not three:
                    np.testing.assert_allclose(x, modulate(expected, flush_symbols=tb.pulse_length), atol=1e-5)
        tb.close()
        app.processEvents()
        print(f'PASS: {filename.name}, samples={len(x)}, power={np.mean(np.abs(x)**2):.5f}')


if __name__ == '__main__':
    main()
