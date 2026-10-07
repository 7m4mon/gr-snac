"""Finite capture buffer and protocol-specific sync extraction for the GRC."""
import json
from pathlib import Path
import numpy as np
from gnuradio import gr


class blk(gr.basic_block):
    def __init__(self, sample_count=1024, frame_count=1, acquire_fn=None, status_path='', validation_error=''):
        gr.basic_block.__init__(self, name='Finite Capture Sync / 4-level Decisions',
                                in_sig=[np.float32], out_sig=[np.uint8])
        if validation_error:
            raise ValueError(validation_error)
        self.sample_count, self.frame_count = int(sample_count), int(frame_count)
        if self.sample_count < 1 or self.frame_count < 1:
            raise ValueError('Positive finite capture and frame counts required')
        self.acquire_fn, self.status_path = acquire_fn, status_path
        self.buffer = np.empty(self.sample_count, dtype=np.float32)
        self.received = self.offset = 0
        self.bits = None
        self.error = None
        self.status = {}

    def forecast(self, noutput_items, ninputs):
        return [0 if self.bits is not None or self.error is not None else 1]

    def general_work(self, input_items, output_items):
        if self.error is not None:
            return -1
        if self.bits is None:
            n = min(len(input_items[0]), self.sample_count-self.received)
            self.buffer[self.received:self.received+n] = input_items[0][:n]
            self.received += n
            self.consume(0, n)
            if self.received < self.sample_count:
                return 0
            try:
                self.bits, self.status = self.acquire_fn(self.buffer, self.frame_count)
                self.status.update(error=None, captured_samples=self.received)
            except Exception as exc:
                self.error = exc
                self.status = dict(error=str(exc), captured_samples=self.received)
            self.buffer = None
            if self.status_path:
                Path(self.status_path).write_text(json.dumps(self.status, indent=2)+'\n')
            if self.error is not None:
                return -1
        n = min(len(output_items[0]), len(self.bits)-self.offset)
        if n == 0:
            return -1
        output_items[0][:n] = self.bits[self.offset:self.offset+n]
        self.offset += n
        return n
