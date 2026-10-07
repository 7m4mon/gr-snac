"""CRC/sequence checking and inverse token packing; embedded in receiver GRC."""
import json
from pathlib import Path
import numpy as np
import pmt
from gnuradio import gr
from gnuradio.snac.messages import pack
from gr_snac_core.frames import FRAME_MODE


class blk(gr.sync_block):
    def __init__(self, total_samples=2048, start_sequence=0, crc_fn=None, status_path=''):
        gr.sync_block.__init__(self, name='CRC / Sequence -> SNAC Tokens',
                               in_sig=[(np.uint8, 104)], out_sig=None)
        self.total_samples = int(total_samples)
        self.expected_frames = (self.total_samples+2047)//2048
        self.start_sequence, self.crc_fn, self.status_path = start_sequence, crc_fn, status_path
        self.frames = self.audio_samples = self.crc_failures = 0
        self.error = None
        self.eos_sent = False
        self.message_port_register_out(pmt.intern('codes'))

    def _meta(self):
        return dict(codec='snac', model='hubertsiuzdak/snac_24khz', sample_rate=24000,
                    num_levels=3, chunk_index=self.frames, stream_mode=FRAME_MODE)

    def _status(self):
        if self.status_path:
            Path(self.status_path).write_text(json.dumps(dict(
                accepted_frames=self.frames, expected_frames=self.expected_frames,
                audio_samples=self.audio_samples, crc_failures=self.crc_failures,
                eos_sent=self.eos_sent, error=str(self.error) if self.error else None,
                note='Token-stage status; waveform completion requires decoder and WAV-length checks'), indent=2)+'\n')

    def work(self, input_items, output_items):
        if self.error is not None or self.eos_sent:
            return -1
        consumed = 0
        try:
            for bits in input_items[0]:
                consumed += 1
                if self.crc_fn(bits) != 0:
                    self.crc_failures += 1
                    raise ValueError(f'CRC failure at frame {self.frames}; audio aborted (no concealment)')
                sequence = int(np.dot(bits[84:90], 2**np.arange(5, -1, -1)))
                if sequence != (self.start_sequence+self.frames)%64:
                    raise ValueError(f'Sequence discontinuity at frame {self.frames}')
                values = bits[:84].reshape(7, 12).dot(2**np.arange(11, -1, -1)).astype(np.uint16)
                n = min(2048, self.total_samples-self.audio_samples)
                meta = self._meta()
                meta.update(audio_samples=n, encoded_samples=2048, crop_start=0,
                            chunk_duration_ms=n/24000*1000)
                self.message_port_pub(pmt.intern('codes'), pack(meta, [values[:1], values[1:3], values[3:]]))
                self.frames += 1
                self.audio_samples += n
                if self.frames == self.expected_frames:
                    meta = self._meta()
                    meta['eos'] = True
                    self.message_port_pub(pmt.intern('codes'), pack(meta))
                    self.eos_sent = True
                    self._status()
                    break
        except Exception as exc:
            self.error = exc
            self._status()
        return consumed

    def stop(self):
        self._status()
        return True
