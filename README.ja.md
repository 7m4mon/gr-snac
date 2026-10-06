# gr-snac 0.1

[English](README.md) | 日本語

Author: **7M4MON**

Date: **2026-10-06**

GNU Radio 3.10 用の Python OOT モジュールです。24 kHz mono float 音声を
SNAC の3階層の token に変換し、PMT message 経由で復号します。
ファイル保存では12-bit packingに対応します。無線フレーム、FEC、変調、SDR送信は含みません。

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
python /usr/bin/gnuradio-companion examples/snac_loopback.grc
```

入力は**空でない24 kHz mono PCM WAV**としてください。GRC例では `input_path` と
`output_path` を編集します。GRC例は入力の形式を変換しないため、事前に確認してください。
同梱Python例はGRC生成コードで、入力パス等はGRCで設定して再生成します。

Encoder/Decoderの **Context Frames (each side)** は **1または2、初期値2** です。
前後に同じ数のフレームを参照します。0や片側だけの設定はありません。
1フレームは2048サンプル＝85.333 ms。EncoderはPCM履歴を、Decoderは受信済みtokenを
ローカルに保持し、前後の文脈を使って中央フレームを処理します。
送信するのは中央フレームの1/2/4個、計7個の新規tokenだけです。
どちらの設定でも1フレーム84 bit、定常payloadは **984.375 bit/s** です。
末尾の端数フレームはpaddingし、元の長さに切り詰めて復号します。
未来側1/2フレームの待ち時間は各処理段で85.333/170.667 msです。
入力蓄積、送信側と受信側の先読み、推論、通信を含む全体遅延とは異なります。
旧 `chunk_ms` / `context_ms` パラメーターは廃止したためGRCコードを再生成してください。
EncoderとDecoderを両方更新します。独立推論のCLI referenceは比較用として従来どおりです。
全ファイル一括推論と完全に同じ結果や、クリックの完全除去を保証するものではありません。

### 有限入力と終了

`total_samples` を入力の正確な総サンプル数にすると、最後の短いchunkも送信し、
続けてEOS messageを送ります。DecoderはFIFOを排出した後、streamを終了します。
WAV例はヘッダからこの値を設定します。過大な値ではEOSが届かず終了しません。
過小な値では入力が切り詰められます。

`total_samples=0` は連続入力モードです。完全なchunkと必要な右側文脈がそろうと送信します。
GNU Radioのstream EOFはmessageポートへ自動伝搬しないため、このモードで有限入力を
接続してもDecoderは自動終了しません。手動停止時は未完のchunkを破棄します。
停止コールバックからの送信には依存しません。文脈モードでは未出力のlook-ahead部分も手動停止時に破棄します。

DecoderのFIFOが空なら0 samplesを返します。silenceは挿入しません。
初期版は同期推論、FIFOは可変長で上限なし、message経路にはstreamのbackpressureが
ありません。長時間運転や実時間マイク入力は対象外です。
推論処理は共通Codecクラスに分離してあり、後でworker化できます。
不正message・推論エラーはログに記録し、`decoder.error` に保存して出力を終了します。
フレーム欠落・順序違いもエラーとして終了します。無線の欠落補間やペーシングは未実装です。

Audio Sinkを追加する場合は24 kHz対応を確認してください。48 kHz機器なら、
DecoderとAudio Sinkの間にRational Resampler（interpolation=2、decimation=1）を入れます。
ファイル出力だけならThrottleは不要です。

## PMT message形式

### 中間SNACファイルの保存

`snac_loopback.grc` は Encoder → **SNAC Token File (12-bit)** → Decoder の順に接続します。
`token_path`（初期値 `encoded.snac`）へ各tokenを実際に12 bitに詰めて保存し、
EOSでファイルを閉じて `encoded.snac.json` に測定結果を出します。
実行のたびに指定ファイルを上書きします。途中停止は `complete: false` です。

- `steady_token_bitrate_bps`: 定常payloadの984.375 bit/s。
- `token_bitrate_bps`: token数 × 12 ÷ 元の音声秒数。端数の最終フレームのpaddingを含む。
- `file_bitrate_bps`: 実ファイルサイズ × 8 ÷ 元の音声秒数。ヘッダー等を含む。
- `file_bytes` / `payload_bytes` / `overhead_bytes`: 実際のバイト数の内訳。

これはWAVではなく、本プロジェクト独自の `.snac` コンテナです。
v2はモデル情報、連続84-bit payload、末尾の総サンプル数を保存し、
フレームごとのヘッダーやbyte paddingは入れません。最終byteのみ0埋めします。
元の音声なしで以下のように復号できます（同じSNACモデルの重みが必要）。

```sh
python tools/decode_snac_file.py examples/encoded.snac examples/from_tokens.wav --context-frames 2
```

モデルの重み自体はファイルに含みません。文脈の重複送信はありません。
旧v1ファイルも復号できます。v2には更新後のDecoder/ツールが必要です。
GRCの定義を更新するにはインストール後にGRCを開き直してください。

標準の `(metadata, uniform-vector)` PDUペアではなく、次のnative PMT dictionaryです。
`codes` ポート同士を直接接続します。Message Debugでも観測できます。

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

各tokenは0..4095。PMT上では16-bitの入れ物で保持し、ファイル保存時に12-bit packingを行います。
新形式は `stream_mode: "frames-v1"` を持ち、各階層のtoken数は1/2/4個です。
`audio_samples` は通常2048、最後だけ1..2048です。Decoderがtoken履歴を組み立てます。
stream_modeのない旧messageは従来の独立復号として受け付けます。
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

## 2026-10-06 更新：不連続音の改善と検証

従来の1秒（24,000サンプル）ごとの独立encode/decodeでは、文脈が途切れ、
paddingや畳み込みの端の影響で連結境界に段差が生じていました。
現行ブロックは2,048サンプル単位で前後の文脈を参照し、中央フレームだけを
出力します。EncoderはPCM、Decoderは受信済みtokenの履歴を保持します。
`context_frames` は1または2（初期値2）。文脈の重複送信を避け、1フレーム
1/2/4個のtoken、84 bit、定常984.375 bit/sを維持します。
末尾のpaddingは元のサンプル数へ切り詰め、EOS時に残ったフレームを排出します。

### 保存された音声比較・実行結果

検証音源には **JVS（Japanese versatile speech）corpus** を使用しました。
以下は別PCでの検証記録です。今回この環境で再測定した値ではありません。

- 初期の前後500 ms方式では、001の3秒境界の隣接サンプル差が
  0.055756から0.001910、5秒境界が0.068390から0.000853へ減少しました。
  002の2秒境界は0.038910から0.000195へ減少しました。
  これは現行フレーム方式に移行する前の測定です。
  [境界調査](examples/boundary_analysis/README.md)に詳細があります。
- 現行方式と同じ前後2フレームの比較では、001/002とも3階層のtokenが
  全ファイル一括encodeと100%一致しました。一括復号との波形RMSEは
  それぞれ0.001358 / 0.001011でした。
  [比較結果](examples/frame_context/comparison.json)と
  [実験条件](examples/frame_context/README.md)を参照してください。
- 更新後のGRC生成コードを実GNU Radio schedulerで実行した記録では、
  001の206,905サンプルを102フレーム・714 tokenとして保存しました。
  v2ファイルは1,214 bytes（payload 1,071 bytes、その他143 bytes）です。
  保存tokenだけから元と同じ206,905サンプルを復号し、EOS終了を確認しています。
  [実行結果](examples/frame_stream_check/README.md)を参照してください。

境界差やtoken一致率だけでは聴感上の音質を評価できません。モデルのNoiseBlockは
推論時にも乱数を使うため、tokenが一致しても波形の完全一致は要求しません。
クリックの完全除去、他の音声での同じ結果、実時間無線での動作は未確認です。
旧500 ms方式の記録にある設定名・伝送量は当時の値で、現行設定には適用しません。

### 追加・更新したテスト

- `tests/test_context.py`: 不規則な入力分割、短い末尾、未来文脈の待機、
  出力サンプルの欠落・重複がないことと保持バッファの上限。
- `tests/test_blocks.py`: Encoder/Decoderの文脈1/2の全組合せで正確な出力時系列、
  1/2/4 tokenのみの送信、設定値の検証、フレーム欠落の拒否、EOSとFIFO排出、
  tokenファイル保存後のmessage転送。
- `tests/test_token_file.py`: 12-bit全値の往復、奇数tokenと既知のbit列、
  v2のフレームをまたぐpacking、端数末尾の保持、v1読み込み、切断ファイルの拒否、
  途中停止の不完全扱い。
- 実モデルQAは3件に拡張。encode/decodeに加え、文脈1/2それぞれの
  実scheduler接続・保存・復号・自動終了を検証します。25,003サンプルの入力に対し、
  13フレーム・91 tokenと元の出力長を確認する構成です。

単体テストと実モデルQAの実行コマンドは上記「テスト」のとおりです。
音声比較はモデルと入力WAVを用意したWSL環境で実行できます。

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 python tools/compare_frame_context.py
```

`HF_HUB_OFFLINE=1` はモデルがキャッシュ済みの場合に使用してください。
今回のWindows環境では `python -m unittest discover -s tests -v` を試しましたが、
NumPy未導入により4つのテストモジュールのimportで停止しました。
現行テスト一式の成功件数および実モデルQA 3件の再実行結果は未確認です。

## 参照

- [SNAC upstream](https://github.com/hubertsiuzdak/snac)
- [24 kHz model configuration](https://huggingface.co/hubertsiuzdak/snac_24khz/blob/main/config.json)
- [GNU Radio 3.10](https://github.com/gnuradio/gnuradio/tree/maint-3.10)

将来のToken PackerやUEPは、保持した3階層の後段に別ブロックとして追加する想定です。
