# gr-snac 0.1

English | [日本語](README.ja.md)

Author: **7M4MON**

Date: **2026-10-05**

Python out-of-tree (OOT) blocks for GNU Radio 3.10 that encode 24 kHz mono
float audio into SNAC tokens and decode them back to audio. All three token
levels remain separate in native PMT messages.

Version 0.1 includes encoder and decoder blocks, GNU Radio Companion (GRC)
definitions, WAV loopback examples, standalone token measurements, and tests.
A separate Gaussian 4CPFSK GRC experiment now builds CRC/FEC/sync radio frames
from random 84-bit payloads and measures transmit waveforms using stock GNU Radio
blocks. A WAV-to-SNAC transmitter and a finite-file IQ-to-WAV receiver are connected
to this chain. SDR transmission/reception is not implemented.
As of 2026-10-07, the framed v2 examples also use stock matrix interleaving and
additive whitening between FEC encoding and dibit conversion.

The [WAV transmitter GRC](examples/narrowband_4cpfsk/wav_snac_4cpfsk.grc) uses the
existing SNAC Encoder with a standard repeating WAV source and a sample-count
Head. `repeat_count` defaults to **5 total plays**. Input must be nonempty 24 kHz
mono integer-PCM WAV. Repetitions are concatenated before SNAC; only the final
partial frame is padded. A message-only adapter packs the 1/2/4 tokens into 84
payload bits and feeds the stock PDU-to-stream/FEC/interleaver/whitener/CPM chain.
No speaker or SDR output is enabled. Real-model tests cover a 1001-sample WAV
played once and five times, plus the bundled speech WAV played five times
(506 radio frames, 1813632 IQ samples). See the
[example README](examples/narrowband_4cpfsk/README.md) for launch commands and
metadata needed to identify the valid audio length in the final padded frame.

The [receiver GRC](examples/narrowband_4cpfsk/receive_snac_4cpfsk.grc) reads the IQ
and its `.frames.json` sidecar, uses stock quadrature demodulation, FIR equalization,
dewhitening, deinterleaving and tail-biting FEC decoding, then checks CRC/sequence
and sends recovered tokens to the existing SNAC Decoder. It saves 24 kHz mono
PCM16 WAV without speaker playback. Custom code performs finite-capture sync
acquisition and protocol/token conversion. This first receiver assumes no CFO or
sample-clock mismatch and uses the sidecar for finite audio length; it is not a
continuous over-the-air receiver. See the example README for tests and limitations.

## Radio frame proposal and waveform results (2026-10-06)

The proposed frame starts with 84 payload bits (seven 12-bit tokens) per
2048 audio samples, or 85.333… ms at 24 kHz. Adding 8 sequence/flag bits and
12 CRC bits gives 104 information bits. Assuming rate-1/2 FEC with no additional
termination bits gives 208 coded bits, or 104 four-level symbols. Adding a
provisional 8-symbol sync gives **112 symbols/frame and 1312.5 symbols/s**.
The 2625 bit/s gross equivalent includes sync; the coded data portion is
2437.5 bit/s. The initial unframed spectrum experiment has now been extended
with actual CRC, FEC and sync insertion in separate framed flowgraphs.

The experiment uses standard Map and Gaussian CPM blocks rather than a custom
modulator. Defaults are h=0.25, BT=0.30, pulse length L=4, 32 samples/symbol and
42 ksample/s. Seeded random symbols stand in for coded data. Twelve h/BT settings
were measured with 60-second records on GNU Radio 3.10.1.1 / Ubuntu 22.04 (WSL).
Both generated Qt applications were smoke-tested offscreen, including IQ capture
for single-carrier and three-carrier configurations at 2.0 and 2.5 kHz spacing.

| Initial unframed default-setting measurement | Result |
|---|---:|
| 99% occupied bandwidth | 1379.6 Hz |
| 99.9% occupied bandwidth | 1829.6 Hz |
| ACPR at 2.0 kHz spacing, lower / upper | -36.45 / -36.43 dB |
| ACPR at 2.5 kHz spacing, lower / upper | -46.63 / -46.60 dB |

ACPR uses rectangular integration bands as wide as the channel spacing. These
results identify spectral candidates, not validated radio links: no pass/fail
mask, BER, acquisition, frequency-error or RF tests have been applied. Actual
framing can change the spectrum and required symbol rate. Six additional
convolutional-code termination bits would require 118 symbols/frame, or
1382.8125 symbols/s; the implementation instead uses tail-biting to preserve
112 symbols/frame. The provisional sync length still needs receiver testing.

