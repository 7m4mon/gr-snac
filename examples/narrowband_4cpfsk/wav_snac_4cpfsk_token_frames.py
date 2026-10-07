"""Message-only SNAC token packer, embedded in the WAV transmitter GRC.

No custom stream scheduler or FEC: emit 104-bit PDUs to standard PDU to Tagged
Stream. frame_packer is supplied by the GRC's embedded radio_frame module.
"""
import json
import logging
import threading
from pathlib import Path

import numpy as np
import pmt
from gnuradio import gr
from gnuradio.snac.messages import unpack
from gr_snac_core.frames import FRAME_MODE


class blk(gr.basic_block):
    """SNAC 1/2/4 tokens -> 84 payload bits -> 104 information bits."""

    def __init__(self, total_samples=2048, start_sequence=0, flags=0,
                 frame_packer=None, status_path=''):
        gr.basic_block.__init__(self, name='SNAC Tokens to Radio PDU', in_sig=None, out_sig=None)
        if type(total_samples) is not int or total_samples < 1:
            raise ValueError('total_samples must be a positive integer')
        if not 0 <= start_sequence < 64 or not 0 <= flags < 4:
            raise ValueError('Invalid sequence or flags')
        self.total_samples = total_samples
        self.expected_frames = (total_samples+2047)//2048
        self.start_sequence, self.flags = start_sequence, flags
        self.frame_packer = frame_packer
        self.status_path = status_path
        self.frames = self.audio_samples = 0
        self.eos_received = False
        self.error = None
        self._lock = threading.Lock()
        self.message_port_register_in(pmt.intern('codes'))
        self.message_port_register_out(pmt.intern('pdus'))
        self.set_msg_handler(pmt.intern('codes'), self._handle)

    def _write_status(self):
        if self.status_path:
            record = dict(source='SNAC encoder messages', payload_bit_order='level0, level1, level2; each token MSB first',
                frames=self.frames, expected_frames=self.expected_frames, audio_samples=self.audio_samples,
                expected_audio_samples=self.total_samples, eos_received=self.eos_received,
                error=str(self.error) if self.error else None,
                note='Encoder/PDU status only; check IQ length to confirm complete waveform capture')
            Path(self.status_path).write_text(json.dumps(record, indent=2)+'\n')

    def _handle(self, message):
        with self._lock:
            if self.error is not None:
                return
            try:
                if self.eos_received:
                    raise ValueError('SNAC message after EOS')
                meta, levels = unpack(message, 'hubertsiuzdak/snac_24khz')
                if meta.get('stream_mode') != FRAME_MODE or meta['chunk_index'] != self.frames:
                    raise ValueError('Missing, reordered or unsupported SNAC frame')
                if levels is None:
                    if self.frames != self.expected_frames or self.audio_samples != self.total_samples:
                        raise ValueError('Premature SNAC EOS')
                    self.eos_received = True
                    self._write_status()
                    return
                expected_samples = min(2048, self.total_samples-self.audio_samples)
                if self.frames >= self.expected_frames or meta['audio_samples'] != expected_samples:
                    raise ValueError('SNAC frame sample count does not match repeated WAV length')
                if tuple(map(len, levels)) != (1, 2, 4):
                    raise ValueError('Expected 1/2/4 SNAC tokens')
                tokens = np.concatenate(levels).astype(np.uint16)
                payload = ((tokens[:, None] >> np.arange(11, -1, -1)) & 1).astype(np.uint8).reshape(-1)
                if self.frame_packer is None:
                    raise ValueError('frame_packer must be supplied by embedded radio_frame module')
                bits = self.frame_packer(payload, (self.start_sequence+self.frames)%64, self.flags)
                self.message_port_pub(pmt.intern('pdus'), pmt.cons(pmt.PMT_NIL,
                    pmt.init_u8vector(104, bits.tolist())))
                self.frames += 1
                self.audio_samples += meta['audio_samples']
            except Exception as exc:
                self.error = exc
                logging.getLogger(__name__).exception('SNAC token framing failed')
                self._write_status()

    def stop(self):
        with self._lock:
            self._write_status()
        return True
