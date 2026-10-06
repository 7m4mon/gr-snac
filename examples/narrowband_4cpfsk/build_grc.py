"""Regenerate the example GRCs using installed GNU Radio block defaults."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent
BLOCKS = Path('/usr/share/gnuradio/grc/blocks')


def build(three=False):
    name = 'three_carriers' if three else 'narrowband_4cpfsk'
    graph = yaml.safe_load((ROOT.parent / 'snac_loopback.grc').read_text())
    graph['options']['parameters'].update(id=name, generate_options='qt_gui',
        title='Gaussian 4CPFSK: ' + ('three carriers' if three else 'single carrier'),
        description='Standard GNU Radio CPM; edit variables and restart.', author='7M4MON')
    graph['blocks'], graph['connections'] = [], []

    def block(name, kind, params, x, y):
        defaults = {}
        path = BLOCKS / (kind + '.block.yml')
        if path.exists():
            for p in yaml.safe_load(path.read_text()).get('parameters', []):
                defaults[p['id']] = str(p.get('default', p.get('options', [''])[0]))
        defaults.update(params)
        for key in defaults:
            if key.startswith('alpha'):
                defaults[key] = '1.0'
        graph['blocks'].append(dict(name=name, id=kind, parameters=defaults,
            states=dict(coordinate=[x, y], rotation=0, state='enabled',
                        bus_sink=False, bus_source=False, bus_structure=None)))

    def link(a, b, port=0):
        graph['connections'].append([a, '0', b, str(port)])

    variables = dict(symbol_rate='1312.5', samples_per_symbol='32',
        sample_rate='symbol_rate * samples_per_symbol', modulation_index_h='0.25',
        gaussian_bt='0.30', pulse_length='4', channel_spacing='2500',
        seed='12345', random_symbols='262144', duration_seconds='60',
        iq_path=repr(name + '.cf32'))
    for i, (key, value) in enumerate(variables.items()):
        block(key, 'variable', {'value': value}, 16 + (i % 5)*240, 16 + (i//5)*90)
    block('numpy_import', 'import', {'imports': 'import numpy as np'}, 16, 280)
    block('window_size', 'snippet', dict(section='main_after_init', priority='0',
        code='self.resize(1200, 900)'), 320, 280)
    for i in range(3 if three else 1):
        y = 380 + i*190
        block(f'source_{i}', 'blocks_vector_source_x', dict(type='byte',
            vector=f'np.random.default_rng(seed + {i}).integers(0, 4, random_symbols, dtype=np.uint8).tolist()',
            repeat='True', vlen='1', tags='[]'), 16, y)
        block(f'gray_{i}', 'digital_map_bb', {'map': '[253, 255, 3, 1]'}, 320, y)
        block(f'cpm_{i}', 'digital_cpmmod_bc', dict(type='analog.cpm.GAUSSIAN',
            mod_index='modulation_index_h', samples_per_symbol='samples_per_symbol',
            L='pulse_length', beta='gaussian_bt'), 520, y)
        link(f'source_{i}', f'gray_{i}')
        link(f'gray_{i}', f'cpm_{i}')
        if three:
            block(f'osc_{i}', 'analog_sig_source_x', dict(type='complex',
                samp_rate='sample_rate', waveform='analog.GR_COS_WAVE',
                freq=f'({i} - 1) * channel_spacing', amp='1', offset='0', phase='0'), 520, y+90)
            block(f'shift_{i}', 'blocks_multiply_xx', dict(type='complex',
                num_inputs='2', vlen='1'), 790, y)
            link(f'cpm_{i}', f'shift_{i}')
            link(f'osc_{i}', f'shift_{i}', 1)
    if three:
        block('sum_carriers', 'blocks_add_xx', dict(type='complex', num_inputs='3', vlen='1'), 1000, 520)
        for i in range(3):
            link(f'shift_{i}', 'sum_carriers', i)
    block('capture_length', 'blocks_head', dict(type='complex', num_items='int(duration_seconds * sample_rate)', vlen='1'), 1220, 380)
    link('sum_carriers' if three else 'cpm_0', 'capture_length')
    block('throttle', 'blocks_throttle', dict(type='complex', samples_per_second='sample_rate', vlen='1', ignoretag='True'), 1440, 380)
    link('capture_length', 'throttle')
    block('frequency', 'qtgui_freq_sink_x', dict(type='complex', name='Spectrum (use mouse zoom for +/-5 kHz)',
        fftsize='8192', bw='sample_rate', fc='0', average='0.05', grid='True',
        ctrlpanel='False', norm_window='True', gui_hint='0,0,1,1', nconnections='1'), 1670, 380)
    block('waterfall', 'qtgui_waterfall_sink_x', dict(type='complex', name='Gaussian 4CPFSK',
        fftsize='8192', bw='sample_rate', fc='0', gui_hint='1,0,1,1', nconnections='1'), 1670, 540)
    block('iq_file', 'blocks_file_sink', dict(type='complex', file='iq_path', vlen='1', append='False', unbuffered='False'), 1670, 700)
    for sink in ['frequency', 'waterfall', 'iq_file']:
        link('throttle', sink)
    (ROOT / (name + '.grc')).write_text(yaml.safe_dump(graph, sort_keys=False))


if __name__ == '__main__':
    build()
    build(True)
