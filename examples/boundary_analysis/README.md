# 音声区間の境界調査

独立した短い区間の圧縮・復号では、paddingや畳み込みの端の影響で連結境界に段差が生じます。
GNU Radioを使わない独立推論でも段差を再現しています。
対策は前後の文脈を与え、必要な中央部分だけを取り出すことです。
現行ブロックの前後1 / 2フレーム方式は[文脈比較](../frame_context/README.md)を参照してください。

このフォルダーの比較音声・JSONは、1秒区間と前後500 msの文脈を使う境界診断用データです。
現行ブロックのパラメーター設定や伝送速度を示すものではありません。

| 音声・境界 | 独立処理のサンプル差 | 文脈を含む処理 |
|---|---:|---:|
| 001・3秒 | 0.055756 | 0.001910 |
| 001・5秒 | 0.068390 | 0.000853 |
| 002・2秒 | 0.038910 | 0.000195 |

値は境界の隣接2サンプルの絶対差（float full scale基準）。全体の音質やクリックの完全除去を保証しません。
2本の試験音声で元と同じ出力長、有限値、EOS終了を確認しました。
結果は`gnu_radio_verification.json`と比較WAVを参照してください。

```sh
source tools/activate-wsl.sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 python tools/verify_context_audio.py
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 python tools/diagnose_boundaries.py
```
