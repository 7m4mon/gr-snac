"""Run the same stock Map -> Gaussian CPM path as the GRC, without GUI/throttle."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from gnuradio import analog, blocks, digital, gr
from analyze_4cpfsk import analyze, plot


def modulate(symbols, h=.25, bt=.3, sps=32, length=4):
    tb = gr.top_block()
    source = blocks.vector_source_b(np.asarray(symbols, dtype=np.uint8).tolist(), False)
    mapper = digital.map_bb([253, 255, 3, 1])
    cpm = digital.cpmmod_bc(analog.cpm.GAUSSIAN, h, sps, length, bt)
    sink = blocks.vector_sink_c()
    tb.connect(source, mapper, cpm, sink)
    tb.run()
    return np.asarray(sink.data(), dtype=np.complex64)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, default=Path('results'))
    ap.add_argument('--seconds', type=float, default=60.)
    ap.add_argument('--symbol-rate', type=float, default=1312.5)
    ap.add_argument('--sps', type=int, default=32)
    ap.add_argument('--length', type=int, default=4)
    ap.add_argument('--seed', type=int, default=12345)
    ap.add_argument('--save-iq', action='store_true')
    args = ap.parse_args()
    if args.seconds <= 0 or args.symbol_rate <= 0 or args.sps < 2 or args.length < 1:
        ap.error('Require positive duration/rate/length and SPS >= 2')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    symbols = np.random.default_rng(args.seed).integers(0, 4,
                int(np.ceil(args.seconds*args.symbol_rate)), dtype=np.uint8)
    rows = []
    for h in [.20, .25, .30]:
        for bt in [.25, .30, .35, .50]:
            iq = modulate(symbols, h, bt, args.sps, args.length)
            result, f, db = analyze(iq, args.symbol_rate*args.sps)
            row = dict(h=h, bt=bt, pulse_length=args.length, seed=args.seed,
                       symbol_rate=args.symbol_rate, sps=args.sps, **result)
            rows.append(row)
            stem = args.output_dir / f'h{h:.2f}_bt{bt:.2f}'
            plot(f, db, Path(str(stem)+'.png'),
                 title=f'Gaussian 4CPFSK h={h}, BT={bt}, L={args.length}')
            if args.save_iq:
                iq.tofile(str(stem)+'.cf32')
            print(f'h={h:.2f} BT={bt:.2f} OBW99={result["obw99_hz"]:.1f} Hz')
    with (args.output_dir/'sweep.csv').open('w', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output_dir/'metadata.json').write_text(json.dumps(dict(
        gnuradio_version=gr.version(), seconds=args.seconds, seed=args.seed,
        window='blackmanharris', overlap=.5, detrend=False,
        mapping=[-3, -1, 3, 1], input='uniform dibit indices 0..3',
        obw='equal tail power', acpr='per-side adjacent/main; rectangular bands of width spacing'), indent=2))


if __name__ == '__main__':
    main()
