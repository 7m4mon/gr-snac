# SNAC Gaussian 4CPFSK modem experiment

SNAC音声を無線フレームへ詰め、Gaussian 4CPFSKで変調し、保存IQから音声へ戻すGNU Radioの実験例です。
FEC、インターリーブ、ホワイトニング、変調、周波数復調、FIR等化には標準ブロックを使います。
独自処理は情報ビット・CRCの組立て、有限captureの同期捕捉、フレームとtokenの変換です。
SDR送受信、スピーカー出力、ライブ音声には対応していません。

## フローグラフ

| GRC | 用途 |
|---|---|
| [wav_snac_4cpfsk.grc](wav_snac_4cpfsk.grc) | WAV → SNAC → 無線フレーム → IQ保存 |
| [receive_snac_4cpfsk.grc](receive_snac_4cpfsk.grc) | 保存IQ → フレーム復号 → SNAC → WAV保存 |
| [framed_4cpfsk.grc](framed_4cpfsk.grc) | 乱数payloadの単一キャリア評価 |
| [three_carriers_framed.grc](three_carriers_framed.grc) | 別seedのpayloadを使う3キャリア評価 |
| [narrowband_4cpfsk.grc](narrowband_4cpfsk.grc) / [three_carriers.grc](three_carriers.grc) | 無構造乱数との比較 |

## 設計

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

情報ビットはPayload → Sequence → Flags → CRCの順、MSB first、byte paddingなしです。
CRCは直前92 bitを保護し、poly=0x80F、init=0、refin/refout=false、xorout=0です。
Sequenceは63→0に折り返し、Flagsの用途は未割当です。
Gray Mapは00→−3、01→−1、10→+3、11→+1。CPMの位相とフィルタ状態はフレーム間で連続させます。
capture末尾にだけL symbolsの0レベルを加え、Gaussian応答を排出します。
メタデータのformatは`snac-radio-experimental-v2`。これは保存形式の識別子で、オンエアの版識別はありません。

受信はQuadrature Demod → 9-symbol FIR等化 → 同期捕捉・4値判定 → 同期除去 →
ホワイトニング解除 → デインターリーブ → tail-biting FEC復号 → CRC/Sequence確認 → SNAC Decoderです。
同期捕捉は有限capture全体を保持し、32通りのサンプル位相とフレーム位置を探索します。
音声長・予定フレーム数・開始SequenceはIQに付属するJSONから取得します。
送信token、元音声、乱数seedは受信処理に使いません。

## 音声の送受信

既存SNAC OOTとモデル用Python環境が必要です。入力は空でない24 kHz mono整数PCM WAVです。
`repeat_count=5`は合計5回の再生を意味し、無音を挟まず連結してからSNACへ渡します。

リポジトリ直下から起動します。

```sh
source tools/activate-wsl.sh
cd examples/narrowband_4cpfsk
python /usr/bin/gnuradio-companion wav_snac_4cpfsk.grc
```

`input_path`、`repeat_count`、`iq_path`を設定してGenerate / Executeします。
送信が完了してIQ保存が確定したら、受信GRCを起動します。

```sh
python /usr/bin/gnuradio-companion receive_snac_4cpfsk.grc
```

受信の初期値は`iq_path=wav_snac_4cpfsk.cf32`、`wav_path=received_snac.wav`です。
IQと`IQパス + '.frames.json'`を同じ場所に置いてください。別の作業ディレクトリから使う場合は絶対パスを指定します。
生成Pythonを直接使う場合：

```sh
python /usr/bin/grcc -o . wav_snac_4cpfsk.grc receive_snac_4cpfsk.grc
python wav_snac_4cpfsk.py --input-path /absolute/path/voice.wav --repeat-count 5
python receive_snac_4cpfsk.py --iq-path /absolute/path/capture.cf32 --wav-path /absolute/path/received.wav
```

補助コードはGRCに埋め込まれています。生成Pythonを別フォルダーへコピーする場合は、同時生成された補助Pythonも含めます。

