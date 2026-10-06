"""Offscreen smoke check of both GRC-generated Qt applications."""
import os
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5 import QtCore, QtWidgets
from narrowband_4cpfsk import narrowband_4cpfsk
from three_carriers import three_carriers
import numpy as np


def main():
    output = Path(__file__).resolve().parent / 'results_gui'
    output.mkdir(exist_ok=True)
    os.chdir(output)
    app = QtWidgets.QApplication([])
    for cls, spacing in [(narrowband_4cpfsk, 2500), (three_carriers, 2500), (three_carriers, 2000)]:
        tb = cls()
        # Equivalent to the GRC main_after_init window-size snippet.
        tb.resize(1200, 900)
        tb.set_duration_seconds(1)
        tb.set_channel_spacing(spacing)
        filename = output / f'{cls.__name__}_{spacing}.cf32'
        tb.set_iq_path(str(filename))
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
        assert len(x) == 42000, (filename, len(x))
        assert np.isfinite(x).all()
        if cls == narrowband_4cpfsk:
            np.testing.assert_allclose(np.abs(x), 1, atol=1e-5)
        else:
            assert 2.8 < np.mean(np.abs(x)**2) < 3.2
        tb.close()
        app.processEvents()
        print(f'PASS: {filename.name}, samples={len(x)}, power={np.mean(np.abs(x)**2):.5f}')


if __name__ == '__main__':
    main()
