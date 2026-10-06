import logging
import numpy as np
import pmt
from gnuradio import gr
from gr_snac_core.codec import Codec, MODEL, RATE
from gr_snac_core.chunks import ContextChunks
from gr_snac_core.frames import FRAME_SAMPLES, FRAME_COUNTS, FRAME_MODE, context_frames as check_context
from .messages import pack

LOG = logging.getLogger(__name__)


class snac_encoder(gr.sync_block):
    def __init__(self, model=MODEL, device="auto", verbose=False,
                 total_samples=0, context_frames=2):
        gr.sync_block.__init__(self, name="SNAC Encoder 24k", in_sig=[np.float32], out_sig=None)
        self.context = check_context(context_frames)
        if type(total_samples) is not int or total_samples < 0:
            raise ValueError("total_samples must be a nonnegative integer")
        self.total_samples = total_samples
        self.codec = Codec(model, device)
        if self.codec.alignment != FRAME_SAMPLES:
            raise ValueError("streaming requires the SNAC 24k 2048-sample grid")
        self.windows = ContextChunks(FRAME_SAMPLES, self.context*FRAME_SAMPLES, FRAME_SAMPLES)
        self.verbose = verbose
        self.received = self.index = 0
        self.ended = False
        self.port = pmt.intern("codes")
        self.message_port_register_out(self.port)

    def _metadata(self):
        return dict(codec="snac", model=self.codec.model_id, sample_rate=RATE,
                    num_levels=3, chunk_index=self.index, stream_mode=FRAME_MODE)

    def _emit(self, audio, crop, samples):
        if self.verbose and np.any(np.abs(audio) > 1):
            LOG.warning("SNAC ENC frame=%d clipping input", self.index)
        levels, elapsed = self.codec.encode(audio)
        offset = crop // FRAME_SAMPLES
        # Only the new central frame crosses the message/radio boundary.
        levels = [level[offset*w:(offset+1)*w].copy() for level, w in zip(levels, FRAME_COUNTS)]
        if tuple(map(len, levels)) != FRAME_COUNTS:
            raise ValueError("encoder returned an incompatible frame hierarchy")
        meta = self._metadata()
        meta.update(audio_samples=samples, chunk_duration_ms=samples/RATE*1000,
                    encoded_samples=FRAME_SAMPLES, crop_start=0)
        self.message_port_pub(self.port, pack(meta, levels))
        if self.verbose:
            LOG.warning("SNAC ENC frame=%d samples=%d tokens=[1,2,4] bits=84 context=%d inference=%.6fs",
                        self.index, samples, self.context, elapsed)
        self.index += 1

    def work(self, input_items, output_items):
        if self.ended:
            return -1
        data = input_items[0]
        count = len(data)
        if self.total_samples:
            count = min(count, self.total_samples-self.received)
        final = bool(self.total_samples and self.received+count == self.total_samples)
        for audio, crop, samples in self.windows.feed(data[:count], final=final):
            self._emit(audio, crop, samples)
        self.received += count
        if final:
            meta = self._metadata()
            meta["eos"] = True
            self.message_port_pub(self.port, pack(meta))
            self.ended = True
        return count
