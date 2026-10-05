from collections import deque
import logging
import threading
import numpy as np
import pmt
from gnuradio import gr
from gr_snac_core.codec import Codec, MODEL, RATE, statistics
from .messages import unpack

LOG = logging.getLogger(__name__)


class snac_decoder(gr.sync_block):
    def __init__(self, model=MODEL, device="auto", verbose=False):
        gr.sync_block.__init__(self, name="SNAC Decoder 24k", in_sig=None, out_sig=[np.float32])
        self.codec = Codec(model, device)
        self.verbose = verbose
        self.fifo = deque()
        self.lock = threading.Lock()
        self.offset = 0
        self.ended = False
        self.error = None
        self.port = pmt.intern("codes")
        self.message_port_register_in(self.port)
        self.set_msg_handler(self.port, self._handle)

    def _handle(self, message):
        try:
            if self.ended:
                raise ValueError("received codes after EOS")
            meta, levels = unpack(message, self.codec.model_id)
            if levels is None:
                with self.lock:
                    self.ended = True
                return
            audio, elapsed = self.codec.decode(levels, meta["audio_samples"])
            with self.lock:
                self.fifo.append(audio)
            if self.verbose:
                LOG.warning("SNAC DEC chunk=%d %s decoded_samples=%d duration=%.3f ms inference=%.6fs device=%s",
                            meta["chunk_index"], statistics(levels, len(audio)), len(audio),
                            len(audio) / RATE * 1000, elapsed, self.codec.device)
        except Exception as exc:
            # Surface failures to callers and terminate; never silently emit invented audio.
            LOG.exception("SNAC decoder failed")
            with self.lock:
                self.error = exc
                self.ended = True

    def work(self, input_items, output_items):
        output = output_items[0]
        written = 0
        with self.lock:
            while self.fifo and written < len(output):
                head = self.fifo[0]
                n = min(len(head) - self.offset, len(output) - written)
                output[written:written + n] = head[self.offset:self.offset + n]
                written += n
                self.offset += n
                if self.offset == len(head):
                    self.fifo.popleft()
                    self.offset = 0
            if written == 0 and self.ended:
                return -1
        return written
