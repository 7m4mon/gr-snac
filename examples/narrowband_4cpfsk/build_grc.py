"""Regenerate the example GRCs using installed GNU Radio block defaults."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent
BLOCKS = Path('/usr/share/gnuradio/grc/blocks')


def build(three=False, framed=False, wav=False):
    if wav:
        framed, three = True, False
    name = ('three_carriers_framed' if three else 'framed_4cpfsk') if framed else (
        'three_carriers' if three else 'narrowband_4cpfsk')
    if wav:
        name = 'wav_snac_4cpfsk'
    graph = yaml.safe_load((ROOT.parent / 'snac_loopback.grc').read_text())
    graph['options']['parameters'].update(id=name, generate_options='qt_gui',
        title='Gaussian 4CPFSK: ' + ('framed ' if framed else '') + ('three carriers' if three else 'single carrier'),
        description='Standard GNU Radio CPM/FEC; edit variables and restart.', author='7M4MON')
    if wav:
        graph['options']['parameters'].update(title='WAV -> SNAC -> framed 4CPFSK',
            description='Finite repeated WAV through the SNAC encoder and stock radio PHY; IQ output only.')
    graph['blocks'], graph['connections'] = [], []

    def block(name, kind, params, x, y):
        defaults = {}
        path = BLOCKS / (kind + '.block.yml')
        if kind == 'snac_encoder':
            path = ROOT.parent.parent / 'grc/snac_encoder.block.yml'
        if kind == 'variable_cc_encoder_def':
            path = BLOCKS / 'variable_cc_encoder_def_list.block.yml'
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
    if framed:
        del variables['random_symbols']
        variables.update(frame_count='max(1, int(np.ceil(duration_seconds * symbol_rate / 112)))',
            start_sequence='0', frame_flags='0', dibit_path=repr(name+'.dibits'))
    if wav:
        del variables['duration_seconds']
        del variables['seed']
        variables.update(input_path='../VOICEACTRESS100_001_001.wav', repeat_count='5',
            wav_info='radio_frame.wav_transmission_info(input_path, repeat_count)',
            total_samples="wav_info['total_audio_samples']", frame_count="wav_info['frame_count']")
    for i, (key, value) in enumerate(variables.items()):
        kind = 'parameter' if framed and key == 'duration_seconds' else 'variable'
        params = {'value': value}
        if kind == 'parameter':
            params.update(type='eng_float', label='Capture duration (rounded up to whole frames)', short_id='', hide='none')
        if wav and key in ('input_path', 'repeat_count'):
            kind = 'parameter'
            params.update(type='str' if key == 'input_path' else 'intx',
                          label='WAV input (24 kHz mono PCM)' if key == 'input_path' else 'Total WAV plays', short_id='', hide='none')
        block(key, kind, params, 16 + (i % 5)*240, 16 + (i//5)*90)
    block('numpy_import', 'import', {'imports': 'import numpy as np'}, 16, 350 if framed else 280)
    if framed:
        # GRC evaluates expressions before the generated script is on sys.path.
        # Embed the helper so opening the .grc never needs an external import path.
        block('radio_frame', 'epy_module',
              {'source_code': (ROOT / 'radio_frame.py').read_text(encoding='utf-8')}, 600, 350)
        block('capture_metadata', 'snippet', dict(section='main_after_init', priority='1',
            code='radio_frame.write_capture_metadata(self.iq_path, self.frame_count, self.seed, '
                 'self.start_sequence, self.frame_flags, self.symbol_rate, self.samples_per_symbol, '
                 f'self.modulation_index_h, self.gaussian_bt, self.pulse_length, self.channel_spacing, {3 if three else 1})'), 850, 350)
        if wav:
            metadata = graph['blocks'][-1]['parameters']
            metadata['code'] = ('radio_frame.write_capture_metadata(self.iq_path, self.frame_count, 0, '
                'self.start_sequence, self.frame_flags, self.symbol_rate, self.samples_per_symbol, '
                'self.modulation_index_h, self.gaussian_bt, self.pulse_length, self.channel_spacing, 1)\n'
                'from pathlib import Path\nimport json\n'
                "meta_path = Path(self.iq_path + '.frames.json')\n"
                "record = json.loads(meta_path.read_text())\n"
                "record.pop('seed', None)\nrecord.pop('carrier_seeds', None)\n"
                "record.update(source='WAV -> SNAC encoder', audio=self.wav_info, codec_model=self.snac_encoder.codec.model_id, context_frames=self.snac_encoder.context)\n"
                "meta_path.write_text(json.dumps(record, indent=2) + '\\n')")
            block('frame_errors', 'snippet', dict(section='main_after_init', priority='2', code=(
                'def check_frame_error():\n'
                '    if self.token_frames.error is not None:\n'
                "        self.setWindowTitle('SNAC framing error: ' + str(self.token_frames.error))\n"
                '        self.stop()\n'
                '        self._frame_error_timer.stop()\n'
                'self._frame_error_timer = Qt.QTimer(self)\n'
                'self._frame_error_timer.timeout.connect(check_frame_error)\n'
                'self._frame_error_timer.start(100)')), 1100, 350)
    block('window_size', 'snippet', dict(section='main_after_init', priority='0',
        code='self.resize(1200, 900)'), 320, 350 if framed else 280)
    offset = 1440 if framed else 0
    if wav:
        block('wav_source', 'blocks_wavfile_source', dict(file='input_path', repeat='True', nchan='1'), 16, 480)
        block('audio_length', 'blocks_head', dict(type='float', num_items='total_samples', vlen='1'), 240, 480)
        block('snac_encoder', 'snac_encoder', dict(model='hubertsiuzdak/snac_24khz',
            device='cpu', context_frames='2', total_samples='total_samples', verbose='False'), 480, 480)
        block('token_frames', 'epy_block', dict(_source_code=(ROOT/'snac_frame_pdu.py').read_text(encoding='utf-8'),
            total_samples='total_samples', start_sequence='start_sequence', flags='frame_flags',
            frame_packer='radio_frame.pack_information', status_path="iq_path + '.audio.json'"), 760, 480)
        link('wav_source', 'audio_length')
        link('audio_length', 'snac_encoder')
        graph['connections'].append(['snac_encoder', 'codes', 'token_frames', 'codes'])
    for i in range(3 if three else 1):
        y = (800 if wav else 500 if framed else 380) + i*(300 if framed else 190)
        if wav:
            block(f'source_{i}', 'pdu_pdu_to_tagged_stream', dict(type='byte', tag='packet_len'), 16, y)
            graph['connections'].append(['token_frames', 'pdus', f'source_{i}', 'pdus'])
        else:
            block(f'source_{i}', 'blocks_vector_source_x', dict(type='byte',
            vector=(f'radio_frame.random_information(frame_count, seed + {i}, start_sequence, frame_flags).tolist()'
                    if framed else f'np.random.default_rng(seed + {i}).integers(0, 4, random_symbols, dtype=np.uint8).tolist()'),
                repeat='False' if framed else 'True', vlen='1', tags='[]'), 16, y)
        if framed:
            block(f'encoder_definition_{i}', 'variable_cc_encoder_def', dict(ndim='0',
                framebits='104', k='7', rate='2', polys='[109, 79]', state_start='0',
                mode='fec.CC_TAILBITING', padding='False'), 250, y+100)
            block(f'fec_{i}', 'fec_extended_encoder', dict(encoder_list=f'encoder_definition_{i}',
                threadtype='none', puncpat="'11'"), 300, y)
            block(f'interleaver_{i}', 'blocks_matrix_interleaver', dict(type='byte',
                vlen='1', rows='16', cols='13', deint='False'), 520, y)
            block(f'whitening_{i}', 'digital_additive_scrambler_bb', dict(mask='0x21',
                seed='0x1ff', len='8', count='208', bits_per_byte='1', reset_tag_key="''"), 740, y)
            block(f'pairs_{i}', 'blocks_repack_bits_bb', dict(k='1', l='2',
                len_tag_key="''", align_output='False', endianness='gr.GR_MSB_FIRST'), 960, y)
            block(f'sync_{i}', 'blocks_vector_source_x', dict(type='byte',
                vector='radio_frame.SYNC_DIBITS', repeat='True', vlen='1', tags='[]'), 1120, y+120)
            block(f'frame_mux_{i}', 'blocks_stream_mux', dict(type='byte',
                lengths='[8, 104]', num_inputs='2', vlen='1'), 1320, y)
            block(f'frame_limit_{i}', 'blocks_head', dict(type='byte',
                num_items='frame_count * 112', vlen='1'), 1520, y)
            block(f'dibit_file_{i}', 'blocks_file_sink', dict(type='byte',
                file=f"dibit_path + '.carrier{i}'" if three else 'dibit_path',
                vlen='1', append='False', unbuffered='False'), 1540, y+120)
            link(f'source_{i}', f'fec_{i}')
            link(f'fec_{i}', f'interleaver_{i}')
            link(f'interleaver_{i}', f'whitening_{i}')
            link(f'whitening_{i}', f'pairs_{i}')
            link(f'pairs_{i}', f'frame_mux_{i}', 1)
            link(f'sync_{i}', f'frame_mux_{i}', 0)
            link(f'frame_mux_{i}', f'frame_limit_{i}')
            link(f'frame_limit_{i}', f'dibit_file_{i}')
        block(f'gray_{i}', 'digital_map_bb', {'map': '[253, 255, 3, 1]'}, 320+offset, y)
        block(f'cpm_{i}', 'digital_cpmmod_bc', dict(type='analog.cpm.GAUSSIAN',
            mod_index='modulation_index_h', samples_per_symbol='samples_per_symbol',
            L='pulse_length', beta='gaussian_bt'), 520+offset, y)
        link(f'frame_limit_{i}' if framed else f'source_{i}', f'gray_{i}')
        if framed:
            # One end-of-capture drain, not a guard interval between frames.
            block(f'drain_zero_{i}', 'blocks_vector_source_x', dict(type='byte',
                vector='[0]', repeat='True', vlen='1', tags='[]'), 1760, y+200)
            block(f'drain_mux_{i}', 'blocks_stream_mux', dict(type='byte',
                lengths='[frame_count * 112, pulse_length]', num_inputs='2', vlen='1'), 1950, y+200)
            block(f'drain_limit_{i}', 'blocks_head', dict(type='byte',
                num_items='frame_count * 112 + pulse_length', vlen='1'), 2200, y+200)
            link(f'gray_{i}', f'drain_mux_{i}', 0)
            link(f'drain_zero_{i}', f'drain_mux_{i}', 1)
            link(f'drain_mux_{i}', f'drain_limit_{i}')
            link(f'drain_limit_{i}', f'cpm_{i}')
        else:
            link(f'gray_{i}', f'cpm_{i}')
        if three:
            block(f'osc_{i}', 'analog_sig_source_x', dict(type='complex',
                samp_rate='sample_rate', waveform='analog.GR_COS_WAVE',
                freq=f'({i} - 1) * channel_spacing', amp='1', offset='0', phase='0'), 520+offset, y+90)
            block(f'shift_{i}', 'blocks_multiply_xx', dict(type='complex',
                num_inputs='2', vlen='1'), 790+offset, y)
            link(f'cpm_{i}', f'shift_{i}')
            link(f'osc_{i}', f'shift_{i}', 1)
    if three:
        block('sum_carriers', 'blocks_add_xx', dict(type='complex', num_inputs='3', vlen='1'), 1000+offset, 520)
        for i in range(3):
            link(f'shift_{i}', 'sum_carriers', i)
    block('capture_length', 'blocks_head', dict(type='complex', num_items=(
        '(frame_count * 112 + pulse_length) * samples_per_symbol' if framed else 'int(duration_seconds * sample_rate)'), vlen='1'), 1220+offset, 380)
    link('sum_carriers' if three else 'cpm_0', 'capture_length')
    block('throttle', 'blocks_throttle', dict(type='complex', samples_per_second='sample_rate', vlen='1', ignoretag='True'), 1440+offset, 380)
    link('capture_length', 'throttle')
    block('frequency', 'qtgui_freq_sink_x', dict(type='complex', name='Spectrum (use mouse zoom for +/-5 kHz)',
        fftsize='8192', bw='sample_rate', fc='0', average='0.05', grid='True',
        ctrlpanel='False', norm_window='True', gui_hint='0,0,1,1', nconnections='1'), 1670+offset, 380)
    block('waterfall', 'qtgui_waterfall_sink_x', dict(type='complex', name='Gaussian 4CPFSK',
        fftsize='8192', bw='sample_rate', fc='0', gui_hint='1,0,1,1', nconnections='1'), 1670+offset, 540)
    block('iq_file', 'blocks_file_sink', dict(type='complex', file='iq_path', vlen='1', append='False', unbuffered='False'), 1670+offset, 700)
    for sink in ['frequency', 'waterfall', 'iq_file']:
        link('throttle', sink)
    (ROOT / (name + '.grc')).write_text(yaml.safe_dump(graph, sort_keys=False))


if __name__ == '__main__':
    build()
    build(True)
    build(framed=True)
    build(three=True, framed=True)
    build(wav=True)
