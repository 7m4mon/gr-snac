#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: WAV -> SNAC -> framed 4CPFSK
# Author: 7M4MON
# Description: Finite repeated WAV through the SNAC encoder and stock radio PHY; IQ output only.
# GNU Radio version: 3.10.1.1

from packaging.version import Version as StrictVersion

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print("Warning: failed to XInitThreads()")

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio.filter import firdes
import sip
from gnuradio import blocks
from gnuradio import digital
from gnuradio import fec
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import gr, digital, analog
from gnuradio import gr, pdu
from gnuradio import snac
import numpy as np
import wav_snac_4cpfsk_radio_frame as radio_frame  # embedded python module
import wav_snac_4cpfsk_token_frames as token_frames  # embedded python block


def snipfcn_capture_metadata(self):
    radio_frame.write_capture_metadata(self.iq_path, self.frame_count, 0, self.start_sequence, self.frame_flags, self.symbol_rate, self.samples_per_symbol, self.modulation_index_h, self.gaussian_bt, self.pulse_length, self.channel_spacing, 1)
    from pathlib import Path
    import json
    meta_path = Path(self.iq_path + '.frames.json')
    record = json.loads(meta_path.read_text())
    record.pop('seed', None)
    record.pop('carrier_seeds', None)
    record.update(source='WAV -> SNAC encoder', audio=self.wav_info, codec_model=self.snac_encoder.codec.model_id, context_frames=self.snac_encoder.context)
    meta_path.write_text(json.dumps(record, indent=2) + '\n')

def snipfcn_frame_errors(self):
    def check_frame_error():
        if self.token_frames.error is not None:
            self.setWindowTitle('SNAC framing error: ' + str(self.token_frames.error))
            self.stop()
            self._frame_error_timer.stop()
    self._frame_error_timer = Qt.QTimer(self)
    self._frame_error_timer.timeout.connect(check_frame_error)
    self._frame_error_timer.start(100)

def snipfcn_window_size(self):
    self.resize(1200, 900)


def snippets_main_after_init(tb):
    snipfcn_frame_errors(tb)
    snipfcn_capture_metadata(tb)
    snipfcn_window_size(tb)

from gnuradio import qtgui

