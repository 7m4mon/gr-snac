"""gr-snac token containers (v2 continuous frames; legacy v1 crop windows).

V2: MAGIC2, uint32 JSON length, JSON header, continuous 84-bit frame payloads,
zero low padding bits in the last byte only, uint64 total samples + b'END2'.
The frame count follows from total samples; no per-frame metadata is stored.

Not an upstream SNAC standard. Little-endian record header: output samples,
encoded samples, crop start, and three token counts (six uint32 values).
Tokens are packed high bits first, in level order, with zero low padding bits.
A zero record marks clean EOS. The model weights are not embedded.
"""
import json
import struct
from pathlib import Path
import numpy as np
from .codec import MODEL, RATE, validate_levels
from .frames import FRAME_MODE, FRAME_SAMPLES, FRAME_COUNTS, validate_frame

MAGIC = b"SNAC12\x01\n"
RECORD = struct.Struct("<6I")
MAGIC2 = b"SNAC12\x02\n"
FOOTER2 = struct.Struct("<Q4s")


def pack12(levels):
    values = np.concatenate(validate_levels(levels))
    if len(values) % 2:
        values = np.append(values, np.uint16(0))
    a, b = values[::2], values[1::2]
    data = np.column_stack((a >> 4, ((a & 15) << 4) | (b >> 8), b & 255)).astype(np.uint8).tobytes()
    return data[:(sum(map(len, levels)) * 12 + 7) // 8]


def unpack12(data, counts):
    n = sum(counts)
    if len(data) != (n * 12 + 7) // 8:
        raise ValueError("wrong packed payload length")
    if n % 2 and data[-1] & 15:
        raise ValueError("nonzero token padding")
    padded = data + b"\0" * ((-len(data)) % 3)
    triples = np.frombuffer(padded, np.uint8).astype(np.uint16).reshape(-1, 3)
    values = np.column_stack(((triples[:, 0] << 4) | (triples[:, 1] >> 4),
                              ((triples[:, 1] & 15) << 8) | triples[:, 2])).reshape(-1)[:n]
    return list(np.split(values, np.cumsum(counts)[:-1]))


class TokenWriter:
    def __init__(self, filename, model=MODEL):
        self.path = Path(filename)
        self.model = model
        self.samples = self.tokens = self.payload_bytes = self.chunks = 0
        self.closed = False
        self.mode = None
        self.partial = False
        self.accumulator = self.nbits = 0
        self.file = self.path.open("wb")

    def _header(self, mode):
        self.mode = mode
        info = dict(model=self.model, sample_rate=RATE, token_bits=12)
        if mode == FRAME_MODE:
            info.update(stream_mode=FRAME_MODE, frame_samples=FRAME_SAMPLES)
        header = json.dumps(info, separators=(",", ":")).encode()
        self.file.write((MAGIC2 if mode == FRAME_MODE else MAGIC) + struct.pack("<I", len(header)) + header)

    def write(self, meta, levels):
        if self.closed:
            raise ValueError("token file already closed")
        if meta["chunk_index"] != self.chunks:
            raise ValueError("out-of-order token chunk")
        levels = validate_levels(levels)
        mode = meta.get("stream_mode", "legacy")
        if self.mode is None:
            self._header(mode)
        if mode != self.mode:
            raise ValueError("token file stream mode changed")
        if mode == FRAME_MODE:
            validate_frame(meta, levels)
            if self.partial:
                raise ValueError("frame after partial final frame")
            self.partial = meta["audio_samples"] < FRAME_SAMPLES
            payload = bytearray()
            for value in np.concatenate(levels):
                self.accumulator = (self.accumulator << 12) | int(value)
                self.nbits += 12
                while self.nbits >= 8:
                    self.nbits -= 8
                    payload.append((self.accumulator >> self.nbits) & 255)
                self.accumulator &= (1 << self.nbits)-1
        else:
            payload = pack12(levels)
            self.file.write(RECORD.pack(meta["audio_samples"], meta.get("encoded_samples", meta["audio_samples"]),
                                        meta.get("crop_start", 0), *map(len, levels)))
        self.file.write(payload)
        self.samples += meta["audio_samples"]
        self.tokens += sum(map(len, levels))
        self.payload_bytes += len(payload)
        self.chunks += 1

    def finish(self, complete=False):
        if self.closed:
            return self.report
        if self.mode is None:
            self._header("legacy")
        if complete:
            if self.mode == FRAME_MODE:
                if self.nbits:
                    self.file.write(bytes([self.accumulator << (8-self.nbits)]))
                    self.payload_bytes += 1
                self.file.write(FOOTER2.pack(self.samples, b"END2"))
            else:
                self.file.write(bytes(RECORD.size))
        self.file.close()
        self.closed = True
        seconds = self.samples / RATE
        size = self.path.stat().st_size
        self.report = dict(format="gr-snac-12-v2" if self.mode == FRAME_MODE else "gr-snac-12-v1", model=self.model, complete=complete,
                           audio_samples=self.samples, duration_seconds=seconds, chunks=self.chunks,
                           tokens=self.tokens, token_bits=self.tokens*12, payload_bytes=self.payload_bytes,
                           file_bytes=size, overhead_bytes=size-self.payload_bytes,
                           token_bitrate_bps=self.tokens*12/seconds if seconds else 0,
                           file_bitrate_bps=size*8/seconds if seconds else 0)
        if self.mode == FRAME_MODE:
            self.report.update(bits_per_frame=84, steady_token_bitrate_bps=84*RATE/FRAME_SAMPLES)
        Path(str(self.path) + ".json").write_text(json.dumps(self.report, indent=2) + "\n", encoding="utf-8")
        return self.report


def read_tokens(filename):
    """Yield (metadata, levels), rejecting truncated/incompatible containers."""
    with open(filename, "rb") as source:
        def exact(n):
            value = source.read(n)
            if len(value) != n:
                raise ValueError("truncated SNAC file (missing data or EOS)")
            return value
        magic = exact(len(MAGIC))
        if magic not in (MAGIC, MAGIC2):
            raise ValueError("not a supported gr-snac token file")
        length, = struct.unpack("<I", exact(4))
        if length > 65536:
            raise ValueError("oversized header")
        header = json.loads(exact(length))
        if header.get("sample_rate") != RATE or header.get("token_bits") != 12 or not isinstance(header.get("model"), str):
            raise ValueError("incompatible token file header")
        if magic == MAGIC2:
            if header.get("stream_mode") != FRAME_MODE or header.get("frame_samples") != FRAME_SAMPLES:
                raise ValueError("incompatible frame header")
            start = source.tell()
            size = Path(filename).stat().st_size
            if size < start + FOOTER2.size:
                raise ValueError("missing frame EOS")
            source.seek(-FOOTER2.size, 2)
            samples, end = FOOTER2.unpack(exact(FOOTER2.size))
            count = (samples+FRAME_SAMPLES-1)//FRAME_SAMPLES
            if end != b"END2" or not samples or size-start-FOOTER2.size != (count*84+7)//8:
                raise ValueError("invalid frame payload/EOS length")
            source.seek(start)
            accumulator = nbits = 0
            for index in range(count):
                values = []
                for _ in range(7):
                    while nbits < 12:
                        accumulator = (accumulator << 8) | exact(1)[0]
                        nbits += 8
                    nbits -= 12
                    values.append((accumulator >> nbits) & 4095)
                    accumulator &= (1 << nbits)-1
                n = min(FRAME_SAMPLES, samples-index*FRAME_SAMPLES)
                yield dict(model=header["model"], audio_samples=n, encoded_samples=FRAME_SAMPLES,
                           crop_start=0, chunk_index=index, stream_mode=FRAME_MODE), list(np.split(np.array(values, np.uint16), [1, 3]))
            if accumulator:
                raise ValueError("nonzero final token padding")
            return
        index = 0
        while True:
            samples, encoded, crop, *counts = RECORD.unpack(exact(RECORD.size))
            if not any((samples, encoded, crop, *counts)):
                if source.read(1):
                    raise ValueError("data after EOS")
                return
            if samples <= 0 or encoded < crop + samples or not all(counts):
                raise ValueError("invalid token record")
            size = (sum(counts)*12 + 7)//8
            # Prevent malformed files from requesting allocations larger than the file.
            if size > Path(filename).stat().st_size - source.tell():
                raise ValueError("truncated token payload")
            levels = unpack12(exact(size), counts)
            yield dict(model=header["model"], audio_samples=samples, encoded_samples=encoded,
                       crop_start=crop, chunk_index=index), levels
            index += 1