送信はIQ（ヘッダーなしcomplex64）、変調前dibit、`.frames.json`、`.audio.json`を保存します。
受信は24 kHz mono PCM16 WAVと`.sync.json`、`.frames.json`、`.rx.json`を保存します。
正常完了は受信`.rx.json`の`complete=true`と保存サンプル数で確認します。
CRC不一致、Sequence欠落、同期失敗、SNACエラーでは停止します。途中までのWAVは完全受信ではありません。
ファイルは再実行で上書きされ、手動停止では不完全になる場合があります。

## 検証結果

GNU Radio 3.10.1.1 / Ubuntu 22.04（WSL）、実SNACモデル、CPUで確認しました。

| 入力 | 受信フレーム | 復元音声samples | 復号後bit / token誤り |
|---|---:|---:|---:|
| 1001 samples × 1回 | 1 | 1001 | 0 / 0 |
| 1001 samples × 5回 | 3 | 5005 | 0 / 0 |
| 音声206905 samples × 5回 | 506 | 1034525 | 0 / 0 |

全ケースでCRC失敗0、EOSと有限終了を確認しました。音声5回は約43.105秒です。
比較試験だけNoiseBlockの乱数seedをそろえ、同じtokenの直接復号PCMとの最大差0を確認しました。
SNACは非可逆圧縮なので、元WAVとのPCM一致を意味しません。

乱数137フレームの全bit一致、先頭123サンプル追加、振幅0.37倍・位相1.23 radでの同期捕捉も確認しました。
データ部に各フレーム1 bitずつ誤りを加えたFEC訂正、不正同期・CRC・Sequenceの拒否を検証しています。
GRC単独コピーでのコンパイル、GUI起動、IQ・dibit保存も確認しています。

## スペクトル評価

乱数payloadの704フレーム、seed=12345、h=0.25、BT=0.30、L=4での結果です。

| 指標 | 結果 |
|---|---:|
| 99% OBW | 1370.9 Hz |
| 99.9% OBW | 1837.1 Hz |
| ACPR 2.0 kHz間隔 | −36.21 dB |
| ACPR 2.5 kHz間隔 | −46.62 dB |

ACPRは上下のうち漏洩が大きい側。主帯域・隣接帯域をチャネル間隔と同じ幅で積分した電力比です。
Welch法は8192点Blackman-Harris窓、50% overlap。先頭0.1秒と末尾処理128 samplesを除外します。
OBWは両端等電力除外方式です。合否マスクや実受信フィルタの評価ではありません。
h×BTの12条件を比較し、小さいh・BTで帯域と漏洩が減る傾向を確認しました。
3キャリアは2.0 / 2.5 kHz間隔で生成・保存を確認していますが、隣接干渉下の受信試験ではありません。

```sh
python3 sweep_4cpfsk.py --framed --seconds 60 --output-dir results_framed
python3 analyze_4cpfsk.py framed_4cpfsk.cf32 --sample-rate 42000 --spacing 2500 --discard-tail-samples 128
```

3キャリア合成波のOBWは全体の幅です。単一送信機のACPR評価には単一キャリアIQを使います。

## 検証の実行

```sh
python verify_4cpfsk.py
python verify_frames.py
python verify_receiver.py
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python verify_wav_tx.py --speech-wav /absolute/path/voice.wav
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python verify_rx_loopback.py --speech-wav /absolute/path/voice.wav
python verify_grc_portability.py
python verify_rx_portability.py
python /usr/bin/grcc -o . narrowband_4cpfsk.grc three_carriers.grc framed_4cpfsk.grc three_carriers_framed.grc
python verify_gui.py
```

`verify_rx_portability.py`は音声ループバック検証で作った短いIQを使います。
GUI検証は対象GRCのPython生成後に実行します。
測定記録は各検証スクリプトの出力JSONとsweepのCSV・PNGを参照してください。

## 制約

受信対応は単一キャリア、上記の初期変調設定、周波数偏差・サンプルクロック偏差なしの有限ファイルです。
実RF、雑音下BER/FER、同期語の誤検出率、周波数・クロック追従、フェージング、隣接局、連続受信は未評価です。
フレーム欠落の音声補間、ライブ音声のペーシング、RF開始・終了の振幅ランプも未実装です。
送信帯域が狭いことは受信性能や規格適合を保証しません。
