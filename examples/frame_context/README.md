# 前後フレームの文脈比較

各2048 PCM samples（85.333 ms）を1/2/4個、計84 bitのtokenへ変換します。
Encoderは前後のPCMを参照して中央tokenを取り出し、Decoderは受信tokenの前後を参照して中央音声を復元します。
文脈の重複送信はなく、定常payloadは984.375 bit/sです。

2本の音声で、片側のみ、前後1フレーム、前後2フレーム、全体一括処理を比較しました。
前後2フレームでは全3階層のtokenが一括処理と一致しました。
前後1フレームのtoken一致率は、001が85.3 / 81.4 / 78.4%、002が94.3 / 85.2 / 77.0%でした。
片側のみでは反対側の端の影響が残ります。他の音声で同じ結果になる保証はありません。

```sh
source tools/activate-wsl.sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 python tools/compare_frame_context.py
```

`comparison.json`にtoken一致率、境界のサンプル差、一括復号とのRMSEを記録します。
token一致率やサンプル差は知覚音質そのものではないため、比較WAVも聴いて確認してください。
NoiseBlockが推論時にも乱数を使うので、同じtokenでも復号波形の完全一致は要求しません。

未来側1 / 2フレームの先読み待ちはEncoderとDecoderの各段で85.333 / 170.667 msです。
全体遅延には入力蓄積・推論・通信も加わります。これはオフライン比較で、リアルタイム無線性能の評価ではありません。
