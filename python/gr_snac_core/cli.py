import argparse
import json
import numpy as np
from .codec import Codec, MODEL, RATE, chunk_size, statistics
from .wav import read_wav, write_wav


def run(reference=False):
    parser = argparse.ArgumentParser(description="SNAC 24 kHz chunked reference and token measurements")
    parser.add_argument("input", help="input WAV")
    if reference:
        parser.add_argument("output", help="reconstructed 24 kHz mono WAV")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--chunk-ms", type=float, default=1000)
    args = parser.parse_args()
    size = chunk_size(args.chunk_ms)
    audio, original_rate = read_wav(args.input)
    codec = Codec(args.model, args.device)
    counts = np.zeros(3, dtype=np.int64)
    encode_time = decode_time = 0.0
    reconstructed = []
    for index, offset in enumerate(range(0, len(audio), size)):
        chunk = audio[offset:offset + size]
        levels, elapsed = codec.encode(chunk)
        encode_time += elapsed
        counts += [len(x) for x in levels]
        report = dict(chunk_index=index, audio_samples=len(chunk),
                      duration_ms=len(chunk) / RATE * 1000,
                      encode_seconds=elapsed, **statistics(levels, len(chunk)))
        if reference:
            decoded, elapsed = codec.decode(levels, len(chunk))
            decode_time += elapsed
            reconstructed.append(decoded)
            report.update(decode_seconds=elapsed, decoded_samples=len(decoded))
        print(json.dumps(report))
    duration = len(audio) / RATE
    total = int(sum(counts))
    print(json.dumps(dict(input_sample_rate=original_rate, sample_rate=RATE,
                         duration_seconds=duration, tokens=counts.tolist(), total_tokens=total,
                         raw_token_bits=total * 12, average_bitrate=total * 12 / duration,
                         encode_seconds=encode_time, decode_seconds=decode_time,
                         real_time_factor=(encode_time + decode_time) / duration,
                         device=codec.device)))
    if reference:
        write_wav(args.output, np.concatenate(reconstructed))
