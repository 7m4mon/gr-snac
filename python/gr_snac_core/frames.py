"""Fixed-rate SNAC frames with locally retained decoder context."""
import numpy as np
from .codec import validate_levels

FRAME_SAMPLES = 2048
FRAME_COUNTS = (1, 2, 4)
FRAME_MODE = "frames-v1"


def context_frames(value):
    if type(value) is not int or value not in (1, 2):
        raise ValueError("context_frames must be 1 or 2")
    return value


def validate_frame(meta, levels):
    levels = validate_levels(levels)
    n = meta.get("audio_samples")
    if (meta.get("stream_mode") != FRAME_MODE or type(n) is not int
            or not 0 < n <= FRAME_SAMPLES
            or meta.get("encoded_samples", FRAME_SAMPLES) != FRAME_SAMPLES
            or meta.get("crop_start", 0) != 0
            or tuple(map(len, levels)) != FRAME_COUNTS):
        raise ValueError("expected one 2048-sample frame with 1/2/4 tokens")
    return levels


class FrameDecoder:
    def __init__(self, codec, context=2):
        self.codec = codec
        self.context = context_frames(context)
        self.buffer = []
        self.origin = self.position = self.expected = 0
        self.partial = self.ended = False

    def push(self, meta, levels):
        if self.ended or self.partial or meta.get("chunk_index") != self.expected:
            raise ValueError("missing, reordered, or trailing SNAC frame")
        levels = validate_frame(meta, levels)
        self.buffer.append((levels, meta["audio_samples"]))
        self.partial = meta["audio_samples"] < FRAME_SAMPLES
        self.expected += 1
        yield from self._ready(False)

    def finish(self):
        if self.ended:
            raise ValueError("duplicate EOS")
        self.ended = True
        yield from self._ready(True)

    def _ready(self, final):
        while self.position < self.expected:
            if not final and self.position + self.context >= self.expected:
                break
            left = max(0, self.position-self.context)
            right = min(self.expected, self.position+self.context+1)
            window = self.buffer[left-self.origin:right-self.origin]
            levels = [np.concatenate([entry[0][i] for entry in window]) for i in range(3)]
            audio, elapsed = self.codec.decode(levels, (right-left)*FRAME_SAMPLES)
            count = self.buffer[self.position-self.origin][1]
            crop = (self.position-left)*FRAME_SAMPLES
            index = self.position
            self.position += 1
            keep = max(0, self.position-self.context)
            del self.buffer[:keep-self.origin]
            self.origin = keep
            yield audio[crop:crop+count].copy(), elapsed, index
