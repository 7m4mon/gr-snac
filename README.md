# gr-snac

English | [日本語](README.ja.md)

Author: **7M4MON**

<img width="1112" height="452" alt="Image" src="https://github.com/user-attachments/assets/ec9445ca-3ec1-4d83-af7b-179f3f53282b" />
<img width="1209" height="933" alt="Image" src="https://github.com/user-attachments/assets/de563323-6855-47d7-8ae9-c00291b3f3e0" />  
<img width="1141" height="665" alt="Image" src="https://github.com/user-attachments/assets/444401e2-a107-4514-9021-52e405e111cd" />  
<img width="1600" height="869" alt="Image" src="https://github.com/user-attachments/assets/5c448947-ce11-4935-9556-02df70dcdafa" />  

SNAC encoder/decoder blocks for GNU Radio 3.10 and an experimental narrowband digital speech modem.
The codec takes 24 kHz mono audio, preserves three token levels, and supports 12-bit packed token files.
The modem examples connect WAV → SNAC → framing/FEC/interleaving/whitening → Gaussian 4CPFSK → IQ,
and saved IQ → frame decoding → SNAC → WAV. SDR operation and live microphone input are not implemented.

## Modem design and results

| Item | Setting |
|---|---|
| Speech frame | 2048 samples at 24 kHz, 85.333 ms |
| Payload | 1/2/4 tokens × 12 bit = 84 bit, 984.375 bit/s |
| Sequence / flags / CRC | 6 / 2 / 12 bit, CRC-12/DECT |
| FEC | K=7, rate 1/2, tail-biting, polys=[109,79], 104 → 208 bit |
| Interleaving / whitening | 16×13 matrix; nine-bit LFSR reset every coded frame |
| Sync | 8 dibits, excluded from whitening |
| Radio rate | 112 symbols/frame, 1312.5 symbols/s, 2625 bit/s including sync |
| Modulation | Gaussian 4CPFSK, h=0.25, BT=0.30, L=4, SPS=32, Fs=42 kHz |

A 43.1-second speech test recovered 506 frames with no decoded-bit/token errors or CRC failures,
preserving the exact audio length. This is finite-file IQ reception without frequency or clock mismatch;
the receiver uses a JSON sidecar for frame counts and valid audio length.
RF operation, noise BER/FER, fading, adjacent-channel interference and continuous reception are untested.

At the default settings, framed random-payload waveforms measured 1370.9 Hz OBW99 and 1837.1 Hz OBW99.9.
ACPR at 2.5 kHz spacing was −46.62 dB on the worse side. These spectral measurements do not establish
radio-link performance or compliance with a channel mask.

See the [modem README](examples/narrowband_4cpfsk/README.md) for commands, measurement definitions and limitations.
Use [snac_loopback.grc](examples/snac_loopback.grc) for codec-only processing, or the
[WAV transmitter](examples/narrowband_4cpfsk/wav_snac_4cpfsk.grc) and
[IQ receiver](examples/narrowband_4cpfsk/receive_snac_4cpfsk.grc) for the modem experiment.

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
Zero/one-sided context is not supported. The standalone reference CLI uses independent chunks for comparison.
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
the supported scope. A shared `Codec` class separates inference for future worker
threads. Invalid messages and inference failures are logged, stored in
`decoder.error`, and terminate output. Missing/reordered frames also terminate;
radio pacing and packet-loss concealment are not implemented.

If adding an Audio Sink, check its 24 kHz support. For a 48 kHz device, insert a
Rational Resampler with interpolation 2 and decimation 1. File-only loopback
does not require a Throttle block.

## PMT message format

The loopback connects Encoder → **SNAC Token File (12-bit)** → Decoder.
Set `token_path` (default `encoded.snac`) to save the intermediate tokens,
packed continuously into 12 bits each, with model/length metadata in a custom gr-snac
container. The file is overwritten on each run. At EOS, `encoded.snac.json`
reports `steady_token_bitrate_bps` (984.375), `token_bitrate_bps` (including final-frame padding) and
`file_bitrate_bps` (actual file bytes including headers, times 8, divided by
original audio duration). Manual stop marks the recording incomplete.

Decode without the input WAV using
`python tools/decode_snac_file.py examples/encoded.snac examples/from_tokens.wav --context-frames 2`.
The same model weights must be available separately; they are not in the file.
The token container packs payload continuously with no per-frame headers or byte padding; only the last byte is padded. Its footer stores the original sample count. Neither context setting duplicates tokens.

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
token history. In continuous mode, output waits for the right context; manual shutdown discards
any pending output and look-ahead. Exact `total_samples` flushes all remaining audio.

Tokens are integers from 0 to 4095, stored in 16-bit PMT vectors and packed into
12 bits each when saved to the token file.
`raw_bits = 12 * sum(token_counts)` estimates a future packed payload; it
excludes PMT storage overhead, headers, and FEC.

EOS has the same codec/model/sample-rate/level-count metadata, the next chunk
index, and `eos: true`, without level vectors. The decoder validates metadata,
model identity, u16vector types, token ranges, and hierarchy lengths.

Set `verbose=True` to log token counts, effective bitrate, inference time, and
device per chunk. The encoder also reports clipping.

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

Unit tests cover invalid inputs, WAV conversion, frame processing, partial tails, EOS and FIFO output.
Real-model QA checks loading, reconstruction, output length and termination under the GNU Radio scheduler.
Validation used CPU on GNU Radio 3.10.1.1 / Ubuntu 22.04 under WSL 2. CUDA operation remains unverified.
See [frame_context](examples/frame_context/README.md) for context comparisons and
[frame_stream_check](examples/frame_stream_check/README.md) for current token-file measurements.

## References

- [SNAC upstream](https://github.com/hubertsiuzdak/snac)
- [24 kHz model configuration](https://huggingface.co/hubertsiuzdak/snac_24khz/blob/main/config.json)
- [GNU Radio 3.10](https://github.com/gnuradio/gnuradio/tree/maint-3.10)
