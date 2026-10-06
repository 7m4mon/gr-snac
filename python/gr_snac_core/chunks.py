"""Bounded look-ahead windows with sample-exact output intervals."""
import numpy as np


class ContextChunks:
    def __init__(self, size, context, alignment):
        self.size, self.context, self.alignment = size, context, alignment
        self.buffer = np.empty(0, np.float32)
        self.origin = self.position = self.received = 0

    def feed(self, audio, final=False):
        # Bound temporary storage even if the scheduler supplies a large buffer.
        for offset in range(0, len(audio), self.size):
            part = audio[offset:offset + self.size]
            self.buffer = np.concatenate((self.buffer, part))
            self.received += len(part)
            yield from self._ready(False)
        if final:
            yield from self._ready(True)

    def _ready(self, final):
        while self.position < self.received:
            end = self.position + self.size
            if not final and end + self.context > self.received:
                break
            end = min(end, self.received)
            right = min(end + self.context, self.received)
            left = max(0, (self.position - self.context) // self.alignment * self.alignment)
            window = self.buffer[left-self.origin:right-self.origin].copy()
            crop = self.position - left
            count = end - self.position
            self.position = end
            keep = max(0, (end - self.context) // self.alignment * self.alignment)
            self.buffer = self.buffer[keep-self.origin:].copy()
            self.origin = keep
            yield window, crop, count