class wav_snac_4cpfsk(gr.top_block, Qt.QWidget):

    def __init__(self, input_path='../VOICEACTRESS100_001_001.wav', repeat_count=5):
        gr.top_block.__init__(self, "WAV -> SNAC -> framed 4CPFSK", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("WAV -> SNAC -> framed 4CPFSK")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except:
            pass
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "wav_snac_4cpfsk")

        try:
            if StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
                self.restoreGeometry(self.settings.value("geometry").toByteArray())
            else:
                self.restoreGeometry(self.settings.value("geometry"))
        except:
            pass

        ##################################################
        # Parameters
        ##################################################
        self.input_path = input_path
        self.repeat_count = repeat_count

        ##################################################
        # Variables
        ##################################################
        self.wav_info = wav_info = radio_frame.wav_transmission_info(input_path, repeat_count)
        self.symbol_rate = symbol_rate = 1312.5
        self.samples_per_symbol = samples_per_symbol = 32
        self.total_samples = total_samples = wav_info['total_audio_samples']
        self.start_sequence = start_sequence = 0
        self.sample_rate = sample_rate = symbol_rate * samples_per_symbol
        self.pulse_length = pulse_length = 4
        self.modulation_index_h = modulation_index_h = 0.25
        self.iq_path = iq_path = 'wav_snac_4cpfsk.cf32'
        self.gaussian_bt = gaussian_bt = 0.30
        self.frame_flags = frame_flags = 0
        self.frame_count = frame_count = wav_info['frame_count']
        self.encoder_definition_0 = encoder_definition_0 = fec.cc_encoder_make(104,7, 2, [109, 79], 0, fec.CC_TAILBITING, False)
        self.dibit_path = dibit_path = 'wav_snac_4cpfsk.dibits'
        self.channel_spacing = channel_spacing = 2500

        ##################################################
        # Blocks
        ##################################################
        self.whitening_0 = digital.additive_scrambler_bb(0x21, 0x1ff, 8, count=208, bits_per_byte=1, reset_tag_key='')
        self.wav_source = blocks.wavfile_source(input_path, True)
        self.waterfall = qtgui.waterfall_sink_c(
            8192, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            sample_rate, #bw
            'Gaussian 4CPFSK', #name
            1, #number of inputs
            None # parent
        )
        self.waterfall.set_update_time(0.10)
        self.waterfall.enable_grid(False)
        self.waterfall.enable_axis_labels(True)



        labels = ['', '', '', '', '',
                  '', '', '', '', '']
        colors = [0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.waterfall.set_line_label(i, "Data {0}".format(i))
            else:
                self.waterfall.set_line_label(i, labels[i])
            self.waterfall.set_color_map(i, colors[i])
            self.waterfall.set_line_alpha(i, alphas[i])

        self.waterfall.set_intensity_range(-140, 10)

        self._waterfall_win = sip.wrapinstance(self.waterfall.qwidget(), Qt.QWidget)

        self.top_grid_layout.addWidget(self._waterfall_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 1):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.token_frames = token_frames.blk(total_samples=total_samples, start_sequence=start_sequence, flags=frame_flags, frame_packer=radio_frame.pack_information, status_path=iq_path + '.audio.json')
        self.throttle = blocks.throttle(gr.sizeof_gr_complex*1, sample_rate,True)
        self.sync_0 = blocks.vector_source_b(radio_frame.SYNC_DIBITS, True, 1, [])
        self.source_0 = pdu.pdu_to_tagged_stream(gr.types.byte_t, 'packet_len')
        self.snac_encoder = snac.snac_encoder(model='hubertsiuzdak/snac_24khz', device='cpu', verbose=False, total_samples=total_samples, context_frames=2)
        self.pairs_0 = blocks.repack_bits_bb(1, 2, '', False, gr.GR_MSB_FIRST)
        self.iq_file = blocks.file_sink(gr.sizeof_gr_complex*1, iq_path, False)
        self.iq_file.set_unbuffered(False)
        self.interleaver_0 = blocks.matrix_interleaver(
            itemsize=gr.sizeof_char * 1, rows=16, cols=13, deint=False
        )
        self.gray_0 = digital.map_bb([253, 255, 3, 1])
        self.frequency = qtgui.freq_sink_c(
            8192, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            sample_rate, #bw
            'Spectrum (use mouse zoom for +/-5 kHz)', #name
            1,
            None # parent
        )
        self.frequency.set_update_time(0.10)
        self.frequency.set_y_axis(-140, 10)
        self.frequency.set_y_label('Relative Gain', 'dB')
        self.frequency.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.frequency.enable_autoscale(False)
        self.frequency.enable_grid(True)
        self.frequency.set_fft_average(0.05)
        self.frequency.enable_axis_labels(True)
        self.frequency.enable_control_panel(False)
        self.frequency.set_fft_window_normalized(True)



        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.frequency.set_line_label(i, "Data {0}".format(i))
            else:
                self.frequency.set_line_label(i, labels[i])
            self.frequency.set_line_width(i, widths[i])
            self.frequency.set_line_color(i, colors[i])
            self.frequency.set_line_alpha(i, alphas[i])

        self._frequency_win = sip.wrapinstance(self.frequency.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._frequency_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 1):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.frame_mux_0 = blocks.stream_mux(gr.sizeof_char*1, [8, 104])
        self.frame_limit_0 = blocks.head(gr.sizeof_char*1, frame_count * 112)
        self.fec_0 = fec.extended_encoder(encoder_obj_list=encoder_definition_0, threading= None, puncpat='11')
        self.drain_zero_0 = blocks.vector_source_b([0], True, 1, [])
        self.drain_mux_0 = blocks.stream_mux(gr.sizeof_char*1, [frame_count * 112, pulse_length])
        self.drain_limit_0 = blocks.head(gr.sizeof_char*1, frame_count * 112 + pulse_length)
        self.dibit_file_0 = blocks.file_sink(gr.sizeof_char*1, dibit_path, False)
        self.dibit_file_0.set_unbuffered(False)
        self.cpm_0 = digital.cpmmod_bc(analog.cpm.GAUSSIAN, modulation_index_h, samples_per_symbol, pulse_length, gaussian_bt)
        self.capture_length = blocks.head(gr.sizeof_gr_complex*1, (frame_count * 112 + pulse_length) * samples_per_symbol)
        self.audio_length = blocks.head(gr.sizeof_float*1, total_samples)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.snac_encoder, 'codes'), (self.token_frames, 'codes'))
        self.msg_connect((self.token_frames, 'pdus'), (self.source_0, 'pdus'))
        self.connect((self.audio_length, 0), (self.snac_encoder, 0))
        self.connect((self.capture_length, 0), (self.throttle, 0))
        self.connect((self.cpm_0, 0), (self.capture_length, 0))
        self.connect((self.drain_limit_0, 0), (self.cpm_0, 0))
        self.connect((self.drain_mux_0, 0), (self.drain_limit_0, 0))
        self.connect((self.drain_zero_0, 0), (self.drain_mux_0, 1))
        self.connect((self.fec_0, 0), (self.interleaver_0, 0))
        self.connect((self.frame_limit_0, 0), (self.dibit_file_0, 0))
        self.connect((self.frame_limit_0, 0), (self.gray_0, 0))
        self.connect((self.frame_mux_0, 0), (self.frame_limit_0, 0))
        self.connect((self.gray_0, 0), (self.drain_mux_0, 0))
        self.connect((self.interleaver_0, 0), (self.whitening_0, 0))
        self.connect((self.pairs_0, 0), (self.frame_mux_0, 1))
        self.connect((self.source_0, 0), (self.fec_0, 0))
        self.connect((self.sync_0, 0), (self.frame_mux_0, 0))
        self.connect((self.throttle, 0), (self.frequency, 0))
        self.connect((self.throttle, 0), (self.iq_file, 0))
        self.connect((self.throttle, 0), (self.waterfall, 0))
        self.connect((self.wav_source, 0), (self.audio_length, 0))
        self.connect((self.whitening_0, 0), (self.pairs_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "wav_snac_4cpfsk")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_input_path(self):
        return self.input_path

    def set_input_path(self, input_path):
        self.input_path = input_path
        self.set_wav_info(radio_frame.wav_transmission_info(self.input_path, self.repeat_count))

    def get_repeat_count(self):
        return self.repeat_count

    def set_repeat_count(self, repeat_count):
        self.repeat_count = repeat_count
        self.set_wav_info(radio_frame.wav_transmission_info(self.input_path, self.repeat_count))

    def get_wav_info(self):
        return self.wav_info

    def set_wav_info(self, wav_info):
        self.wav_info = wav_info
        self.set_frame_count(self.wav_info['frame_count'])
        self.set_total_samples(self.wav_info['total_audio_samples'])

    def get_symbol_rate(self):
        return self.symbol_rate

    def set_symbol_rate(self, symbol_rate):
        self.symbol_rate = symbol_rate
        self.set_sample_rate(self.symbol_rate * self.samples_per_symbol)

    def get_samples_per_symbol(self):
        return self.samples_per_symbol

    def set_samples_per_symbol(self, samples_per_symbol):
        self.samples_per_symbol = samples_per_symbol
        self.set_sample_rate(self.symbol_rate * self.samples_per_symbol)
        self.capture_length.set_length((self.frame_count * 112 + self.pulse_length) * self.samples_per_symbol)

    def get_total_samples(self):
        return self.total_samples

    def set_total_samples(self, total_samples):
        self.total_samples = total_samples
        self.audio_length.set_length(self.total_samples)
        self.token_frames.total_samples = self.total_samples

    def get_start_sequence(self):
        return self.start_sequence

    def set_start_sequence(self, start_sequence):
        self.start_sequence = start_sequence
        self.token_frames.start_sequence = self.start_sequence

    def get_sample_rate(self):
        return self.sample_rate

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate
        self.throttle.set_sample_rate(self.sample_rate)
        self.frequency.set_frequency_range(0, self.sample_rate)
        self.waterfall.set_frequency_range(0, self.sample_rate)

    def get_pulse_length(self):
        return self.pulse_length

    def set_pulse_length(self, pulse_length):
        self.pulse_length = pulse_length
        self.drain_limit_0.set_length(self.frame_count * 112 + self.pulse_length)
        self.capture_length.set_length((self.frame_count * 112 + self.pulse_length) * self.samples_per_symbol)

    def get_modulation_index_h(self):
        return self.modulation_index_h

    def set_modulation_index_h(self, modulation_index_h):
        self.modulation_index_h = modulation_index_h

    def get_iq_path(self):
        return self.iq_path

    def set_iq_path(self, iq_path):
        self.iq_path = iq_path
        self.token_frames.status_path = self.iq_path + '.audio.json'
        self.iq_file.open(self.iq_path)

    def get_gaussian_bt(self):
        return self.gaussian_bt

    def set_gaussian_bt(self, gaussian_bt):
        self.gaussian_bt = gaussian_bt

    def get_frame_flags(self):
        return self.frame_flags

    def set_frame_flags(self, frame_flags):
        self.frame_flags = frame_flags
        self.token_frames.flags = self.frame_flags

    def get_frame_count(self):
        return self.frame_count

    def set_frame_count(self, frame_count):
        self.frame_count = frame_count
        self.frame_limit_0.set_length(self.frame_count * 112)
        self.drain_limit_0.set_length(self.frame_count * 112 + self.pulse_length)
        self.capture_length.set_length((self.frame_count * 112 + self.pulse_length) * self.samples_per_symbol)

    def get_encoder_definition_0(self):
        return self.encoder_definition_0

    def set_encoder_definition_0(self, encoder_definition_0):
        self.encoder_definition_0 = encoder_definition_0

    def get_dibit_path(self):
        return self.dibit_path

    def set_dibit_path(self, dibit_path):
        self.dibit_path = dibit_path
        self.dibit_file_0.open(self.dibit_path)

    def get_channel_spacing(self):
        return self.channel_spacing

    def set_channel_spacing(self, channel_spacing):
        self.channel_spacing = channel_spacing



def argument_parser():
    description = 'Finite repeated WAV through the SNAC encoder and stock radio PHY; IQ output only.'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--input-path", dest="input_path", type=str, default='../VOICEACTRESS100_001_001.wav',
        help="Set WAV input (24 kHz mono PCM) [default=%(default)r]")
    parser.add_argument(
        "--repeat-count", dest="repeat_count", type=intx, default=5,
        help="Set Total WAV plays [default=%(default)r]")
    return parser


def main(top_block_cls=wav_snac_4cpfsk, options=None):
    if options is None:
        options = argument_parser().parse_args()

    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls(input_path=options.input_path, repeat_count=options.repeat_count)
    snippets_main_after_init(tb)
    tb.start()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
