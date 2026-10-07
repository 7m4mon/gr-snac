#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: 4CPFSK IQ -> SNAC -> WAV
# Author: 7M4MON
# Description: Finite file receiver: fixed sample clock, no CFO tracking; metadata supplies audio length.
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
from gnuradio import analog
import math
from gnuradio import blocks
import pmt
from gnuradio import digital
from gnuradio import fec
from gnuradio import filter
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import snac
import numpy as np
import receive_snac_4cpfsk_acquisition as acquisition  # embedded python block
import receive_snac_4cpfsk_radio_frame as radio_frame  # embedded python module
import receive_snac_4cpfsk_rx_support as rx_support  # embedded python module
import receive_snac_4cpfsk_tokens as tokens  # embedded python block


def snipfcn_rx_errors(self):
    self.resize(1100, 700)
    def check_receiver():
        error = self.acquisition.error or self.tokens.error or self.snac_decoder.error
        ready = self.tokens.eos_sent and self.wav_sink.nitems_read(0) == self.capture['audio_samples']
        if error is not None or ready:
            self.stop()
            self.wait()
            result = rx_support.finish_receiver(self)
            self.setWindowTitle('Receive complete: ' + self.wav_path if result['complete'] else 'Receive failed: ' + str(error))
            print(result, flush=True)
            self._rx_timer.stop()
    self._rx_timer = Qt.QTimer(self)
    self._rx_timer.timeout.connect(check_receiver)
    self._rx_timer.start(100)


def snippets_main_after_init(tb):
    snipfcn_rx_errors(tb)

from gnuradio import qtgui

