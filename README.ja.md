# gr-snac 0.1

[English](README.md) | 日本語

Author: **7M4MON**

Date: **2026-10-05**

GNU Radio 3.10 用の Python OOT モジュールです。24 kHz mono float 音声を
SNAC の3階層の token に変換し、PMT message 経由で復号します。
ファイル保存では12-bit packingに対応します。Codec OOT本体とは別に、標準ブロックで
構成したGaussian 4CPFSKのGRC波形評価例を追加しています。
無線フレーム生成、FEC、Codecから変調器への接続、SDR送信は未実装です。

## SNACを無線に載せるためのフレーム案と評価結果（2026-10-06）

SNACのtokenを12 bitで詰めると、2048音声サンプル（85.333… ms）ごとに
1/2/4個、合計7個のtoken＝84 bitになります。定常ペイロード速度は
984.375 bit/sです。この単位を1無線フレームのペイロードとして扱い、
同期・誤り検出・誤り訂正の分を加えて必要な変調速度を求めました。

| 段階 | 内容 | 長さ |
|---|---|---:|
| Codec payload | 7 tokens × 12 bit | 84 bit |
| 管理情報 | Sequence / Flags | 8 bit |
| 誤り検出 | CRC-12（方式詳細は未定） | 12 bit |
| FEC入力 | 上記の合計 | 104 bit |
| FEC出力 | rate 1/2、追加終端ビットなしと仮定 | 208 bit |
| 4値変調 | 2 bit/symbol | 104 symbols |
| 同期 | Mini Sync（仮置き） | 8 symbols |
| 合計 | 85.333… msごとの無線フレーム案 | 112 symbols |

したがって必要なシンボルレートは112 / (2048 / 24000) = **1312.5 sym/s**です。
同期区間も2 bit/symbolとして数えた総伝送速度は2625 bit/s、FEC出力データ部分は
2437.5 bit/sです。これはフレーム設計上の収支であり、現在のGRCが実際に
CRC・FEC・同期語を挿入しているわけではありません。

次に、この速度で2.5 kHz、可能なら2.0 kHzのチャネル間隔を狙えるかを調べるため、
Gaussian-shaped 4CPFSKを選びました。周波数偏移をGaussianパルスで整形してから
位相へ変換し、各キャリアの定包絡性を保ちます。最終IQへの帯域制限LPFは使いません。
標準のCPMブロックが4値入力・Gaussianパルス・変調指数hに対応していたため、
独自の変調OOTやEmbedded Pythonブロックは作らず、標準ブロックを組み合わせました。

初期値はh=0.25、BT=0.30、パルス長L=4、32 samples/symbol、Fs=42000 Hzです。
定常周波数は±164.0625 Hzと±492.1875 Hzを狙います。SNAC実データとの接続は
後段に回し、まず同一seedの乱数データでh×BTの12条件を比較しました。
単一キャリアのPSD・OBW・ACPRを測定し、別seedの3キャリアを加算するGRCも作成して、
2.0 / 2.5 kHz間隔で起動・IQ保存を確認しました。

GNU Radio 3.10.1.1 / Ubuntu 22.04 (WSL)、60秒のIQ、先頭0.1秒除外、
8192点Blackman-Harris窓のWelch法による初期値の結果は次のとおりです。

| 指標 | 結果 |
|---|---:|
| 99% occupied bandwidth | 1379.6 Hz |
| 99.9% occupied bandwidth | 1829.6 Hz |
| 2.0 kHz間隔 ACPR（下側／上側） | -36.45 / -36.43 dB |
| 2.5 kHz間隔 ACPR（下側／上側） | -46.63 / -46.60 dB |

ACPRはチャネル間隔と同じ幅の矩形帯域を積分した隣接／主チャネル電力比です。
初期値はスペクトル面では両方の間隔の候補となり、2.5 kHz間隔の方が隣接帯域への
漏洩が少ない結果でした。ただし合否基準となるマスクは設定しておらず、
BER、受信同期、周波数誤差、隣接局との電力差、実RFでの成立性は未評価です。
hやBTを小さくして狭帯域化できても、受信性能が良くなるとは限りません。

フレーム案も今後の検証が必要です。例えば拘束長7の畳み込み符号に6個の終端入力
ビットを追加すると、220 coded bits + 8 sync symbols = 118 symbolsとなり、
必要レートは1382.8125 sym/sへ増えます。8 symbolsのMini Syncも捕捉性能を
保証するものではありません。実フレーム化の際は符号方式・終端方法・同期列を決め、
フレーム境界で位相とGaussianフィルタの状態を維持した波形を再評価します。

実行方法、測定定義、12条件の結果は
[4CPFSK評価例のREADME](examples/narrowband_4cpfsk/README.md)を参照してください。
GRCは[単一キャリア](examples/narrowband_4cpfsk/narrowband_4cpfsk.grc)と
[3キャリア](examples/narrowband_4cpfsk/three_carriers.grc)を用意しています。

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
12 bit/token換算で1008 bit/sでした。著者による音声の聴感確認は実施済みです。
連結境界の不連続音を実際に確認したことが、現行Encoder/Decoderに前後フレームの
文脈を追加した理由です。CUDA動作は未確認です。

## 参照

- [SNAC upstream](https://github.com/hubertsiuzdak/snac)
- [24 kHz model configuration](https://huggingface.co/hubertsiuzdak/snac_24khz/blob/main/config.json)
- [GNU Radio 3.10](https://github.com/gnuradio/gnuradio/tree/maint-3.10)

将来のToken PackerやUEPは、保持した3階層の後段に別ブロックとして追加する想定です。
