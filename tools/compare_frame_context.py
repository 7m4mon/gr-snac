"""Offline experiment: transmit each 2048-sample frame's tokens only once.

Encoder PCM context and decoder token context are local, not retransmitted.
This is a quality experiment, not a paced radio/scheduler implementation.
"""
import json
import argparse
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from gr_snac_core.codec import Codec, RATE
from gr_snac_core.wav import read_wav, write_wav


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contexts", nargs="+", default=["1:0", "0:1", "1:1", "2:2"],
                        help="past:future frame counts, e.g. 3:1 3:3")
    args = parser.parse_args()
    contexts = [tuple(map(int, value.split(":"))) for value in args.contexts]
    if any(len(pair) != 2 or min(pair) < 0 for pair in contexts):
        parser.error("contexts must be nonnegative past:future pairs")
    codec = Codec(device="cpu")
    frame = codec.alignment
    widths = [frame // (int(codec.model.hop_length)*s) for s in codec.model.vq_strides]
    folder = ROOT / "examples/frame_context"
    folder.mkdir(exist_ok=True)
    report_path = folder / "comparison.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    for name in ("VOICEACTRESS100_001_001", "VOICEACTRESS100_001_002"):
        audio, _ = read_wav(ROOT / "examples" / (name + ".wav"))
        ref_codes, _ = codec.encode(audio)
        reference, _ = codec.decode(ref_codes, len(audio))
        write_wav(folder / (name + "_whole.wav"), reference)
        nframes = (len(audio)+frame-1)//frame
        boundaries = np.arange(frame, len(audio), frame)
        item = report.get(name, {})
        item["whole_boundary_jump_p95"] = float(np.percentile(np.abs(np.diff(reference)[boundaries-1]), 95))
        for past, future in contexts:
            frames = []
            for i in range(nframes):
                left = max(0, i-past)
                right = min(nframes, i+1+future)
                codes, _ = codec.encode(audio[left*frame:min(len(audio), right*frame)])
                frames.append([c[(i-left)*w:(i-left+1)*w].copy() for c, w in zip(codes, widths)])
            transmitted = [np.concatenate([c[level] for c in frames]) for level in range(3)]
            pieces = []
            for i in range(nframes):
                left = max(0, i-past)
                right = min(nframes, i+1+future)
                codes = [c[left*w:right*w] for c, w in zip(transmitted, widths)]
                decoded, _ = codec.decode(codes, (right-left)*frame)
                count = min(frame, len(audio)-i*frame)
                pieces.append(decoded[(i-left)*frame:(i-left)*frame+count])
            result = np.concatenate(pieces)
            assert len(result) == len(audio) and np.isfinite(result).all()
            label = f"past{past}_future{future}"
            write_wav(folder / (name + "_" + label + ".wav"), result)
            item[label] = dict(tokens=sum(map(len, transmitted)),
                               bits_per_frame=sum(widths)*12,
                               steady_bitrate=sum(widths)*12*RATE/frame,
                               encoder_token_agreement=[float(np.mean(a == b)) for a, b in zip(transmitted, ref_codes)],
                               boundary_jump_p95=float(np.percentile(np.abs(np.diff(result)[boundaries-1]), 95)),
                               rmse_to_whole=float(np.sqrt(np.mean((result-reference)**2))))
            print(name, label, json.dumps(item[label]), flush=True)
        report[name] = item
        report_path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
