"""Two-sided Welch measurements for native complex64 baseband IQ."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.signal import welch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def analyze(iq, sample_rate=42000., nperseg=8192, discard_seconds=0.1):
    if sample_rate <= 0 or nperseg < 8 or discard_seconds < 0:
        raise ValueError('Invalid sample rate, FFT length or discard duration')
    x = np.asarray(iq)[int(discard_seconds * sample_rate):]
    if len(x) < 2*nperseg or not np.isfinite(x).all():
        raise ValueError('Need at least two FFT segments of finite IQ after startup discard')
    f, p = welch(x, fs=sample_rate, window='blackmanharris', nperseg=nperseg,
                 noverlap=nperseg//2, detrend=False, return_onesided=False, scaling='density')
    order = np.argsort(f)
    f, p = f[order], p[order].astype(float)
    df = sample_rate/nperseg
    total = np.sum(p)*df
    if total <= 0:
        raise ValueError('IQ has zero power')
    # Each bin is a constant-density interval; interpolate fractional edge bins.
    edges = np.r_[f-df/2, f[-1]+df/2]
    cdf = np.r_[0., np.cumsum(p)*df]
    def power(lo, hi):
        return float(np.interp(hi, edges, cdf)-np.interp(lo, edges, cdf))
    def db(ratio):
        return float(10*np.log10(max(ratio, np.finfo(float).tiny)))
    peak_db = 10*np.log10(np.maximum(p/p.max(), np.finfo(float).tiny))
    result = dict(sample_rate_hz=sample_rate, nperseg=nperseg, fft_bin_hz=df,
        discard_seconds=discard_seconds, analyzed_samples=len(x),
        analyzed_seconds=len(x)/sample_rate, total_power=total,
        magnitude_min=float(np.abs(x).min()), magnitude_max=float(np.abs(x).max()))
    for percentage in [99, 99.9]:
        tail = (1-percentage/100)/2
        low, high = np.interp(np.array([tail, 1-tail])*total, cdf, edges)
        key = '99' if percentage == 99 else '999'
        result[f'obw{key}_hz'] = float(high-low)
    for offset in [1000, 1250, 2000, 2500]:
        if offset >= sample_rate/2:
            raise ValueError('Sample rate too low for requested PSD offsets')
        for sign, label in [(-1, 'minus'), (1, 'plus')]:
            result[f'psd_{label}_{offset}_peak_db'] = db(np.interp(sign*offset, f, p)/p.max())
    for spacing in [2000, 2500]:
        if 1.5*spacing > edges[-1]:
            raise ValueError('Sample rate too low for adjacent channel integration')
        main = power(-spacing/2, spacing/2)
        result[f'main_{spacing}_power'] = main
        for sign, label in [(-1, 'lower'), (1, 'upper')]:
            adj = power(sign*spacing-spacing/2, sign*spacing+spacing/2)
            result[f'adj_{spacing}_{label}_power'] = adj
            result[f'acpr_{spacing}_{label}_db'] = db(adj/main)
    return result, f, peak_db


def plot(f, db, path, title='Gaussian 4CPFSK', spacing=2500):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(f, db, linewidth=0.8)
    for offset in [-spacing, -spacing/2, 0, spacing/2, spacing]:
        ax.axvline(offset, color='gray', linestyle='--', linewidth=0.7)
    ax.set(xlim=(-5000, 5000), ylim=(-100, 3), xlabel='Baseband frequency [Hz]',
           ylabel='PSD relative to peak [dB]', title=title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('iq', type=Path)
    ap.add_argument('--sample-rate', type=float, default=42000.)
    ap.add_argument('--nperseg', type=int, default=8192)
    ap.add_argument('--discard-seconds', type=float, default=0.1)
    ap.add_argument('--spacing', type=int, choices=[2000, 2500], default=2500)
    args = ap.parse_args()
    if args.iq.stat().st_size % 8:
        ap.error('File size must be a multiple of 8 bytes (complex64)')
    result, f, db = analyze(np.fromfile(args.iq, dtype=np.complex64), args.sample_rate,
                             args.nperseg, args.discard_seconds)
    args.iq.with_suffix('.json').write_text(json.dumps(result, indent=2))
    plot(f, db, args.iq.with_suffix('.png'), spacing=args.spacing)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
