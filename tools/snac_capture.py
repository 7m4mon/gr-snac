#!/usr/bin/env python3
"""Capture actual GNU Radio encoder messages as separate uint16 token files."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import wave

root = Path(__file__).resolve().parents[1] / "python"
sys.path.insert(0, str(root))
import gnuradio
gnuradio.__path__.insert(0, str(root / "gnuradio"))
from gnuradio import blocks, gr, snac
from gnuradio.snac.messages import unpack
from gr_snac_core.codec import MODEL, RATE, statistics
import numpy as np
import pmt


class Capture(gr.basic_block):
    def __init__(self, directory, model):
        gr.basic_block.__init__(self, name="SNAC token capture", in_sig=None, out_sig=None)
        self.directory = directory
        self.model = model
        self.files = [open(directory / f"level{i}.u16le", "xb") for i in range(3)]
        self.chunks = []
        self.counts = [0, 0, 0]
        self.eos = False
        self.error = None
        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))
        self.set_msg_handler(pmt.intern("in"), self.handle)

    def handle(self, message):
        try:
            metadata, levels = unpack(message, self.model)
            if levels is None:
                self.eos = True
            else:
                counts = [len(level) for level in levels]
                self.chunks.append(dict(metadata=metadata, token_offsets=self.counts.copy(),
                                        token_counts=counts))
                for i, level in enumerate(levels):
                    self.files[i].write(np.asarray(level, dtype="<u2").tobytes())
                    self.counts[i] += counts[i]
        except Exception as exc:
            self.error = exc
        # Forward the exact message, so decoder completion also confirms capture order.
        self.message_port_pub(pmt.intern("out"), message)

    def close(self):
        for file in self.files:
            file.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("directory", type=Path, help="new output directory; must not exist")
    parser.add_argument("--chunk-ms", type=float, default=1000)
    parser.add_argument("--device", choices=("cpu", "auto", "cuda"), default="cpu")
    parser.add_argument("--model", default=MODEL)
    args = parser.parse_args()
    with wave.open(str(args.input), "rb") as wav:
        samples = wav.getnframes()
        if wav.getframerate() != RATE or wav.getnchannels() != 1 or samples == 0:
            parser.error("input must be nonempty 24 kHz mono PCM WAV")
    args.directory.mkdir(parents=True, exist_ok=False)
    tb = gr.top_block()
    source = blocks.wavfile_source(str(args.input), False)
    encoder = snac.snac_encoder(model=args.model, device=args.device,
                                chunk_ms=args.chunk_ms, total_samples=samples)
    decoder = snac.snac_decoder(model=args.model, device=args.device)
    capture = Capture(args.directory, args.model)
    sink = blocks.wavfile_sink(str(args.directory / "reconstructed.wav"), 1, RATE,
                               blocks.FORMAT_WAV, blocks.FORMAT_PCM_16, False)
    tb.connect(source, encoder)
    tb.msg_connect(encoder, "codes", capture, "in")
    tb.msg_connect(capture, "out", decoder, "codes")
    tb.connect(decoder, sink)
    try:
        tb.run()
    finally:
        tb.stop()
        tb.wait()
        sink.close()
        capture.close()
    if capture.error:
        raise RuntimeError("token capture failed") from capture.error
    if decoder.error:
        raise RuntimeError("decode failed") from decoder.error
    assert capture.eos, "missing EOS"
    assert sum(c["metadata"]["audio_samples"] for c in capture.chunks) == samples
    # Independently reload the stored bytes and check each chunk's token accounting.
    stored = [np.fromfile(args.directory / f"level{i}.u16le", dtype="<u2") for i in range(3)]
    assert [len(level) for level in stored] == capture.counts
    assert all(np.all(level < 4096) for level in stored)
    duration = samples / RATE
    total = sum(capture.counts)
    report = dict(sample_rate=RATE, audio_samples=samples, duration_seconds=duration,
                  chunk_ms=args.chunk_ms, chunk_count=len(capture.chunks),
                  token_counts=capture.counts, total_tokens=total,
                  payload_bits_12bit=total * 12, payload_bytes_12bit_equivalent=total * 12 / 8,
                  payload_bitrate_12bit=total * 12 / duration,
                  stored_token_bytes_u16=total * 2, stored_token_bitrate_u16=total * 16 / duration,
                  note="12-bit figures are calculated, not packed; no framing or FEC included.")
    manifest = dict(format="gr-snac-u16le-v1", model=args.model, sample_rate=RATE,
                    storage="Three headerless little-endian uint16 files; offsets/counts are tokens.",
                    chunks=capture.chunks,
                    sha256={f"level{i}.u16le": hashlib.sha256((args.directory / f"level{i}.u16le").read_bytes()).hexdigest()
                            for i in range(3)})
    (args.directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with (args.directory / "chunks.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["chunk", "audio_samples", "duration_seconds", "level0", "level1", "level2",
                         "total_tokens", "payload_bits_12bit", "payload_bitrate_12bit"])
        for chunk in capture.chunks:
            meta = chunk["metadata"]
            counts = chunk["token_counts"]
            n = meta["audio_samples"]
            writer.writerow([meta["chunk_index"], n, n / RATE, *counts,
                             sum(counts), sum(counts) * 12, sum(counts) * 12 * RATE / n])
    report["archive_bytes_with_metadata"] = sum((args.directory / name).stat().st_size
                                                for name in ["manifest.json", "chunks.csv", "level0.u16le", "level1.u16le", "level2.u16le"])
    with wave.open(str(args.directory / "reconstructed.wav"), "rb") as wav:
        assert wav.getnframes() == samples
    (args.directory / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