The implemented format is payload[84], sequence[6], flags[2], CRC-12/DECT[12],
MSB first with no byte padding. CRC covers the preceding 92 bits. Stock GNU Radio
K=7, rate-1/2 CC encoding uses polys=[109,79], CC_TAILBITING and no padding.
Repack Bits converts 208 coded bits to 104 dibits; Stream Mux prepends the eight
sync dibits [0,3,1,0,2,1,3,2] (0x349E). Python only assembles the information bits
and bitwise CRC. CPM state is continuous across frames. A one-time zero-level
drain at the end of the finite capture preserves the final Gaussian pulse tail.

For 704 framed random-payload frames at h=.25, BT=.30, seed=12345:

| Framed v1 measurement (before interleaving/whitening) | Result |
|---|---:|
| 99% occupied bandwidth | 1372.4 Hz |
| 99.9% occupied bandwidth | 1835.5 Hz |
| ACPR at 2.0 kHz spacing, lower / upper | -36.26 / -36.42 dB |
| ACPR at 2.5 kHz spacing, lower / upper | -46.73 / -46.68 dB |

Validation covers CRC check/residue, single-bit error detection, sequence wrap,
stock FEC against an independent test oracle, sync positions, and generated GRC
dibit/IQ captures including the final drain. These transmit-spectrum tests do not
establish BER/acquisition performance; finite-file receiver tests are documented separately.

Version 2 adds a stock 16-row by 13-column Matrix Interleaver and Additive
Scrambler (mask=0x21, seed=0x1FF, GNU Radio len=8, one bit per byte, count=208).
The nine-bit LFSR resets at each coded frame; sync is excluded. The frame stays
112 symbols long. Inverse whitening and deinterleaving recover the exact FEC
output, including across frame boundaries. These are experimental settings,
not receiver-performance optimization. The data bits are not wire-compatible
with v1; metadata identifies v2 but no on-air version field was added.

See the [Japanese design narrative](README.ja.md) and the
[experiment README](examples/narrowband_4cpfsk/README.md) for measurement
definitions, all twelve results and reproduction commands. Open the
[framed single-carrier GRC](examples/narrowband_4cpfsk/framed_4cpfsk.grc) or
[framed three-carrier GRC](examples/narrowband_4cpfsk/three_carriers_framed.grc) to run
the new experiment. The original unframed examples remain available for comparison.

## Installation on Linux

Requirements: GNU Radio 3.10 with development files, Python 3.10 or later,
CMake, a C++ compiler for dependency detection, and `requirements.txt`.
Use the same Python minor version as GNU Radio.

From a checkout on Debian/Ubuntu:

```sh
sudo apt update
sudo apt install gnuradio gnuradio-dev cmake g++ python3-venv
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install 'numpy>=1.23,<2' -r requirements.txt
cmake -S . -B build -DCMAKE_INSTALL_PREFIX="$VIRTUAL_ENV" \
  -DPYTHON_EXECUTABLE="$VIRTUAL_ENV/bin/python"
cmake --build build
cmake --install build
export PYTHONPATH="$VIRTUAL_ENV/lib/python$(python -c 'import sys; print("%d.%d" % sys.version_info[:2])')/site-packages${PYTHONPATH:+:$PYTHONPATH}"
export GRC_BLOCKS_PATH="$VIRTUAL_ENV/share/gnuradio/grc/blocks${GRC_BLOCKS_PATH:+:$GRC_BLOCKS_PATH}"
python -c 'from gnuradio import snac; print(snac.snac_encoder)'
python /usr/bin/gnuradio-companion examples/snac_loopback.grc
```

These commands install CPU PyTorch. Choose a compatible PyTorch build for CUDA.
NumPy is constrained below 2 for compatibility with the GNU Radio 3.10.1
distribution binaries used in testing. Launch GRC from this shell; adjust its
executable path if needed. Set `-DGR_PYTHON_DIR=/path/to/site-packages` explicitly
if your distribution requires it. System-wide installation is also possible.

Import blocks with `from gnuradio import snac`; the upstream model library uses
`from snac import SNAC`. Block sources live in `python/gnuradio/snac/` to avoid
a package name collision. Shared inference code in `python/gr_snac_core/` does
not depend on GNU Radio.

## Windows through WSL 2

Tested on Ubuntu 22.04 under WSL 2. Install GNU Radio and Python dependencies
inside Ubuntu, separately from Windows Python environments. With Ubuntu
installed, enter it from PowerShell:

```powershell
wsl -d Ubuntu-22.04
```

Run this initial setup inside Ubuntu:

