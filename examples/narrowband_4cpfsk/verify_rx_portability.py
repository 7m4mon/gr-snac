"""Compile only the RX GRC elsewhere, then recover an existing short IQ capture."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def main():
    environment = os.environ.copy()
    environment.update(QT_QPA_PLATFORM='offscreen', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='gr-snac-rx-portability-') as folder:
        directory = Path(folder)
        shutil.copy2(ROOT/'receive_snac_4cpfsk.grc', directory)
        subprocess.run([sys.executable, '/usr/bin/grcc', '-o', str(directory), str(directory/'receive_snac_4cpfsk.grc')],
                       cwd=directory, env=environment, check=True, timeout=60)
        code = '''
import sys
from pathlib import Path
from PyQt5 import QtWidgets
import receive_snac_4cpfsk as graph
app = QtWidgets.QApplication([])
tb = graph.receive_snac_4cpfsk(iq_path=sys.argv[1], wav_path=str(Path('recovered.wav').resolve()))
tb.run()
status = graph.rx_support.finish_receiver(tb)
assert status['complete'] and status['saved_audio_samples'] == 1001, status
assert not Path('radio_frame.py').exists() and not Path('rx_support.py').exists()
print('PASS: isolated RX GRC compile/run; embedded helpers; 1001 recovered samples')
'''
        subprocess.run([sys.executable, '-c', code, str(ROOT/'results_rx/short_once.cf32')],
                       cwd=directory, env=environment, check=True, timeout=120)


if __name__ == '__main__':
    main()
