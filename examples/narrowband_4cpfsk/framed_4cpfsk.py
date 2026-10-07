#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Gaussian 4CPFSK: framed single carrier
# Author: 7M4MON
# Description: Standard GNU Radio CPM/FEC; edit variables and restart.
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
import framed_4cpfsk_radio_frame as radio_frame  # embedded python module
import numpy as np


def snipfcn_capture_metadata(self):
    radio_frame.write_capture_metadata(self.iq_path, self.frame_count, self.seed, self.start_sequence, self.frame_flags, self.symbol_rate, self.samples_per_symbol, self.modulation_index_h, self.gaussian_bt, self.pulse_length, self.channel_spacing, 1)

def snipfcn_window_size(self):
    self.resize(1200, 900)


def snippets_main_after_init(tb):
    snipfcn_capture_metadata(tb)
    snipfcn_window_size(tb)

from gnuradio import qtgui

class framed_4cpfsk(gr.top_block, Qt.QWidget):

    def __init__(self, duration_seconds=60):
        gr.top_block.__init__(self, "Gaussian 4CPFSK: framed single carrier", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Gaussian 4CPFSK: framed single carrier")
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

        self.settings = Qt.QSettings("GNU Radio", "framed_4cpfsk")

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
        self.duration_seconds = duration_seconds

        ##################################################
        # Variables
        ##################################################
        self.symbol_rate = symbol_rate = 1312.5
        self.samples_per_symbol = samples_per_symbol = 32
        self.start_sequence = start_sequence = 0
        self.seed = seed = 12345
        self.sample_rate = sample_rate = symbol_rate * samples_per_symbol
        self.pulse_length = pulse_length = 4
        self.modulation_index_h = modulation_index_h = 0.25
        self.iq_path = iq_path = 'framed_4cpfsk.cf32'
        self.gaussian_bt = gaussian_bt = 0.30
        self.frame_flags = frame_flags = 0
        self.frame_count = frame_count = max(1, int(np.ceil(duration_seconds * symbol_rate / 112)))
        self.encoder_definition_0 = encoder_definition_0 = fec.cc_encoder_make(104,7, 2, [109, 79], 0, fec.CC_TAILBITING, False)
        self.dibit_path = dibit_path = 'framed_4cpfsk.dibits'
        self.channel_spacing = channel_spacing = 2500

        ##################################################
        # Blocks
        ##################################################
        self.whitening_0 = digital.additive_scrambler_bb(0x21, 0x1ff, 8, count=208, bits_per_byte=1, reset_tag_key='')
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
        self.throttle = blocks.throttle(gr.sizeof_gr_complex*1, sample_rate,True)
        self.sync_0 = blocks.vector_source_b(radio_frame.SYNC_DIBITS, True, 1, [])
        self.source_0 = blocks.vector_source_b(radio_frame.random_information(frame_count, seed + 0, start_sequence, frame_flags).tolist(), False, 1, [])
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


        ##################################################
        # Connections
        ##################################################
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
        self.connect((self.whitening_0, 0), (self.pairs_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "framed_4cpfsk")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_duration_seconds(self):
        return self.duration_seconds

    def set_duration_seconds(self, duration_seconds):
        self.duration_seconds = duration_seconds
        self.set_frame_count(max(1, int(np.ceil(self.duration_seconds * self.symbol_rate / 112))))

    def get_symbol_rate(self):
        return self.symbol_rate

    def set_symbol_rate(self, symbol_rate):
        self.symbol_rate = symbol_rate
        self.set_sample_rate(self.symbol_rate * self.samples_per_symbol)
        self.set_frame_count(max(1, int(np.ceil(self.duration_seconds * self.symbol_rate / 112))))

    def get_samples_per_symbol(self):
        return self.samples_per_symbol

    def set_samples_per_symbol(self, samples_per_symbol):
        self.samples_per_symbol = samples_per_symbol
        self.set_sample_rate(self.symbol_rate * self.samples_per_symbol)
        self.capture_length.set_length((self.frame_count * 112 + self.pulse_length) * self.samples_per_symbol)

    def get_start_sequence(self):
        return self.start_sequence

    def set_start_sequence(self, start_sequence):
        self.start_sequence = start_sequence
        self.source_0.set_data(radio_frame.random_information(self.frame_count, self.seed + 0, self.start_sequence, self.frame_flags).tolist(), [])

    def get_seed(self):
        return self.seed

    def set_seed(self, seed):
        self.seed = seed
        self.source_0.set_data(radio_frame.random_information(self.frame_count, self.seed + 0, self.start_sequence, self.frame_flags).tolist(), [])

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
        self.iq_file.open(self.iq_path)

    def get_gaussian_bt(self):
        return self.gaussian_bt

    def set_gaussian_bt(self, gaussian_bt):
        self.gaussian_bt = gaussian_bt

    def get_frame_flags(self):
        return self.frame_flags

    def set_frame_flags(self, frame_flags):
        self.frame_flags = frame_flags
        self.source_0.set_data(radio_frame.random_information(self.frame_count, self.seed + 0, self.start_sequence, self.frame_flags).tolist(), [])

    def get_frame_count(self):
        return self.frame_count

    def set_frame_count(self, frame_count):
        self.frame_count = frame_count
        self.source_0.set_data(radio_frame.random_information(self.frame_count, self.seed + 0, self.start_sequence, self.frame_flags).tolist(), [])
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
    description = 'Standard GNU Radio CPM/FEC; edit variables and restart.'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--duration-seconds", dest="duration_seconds", type=eng_float, default=eng_notation.num_to_str(float(60)),
        help="Set Capture duration (rounded up to whole frames) [default=%(default)r]")
    return parser


def main(top_block_cls=framed_4cpfsk, options=None):
    if options is None:
        options = argument_parser().parse_args()

    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls(duration_seconds=options.duration_seconds)
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