```sh
mkdir -p ~/src
git clone https://github.com/7m4mon/gr-snac.git ~/src/gr-snac
cd ~/src/gr-snac
sudo apt update
sudo apt install gnuradio gnuradio-dev cmake g++ python3-venv
python3 -m venv --system-site-packages "$HOME/.venvs/gr-snac"
source tools/activate-wsl.sh
python -m pip install --upgrade pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install 'numpy>=1.23,<2' -r requirements.txt
cmake -S . -B build-wsl -DCMAKE_INSTALL_PREFIX="$VIRTUAL_ENV" \
  -DPYTHON_EXECUTABLE="$VIRTUAL_ENV/bin/python"
cmake --build build-wsl
cmake --install build-wsl
python tools/verify_wsl.py
```

For later sessions:

```sh
cd ~/src/gr-snac
source tools/activate-wsl.sh
python /usr/bin/gnuradio-companion examples/snac_loopback.grc
```

WSLg provides the GUI display. Set the input and output WAV paths in GRC.
After editing block sources, run `cmake --install build-wsl` to update the
installed copy.

## Model and device selection

The default model is `hubertsiuzdak/snac_24khz`. The implementation checks for
a 24 kHz sample rate, three levels, and a codebook size of 4096.

First use may require internet access to download weights. Later uses reuse the
SNAC / Hugging Face cache. Each block loads its model once during construction,
never once per chunk. Encoder and decoder have separate model instances.

- `auto`: use CUDA when available, otherwise CPU.
- `cpu`: always use CPU.
- `cuda`: require CUDA and raise a clear error when unavailable.

The Python block API defaults to `auto`; GRC and the GNU Radio loopback example
default to CPU. Inference runs inside `torch.inference_mode()`.

## Standalone tools

These scripts work without GNU Radio:

```sh
python tools/snac_token_info.py speech.wav --device cpu --chunk-ms 1000
python examples/snac_reference.py speech.wav reconstructed.wav --device cpu --chunk-ms 1000
```

Integer PCM is converted to float32, stereo channels are averaged to mono, and
`scipy.signal.resample_poly` resamples to 24 kHz when needed. No peak
normalization is applied. Input is clipped to [-1, 1]; empty or nonfinite audio
is rejected. Reconstructed WAV output is 24 kHz mono PCM16.

JSON output reports per-chunk and total token counts, raw bits at 12 bits/token,
bitrate relative to the original duration, processing time, and real-time factor
(processing seconds / audio seconds). Model loading and WAV I/O are excluded
from timing. CUDA timing includes synchronization.

## GNU Radio WAV loopback

```sh
python /usr/bin/gnuradio-companion examples/snac_loopback.grc
```

Use a **nonempty 24 kHz mono PCM WAV**. In `examples/snac_loopback.grc`, edit `input_path` and
`output_path`; the GRC example does not convert the input format.

The generated Python example uses the paths/settings in the GRC file.
Both blocks expose **Context Frames (each side)**: **1 or 2, default 2**.
Frames are fixed at 2048 samples (85.333 ms). The encoder retains PCM history;
the decoder retains received tokens. Only the new frame's 1/2/4 tokens are sent:
84 bits per frame, **984.375 bit/s** steady payload, with either context choice.
No context is retransmitted. A partial final frame is padded and cropped to the
original length. Future context adds 85.333/170.667 ms at each processing stage,
in addition to frame accumulation, computation and transport latency.
Old `chunk_ms` and `context_ms` block parameters are removed: regenerate old
GRC Python code and update both blocks. Zero/one-sided context is not supported.
The standalone reference CLI still uses independent chunks for comparison.
Context does not guarantee whole-file equivalence for all audio.
Low-latency performance and perceptual quality have not been evaluated.

### Finite input and termination

Set `total_samples` to the exact input length to emit the final partial chunk
followed by an end-of-stream (EOS) message. The decoder drains its FIFO before
ending output. WAV examples obtain the count from the header. Too large a count
prevents EOS; too small a count truncates input.

With `total_samples=0`, only full chunks are emitted. Stream EOF does not
automatically propagate through a message port, so finite inputs in this mode
do not automatically stop the decoder. Manual shutdown discards a partial chunk.
Publishing messages during stop is not required.

An empty decoder FIFO returns zero samples without inserting silence.
Inference is synchronous, the FIFO is unbounded, and the message path has no
stream backpressure. Long-running operation and live microphone use are outside
the initial scope. A shared `Codec` class separates inference for future worker
threads. Invalid messages and inference failures are logged, stored in
`decoder.error`, and terminate output. Missing/reordered frames also terminate;
radio pacing and packet-loss concealment are not implemented.

If adding an Audio Sink, check its 24 kHz support. For a 48 kHz device, insert a
Rational Resampler with interpolation 2 and decimation 1. File-only loopback
does not require a Throttle block.

