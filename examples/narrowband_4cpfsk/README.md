# Gaussian 4CPFSK spectrum experiment

標準GNU Radioブロックを中心とした送信波形評価用GRCです。
SNACペイロード984.375 bit/sに対し、1312.5 sym/sを使います。
ランダム84 bitを実際にCRC・FEC・同期語付きフレームへ組み立てる版と、
比較用の無構造ランダムdibit版に加え、WAV→既存SNACブロック→無線フレームの接続版も用意しています。
保存IQから音声WAVへ戻す有限ファイル受信機も追加しました。RF送受信・スピーカー出力はありません。
独自OOT／Embedded Python変調ブロックのインストールは不要です。

GNU Radio **3.10.1.1 / Ubuntu 22.04 (WSL)**で、GRCのコンパイル、Qtの
オフスクリーン起動、単一／3キャリアのIQ保存、12条件×60秒のsweepを確認しています。

84 bitのSNAC単位から同期・CRC・FEC分を見積もり、1312.5 sym/sを選んだ経緯は
[本体READMEのフレーム案と評価結果](../../README.ja.md)に記載しています。
フレーム付き版では、その案の112 symbols/frameを実際に生成します。

| GRC | 入力データ | キャリア |
|---|---|---|
| [wav_snac_4cpfsk.grc](wav_snac_4cpfsk.grc) | WAVを指定回数再生→SNAC→v2フレーム | 1 |
| [receive_snac_4cpfsk.grc](receive_snac_4cpfsk.grc) | 保存IQ→v2フレーム復号→SNAC→WAV | 1 |
| [framed_4cpfsk.grc](framed_4cpfsk.grc) | CRC・FEC・同期付きランダムpayload | 1 |
| [three_carriers_framed.grc](three_carriers_framed.grc) | 同上、payloadは別seed | 3 |
| [narrowband_4cpfsk.grc](narrowband_4cpfsk.grc) | 無構造ランダムdibit（以前の比較用） | 1 |
| [three_carriers.grc](three_carriers.grc) | 同上、別seed | 3 |

## 受信側と音声ループバック（2026-10-07）

送信GRCで保存したIQを受信GRCへ渡し、音声WAVまで復元します。
これは**周波数偏差・サンプルクロック偏差がない、有限長ファイル受信**の実装です。
IQ以外に`.cf32.frames.json`が必要です。音声長やフレーム数はこのJSONから取得します。
送信dibit・送信token・元音声・乱数seedは受信処理に使用しません。

```text
File Source（complex64、42 kHz、Repeat=False）
  → 標準Quadrature Demod（gain = 32 / (π × 0.25)）
  → 標準Stream Mux（末尾に320 float zeros）
  → 標準FIR Filter（Gaussian ISIを補償する9 symbol-spaced taps）
  → 有限捕捉・同期語探索・4値判定・同期語除去
  → 標準Additive Scrambler（送信時と同設定でXOR解除）
  → 標準Matrix Interleaver（Deinterleave=True）
  → 標準UChar to Float → ×2 → −1
  → 標準FEC Extended Decoder（K7 / rate 1/2 / tail-biting）
  → 標準Stream to Vector（104 bit）
  → CRC・Sequence確認 → 84 bitを1/2/4 tokenに戻す
  → 既存SNAC Decoder 24k（context_frames=2、CPU）
  → 標準Wav File Sink（24 kHz mono PCM16）
```

Gaussian整形で隣接symbolの周波数波形が重なるため、復調後の4値判定の前に等化します。
等化tapはGNU Radio CPMの既知のGaussian pulseから最小二乗で求め、実際の畳み込みは
標準FIRブロックで行います。9係数を32サンプル間隔に配置し、Gaussian分と合わせた
遅延は192サンプルです。送信末尾の4 symbolsとは別に、受信FIRの排出用zerosを加えます。

独自部分はフレーム仕様に依存する2ブロックです。`rx_acquire.py`は復調・等化後の
有限captureをメモリに保持し、32通りのサンプル位相とフレーム位置を探します。
固定同期語8 dibitsが112 symbols間隔で予定フレーム数だけ連続する候補を選び、
4値レベルとの二乗誤差が最小の候補を採用します。同期を失った途中フレームを飛ばす機能はありません。
`rx_tokens.py`はCRCとSequenceを検査し、既存SNACのPMT形式へ戻します。
FEC、インターリーブ、スクランブル、周波数復調、FIR、WAV書込みは自作していません。

### 起動と接続

まず`wav_snac_4cpfsk.grc`の送信を最後まで実行・停止し、IQ保存を完了させます。
同じフォルダで、SNAC環境を有効にした端末から受信GRCを開きます。

