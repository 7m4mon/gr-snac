"""Compare independent chunks and context-cropped chunks using local weights."""
import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from gr_snac_core.codec import Codec, RATE
from gr_snac_core.wav import read_wav, write_wav


def main():
    codec = Codec(device="cpu")
    model = codec.model
    import math
    alignment = int(model.hop_length) * math.lcm(*model.vq_strides, model.attn_window_size or 1)
    print("alignment", alignment, flush=True)
    out = ROOT / "examples/boundary_analysis"
    out.mkdir(exist_ok=True)
    for name in ("VOICEACTRESS100_001_001", "VOICEACTRESS100_001_002"):
        audio, _ = read_wav(ROOT / "examples" / (name + ".wav"))
        old, _ = read_wav(ROOT / "examples" / (name + "_reconstructed.wav"))
        results = {"provided": old}
        for context in (0, 12000, 24000):
            pieces = []
            for start in range(0, len(audio), RATE):
                end = min(start + RATE, len(audio))
                left = max(0, (start - context) // alignment * alignment) if context else start
                right = min(len(audio), end + context)
                levels, _ = codec.encode(audio[left:right])
                decoded, _ = codec.decode(levels, right - left)
                pieces.append(decoded[start-left:end-left])
            result = np.concatenate(pieces)
            results[str(context)] = result
            write_wav(out / (name + f"_context_{context}.wav"), result)
        boundaries = np.arange(RATE, len(audio), RATE)
        report = {key: {"samples": len(value), "jumps": np.abs(value[boundaries] - value[boundaries-1]).tolist()}
                  for key, value in results.items()}
        report["independent_vs_provided_rmse"] = float(np.sqrt(np.mean((results["0"] - old)**2)))
        (out / (name + ".json")).write_text(json.dumps(report, indent=2))
        print(name, json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
