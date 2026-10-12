# gr-snac

[English](README.md) | 日本語

Author: **7M4MON**

<img width="1112" height="452" alt="Image" src="https://github.com/user-attachments/assets/ec9445ca-3ec1-4d83-af7b-179f3f53282b" />  
<img width="1209" height="933" alt="Image" src="https://github.com/user-attachments/assets/de563323-6855-47d7-8ae9-c00291b3f3e0" />  
<img width="1141" height="665" alt="Image" src="https://github.com/user-attachments/assets/444401e2-a107-4514-9021-52e405e111cd" />  
<img width="1600" height="869" alt="Image" src="https://github.com/user-attachments/assets/5c448947-ce11-4935-9556-02df70dcdafa" />  

GNU Radio 3.10用のSNAC Encoder / Decoderと、狭帯域デジタル音声モデムの実験例です。
24 kHz mono音声を3階層のtokenに変換し、12-bit packingで保存できます。
モデム例はWAV → SNAC → CRC/FEC・インターリーブ・ホワイトニング → Gaussian 4CPFSK → IQ保存、
および保存IQ → フレーム復号 → SNAC → WAV復元までを扱います。
SDR送受信や実時間マイク入力は未実装です。

## モデム例の設計と結果

| 項目 | 設定 |
|---|---|
| 音声単位 | 2048 samples / 24 kHz = 85.333 ms |
| ペイロード | 1/2/4 token × 12 bit = 84 bit、984.375 bit/s |
| 管理情報・CRC | Sequence 6 bit、Flags 2 bit、CRC-12/DECT 12 bit |
| FEC | K=7、rate 1/2、tail-biting、polys=[109,79]、104 → 208 bit |
| インターリーブ | 16×13、フレーム内 |
| ホワイトニング | 9-bit LFSR、mask=0x21、seed=0x1FF、len=8、208 bitごとにリセット |
| 同期語 | 8 dibits [0,3,1,0,2,1,3,2]、ホワイトニング対象外 |
| 無線フレーム | 112 symbols、1312.5 symbols/s、同期込み2625 bit/s |
| 変調 | Gaussian 4CPFSK、h=0.25、BT=0.30、L=4、SPS=32、Fs=42 kHz |

約43.1秒の音声を506フレームで送受信し、復号後bit / token誤り0、CRC失敗0、元と同じ音声長を確認しました。
試験は周波数・クロック偏差なしの有限IQファイルで、音声長などの情報には付属JSONを使います。
実RF、雑音下のBER/FER、フェージング、隣接干渉、連続受信は未評価です。

乱数payloadのフレーム波形では、初期設定の99% OBWは1370.9 Hz、99.9% OBWは1837.1 Hzでした。
2.5 kHz間隔のACPRは上下の悪い側で−46.62 dBです。帯域評価は実リンクの成立や規格適合を示しません。

使い方・測定条件・検証コマンドは[モデム例のREADME](examples/narrowband_4cpfsk/README.md)を参照してください。
音声ブロック単体は[snac_loopback.grc](examples/snac_loopback.grc)、
モデムは[送信GRC](examples/narrowband_4cpfsk/wav_snac_4cpfsk.grc)と[受信GRC](examples/narrowband_4cpfsk/receive_snac_4cpfsk.grc)で試せます。

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
独立推論のCLI referenceは比較用です。
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
推論は同期処理、FIFOは可変長で上限なし、message経路にはstreamのbackpressureが
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
保存形式はモデル情報、連続84-bit payload、末尾の総サンプル数を保存し、
フレームごとのヘッダーやbyte paddingは入れません。最終byteのみ0埋めします。
元の音声なしで以下のように復号できます（同じSNACモデルの重みが必要）。

```sh
python tools/decode_snac_file.py examples/encoded.snac examples/from_tokens.wav --context-frames 2
```

モデルの重み自体はファイルに含みません。文脈の重複送信はありません。
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
フレームmessageは `stream_mode: "frames-v1"` を持ち、各階層のtoken数は1/2/4個です。
`audio_samples` は通常2048、最後だけ1..2048です。Decoderがtoken履歴を組み立てます。
`raw_bits = 12 * sum(token_counts)` は通信上の仮想的なpayload bit数です。
PMTメモリ量、ヘッダー、FEC等は含みません。
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

単体テストは不正入力、WAV変換、フレーム処理、末尾、EOS、FIFOを確認します。
実モデルQAはモデル読み込みとGNU Radio schedulerでの復号・出力長・有限終了を検証します。
検証環境はWSL 2 / Ubuntu 22.04、GNU Radio 3.10.1.1、CPUです。CUDA動作は未確認です。
音声文脈の比較は[frame_context](examples/frame_context/README.md)、
現行token保存の結果は[frame_stream_check](examples/frame_stream_check/README.md)を参照してください。

## 参照

- [SNAC upstream](https://github.com/hubertsiuzdak/snac)
- [24 kHz model configuration](https://huggingface.co/hubertsiuzdak/snac_24khz/blob/main/config.json)
- [GNU Radio 3.10](https://github.com/gnuradio/gnuradio/tree/maint-3.10)
