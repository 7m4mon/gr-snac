# 前後フレームの文脈比較

## 音声の出典と公開範囲

音声の出典は、高道慎之介氏らによる
[JVS (Japanese versatile speech) corpus](https://sites.google.com/site/shinnosuketakamichi/research-topics/jvs_corpus)。
貴重な音声データを提供してくださったコーパス作成者・話者の皆様に感謝します。

本ディレクトリでは、個人の音声コーデック比較実験用に、次の2発話だけを公開しています。
ファイル名は本実験で使用した名前です。

| 元音声 | 話者 |
|---|---|
| `VOICEACTRESS100_001_001.wav` | 男性 |
| `VOICEACTRESS100_001_002.wav` | 女性 |

その他のWAVは、この2発話をSNACでencode/decodeした比較用の加工音声です。
`whole` は一括処理、`past*_future*` はフレーム単位の処理条件を表します。
複数の処理条件を含みますが、元の発話は2つだけです。

公式ページの利用条件では、音声データの再配布は認められていませんが、
個人のウェブページやブログなどでコーパスの一部（例えば10文程度）を公開することは可能とされています。
本公開は、この一部公開の条件に基づくものです。音声にはコーパスの利用条件が適用され、
このリポジトリのコードのライセンスは適用されません。利用時は上記の公式ページをご確認ください。


## 比較方法

各2048 PCM samples（85.333 ms）を1/2/4個、計84 bitのtokenへ変換します。
Encoderは前後のPCMを参照して中央tokenを取り出し、Decoderは受信tokenの前後を参照して中央音声を復元します。
文脈の重複送信はなく、定常payloadは984.375 bit/sです。

2本の音声で、文脈なし（past0_future0）、片側のみ、前後1フレーム、前後2フレーム、全体一括処理を比較しました。
前後2フレームでは全3階層のtokenが一括処理と一致しました。
前後1フレームのtoken一致率は、001が85.3 / 81.4 / 78.4%、002が94.3 / 85.2 / 77.0%でした。
片側のみでは反対側の端の影響が残ります。他の音声で同じ結果になる保証はありません。

```sh
source tools/activate-wsl.sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 python tools/compare_frame_context.py
# 文脈なしの比較用WAV（001/002）を生成
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 python tools/compare_frame_context.py --contexts 0:0
```

`comparison.json`にtoken一致率、境界のサンプル差、一括復号とのRMSEを記録します。
token一致率やサンプル差は知覚音質そのものではないため、比較WAVも聴いて確認してください。
NoiseBlockが推論時にも乱数を使うので、同じtokenでも復号波形の完全一致は要求しません。

未来側1 / 2フレームの先読み待ちはEncoderとDecoderの各段で85.333 / 170.667 msです。
全体遅延には入力蓄積・推論・通信も加わります。これはオフライン比較で、リアルタイム無線性能の評価ではありません。
