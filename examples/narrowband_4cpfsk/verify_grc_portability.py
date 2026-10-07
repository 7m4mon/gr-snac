"""Compile and run framed GRCs with only the .grc files, without PYTHONPATH."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def main():
    environment = os.environ.copy()
    environment.pop('PYTHONPATH', None)
    environment['QT_QPA_PLATFORM'] = 'offscreen'
    with tempfile.TemporaryDirectory(prefix='gr-snac-grc-portability-') as folder:
        directory = Path(folder)
        input_dir, output_dir = directory/'input', directory/'output'
        input_dir.mkdir()
        output_dir.mkdir()
        for name in ['framed_4cpfsk', 'three_carriers_framed']:
            shutil.copy2(ROOT/(name+'.grc'), input_dir)
            subprocess.run(['grcc', '-o', str(output_dir), str(input_dir/(name+'.grc'))],
                           cwd=directory, env=environment, check=True, timeout=60)
            check = f'''
import json
from pathlib import Path
from PyQt5 import QtWidgets
import {name} as flowgraph
app = QtWidgets.QApplication([])
tb = flowgraph.{name}(duration_seconds=0.3)
flowgraph.snippets_main_after_init(tb)
tb.run()
tb.iq_file.close()
expected = (tb.frame_count*112+tb.pulse_length)*tb.samples_per_symbol
assert Path(tb.iq_path).stat().st_size == expected*8
assert json.loads(Path(tb.iq_path+'.frames.json').read_text())['format'] == 'snac-radio-experimental-v2'
for i in range({3 if name == 'three_carriers_framed' else 1}):
    getattr(tb, 'dibit_file_'+str(i)).close()
    path = tb.dibit_path + ('.carrier'+str(i) if {name == 'three_carriers_framed'} else '')
    assert Path(path).stat().st_size == tb.frame_count*112
assert not Path('radio_frame.py').exists()
print('PASS: {name}: isolated compile, embedded helper, IQ and dibit output')
'''
            subprocess.run([sys.executable, '-c', check], cwd=output_dir,
                           env=environment, check=True, timeout=30)


if __name__ == '__main__':
    main()
