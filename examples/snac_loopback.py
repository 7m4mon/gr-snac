#!/usr/bin/env python3
"""Finite WAV loopback using installed GNU Radio blocks; includes the final partial chunk."""
import argparse
import wave
from gnuradio import gr, blocks, snac


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="cpu")
    parser.add_argument("--chunk-ms", type=float, default=1000)
    args = parser.parse_args()
    with wave.open(args.input, "rb") as wav:
        if wav.getframerate() != 24000 or wav.getnchannels() != 1 or not wav.getnframes():
            parser.error("input must be a nonempty 24 kHz mono PCM WAV")
        count = wav.getnframes()
    tb = gr.top_block()
    source = blocks.wavfile_source(args.input, False)
    enc = snac.snac_encoder(device=args.device, chunk_ms=args.chunk_ms,
                            total_samples=count, verbose=True)
    dec = snac.snac_decoder(device=args.device, verbose=True)
    sink = blocks.wavfile_sink(args.output, 1, 24000, blocks.FORMAT_WAV, blocks.FORMAT_PCM_16, False)
    tb.connect(source, enc)
    tb.msg_connect(enc, "codes", dec, "codes")
    tb.connect(dec, sink)
    try:
        tb.run()
    except KeyboardInterrupt:
        tb.stop()
        tb.wait()
    finally:
        sink.close()
    if dec.error:
        raise RuntimeError("SNAC decode failed") from dec.error


if __name__ == "__main__":
    main()