class receive_snac_4cpfsk(gr.top_block, Qt.QWidget):

    def __init__(self, iq_path='wav_snac_4cpfsk.cf32', wav_path='received_snac.wav'):
        gr.top_block.__init__(self, "4CPFSK IQ -> SNAC -> WAV", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("4CPFSK IQ -> SNAC -> WAV")
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

        self.settings = Qt.QSettings("GNU Radio", "receive_snac_4cpfsk")

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
        self.iq_path = iq_path
        self.wav_path = wav_path

        ##################################################
        # Variables
        ##################################################
        self.sample_rate = sample_rate = 42000
        self.decoder = decoder = fec.cc_decoder.make(104, 7, 2, [109, 79], 0, -1, fec.CC_TAILBITING, False)
        self.capture = capture = rx_support.preview_info(iq_path)

        ##################################################
        # Blocks
        ##################################################
        self.whitening = digital.additive_scrambler_bb(0x21, 0x1ff, 8, count=208, bits_per_byte=1, reset_tag_key='')
        self.wav_sink = blocks.wavfile_sink(
            wav_path,
            1,
            24000,
            blocks.FORMAT_WAV,
            blocks.FORMAT_PCM_16,
            False
            )
        self.vectors = blocks.stream_to_vector(gr.sizeof_char*1, 104)
        self.tokens = tokens.blk(total_samples=capture['audio_samples'], start_sequence=capture['start_sequence'], crc_fn=radio_frame.crc12, status_path=wav_path + '.frames.json')
        self.to_float = blocks.uchar_to_float()
        self.spectrum = qtgui.freq_sink_c(
            2048, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            sample_rate, #bw
            'Received IQ', #name
            1,
            None # parent
        )
        self.spectrum.set_update_time(0.10)
        self.spectrum.set_y_axis(-140, 10)
        self.spectrum.set_y_label('Relative Gain', 'dB')
        self.spectrum.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.spectrum.enable_autoscale(False)
        self.spectrum.enable_grid(False)
        self.spectrum.set_fft_average(1.0)
        self.spectrum.enable_axis_labels(True)
        self.spectrum.enable_control_panel(False)
        self.spectrum.set_fft_window_normalized(False)



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
                self.spectrum.set_line_label(i, "Data {0}".format(i))
            else:
                self.spectrum.set_line_label(i, labels[i])
            self.spectrum.set_line_width(i, widths[i])
            self.spectrum.set_line_color(i, colors[i])
            self.spectrum.set_line_alpha(i, alphas[i])

        self._spectrum_win = sip.wrapinstance(self.spectrum.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._spectrum_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 1):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.snac_decoder = snac.snac_decoder(model='hubertsiuzdak/snac_24khz', device='cpu', verbose=False, context_frames=2)
        self.scale = blocks.multiply_const_ff(2)
        self.offset = blocks.add_const_ff(-1)
        self.iq_source = blocks.file_source(gr.sizeof_gr_complex*1, iq_path, False, 0, 0)
        self.iq_source.set_begin_tag(pmt.PMT_NIL)
        self.fec_decode = fec.extended_decoder(decoder_obj_list=decoder, threading= None, ann=None, puncpat='11', integration_period=10000)
        self.equalizer = filter.fir_filter_fff(1, rx_support.equalizer_taps())
        self.equalizer.declare_sample_delay(0)
        self.drain_mux = blocks.stream_mux(gr.sizeof_float*1, [capture['iq_samples'], 320])
        self.drain = blocks.vector_source_f([0.0]*320, False, 1, [])
        self.demod = analog.quadrature_demod_cf(32/(np.pi*0.25))
        self.deinterleave = blocks.matrix_interleaver(
            itemsize=gr.sizeof_char * 1, rows=16, cols=13, deint=True
        )
        self.acquisition = acquisition.blk(sample_count=capture['iq_samples'] + 320, frame_count=capture['frames'], acquire_fn=rx_support.acquire, status_path=wav_path + '.sync.json', validation_error=capture['validation_error'])


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.tokens, 'codes'), (self.snac_decoder, 'codes'))
        self.connect((self.acquisition, 0), (self.whitening, 0))
        self.connect((self.deinterleave, 0), (self.to_float, 0))
        self.connect((self.demod, 0), (self.drain_mux, 0))
        self.connect((self.drain, 0), (self.drain_mux, 1))
        self.connect((self.drain_mux, 0), (self.equalizer, 0))
        self.connect((self.equalizer, 0), (self.acquisition, 0))
        self.connect((self.fec_decode, 0), (self.vectors, 0))
        self.connect((self.iq_source, 0), (self.demod, 0))
        self.connect((self.iq_source, 0), (self.spectrum, 0))
        self.connect((self.offset, 0), (self.fec_decode, 0))
        self.connect((self.scale, 0), (self.offset, 0))
        self.connect((self.snac_decoder, 0), (self.wav_sink, 0))
        self.connect((self.to_float, 0), (self.scale, 0))
        self.connect((self.vectors, 0), (self.tokens, 0))
        self.connect((self.whitening, 0), (self.deinterleave, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "receive_snac_4cpfsk")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_iq_path(self):
        return self.iq_path

    def set_iq_path(self, iq_path):
        self.iq_path = iq_path
        self.set_capture(rx_support.preview_info(self.iq_path))
        self.iq_source.open(self.iq_path, False)

    def get_wav_path(self):
        return self.wav_path

    def set_wav_path(self, wav_path):
        self.wav_path = wav_path
        self.acquisition.status_path = self.wav_path + '.sync.json'
        self.tokens.status_path = self.wav_path + '.frames.json'
        self.wav_sink.open(self.wav_path)

    def get_sample_rate(self):
        return self.sample_rate

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate
        self.spectrum.set_frequency_range(0, self.sample_rate)

    def get_decoder(self):
        return self.decoder

    def set_decoder(self, decoder):
        self.decoder = decoder

    def get_capture(self):
        return self.capture

    def set_capture(self, capture):
        self.capture = capture
        self.acquisition.frame_count = self.capture['frames']
        self.acquisition.sample_count = self.capture['iq_samples'] + 320
        self.tokens.start_sequence = self.capture['start_sequence']
        self.tokens.total_samples = self.capture['audio_samples']



def argument_parser():
    description = 'Finite file receiver: fixed sample clock, no CFO tracking; metadata supplies audio length.'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "--iq-path", dest="iq_path", type=str, default='wav_snac_4cpfsk.cf32',
        help="Set wav_snac_4cpfsk.cf32 [default=%(default)r]")
    parser.add_argument(
        "--wav-path", dest="wav_path", type=str, default='received_snac.wav',
        help="Set received_snac.wav [default=%(default)r]")
    return parser


def main(top_block_cls=receive_snac_4cpfsk, options=None):
    if options is None:
        options = argument_parser().parse_args()

    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls(iq_path=options.iq_path, wav_path=options.wav_path)
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
