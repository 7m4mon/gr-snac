# Gaussian 4CPFSK spectrum experiment

標準GNU Radioブロックだけを使った送信波形評価用GRCです。
SNACペイロード984.375 bit/sを将来搭載する想定で、1312.5 sym/sを使います。
FEC、フレーム、SNAC接続、受信機、RF送信は実装していません。
独自OOT／Embedded Python変調ブロックのインストールは不要です。

GNU Radio **3.10.1.1 / Ubuntu 22.04 (WSL)**で、両GRCのコンパイル、Qtの
オフスクリーン起動、単一／3キャリアのIQ保存、12条件×60秒のsweepを確認しています。

84 bitのSNAC単位から同期・CRC・FEC分を見積もり、1312.5 sym/sを選んだ経緯は
[本体READMEのフレーム案と評価結果](../../README.ja.md)に記載しています。
現段階はフレーム案に必要な速度での連続ランダム波形評価です。

## 実行

GNU Radio 3.10、Python 3、NumPy、SciPy、Matplotlib、PyQt5が必要です。
GRC再生成用のbuild_grc.pyのみPyYAMLも使用します。
WSL Ubuntu内のリポジトリルートで：

```sh
cd examples/narrowband_4cpfsk
gnuradio-companion narrowband_4cpfsk.grc
# または3キャリア版
gnuradio-companion three_carriers.grc
```

GRCでGenerate / Executeします。Python生成ファイルを直接実行する場合：

```sh
grcc -o . narrowband_4cpfsk.grc three_carriers.grc
python3 narrowband_4cpfsk.py
```

デフォルトで60秒分を送出・保存後、データ処理が停止します。GUIは閉じるまで
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
| duration_seconds | 60 | 保存・表示する長さ |
| iq_path | *.cf32 | IQ保存先 |

標準CPMブロックにはh・BTの実行中変更用setterがないため、ライブスライダは
使いません。channel_spacingは単一キャリアの波形には作用しません。
QT Sinkには実サンプルレート42000 Hzを正しく渡しています。
±5 kHz表示はマウスで横軸をズームしてください。分析PNGは±5 kHzに固定し、
0、±spacing/2、±spacingに線を表示します。GUIのFFT値とWelch解析値は
窓・平均化・基準の違いがあるため、定量比較には解析結果を使用してください。

## 標準ブロック構成

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

## IQ解析

File Sinkはヘッダなしのnative complex64（WSL x86ではlittle-endian float32のI,Q交互）です。
サンプルレート等はファイルに含まれません。変更した条件を別途記録してください。

```sh
python3 analyze_4cpfsk.py narrowband_4cpfsk.cf32 --sample-rate 42000 --spacing 2500
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
# 各条件のIQも保存する場合（約242 MB）
python3 sweep_4cpfsk.py --seconds 60 --output-dir results --save-iq
python3 verify_4cpfsk.py
# GRC生成後のQtオフスクリーン起動・保存チェック
python3 verify_gui.py
```

sweepはGRCと同じ標準Map→Gaussian CPMを使用し、別のNumPy変調器は作りません。
全条件で同じ乱数列を使い、Throttleなしで処理します。
sweep.csv、metadata.json、12枚のPNGを生成します。

主なCSV列：h、bt、pulse_length、seed、symbol_rate、sps、obw99_hz、obw999_hz、
psd_minus/plus_*_peak_db、main_*_power、adj_*_lower/upper_power、
acpr_*_lower/upper_db。PSD点は±1000、±1250、±2000、±2500 Hzです。
正規化前の積分電力は、単一キャリアの全帯域電力が概ね1になる単位です。

OBWと漏洩量はスペクトル面の候補選定用です。BER、同期捕捉、周波数誤差、
実RFの送信開始・終了過渡は未評価です。FECの終端ビット等を追加する場合は
1312.5 sym/sのフレーム収支を再計算してください。

## 初期値の測定結果

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

## 12条件の測定記録（2026-10-06）

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