```sh
source tools/activate-wsl.sh  # リポジトリ直下で実行
cd examples/narrowband_4cpfsk
python /usr/bin/gnuradio-companion receive_snac_4cpfsk.grc
```

`iq_path`の初期値は`wav_snac_4cpfsk.cf32`、`wav_path`は`received_snac.wav`です。
`iq_path + '.frames.json'`も同じ場所に置いてください。別フォルダなら絶対パスを指定します。
Generate / Executeで受信します。完了するとウィンドウのタイトルに`Receive complete`と表示し、
WAVを閉じて保存を確定します。スピーカーへ自動再生しません。
GRCを開いた段階では入力ファイルが未作成でも編集でき、実行時に存在・形式・長さを検証します。
パラメータを変更したら再実行してください。実行中のファイルや長さ変更には対応しません。

```sh
python /usr/bin/grcc -o . receive_snac_4cpfsk.grc
python receive_snac_4cpfsk.py --iq-path /absolute/path/capture.cf32 --wav-path /absolute/path/received.wav
```

補助コードはGRCへ埋め込んでいます。生成Pythonをコピーするときは同時生成された
`receive_snac_4cpfsk_acquisition.py`、`receive_snac_4cpfsk_tokens.py`、
`receive_snac_4cpfsk_rx_support.py`、`receive_snac_4cpfsk_radio_frame.py`も含めます。
既存SNAC OOTとモデル環境は必要です。有限ファイルを計算速度で処理するためThrottleは置きません。

出力はWAVと、`WAVパス + '.sync.json' / '.frames.json' / '.rx.json'`です。
最終結果は`.rx.json`の`complete=true`、保存サンプル数、エラー欄を確認してください。
CRC不一致、Sequence欠落、同期失敗、SNACエラーでは停止し、成功として扱いません。
途中まで生成されたWAVは完全受信ではありません。フレーム欠落の音声補間は未実装です。

### 検証と今回の範囲

```sh
python verify_receiver.py
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python verify_rx_loopback.py --speech-wav /absolute/path/voice.wav
python verify_rx_portability.py  # 上の検証で作った短いIQを使用
```

PHY検証はランダム137フレームを全bit比較し、さらに先頭123サンプルの追加、
振幅0.37倍・位相1.23 radの変更でも同期位置を捕捉して一致を確認します。
各フレームのデータ部に1 bitずつ誤りを入れたFEC訂正、無同期・CRC不正・Sequence不正の拒否も確認します。
これはIQへの雑音付加によるBER/FER評価ではありません。

実SNAC試験では送信・受信の両GRCを動かし、受信channel bit、SNAC token、音声長を比較します。
さらに同じ送信tokenを直接SNAC復号したPCMと、無線を経由したPCMを照合します。
SNACには`eval()`時も乱数を使うNoiseBlockがあるため、この比較試験だけ乱数seedを揃えます。
通常受信時の乱数動作は変えていません。SNACは非可逆なので、元WAVとのPCM一致を要求する試験ではありません。

GNU Radio 3.10.1.1・実SNACモデルCPUでの結果：

| 入力 | 受信フレーム | 復元音声samples | channel bit / token誤り | 直接復号PCMとの最大差 |
|---|---:|---:|---:|---:|
| 1001 samples × 1回 | 1 | 1001 | 0 / 0 | 0 |
| 1001 samples × 5回 | 3 | 5005 | 0 / 0 | 0 |
| 音声206905 samples × 5回 | 506 | 1034525 | 0 / 0 | 0 |

全ケースでCRC失敗0、EOSと有限終了を確認しました。音声音源5回は約43.105秒のWAVへ戻ります。
記録は`results_rx/verification.json`、`results_rx/phy_verification.json`です。
GRCだけを別フォルダへコピーした状態でもコンパイル・受信・WAV保存を確認します。

対応はv2・単一キャリア・SPS32・h=0.25・BT=0.3・L=4です。現時点では有限capture全体を
メモリに保持し、JSONからフレーム数・開始Sequence・末尾音声長を得ます。
オンエアの長さ通知、短い同期語の誤検出率、雑音下の捕捉性能、CFO/クロック追従、
フェージング、隣接局、SDRからの連続受信は今後の課題です。今回の成功は実RFリンク成立の主張ではありません。

