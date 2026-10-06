"""Decode a saved gr-snac token file without the original WAV or encoder."""
import argparse
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from gr_snac_core.token_file import read_tokens
from gr_snac_core.codec import Codec
from gr_snac_core.wav import write_wav
from gr_snac_core.frames import FrameDecoder, FRAME_MODE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda", "auto"))
    parser.add_argument("--context-frames", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    codec = None
    frames = None
    pieces = []
    for meta, levels in read_tokens(args.input):
        if codec is None:
            codec = Codec(meta["model"], args.device)
            if meta.get("stream_mode") == FRAME_MODE:
                frames = FrameDecoder(codec, args.context_frames)
        if frames is not None:
            pieces.extend(audio for audio, _, _ in frames.push(meta, levels))
            continue
        audio, _ = codec.decode(levels, meta["encoded_samples"])
        crop = meta["crop_start"]
        pieces.append(audio[crop:crop+meta["audio_samples"]])
    if frames is not None:
        pieces.extend(audio for audio, _, _ in frames.finish())
    if not pieces:
        raise ValueError("empty token recording")
    audio = np.concatenate(pieces)
    write_wav(args.output, audio)
    print(f"Decoded {len(audio)} samples from tokens only: {args.output}")


if __name__ == "__main__":
    main()
