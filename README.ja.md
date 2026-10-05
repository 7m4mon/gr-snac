# gr-snac 0.1

[English](README.md) | 日本語

Author: **7M4MON**

Date: **2026-10-05**

GNU Radio 3.10 用の Python OOT モジュールです。24 kHz mono float 音声を
SNAC の3階層の token に変換し、PMT message 経由で復号します。
無線フレーム、12-bit packing、FEC、変調、SDR送信は含みません。

## Windowsでの利用（WSL 2）

WSL 2のUbuntu 22.04で動作確認しています。GNU RadioとPython環境はUbuntu内に
インストールしてください。Windows側の仮想環境とは共有しません。
以下ではリポジトリを `~/src/gr-snac` にcloneしたものとします。

PowerShellからUbuntuに入ります。

```powershell
wsl -d Ubuntu-22.04
```

Ubuntu内で初回セットアップを実行します。

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

次回以降は以下で起動できます。

```sh
cd ~/src/gr-snac
source tools/activate-wsl.sh
python /usr/bin/gnuradio-companion examples/snac_loopback.grc
```

GRCには使用するWAVのパスを設定してください。WSLgを利用してGUIを表示できます。
`python /usr/bin/gnuradio-companion` とすることで、仮想環境のPythonを使用します。
ソース変更後は `cmake --install build-wsl` でインストール済みのブロックを更新します。

CPUの実モデル検証は次で実行できます（初回はモデルを取得します）。

```sh
GR_SNAC_MODEL_TESTS=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  python python/gnuradio/snac/qa_snac.py -v
```

## Linuxへのインストール

GNU Radio 3.10、開発用 CMake 設定、Python 3.10 以降が必要です。
Debian/Ubuntu 系では、例として次を使用します。

```sh
sudo apt install gnuradio gnuradio-dev cmake g++ python3-venv
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install 'numpy>=1.23,<2' -r requirements.txt
cmake -S . -B build -DCMAKE_INSTALL_PREFIX="$VIRTUAL_ENV" \
  -DPYTHON_EXECUTABLE="$VIRTUAL_ENV/bin/python"
cmake --build build
cmake --install build
export PYTHONPATH="$VIRTUAL_ENV/lib/python$(python -c 'import sys; print("%d.%d" % sys.version_info[:2])')/site-packages:$PYTHONPATH"
export GRC_BLOCKS_PATH="$VIRTUAL_ENV/share/gnuradio/grc/blocks${GRC_BLOCKS_PATH:+:$GRC_BLOCKS_PATH}"
python -c 'from gnuradio import snac; print(snac.snac_encoder)'
python /usr/bin/gnuradio-companion examples/snac_loopback.grc
```

GNU Radio と同じ Python minor version を使ってください。ディストリビューションによって
`GR_PYTHON_DIR` を明示する必要があります。通常のシステムインストールも可能です。
GRCは上記環境変数を設定したシェルから起動してください。
上記はCPU版の例です。GNU Radio 3.10.1の配布バイナリとの互換性のためNumPyは2未満に
制限しています。CUDAを使用する場合は環境に対応するPyTorchビルドを選択してください。

ブロックは `from gnuradio import snac` で使用します。モデルライブラリは
`from snac import SNAC` です。名前衝突を避けるため、ソースを
`python/gnuradio/snac/` に置き、独立した処理を `python/gr_snac_core/` に分けています。
GNU Radioの `gnuradio` パッケージは追加パスを認識する構成が必要です。
仮想環境から上記importが失敗する場合は、GNU Radioと同じPythonのインストール先に
`-DGR_PYTHON_DIR=/path/to/site-packages` を指定してインストールしてください。

## モデルとデバイス

デフォルトは `hubertsiuzdak/snac_24khz`。24 kHz、3階層、codebook size 4096
を実行時に確認します。初回はインターネット接続が必要になる場合があります。
以後は SNAC / Hugging Face のキャッシュを使います。各ブロック生成時に一度だけ
モデルをロードし、chunkごとにはロードしません。EncoderとDecoderは別インスタンスです。

`device=auto` はCUDAが利用可能ならCUDA、その他はCPUです。`cpu` はCPU固定、
`cuda` はCUDA必須で、利用できなければ明確な例外を出します。
Python APIのデフォルトはauto、GRCとloopback例はCPUです。
推論は `torch.inference_mode()` で実行します。

## GNU Radioに依存しない確認

```sh
python tools/snac_token_info.py speech.wav --device cpu --chunk-ms 1000
python examples/snac_reference.py speech.wav reconstructed.wav --device cpu --chunk-ms 1000
```

WAVは整数PCMをfloat32へ変換し、stereoは平均してmono化、必要なら
`scipy.signal.resample_poly` で24 kHzに変換します。peak normalizeはしません。
入力は[-1, 1]にclipし、NaN/Infや空入力は拒否します。
出力WAVは24 kHz mono PCM16です。
各chunkと合計のtoken数、12 bit/token換算のbit数、元の音声長で割ったbitrate、
処理時間、RTF（処理秒数 / 音声秒数）をJSONで表示します。
モデルロードとWAV I/Oの時間はRTFに含みません。CUDAでは計測の前後に同期します。

## WAV loopback

```sh
python examples/snac_loopback.py input.wav output.wav --device cpu --chunk-ms 1000
```