標準ブロックの設計参照：
[Quadrature Demod](https://wiki.gnuradio.org/index.php?title=Quadrature_Demod)、
[CC Decoder Definition](https://wiki.gnuradio.org/index.php/CC_Decoder_Definition)。
実装・APIは使用環境のGNU Radio 3.10.1.1でも確認しています。

## WAV音声→SNAC送信（2026-10-07）

既存のSNAC Encoder 24kブロックを実際に接続しました。
`repeat_count=5`が初期値で、これは**元のWAVを合計5回**流す意味です。
各周回の間には無音を挿入せず、SNACの文脈・Sequence・変調位相をリセットしません。
音源が2048 samples未満でも送信でき、全周回を連結した最後の端数だけをSNACでpaddingします。

```text
Wav File Source（Repeat=True）
  → Head（WAVのサンプル数 × repeat_count）
  → SNAC Encoder 24k（total_samplesも同じ値、context_frames=2、CPU）
  → SNAC Tokens to Radio PDU（メッセージのみの小さなアダプタ）
  → 標準PDU to Tagged Stream
  → 標準FEC → 標準Matrix Interleaver → 標準Additive Scrambler
  → dibit変換 → 同期語挿入 → Gray Map → 標準Gaussian CPM
  → QT Frequency / Waterfall / IQ File Sink
```

アダプタはSNACの1/2/4 tokenをlevel0→level1→level2の順、各tokenを12 bitの
MSB firstで詰めて84 bitにします。既存のv2と同じSequence／Flags／CRCを追加し、
104 bitのPDUを出します。独自のストリームスケジューラ、FEC、変調器は追加していません。
メッセージ順序・token数・音声サンプル数・EOSを検査します。

入力は**空でない24 kHz・mono・整数PCMのWAV**（8/16/24/32 bit）です。
別レート・ステレオ・float WAVは、あらかじめこの形式へ変換してください。
input_pathはGRCのParameterで指定します。初期値は同梱音声を想定した
`../VOICEACTRESS100_001_001.wav`です。別の場所から起動する場合は絶対パスを指定してください。

既存SNAC OOTとモデル用Python環境が必要です。リポジトリ直下から：

```sh
source tools/activate-wsl.sh
cd examples/narrowband_4cpfsk
python /usr/bin/gnuradio-companion wav_snac_4cpfsk.grc
```

GRCでinput_pathとrepeat_countを指定し、Generate / Executeします。
Python実行では起動引数でも設定できます。

```sh
python /usr/bin/grcc -o . wav_snac_4cpfsk.grc
python wav_snac_4cpfsk.py --input-path /absolute/path/voice.wav --repeat-count 5
```

繰返し回数は1以上の整数です。実行中にsetterで変更せず、設定後に再実行してください。
GRCにはフレーム補助コードとtokenアダプタを埋め込んであり、外部radio_frame.pyの
検索パス設定は不要です。Python生成時には`wav_snac_4cpfsk_radio_frame.py`と
`wav_snac_4cpfsk_token_frames.py`も生成されます。Python一式をコピーする際は両方を含めます。

出力は`wav_snac_4cpfsk.cf32`、`wav_snac_4cpfsk.dibits`、`.cf32.frames.json`、
`.cf32.audio.json`です。前者JSONに元WAVの長さ・繰返し回数・予定IQ長、後者JSONに
実際に処理した音声サンプル数・フレーム数・EOS受信・エラーを保存します。
JSONは完了条件も確認してください。手動停止ではIQが短くなることがあります。
最終フレームの有効音声サンプル数はJSONに記録し、オンエアには新たな長さフィールドを追加していません。

フレーム数は`ceil(WAV_samples × repeat_count / 2048)`、保存IQ長は
`(frame_count × 112 + pulse_length) × samples_per_symbol`です。
SNACの先読みと推論があるため、GUI更新は計算速度にも依存します。保存IQは連続した
標本列ですが、実SDRへ無欠落でリアルタイム送信できることを保証する構成ではありません。
今回はスピーカー・SDRへは出力せず、IQ生成と保存までです。

実モデルによる検証：

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python verify_wav_tx.py --speech-wav /absolute/path/voice.wav
```

| 入力と繰返し | 入力PCM合計 | 無線フレーム数 | IQ samples（末尾処理込み） |
|---|---:|---:|---:|
| 1001 samplesの短いWAV × デフォルト5回 | 5005 | 3 | 10880 |
| 同じ短いWAV × 1回 | 1001 | 1 | 3712 |
| 同梱音声206905 samples × デフォルト5回 | 1034525 | 506 | 1813632 |

実SNACモデルで、PCMの指定回数連結、1/2/4 tokenの84-bit packing、CRC付き情報列、
v2のdibit列、連続IQ、最終部分フレームとEOS、有限入力後の正常終了を照合しました。
同梱音声5回では音声長約43.105秒、IQ長約43.182秒です。

## 実装した無線フレーム v2（2026-10-07）

v1にフレーム内インターリーブと加算型ホワイトニングを追加しました。
実用性能の最適化ではなく、一通りの送信処理を持つ実験例としての実装です。
112 symbols/frame、同期語、CRC/FECの設定は維持しますが、データ部の送信bit列は
v1と互換ではありません。保存メタデータのformatを`snac-radio-experimental-v2`に
変更しました。オンエアの版識別フィールドは追加していないため、将来の受信側でも
同じ版を明示的に選ぶ前提です。

情報ビットの並びは、最初のビットから **Payload 84 → Sequence 6 → Flags 2 → CRC 12**。
payloadはseed付き乱数です。Sequenceはstart_sequenceから1ずつ増えて63→0に折り返し、
Flagsはframe_flagsの2 bitをそのまま送信します（初期値0、用途は未割当）。
各数値はMSB first、ビット配列には1 byteに0または1を格納します。
84 bit payloadを88 bitへ丸めるようなパディングはしません。

CRCはCRC-12/DECTのパラメータを採用しました。

- width=12、poly=0x80F、init=0、refin=false、refout=false、xorout=0。
- payload＋Sequence＋Flagsの92 bitを、順番どおり保護します。
- 12 bitの結果をMSB firstで追加し、情報ブロックは104 bitになります。
- ASCII `123456789`のcheck値は0xF5B、CRCを含むビット列のresidueは0。
  パラメータの出典：[CRC RevEng catalogue](https://reveng.sourceforge.io/crc-catalogue/1-15.htm#crc.cat.crc-12-dect)。

FECはGNU Radio標準CC Encoder／FEC Extended Encoderです。

- rate=1/2、K=7、polys=[109,79]（GNU Radioのビットマスク表現、正値、出力順もこの順）。
- mode=fec.CC_TAILBITING、padding=False、puncture pattern='11'、threading=None。
- 初期状態はそのフレーム末尾6 bitから決め、104 bit処理後に同じ状態へ戻ります。
- 終端bitの追加はなく、**104 → 208 coded bits → 104 dibits**です。
- 208 bitを以下のインターリーブ・ホワイトニングへ渡してから、ビット対`b0,b1`を
  MSB firstで`2*b0+b1`へ変換します。

インターリーブは標準Matrix Interleaver（byte、rows=16、cols=13、deint=False）です。
208 coded bitsを行方向に書き、列方向に読みます。出力の添字`j=16*c+r`は
入力の添字`13*r+c`に対応します。フレームをまたぐ並べ替えやパディングはありません。
逆処理は同じrows/colsでdeint=Trueです。この寸法は208 bitを過不足なく並べ替える
実験設定で、フェージングや復号性能に対して最適化した値ではありません。

ホワイトニングは標準Additive Scramblerを使用します。

- mask=0x21、seed=0x1FF、GNU Radioのlen引数=8、bits_per_byte=1。
- 実際のレジスタ幅は9 bitです。出力PN bitは状態のbit 0、次状態は
  `(state >> 1) | ((((state >> 0) ^ (state >> 5)) & 1) << 8)`です。
- count=208、reset_tag_key=''とし、**毎フレームの符号化データ先頭で同じseedへリセット**。
- PN bitとのXORなので、同じブロック・設定を再度適用すると解除できます。
- 連続運転時の系列周期は511 bitですが、本実装ではフレームごとに先頭208 bitを使います。
- 同期語には適用せず、受信側の逆順は同期除去→dibit展開→ホワイトニング解除→
  デインターリーブ→FEC復号→CRC確認です。上記の有限ファイル受信機でもこの順序です。

同期語はFECの外側で、各フレーム先頭へ挿入します。
8 dibitsは **[0,3,1,0,2,1,3,2]**、ビット表現は`0011010010011110`（0x349E）。
各dibitが2回ずつ現れる実験用固定列です。捕捉性能や誤検出率で最適化した同期語ではありません。
同期もデータも同じGray Map（00→-3、01→-1、10→+3、11→+1）を通ります。
同期語はCRC保護、インターリーブ、ホワイトニングの対象外です。

```text
random_information(): [84 payload + 6 sequence + 2 flags + 12 CRC] × N
  → Vector Source（finite）
  → FEC Extended Encoder（104 bit単位、tail-biting）
  → Matrix Interleaver（16×13、208 coded bits単位）
  → Additive Scrambler（208 bitごとにseedへリセット）
  → Repack Bits（1→2、MSB first）
  → Stream Mux（sync 8 + data 104）← Vector Source（固定sync、repeat）
  → Head（N×112 dibits）→ dibit File Sink
  → Gray Map
  → Stream Mux（全Nフレームの後にだけ0レベルをL symbols追加）
  → Gaussian CPM → IQ File Sink / QT GUI
```

自作のradio_frame.pyは、92 bitの情報組立てと標準にないビット単位CRC-12を担当します。
FEC、インターリーブ、ホワイトニング、dibit変換、同期挿入、位相積分、IQ生成は標準ブロックです。
フレームごとにFEC状態はtail-bitingで独立しますが、**CPMの位相・フィルタ状態は
フレーム境界でリセットしません**。フレーム間のガード時間もありません。
1312.5 sym/sでは1フレーム112 symbols＝85.333… ms＝3584 IQ samplesです。

最後のフレームのGaussian応答を切り捨てないよう、収録末尾にだけL symbolsの
0レベル（周波数偏移0へ収束する入力）を追加します。この0はGray Map後の値であり、
dibit 00（-3）ではありません。末尾処理はフレーム内容にも定常ビットレートにも含めません。
L=4・SPS=32なら128 IQ samplesです。開始・終了時のRF振幅ランプは未実装です。

ランダム版は起動時に有限長の情報列を作ります。WAV版ではSNACのPMT出力を受け、
各メッセージのtokenから84 bitを作って`pack_information(payload, sequence, flags)`へ渡します。
マイク入力など長さ未定のライブ音声には対応していません。

## 実行

GNU Radio 3.10、Python 3、NumPy、SciPy、Matplotlib、PyQt5が必要です。
GRC再生成用のbuild_grc.pyのみPyYAMLも使用します。
WSL Ubuntu内のリポジトリルートで：

```sh
cd examples/narrowband_4cpfsk
gnuradio-companion framed_4cpfsk.grc
# またはフレーム付き3キャリア版
gnuradio-companion three_carriers_framed.grc
```

GRCでGenerate / Executeします。Python生成ファイルを直接実行する場合：

```sh
grcc -o . framed_4cpfsk.grc three_carriers_framed.grc
python3 framed_4cpfsk.py --duration-seconds 60
```

フレーム版は補助コードを標準Python ModuleとしてGRC内に保持します。
GRCを開く際の外部radio_frame.pyやPYTHONPATH指定は不要です。生成時に
framed_4cpfsk_radio_frame.py / three_carriers_framed_radio_frame.pyが自動出力されます。
生成済みPythonを直接コピーして実行する場合は、対応する補助Pythonも一緒に置いてください。
単独のradio_frame.pyはCLI・sweep用と、build_grc.pyが埋め込むコードの管理元として残しています。
デフォルトでは60秒以上となる704フレーム＋末尾処理を送出・保存後、データ処理が停止します。
正確には78848 dibits、IQは2523264 samples（約60.0777秒）です。GUIは閉じるまで
残ります。再実行すると同名IQファイルは上書きされます。
パスは実行時の作業ディレクトリ基準なので、保存場所を固定したい場合は
GRCのiq_pathに絶対パスを指定してください。

## GRC変数（変更後に再生成・再実行）

| 変数 | 初期値 | 意味 |
|---|---:|---|
| symbol_rate | 1312.5 | symbols/s |
| samples_per_symbol | 32 | 整数、2以上 |
| sample_rate | symbol_rate × samples_per_symbol | 独立に変更しない |
| modulation_index_h | 0.25 | 比較値0.20 / 0.25 / 0.30 |
| gaussian_bt | 0.30 | 比較値0.25 / 0.30 / 0.35 / 0.50 |
| pulse_length | 4 | CPM Gaussian周波数パルス長、単位symbol |
| channel_spacing | 2500 | 3キャリアの間隔、2000にも変更可能 |
| seed | 12345 | 再現可能な乱数seed |
| random_symbols | 262144 | 約200秒の乱数列。長時間運転時は繰返す |
| duration_seconds | 60 | 希望収録時間。フレーム版は起動時Parameter、整数フレームへ切上げ |
| iq_path | *.cf32 | IQ保存先 |
| frame_count | ceil(duration_seconds × symbol_rate / 112)、最小1 | フレーム版のみ |
| start_sequence | 0 | 開始Sequence、0..63 |
| frame_flags | 0 | 各フレームのFlags、0..3 |
| dibit_path | *.dibits | フレーム版の変調前シンボル保存先 |

標準CPMブロックにはh・BTの実行中変更用setterがないため、ライブスライダは
使いません。channel_spacingは単一キャリアの波形には作用しません。
フレーム数に依存するStream Muxの長さは生成時に固定されるため、フレーム版では
duration_seconds等をPython setterで変更せず、再起動してください。
QT Sinkには実サンプルレート42000 Hzを正しく渡しています。
±5 kHz表示はマウスで横軸をズームしてください。分析PNGは±5 kHzに固定し、
0、±spacing/2、±spacingに線を表示します。GUIのFFT値とWelch解析値は
窓・平均化・基準の違いがあるため、定量比較には解析結果を使用してください。

## 比較用の無構造ランダム版

Vector Source (uniform dibit indices 0..3) → Map → Gaussian CPM → Head → Throttle
→ Frequency Sink / Waterfall Sink / File Sink。

Mapは[253,255,3,1]です。先頭2値はCPMの符号付きbyte入力で-3,-1となり、
00→-3、01→-1、10→+3、11→+1を実現します。
既存ビットストリームへの接続時は、MSB-firstで2 bitをまとめて0..3のdibitを
作り、Mapの入力に接続してください。SNACファイルのヘッダをそのまま送る構成ではありません。

h=.25では長い定値入力の定常周波数が±164.0625、±492.1875 Hzです。
ランダム入力で4本の線スペクトルが現れることは要求していません。
3キャリア版は各枝のseedを変え、標準Signal Source・Multiply・Addで
−spacing、0、+spacingへ配置します。各枝の平均電力は1、合成平均電力は概ね3です。
定包絡の要求は各枝だけに適用し、合成信号には適用しません。

## IQ・フレームデータの保存と解析

File Sinkはヘッダなしのnative complex64（WSL x86ではlittle-endian float32のI,Q交互）です。
サンプルレート等はファイルに含まれません。変更した条件を別途記録してください。
フレーム版は起動時に`<iq_path>.frames.json`へフォーマット、seed、PHY設定、
予定サンプル数を記録します。これは完了記録ではないため、手動停止した場合は
実際のファイル長も確認してください。`.dibits`は1 byteに0..3を格納し、
112 bytesごとに1フレームです。3キャリア版は`.carrier0/1/2`に分けます。
末尾の0レベル処理は`.dibits`には含まれません。

```sh
python3 analyze_4cpfsk.py narrowband_4cpfsk.cf32 --sample-rate 42000 --spacing 2500
python3 analyze_4cpfsk.py framed_4cpfsk.cf32 --sample-rate 42000 --spacing 2500 --discard-tail-samples 128
python3 analyze_4cpfsk.py three_carriers.cf32 --sample-rate 42000 --spacing 2000
```

同じstemのJSONとPNGを出力します。3キャリア合成の解析ではOBWは合成信号全体の幅であり、
隣接帯域の電力には意図的な隣接キャリアが含まれます。単一送信機のACPR評価には
必ず単一キャリアIQを使ってください。

Welchはtwo-sided、Blackman-Harris、8192 samples、50% overlap、detrend=False。
先頭0.1秒を除外します。FFTビン幅は約5.127 Hzで、点PSDは線形PSDを補間します。
ピーク相対PSDをdBで表示し、総電力基準dBc/Hzとは区別します。
OBW99/999は両端等電力（0.5% / 0.05%ずつ除外）方式です。
帯域積分は線形PSDで行い、境界ビンを比例配分します。

| spacing | main [Hz] | lower adjacent [Hz] | upper adjacent [Hz] |
|---|---|---|---|
| 2000 | -1000..1000 | -3000..-1000 | 1000..3000 |
| 2500 | -1250..1250 | -3750..-1250 | 1250..3750 |

ACPR=10 log10(Padj/Pmain)、左右別、負の値が小さいほど漏洩が少ない定義です。
実際の受信フィルタ・規格の測定帯域を表すものではありません。

## 12条件sweep

```sh
python3 sweep_4cpfsk.py --seconds 60 --output-dir results
# 実際のフレーム構造・FEC・同期を含めた12条件
python3 sweep_4cpfsk.py --framed --seconds 60 --output-dir results_framed_v2
# 各条件のIQも保存する場合（約242 MB）
python3 sweep_4cpfsk.py --seconds 60 --output-dir results --save-iq
python3 verify_4cpfsk.py
python3 verify_frames.py
# GRC生成後のQtオフスクリーン起動・保存チェック
grcc -o . narrowband_4cpfsk.grc three_carriers.grc framed_4cpfsk.grc three_carriers_framed.grc
python3 verify_gui.py
# 変調せずフレームのdibitと最初のフレーム内容をJSONへ保存
python3 radio_frame.py --frames 3 --sequence 62 --output results_framed_v2/example.dibits
```

sweepはGRCと同じ標準Map→Gaussian CPMを使用し、別のNumPy変調器は作りません。
全条件で同じ乱数列を使い、Throttleなしで処理します。
sweep.csv、metadata.json、12枚のPNGを生成します。
--framedではframes.dibitsも保存し、PHYを変える全条件で同一フレーム列を使用します。
末尾のL×SPS samplesはPSD評価から除外します。

主なCSV列：h、bt、pulse_length、seed、symbol_rate、sps、obw99_hz、obw999_hz、
psd_minus/plus_*_peak_db、main_*_power、adj_*_lower/upper_power、
acpr_*_lower/upper_db。PSD点は±1000、±1250、±2000、±2500 Hzです。
正規化前の積分電力は、単一キャリアの全帯域電力が概ね1になる単位です。

OBWと漏洩量はスペクトル面の候補選定用です。BER、同期捕捉、周波数誤差、
実RFの送信開始・終了過渡は未評価です。FECの終端ビット等を追加する場合は
1312.5 sym/sのフレーム収支を再計算してください。

## 無構造ランダム版：初期値の測定結果

seed=12345、60秒、h=0.25、BT=0.30、L=4、Fs=42000 Hz：

| 指標 | 結果 |
|---|---:|
| 99% OBW | 1379.6 Hz |
| 99.9% OBW | 1829.6 Hz |
| 2.0 kHz間隔 ACPR 下／上 | -36.45 / -36.43 dB |
| 2.5 kHz間隔 ACPR 下／上 | -46.63 / -46.60 dB |

標準CPMの有限Gaussianパルスと数値近似を考慮し、定常周波数の検証許容値を
0.1 Hz、振幅の許容値を1e-5としています。BT=.25でL=4とL=6の
99.9% OBW差が20 Hz以内となることも確認します。

## 無構造ランダム版：12条件の測定記録（2026-10-06）

上記と同じ条件でhとBTだけを変更した結果です。ACPR欄は左右のうち
漏洩が大きい側（0 dBに近い側）を示します。CSVでは左右を個別に保存します。
再実行で生成されるresultsディレクトリはGit対象外のため、測定値をここにも残します。

| h | BT | 99% OBW [Hz] | 99.9% OBW [Hz] | ACPR 2.0 kHz [dB] | ACPR 2.5 kHz [dB] |
|---:|---:|---:|---:|---:|---:|
| 0.20 | 0.25 | 1110.3 | 1495.9 | -45.92 | -58.09 |
| 0.20 | 0.30 | 1196.6 | 1613.4 | -41.57 | -51.02 |
| 0.20 | 0.35 | 1261.8 | 1712.7 | -38.55 | -46.33 |
| 0.20 | 0.50 | 1392.5 | 1955.8 | -33.54 | -39.18 |
| 0.25 | 0.25 | 1293.5 | 1697.0 | -40.24 | -52.71 |
| 0.25 | 0.30 | 1379.6 | 1829.6 | -36.43 | -46.60 |
| 0.25 | 0.35 | 1448.1 | 1954.1 | -33.78 | -42.36 |
| 0.25 | 0.50 | 1585.3 | 2298.6 | -29.34 | -35.70 |
| 0.30 | 0.25 | 1478.2 | 1907.4 | -35.12 | -47.45 |
| 0.30 | 0.30 | 1567.4 | 2056.6 | -31.85 | -42.28 |
| 0.30 | 0.35 | 1641.9 | 2191.8 | -29.55 | -38.56 |
| 0.30 | 0.50 | 1806.8 | 2531.5 | -25.67 | -32.53 |

今回の範囲ではh・BTを小さくするとOBWと隣接帯域漏洩が減りました。
h=.30、BT=.50では99.9% OBWが2.5 kHzを超えるなど、全設定が同じ帯域に
収まるわけではありません。初期値h=.25、BT=.30は99.9% OBWが2.0 kHz未満ですが、
2.0 kHz間隔の実通信成立や規格適合を示す結果ではありません。

## フレーム付きv1（インターリーブ／ホワイトニングなし）：測定記録（2026-10-06）

CRC・FEC・固定同期語を含む704フレーム、seed=12345、Sequence開始0、Flags=0、
L=4、Rs=1312.5、SPS=32です。末尾処理128 samplesと先頭0.1秒を除外し、
無構造版と同じWelch設定で測定しました。3キャリア版ではpayloadのseedは別ですが、
同期語・フレーム開始時刻・Sequenceは共通です。完全に無相関な3波を仮定した試験ではありません。
ACPR欄は左右のうち漏洩が大きい側です。

| h | BT | 99% OBW [Hz] | 99.9% OBW [Hz] | ACPR 2.0 kHz [dB] | ACPR 2.5 kHz [dB] |
|---:|---:|---:|---:|---:|---:|
| 0.20 | 0.25 | 1113.1 | 1489.0 | -45.73 | -58.10 |
| 0.20 | 0.30 | 1197.7 | 1611.2 | -41.33 | -50.99 |
| 0.20 | 0.35 | 1262.4 | 1717.4 | -38.31 | -46.28 |
| 0.20 | 0.50 | 1387.6 | 1973.6 | -33.33 | -39.13 |
| 0.25 | 0.25 | 1292.2 | 1692.7 | -40.12 | -52.87 |
| 0.25 | 0.30 | 1372.4 | 1835.5 | -36.26 | -46.68 |
| 0.25 | 0.35 | 1439.5 | 1962.3 | -33.59 | -42.39 |
| 0.25 | 0.50 | 1583.4 | 2303.1 | -29.16 | -35.71 |
| 0.30 | 0.25 | 1468.2 | 1907.2 | -35.07 | -47.64 |
| 0.30 | 0.30 | 1561.0 | 2062.9 | -31.73 | -42.44 |
| 0.30 | 0.35 | 1636.1 | 2202.1 | -29.40 | -38.70 |
| 0.30 | 0.50 | 1811.5 | 2529.0 | -25.51 | -32.61 |

初期値h=.25、BT=.30では99.9% OBWは1835.5 Hz、ACPRは2.0 kHz間隔で
下側-36.26／上側-36.42 dB、2.5 kHz間隔で下側-46.73／上側-46.68 dBでした。
今回のpayloadと測定条件では、フレーム化によって狭帯域化の見通しは大きく変わりませんでした。
固定同期語による周期性は含まれますが、受信同期性能・BER・実RFの成立は未評価です。

verify_frames.pyでは、公開CRC check値とresidue、104箇所の1-bit反転検出、
Sequenceの63→0折返し、不正入力、137フレームの標準FEC出力と独立参照計算の一致、
全フレームの同期位置、定包絡性、位相増分、最後のGaussian応答の排出を検証します。
verify_gui.pyは生成された4種類のGRCアプリを起動し、2.0/2.5 kHz間隔の保存を確認します。
フレーム版の保存dibitは全ビットを照合し、単一キャリアIQもheadless生成結果と照合します。

## フレーム付きv2：測定記録（2026-10-07）

16×13インターリーブとフレームごとにリセットするホワイトニングを有効にし、
704フレーム・seed=12345・その他v1と同じ条件で再測定しました。ACPRは左右の悪い側です。

| h | BT | 99% OBW [Hz] | 99.9% OBW [Hz] | ACPR 2.0 kHz [dB] | ACPR 2.5 kHz [dB] |
|---:|---:|---:|---:|---:|---:|
| 0.20 | 0.25 | 1112.7 | 1487.9 | -45.65 | -58.10 |
| 0.20 | 0.30 | 1196.5 | 1611.7 | -41.27 | -50.97 |
| 0.20 | 0.35 | 1263.1 | 1719.0 | -38.25 | -46.26 |
| 0.20 | 0.50 | 1388.4 | 1975.8 | -33.29 | -39.12 |
| 0.25 | 0.25 | 1289.3 | 1693.4 | -40.06 | -52.81 |
| 0.25 | 0.30 | 1370.9 | 1837.1 | -36.21 | -46.62 |
| 0.25 | 0.35 | 1439.7 | 1964.9 | -33.54 | -42.33 |
| 0.25 | 0.50 | 1583.6 | 2308.4 | -29.12 | -35.65 |
| 0.30 | 0.25 | 1467.4 | 1907.2 | -34.98 | -47.63 |
| 0.30 | 0.30 | 1558.2 | 2062.7 | -31.65 | -42.41 |
| 0.30 | 0.35 | 1634.1 | 2204.8 | -29.33 | -38.65 |
| 0.30 | 0.50 | 1812.5 | 2533.9 | -25.45 | -32.55 |

逆処理には標準Additive ScramblerとMatrix Interleaverのdeint=Trueを使用し、
137フレームの全符号化bitが元に戻ることを検証しました。同一フレームを連続させた
ときの系列リセット、1-bit誤りが逆処理で増殖しないこと、LFSR周期511も確認しています。
GUI起動、保存dibit・IQ照合、12条件の測定も通過しています。
この送信スペクトル測定はBER・雑音下の同期捕捉性能の検証ではありません。有限ファイル受信の結果は上記を参照してください。


## GRC importエラーの修正（2026-10-07）

従来版はGRCの式評価時に外部`import radio_frame`を実行していたため、
通常の`gnuradio-companion framed_4cpfsk.grc`では補助モジュールを検索できず、
続くVectorの式評価も失敗する場合がありました。外部Importを標準Python Moduleへ
置き換え、同じ補助コードをGRC内に保存するよう修正しました。信号処理とv2の送信bit列は変更していません。

```sh
python3 verify_grc_portability.py
```

この検証は`.grc`だけを一時ディレクトリへコピーし、PYTHONPATHを解除した状態で
別の作業ディレクトリからgrccを実行します。その後、生成されたPythonと補助モジュール
だけで単一／3キャリア版を実行し、IQ・dibit・メタデータ保存まで確認します。
