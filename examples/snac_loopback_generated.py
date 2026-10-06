#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: SNAC 24k WAV Loopback
# GNU Radio version: 3.10.1.1

from gnuradio import blocks
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import snac
import wave
from pathlib import Path
from gr_snac_core.demo import demo_wav_path




class snac_loopback_generated(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "SNAC 24k WAV Loopback", catch_exceptions=True)

        ##################################################
        # Variables
        ##################################################
        self.input_path = input_path = demo_wav_path()
        self.sample_count = sample_count = wave.open(input_path, 'rb').getnframes()
        self.output_path = output_path = str(Path(input_path).with_name(Path(input_path).stem + '-snac-output.wav'))

        ##################################################
        # Blocks
        ##################################################
        self.source = blocks.wavfile_source(input_path, False)
        self.sink = blocks.wavfile_sink(
            output_path,
            1,
            24000,
            blocks.FORMAT_WAV,
            blocks.FORMAT_PCM_16,
            False
            )
        self.encoder = snac.snac_encoder(model='hubertsiuzdak/snac_24khz', device='cpu', chunk_ms=1000, verbose=True, total_samples=sample_count)
        self.decoder = snac.snac_decoder(model='hubertsiuzdak/snac_24khz', device='cpu', verbose=True)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.encoder, 'codes'), (self.decoder, 'codes'))
        self.connect((self.decoder, 0), (self.sink, 0))
        self.connect((self.source, 0), (self.encoder, 0))


    def get_input_path(self):
        return self.input_path

    def set_input_path(self, input_path):
        self.input_path = input_path
        self.set_output_path(str(Path(self.input_path).with_name(Path(self.input_path).stem + '-snac-output.wav')))
        self.set_sample_count(wave.open(self.input_path, 'rb').getnframes())

    def get_sample_count(self):
        return self.sample_count

    def set_sample_count(self, sample_count):
        self.sample_count = sample_count

    def get_output_path(self):
        return self.output_path

    def set_output_path(self, output_path):
        self.output_path = output_path
        self.sink.open(self.output_path)




def main(top_block_cls=snac_loopback_generated, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()

    tb.wait()


if __name__ == '__main__':
    main()
