"""Render supplied speech with checkout blocks and the real GNU Radio scheduler."""
import json
import sys
import threading
from pathlib import Path
import numpy as np
import gnuradio
from gnuradio import gr, blocks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
gnuradio.__path__.insert(0, str(ROOT / "python/gnuradio"))
from gnuradio import snac
from gr_snac_core.wav import read_wav, write_wav


def main():
    folder = ROOT / "examples/boundary_analysis"
    folder.mkdir(exist_ok=True)
    report = {}
    for name in ("VOICEACTRESS100_001_001", "VOICEACTRESS100_001_002"):
        audio, _ = read_wav(ROOT / "examples" / (name + ".wav"))
        tb = gr.top_block()
        source = blocks.vector_source_f(audio.tolist(), False)
        enc = snac.snac_encoder(device="cpu", total_samples=len(audio), context_frames=2)
        dec = snac.snac_decoder(device="cpu")
        sink = blocks.vector_sink_f()
        tb.connect(source, enc)
        tb.msg_connect(enc, "codes", dec, "codes")
        tb.connect(dec, sink)
        tb.start()
        waiter = threading.Thread(target=tb.wait, daemon=True)
        waiter.start()
        waiter.join(120)
        if waiter.is_alive():
            tb.stop()
            waiter.join(10)
            raise RuntimeError("flowgraph did not terminate")
        if dec.error:
            raise dec.error
        output = np.array(sink.data(), np.float32)
        assert len(output) == len(audio) and np.isfinite(output).all()
        write_wav(folder / (name + "_gr_frames2.wav"), output)
        positions = np.arange(24000, len(audio), 24000)
        item = {"samples": len(output)}
        for label, value in (("input", audio), ("fixed", output)):
            item[label] = np.abs(value[positions] - value[positions-1]).tolist()
        for label, suffix in (("provided", "_reconstructed"), ("official", "_snac_official_out")):
            path = ROOT / "examples" / (name + suffix + ".wav")
            if path.exists():
                value, _ = read_wav(path)
                item[label] = np.abs(value[positions] - value[positions-1]).tolist()
        report[name] = item
        print(name, json.dumps(item), flush=True)
    (folder / "gnu_radio_frames2_verification.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
