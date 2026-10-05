"""Shared inference and chunk accounting for blocks and standalone tools."""
import math
import time
import numpy as np

MODEL = "hubertsiuzdak/snac_24khz"
RATE = 24000


def chunk_size(chunk_ms):
    value = float(chunk_ms)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("chunk_ms must be finite and positive")
    count = round(RATE * value / 1000)
    if count < 1:
        raise ValueError("chunk_ms rounds to fewer than one sample")
    return count


def prepare_audio(audio):
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim != 1 or not len(audio) or not np.isfinite(audio).all():
        raise ValueError("audio must be nonempty, finite mono audio")
    return np.clip(audio, -1, 1)


def validate_levels(levels):
    if len(levels) != 3:
        raise ValueError("SNAC 24k requires exactly three levels")
    result = []
    for level in levels:
        a = np.asarray(level)
        if a.ndim != 1 or not a.size or a.dtype.kind not in "iu":
            raise ValueError("each level must be a nonempty integer vector")
        if np.any(a < 0) or np.any(a > 4095):
            raise ValueError("token outside 0..4095")
        result.append(a.astype(np.uint16))
    return result


def statistics(levels, samples):
    counts = [len(x) for x in levels]
    bits = sum(counts) * 12
    return dict(tokens=counts, total_tokens=sum(counts), raw_bits=bits,
                bitrate=bits * RATE / samples)


class Codec:
    def __init__(self, model=MODEL, device="auto"):
        import torch
        from snac import SNAC
        if device not in ("auto", "cpu", "cuda"):
            raise ValueError("device must be auto, cpu or cuda")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
        self.device = ("cuda" if torch.cuda.is_available() else "cpu") if device == "auto" else device
        self.model_id = model
        self.torch = torch
        self.model = SNAC.from_pretrained(model).to(self.device).eval()
        if (self.model.sampling_rate != RATE or self.model.n_codebooks != 3
                or self.model.codebook_size != 4096):
            raise ValueError("model must be 24 kHz, three levels, 4096 entries")

    def _sync(self):
        if self.device == "cuda":
            self.torch.cuda.synchronize()

    def encode(self, audio):
        audio = prepare_audio(audio)
        self._sync()
        start = time.perf_counter()
        with self.torch.inference_mode():
            tensor = self.torch.from_numpy(audio.copy()).reshape(1, 1, -1).to(self.device)
            codes = self.model.encode(tensor)
            levels = validate_levels([c.detach().cpu().numpy().reshape(-1) for c in codes])
        self._sync()
        return levels, time.perf_counter() - start

    def decode(self, levels, samples):
        levels = validate_levels(levels)
        if isinstance(samples, bool) or not isinstance(samples, int) or samples <= 0:
            raise ValueError("audio_samples must be a positive integer")
        # Check the model's hierarchy before invoking its tensor operations.
        strides = self.model.vq_strides
        latent_lengths = [len(x) * s for x, s in zip(levels, strides)]
        if len(set(latent_lengths)) != 1:
            raise ValueError("inconsistent token hierarchy lengths")
        capacity = latent_lengths[0] * int(self.model.hop_length)
        if samples > capacity:
            raise ValueError("audio_samples exceeds token capacity")
        self._sync()
        start = time.perf_counter()
        with self.torch.inference_mode():
            codes = [self.torch.tensor(x.astype(np.int64), device=self.device).reshape(1, -1)
                     for x in levels]
            audio = self.model.decode(codes).detach().cpu().numpy().reshape(-1)
        if len(audio) < samples or not np.isfinite(audio).all():
            raise ValueError("decoder returned short or nonfinite audio")
        self._sync()
        # encode() pads internally, decode() does not remove that padding.
        return audio[:samples].astype(np.float32, copy=True), time.perf_counter() - start