入力は**空でない24 kHz mono PCM WAV**としてください。GRC例では `input_path` と
`output_path` を編集します。GRC例は入力の形式を変換しないため、事前に確認してください。
Python例は入力のチャンネル数とサンプルレートをチェックします。

Encoderの `chunk_ms` は標準1000、100/200/500/1000など、1サンプル以上に丸められる
任意の正の有限値を指定できます。`round(24000 * chunk_ms / 1000)` で処理します。
実際に返されたtoken数を使用し、階層ごとの数を固定しません。
SNACは内部で入力をパディングするため、短いchunkでは実効bitrateが増えます。
Decoderは `audio_samples` を使ってパディング部分を削り、元の長さに戻します。
chunkは独立推論なので境界で音の不連続が起こり得ます。低遅延や音質は未評価です。

### 有限入力と終了

`total_samples` を入力の正確な総サンプル数にすると、最後の短いchunkも送信し、
続けてEOS messageを送ります。DecoderはFIFOを排出した後、streamを終了します。
WAV例はヘッダからこの値を設定します。過大な値ではEOSが届かず終了しません。
過小な値では入力が切り詰められます。

`total_samples=0` は連続入力モードです。完全なchunkだけを送信します。
GNU Radioのstream EOFはmessageポートへ自動伝搬しないため、このモードで有限入力を
接続してもDecoderは自動終了しません。手動停止時は未完のchunkを破棄します。
停止コールバックからの送信には依存しません。

DecoderのFIFOが空なら0 samplesを返します。silenceは挿入しません。
初期版は同期推論、FIFOは可変長で上限なし、message経路にはstreamのbackpressureが
ありません。長時間運転や実時間マイク入力は対象外です。
推論処理は共通Codecクラスに分離してあり、後でworker化できます。
不正message・推論エラーはログに記録し、`decoder.error` に保存して出力を終了します。
Python loopbackは終了後にそのエラーを例外化します。

Audio Sinkを追加する場合は24 kHz対応を確認してください。48 kHz機器なら、
DecoderとAudio Sinkの間にRational Resampler（interpolation=2、decimation=1）を入れます。
ファイル出力だけならThrottleは不要です。

## PMT message形式

標準の `(metadata, uniform-vector)` PDUペアではなく、次のnative PMT dictionaryです。
`codes` ポート同士を直接接続します。Message Debugでも観測できます。

```text
{
  metadata: {
    codec: "snac", model: "hubertsiuzdak/snac_24khz",
    sample_rate: 24000, audio_samples: N,
    chunk_index: 0, chunk_duration_ms: N / 24000 * 1000, num_levels: 3
  },
  level0: u16vector(...),
  level1: u16vector(...),
  level2: u16vector(...)
}
```

各tokenは0..4095。16-bitの入れ物で保持しますが12-bit packingは行いません。
`raw_bits = 12 * sum(token_counts)` は通信上の仮想的なpayload bit数です。
PMTメモリ量、ヘッダ、将来のFEC等は含みません。
EOSは同じcodec/model/sample_rate/num_levelsと次のchunk_indexを持つmetadataに
`eos: true` を加え、level配列は持ちません。
Decoderはmodel一致、metadata、u16vector型、token範囲、モデルの階層長整合性を検証します。

`verbose=True` でchunkごとのtoken数、実効bitrate、処理時間、deviceをログに出します。
Encoderはclip発生も通知します。

## テスト

```sh
python -m unittest discover -s tests -v
ctest --test-dir build --output-on-failure
# モデル取得を許可して、実モデルと実際のGNU Radio schedulerを試す
GR_SNAC_MODEL_TESTS=1 python python/gnuradio/snac/qa_snac.py
# CUDA環境では追加で
GR_SNAC_MODEL_TESTS=1 GR_SNAC_TEST_DEVICE=cuda python python/gnuradio/snac/qa_snac.py
```

通常のQAはchunk処理、不正入力、WAV変換、末尾・EOS・FIFOを検証します。
ブロック単体テストはGNU Radio/PMTとCodecのテストダブルを使います。
実モデルQAはmodel load、100/200/500/1000 msのencode/decode、token範囲、
有限な出力、復元長、および実際のstream→message→stream接続と自動終了を確認します。
明示的に有効化しない場合は終了コード77でskipします。

検証環境はWSL 2 / Ubuntu 22.04、GNU Radio 3.10.1.1、Python 3.10.12、
PyTorch 2.14.1+cpu、SNAC 1.2.1、NumPy 1.26.4、SciPy 1.15.3です。
WindowsとWSLの両方で8件の単体テストに成功しました。WSLではさらにCMakeインストール、
実モデルCPU QA 2件、GRCによるコード生成とWAVループバック実行に成功しました。
25,003サンプルのsynthetic audioを使い、24,000サンプルと末尾1,003サンプルの
両chunkの復号と自動終了を確認しました。1秒chunkのtoken数は[12,24,48]、
12 bit/token換算で1008 bit/sでした。CUDA動作と音声の聴感確認は未実施です。

## 参照

- [SNAC upstream](https://github.com/hubertsiuzdak/snac)
- [24 kHz model configuration](https://huggingface.co/hubertsiuzdak/snac_24khz/blob/main/config.json)
- [GNU Radio 3.10](https://github.com/gnuradio/gnuradio/tree/maint-3.10)

将来のToken PackerやUEPは、保持した3階層の後段に別ブロックとして追加する想定です。
