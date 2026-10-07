"""Generate finite IQ -> stock demod/FEC -> SNAC -> WAV receiver GRC."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent
BLOCKS = Path('/usr/share/gnuradio/grc/blocks')


def build():
    graph = yaml.safe_load((ROOT/'wav_snac_4cpfsk.grc').read_text())
    graph['options']['parameters'].update(id='receive_snac_4cpfsk', title='4CPFSK IQ -> SNAC -> WAV',
        description='Finite file receiver: fixed sample clock, no CFO tracking; metadata supplies audio length.')
    graph['blocks'], graph['connections'] = [], []

    def block(name, kind, params, x, y):
        path = BLOCKS/(kind+'.block.yml')
        if kind == 'fir_filter_xxx':
            path = BLOCKS/'filter_fir_filter_xxx.block.yml'
        if kind == 'snac_decoder':
            path = ROOT.parent.parent/'grc/snac_decoder.block.yml'
        defaults = {}
        if path.exists():
            for p in yaml.safe_load(path.read_text()).get('parameters', []):
                defaults[p['id']] = str(p.get('default', p.get('options', [''])[0]))
        defaults.update(params)
        for key in defaults:
            if key.startswith('alpha'):
                defaults[key] = '1.0'
        graph['blocks'].append(dict(name=name, id=kind, parameters=defaults,
            states=dict(coordinate=[x, y], rotation=0, state='enabled', bus_sink=False, bus_source=False, bus_structure=None)))

    def link(a, b, port=0):
        graph['connections'].append([a, '0', b, str(port)])

    for i, (name, value) in enumerate([('iq_path', 'wav_snac_4cpfsk.cf32'), ('wav_path', 'received_snac.wav')]):
        block(name, 'parameter', dict(value=value, type='str', label=name, short_id='', hide='none'), 16+i*300, 16)
    block('rx_support', 'epy_module', dict(source_code=(ROOT/'rx_support.py').read_text()), 650, 16)
    block('radio_frame', 'epy_module', dict(source_code=(ROOT/'radio_frame.py').read_text()), 950, 16)
    block('imports', 'import', dict(imports='import numpy as np\nfrom gnuradio import fec'), 1250, 16)
    block('capture', 'variable', dict(value='rx_support.preview_info(iq_path)'), 16, 150)
    block('sample_rate', 'variable', dict(value='42000'), 320, 150)
    block('decoder', 'variable', dict(value='fec.cc_decoder.make(104, 7, 2, [109, 79], 0, -1, fec.CC_TAILBITING, False)'), 650, 150)
    block('iq_source', 'blocks_file_source', dict(type='complex', file='iq_path', repeat='False', vlen='1'), 16, 320)
    block('demod', 'analog_quadrature_demod_cf', dict(gain='32/(np.pi*0.25)'), 260, 320)
    block('drain', 'blocks_vector_source_x', dict(type='float', vector='[0.0]*320', repeat='False', vlen='1', tags='[]'), 260, 460)
    block('drain_mux', 'blocks_stream_mux', dict(type='float', lengths="[capture['iq_samples'], 320]", vlen='1'), 500, 320)
    block('equalizer', 'fir_filter_xxx', dict(type='fff', decim='1', taps='rx_support.equalizer_taps()', samp_delay='0'), 750, 320)
    block('acquisition', 'epy_block', dict(_source_code=(ROOT/'rx_acquire.py').read_text(),
        sample_count="capture['iq_samples'] + 320", frame_count="capture['frames']",
        acquire_fn='rx_support.acquire', status_path="wav_path + '.sync.json'", validation_error="capture['validation_error']"), 1020, 320)
    block('whitening', 'digital_additive_scrambler_bb', dict(mask='0x21', seed='0x1ff', len='8', count='208', bits_per_byte='1', reset_tag_key=''), 16, 650)
    block('deinterleave', 'blocks_matrix_interleaver', dict(type='byte', rows='16', cols='13', deint='True'), 290, 650)
    block('to_float', 'blocks_uchar_to_float', {}, 550, 650)
    block('scale', 'blocks_multiply_const_vxx', dict(type='float', const='2', vlen='1'), 750, 650)
    block('offset', 'blocks_add_const_vxx', dict(type='float', const='-1', vlen='1'), 960, 650)
    block('fec_decode', 'fec_extended_decoder', dict(decoder_list='decoder', threadtype='none', ann='None', puncpat='11'), 1180, 650)
    block('vectors', 'blocks_stream_to_vector', dict(type='byte', num_items='104', vlen='1'), 16, 900)
    block('tokens', 'epy_block', dict(_source_code=(ROOT/'rx_tokens.py').read_text(), total_samples="capture['audio_samples']",
        start_sequence="capture['start_sequence']", crc_fn='radio_frame.crc12', status_path="wav_path + '.frames.json'"), 280, 900)
    block('snac_decoder', 'snac_decoder', dict(model='hubertsiuzdak/snac_24khz', device='cpu', context_frames='2', verbose='False'), 630, 900)
    block('wav_sink', 'blocks_wavfile_sink', dict(file='wav_path', nchan='1', samp_rate='24000', format='FORMAT_WAV',
        bits_per_sample1='FORMAT_PCM_16', append='False'), 1000, 900)
    block('spectrum', 'qtgui_freq_sink_x', dict(type='complex', name="'Received IQ'", fftsize='2048',
        freqhalf='True', fc='0', bw='sample_rate', nconnections='1', gui_hint='0,0,1,1'), 16, 1140)
    block('rx_errors', 'snippet', dict(section='main_after_init', priority='0', code=(
        'self.resize(1100, 700)\n'
        'def check_receiver():\n'
        '    error = self.acquisition.error or self.tokens.error or self.snac_decoder.error\n'
        "    ready = self.tokens.eos_sent and self.wav_sink.nitems_read(0) == self.capture['audio_samples']\n"
        '    if error is not None or ready:\n'
        '        self.stop()\n'
        '        self.wait()\n'
        '        result = rx_support.finish_receiver(self)\n'
        "        self.setWindowTitle('Receive complete: ' + self.wav_path if result['complete'] else 'Receive failed: ' + str(error))\n"
        '        print(result, flush=True)\n'
        '        self._rx_timer.stop()\n'
        'self._rx_timer = Qt.QTimer(self)\n'
        'self._rx_timer.timeout.connect(check_receiver)\n'
        'self._rx_timer.start(100)')), 800, 1140)
    chain = ['iq_source', 'demod', 'drain_mux', 'equalizer', 'acquisition', 'whitening', 'deinterleave',
             'to_float', 'scale', 'offset', 'fec_decode', 'vectors', 'tokens']
    for a, b in zip(chain, chain[1:]):
        link(a, b)
    link('drain', 'drain_mux', 1)
    link('iq_source', 'spectrum')
    graph['connections'].append(['tokens', 'codes', 'snac_decoder', 'codes'])
    link('snac_decoder', 'wav_sink')
    (ROOT/'receive_snac_4cpfsk.grc').write_text(yaml.safe_dump(graph, sort_keys=False, width=120), encoding='utf-8')


if __name__ == '__main__':
    build()