## PMT message format

The loopback now connects Encoder → **SNAC Token File (12-bit)** → Decoder.
Set `token_path` (default `encoded.snac`) to save the intermediate tokens,
packed continuously into 12 bits each, with model/length metadata in a custom gr-snac
container. The file is overwritten on each run. At EOS, `encoded.snac.json`
reports `steady_token_bitrate_bps` (984.375), `token_bitrate_bps` (including final-frame padding) and
`file_bitrate_bps` (actual file bytes including headers, times 8, divided by
original audio duration). Manual stop marks the recording incomplete.

Decode without the input WAV using
`python tools/decode_snac_file.py examples/encoded.snac examples/from_tokens.wav --context-frames 2`.
The same model weights must be available separately; they are not in the file.
The v2 container has no per-frame headers or byte padding; only the last byte
is padded. Its footer stores the original sample count. Legacy v1 files remain
readable; v2 needs the updated tools. Neither context setting duplicates tokens.

Connect the `codes` message ports directly. Messages are native PMT dictionaries,
rather than conventional `(metadata, uniform-vector)` PDU pairs. Message Debug
can inspect them:

```text
{
  metadata: {
    codec: "snac", model: "hubertsiuzdak/snac_24khz",
    sample_rate: 24000, audio_samples: N, stream_mode: "frames-v1",
    encoded_samples: 2048, crop_start: 0,
    chunk_index: 0, chunk_duration_ms: N / 24000 * 1000, num_levels: 3
  },
  level0: u16vector(...),
  level1: u16vector(...),
  level2: u16vector(...)
}
```

Frame messages contain exactly 1/2/4 tokens and `audio_samples=2048` (except the
last partial frame). The decoder constructs overlapping windows from its local
token history. Messages without `stream_mode` retain legacy decoding behavior.
In continuous mode, output waits for the right context; manual shutdown discards
any pending output and look-ahead. Exact `total_samples` flushes all remaining audio.

Tokens are integers from 0 to 4095, stored in 16-bit PMT vectors and packed into
12 bits each when saved to the token file.
`raw_bits = 12 * sum(token_counts)` estimates a future packed payload; it
excludes PMT storage overhead, headers, and FEC.

EOS has the same codec/model/sample-rate/level-count metadata, the next chunk
index, and `eos: true`, without level vectors. The decoder validates metadata,
model identity, u16vector types, token ranges, and hierarchy lengths.

Set `verbose=True` to log token counts, effective bitrate, inference time, and
device per chunk. The encoder also reports clipping. Future Token Packer and
unequal error protection (UEP) blocks can use the preserved levels.

## Tests and validation

```sh
python -m unittest discover -s tests -v
ctest --test-dir build --output-on-failure
# Opt in to weights download/loading and real GNU Radio scheduler tests.
GR_SNAC_MODEL_TESTS=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  python python/gnuradio/snac/qa_snac.py -v
# Optional, on a CUDA-capable installation:
GR_SNAC_MODEL_TESTS=1 GR_SNAC_TEST_DEVICE=cuda python python/gnuradio/snac/qa_snac.py
```

Unit tests cover buffering, invalid inputs, WAV conversion, partial tails, EOS,
and FIFO output. Block unit tests use GNU Radio/PMT and codec test doubles.
Real-model QA checks model loading, 100/200/500/1000 ms encode/decode, token
ranges, finite output, duration, and actual stream-to-message-to-stream
scheduling and termination. Without opt-in, it exits with skip code 77.

Validated on WSL 2 / Ubuntu 22.04 with GNU Radio 3.10.1.1, Python 3.10.12,
PyTorch 2.14.1+cpu, SNAC 1.2.1, NumPy 1.26.4, and SciPy 1.15.3:

- Eight unit tests passed on Windows and WSL.
- CMake installation and two CPU real-model QA tests passed on WSL.
- GRC generated and ran the WAV loopback successfully.
- A 25,003-sample synthetic input retained its 24,000-sample chunk and
  1,003-sample tail, with automatic termination and the same output length.
- The one-second chunk produced [12, 24, 48] tokens, equivalent to 1008 bit/s
  at 12 bits/token.

Listening tests were performed by the author. Audible discontinuities at the
joins motivated the addition of past and future frame context to the current
encoder and decoder. CUDA operation remains unverified.

## References

- [SNAC upstream](https://github.com/hubertsiuzdak/snac)
- [24 kHz model configuration](https://huggingface.co/hubertsiuzdak/snac_24khz/blob/main/config.json)
- [GNU Radio 3.10](https://github.com/gnuradio/gnuradio/tree/maint-3.10)
