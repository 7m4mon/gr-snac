# gr-snac 0.1

English | [日本語](README.ja.md)

Author: **7M4MON**

Date: **2026-10-06**

Python out-of-tree (OOT) blocks for GNU Radio 3.10 that encode 24 kHz mono
float audio into SNAC tokens and decode them back to audio. All three token
levels remain separate in native PMT messages.

Version 0.1 includes encoder and decoder blocks, GNU Radio Companion (GRC)
definitions, WAV loopback examples, standalone token measurements, and tests.
Radio framing, FEC, modulation, and SDR transmission are outside
its scope.

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

CUDA operation and listening tests remain unverified.

## 2026-10-06 update: boundary discontinuities and tests

The previous independent one-second (24,000-sample) encode/decode calls lost
context at each join, exposing padding and convolution edge effects. The
current blocks process 2,048-sample frames with past and future context and
retain only the central output frame. The encoder keeps PCM history and the
decoder keeps received tokens. `context_frames` accepts 1 or 2, defaulting to 2.
Only 1/2/4 new tokens cross the message boundary per frame: 84 bits and a steady
984.375 bit/s, without retransmitting context. Final padding is cropped to the
original sample count, and EOS flushes pending frames.

### Recorded audio comparisons and scheduler verification

The test audio was taken from the **JVS (Japanese versatile speech) corpus**.
These results were recorded on another PC; they were not remeasured here.

- The earlier 500 ms context prototype reduced adjacent-sample differences at
  the 001 recording's 3-second boundary from 0.055756 to 0.001910 and its
  5-second boundary from 0.068390 to 0.000853. The 002 recording's 2-second
  boundary decreased from 0.038910 to 0.000195. These measurements predate the
  current frame implementation; see the [boundary investigation](examples/boundary_analysis/README.md).
- With two frames of context on each side, the offline comparison matched
  whole-file encoding tokens at all three levels for both 001 and 002 (100%).
  Waveform RMSE against whole-file decoding was 0.001358 and 0.001011,
  respectively. See the [comparison data](examples/frame_context/comparison.json)
  and [experiment conditions](examples/frame_context/README.md).
- The updated GRC-generated flowgraph ran with the real GNU Radio scheduler.
  Recording 001 retained 206,905 samples in 102 frames / 714 tokens. Its v2
  file occupied 1,214 bytes: 1,071 payload bytes and 143 overhead bytes.
  Decoding the saved tokens alone retained all 206,905 samples and terminated
  at EOS. See the [scheduler verification](examples/frame_stream_check/README.md).

Boundary differences and token agreement do not establish perceptual quality.
The model's NoiseBlock uses randomness during inference, so identical tokens
need not produce identical waveforms. Complete click removal, the same results
on other recordings, and real-time radio operation remain unverified. Parameter
names and transmission sizes in the older 500 ms reports describe that prototype.

### Added and updated test coverage

- `tests/test_context.py`: irregular input sizes, short tails, future-context
  waiting, exact sample retention, and bounded context buffers.
- `tests/test_blocks.py`: all encoder/decoder context 1/2 combinations,
  sample-exact output timelines, 1/2/4 transmitted tokens, parameter validation,
  missing-frame rejection, EOS/FIFO draining, and forwarding after token storage.
- `tests/test_token_file.py`: all 12-bit values, odd token counts and known bit
  patterns, v2 packing across frame boundaries, partial tails, v1 reading,
  truncated-file rejection, and incomplete manual stops.
- Real-model QA now contains three tests, including real scheduler recording,
  decoding, and automatic termination with both context settings. The
  25,003-sample fixture checks 13 frames / 91 tokens and the original output length.

Use the commands in Tests above for unit and real-model QA. With the model and
input WAVs available in WSL, reproduce the audio comparison with:

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 python tools/compare_frame_context.py
```

Use `HF_HUB_OFFLINE=1` only with cached model weights. During this README update,
`python -m unittest discover -s tests -v` stopped while importing all four test
modules because this Windows Python environment lacks NumPy. The current suite's
pass count and a rerun of all three real-model QA tests remain unverified.

## References

- [SNAC upstream](https://github.com/hubertsiuzdak/snac)
- [24 kHz model configuration](https://huggingface.co/hubertsiuzdak/snac_24khz/blob/main/config.json)
- [GNU Radio 3.10](https://github.com/gnuradio/gnuradio/tree/maint-3.10)
