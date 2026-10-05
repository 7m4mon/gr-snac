"""PCM conversion without peak normalization."""
import math
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
from .codec import RATE, prepare_audio


def read_wav(path):
    rate, audio = wavfile.read(path)
    if audio.dtype.kind == "u" and audio.dtype.itemsize == 1:
        audio = (audio.astype(np.float32) - 128) / 128
    elif audio.dtype.kind == "i":
        audio = audio.astype(np.float32) / (2 ** (8 * audio.dtype.itemsize - 1))
    elif audio.dtype.kind == "f":
        audio = audio.astype(np.float32)
    else:
        raise ValueError("unsupported WAV sample format")
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    audio = prepare_audio(audio)
    if rate != RATE:
        divisor = math.gcd(rate, RATE)
        audio = resample_poly(audio, RATE // divisor, rate // divisor)
    return prepare_audio(audio), rate


def write_wav(path, audio):
    wavfile.write(path, RATE, (np.clip(audio, -1, 1) * 32767).astype(np.int16))
