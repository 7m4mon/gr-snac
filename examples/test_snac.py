import torch
import soundfile as sf
import numpy as np
from scipy.signal import resample_poly
from snac import SNAC

infile = "VOICEACTRESS100_001_001.wav"
outfile = "snac_official_out.wav"

device = "cpu"

model = SNAC.from_pretrained("hubertsiuzdak/snac_24khz").eval().to(device)

wav, sr = sf.read(infile, always_2d=True)

# stereo -> mono
wav = wav.mean(axis=1)

# resample to 24 kHz if needed
if sr != 24000:
    from math import gcd
    g = gcd(sr, 24000)
    wav = resample_poly(wav, 24000 // g, sr // g)

# [B, C, T]
wav = torch.tensor(wav, dtype=torch.float32).unsqueeze(0).unsqueeze(0)

with torch.inference_mode():
    codes = model.encode(wav)
    decoded = model.decode(codes)

decoded = decoded.squeeze().cpu().numpy()

sf.write(outfile, decoded, 24000)

print("saved:", outfile)
print("codes:", [c.shape for c in codes])