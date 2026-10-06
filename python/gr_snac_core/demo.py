"""A deterministic demo WAV for the GRC example; standard library only."""
from functools import lru_cache
import math
import os
from pathlib import Path
import struct
import tempfile
import wave


@lru_cache(maxsize=1)
def demo_wav_path():
    """Create a short tone in the user cache on first use."""
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "gr-snac"
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / "demo-24k-mono-v1.wav"
    if not target.exists():
        # A partial final chunk deliberately exercises the EOS path.
        count = 25003
        pcm = b"".join(struct.pack("<h", round(3000 * math.sin(2 * math.pi * 220 * n / 24000)))
                       for n in range(count))
        with tempfile.NamedTemporaryFile(dir=cache, suffix=".wav", delete=False) as temp:
            temporary = Path(temp.name)
        try:
            with wave.open(str(temporary), "wb") as wav:
                wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                wav.writeframes(pcm)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return str(target)
