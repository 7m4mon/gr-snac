"""Physical waveform and analysis checks; run with GNU Radio's Python."""
import numpy as np
from sweep_4cpfsk import modulate
from analyze_4cpfsk import analyze


def main():
    rs, sps = 1312.5, 32
    fs = rs*sps
    for h in [.2, .25, .3]:
        for index, level in enumerate([-3, -1, 3, 1]):
            iq = modulate(np.full(2048, index, dtype=np.uint8), h=h)
            freq = np.angle(iq[1:]*iq[:-1].conj())*fs/(2*np.pi)
            expected = level*h*rs/2
            # GNU Radio's finite Gaussian pulse has small truncation error.
            np.testing.assert_allclose(np.mean(freq[320:]), expected, atol=.1)
            np.testing.assert_allclose(np.abs(iq), 1, atol=1e-5)
    # Directly exercise symbol transitions and flowgraph scheduler boundaries.
    symbols = np.random.default_rng(17).integers(0, 4, 16384, dtype=np.uint8)
    iq = modulate(symbols)
    np.testing.assert_allclose(np.abs(iq), 1, atol=1e-5)
    step = np.angle(iq[1:]*iq[:-1].conj())
    assert np.max(np.abs(step)) < 3*.25*np.pi/sps + .001
    result, _, _ = analyze(iq)
    assert result['obw999_hz'] >= result['obw99_hz'] > 0
    np.testing.assert_allclose(result['total_power'], 1, rtol=.01)
    # A unit complex tone has unit integrated power, and belongs to main channel.
    t = np.arange(42000)/fs
    tone = np.exp(2j*np.pi*200*t).astype(np.complex64)
    result, _, _ = analyze(tone)
    np.testing.assert_allclose(result['main_2000_power'], 1, rtol=.001)
    assert result['acpr_2000_upper_db'] < -60
    # Pulse truncation convergence at the narrowest requested BT.
    r4, _, _ = analyze(modulate(symbols, bt=.25, length=4))
    r6, _, _ = analyze(modulate(symbols, bt=.25, length=6))
    assert abs(r4['obw999_hz']-r6['obw999_hz']) < 20
    print('PASS: Gray mapping, 12 steady tones, envelope, phase-step bounds, PSD power, OBW, L=4/6 convergence')


if __name__ == '__main__':
    main()
