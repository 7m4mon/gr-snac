import logging
import numpy as np
import pmt
from gnuradio import gr
from gr_snac_core.codec import Codec, MODEL, RATE, chunk_size, statistics
from .messages import pack

LOG = logging.getLogger(__name__)


class snac_encoder(gr.sync_block):
    def __init__(self, model=MODEL, device="auto", chunk_ms=1000, verbose=False,
                 total_samples=0):
        gr.sync_block.__init__(self, name="SNAC Encoder 24k", in_sig=[np.float32], out_sig=None)
        self.size = chunk_size(chunk_ms)
        if type(total_samples) is not int or total_samples < 0:
            raise ValueError("total_samples must be a nonnegative integer")
        self.total_samples = total_samples
        self.codec = Codec(model, device)
        self.verbose = verbose
        self.buffer = np.empty(self.size, dtype=np.float32)
        self.fill = self.received = self.index = 0
        self.ended = False
        self.port = pmt.intern("codes")
        self.message_port_register_out(self.port)

    def _metadata(self):
        return dict(codec="snac", model=self.codec.model_id, sample_rate=RATE,
                    num_levels=3, chunk_index=self.index)

    def _emit(self):
        audio = self.buffer[:self.fill]
        if self.verbose and np.any(np.abs(audio) > 1):
            LOG.warning("SNAC ENC chunk=%d clipping input", self.index)
        levels, elapsed = self.codec.encode(audio)
        meta = self._metadata()
        meta.update(audio_samples=self.fill, chunk_duration_ms=self.fill / RATE * 1000)
        self.message_port_pub(self.port, pack(meta, levels))
        if self.verbose:
            LOG.warning("SNAC ENC chunk=%d audio_samples=%d duration=%.3f ms %s inference=%.6fs device=%s",
                        self.index, self.fill, meta["chunk_duration_ms"],
                        statistics(levels, self.fill), elapsed, self.codec.device)
        self.index += 1
        self.fill = 0

    def work(self, input_items, output_items):
        if self.ended:
            return -1
        data = input_items[0]
        count = len(data)
        if self.total_samples:
            count = min(count, self.total_samples - self.received)
        offset = 0
        while offset < count:
            n = min(count - offset, self.size - self.fill)
            self.buffer[self.fill:self.fill + n] = data[offset:offset + n]
            self.fill += n
            offset += n
            if self.fill == self.size:
                self._emit()
        self.received += count
        if self.total_samples and self.received == self.total_samples:
            if self.fill:
                self._emit()
            meta = self._metadata()
            meta["eos"] = True
            self.message_port_pub(self.port, pack(meta))
            self.ended = True
        return count
