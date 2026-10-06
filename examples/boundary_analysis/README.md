# チャンク境界の調査と修正（2026-10-06）

提供された001/002の元音声とGNU Radio復号音声はいずれも24 kHz mono。
長さはそれぞれ206,905 / 180,224サンプルで一致した。
001の公式出力は208,896サンプルで、末尾のモデルpaddingを残している。

従来のブロックは24,000サンプルずつ独立してencode/decodeし、復号結果を
直接連結していた。前後の文脈が途切れ、1秒区切りでpadding・畳み込みの
端の影響が生じる。音声の状態によって段差の大きさが異なるため、聴感上は
必ずしも一定周期のクリックにはならない。

GNU Radioを使わない独立チャンク推論でも同様の段差を再現した。
提供出力とのRMSEは001が0.00147、002が0.00105で、完全なビット一致ではない。
これは再現条件の差を含むため、差のすべての原因を特定したという意味ではない。

修正は前後500 msを含めて推論し、復号後に必要な中央区間のみ取り出す方式。
開始位置はモデルのhop、VQ stride、attention windowから求めた2048サンプル
単位にそろえる。各出力区間の長さは変えず、重複出力・欠落を防ぐ。
クロスフェード、無音挿入、波形のpeak normalizationは行わない。

実GNU Radio schedulerでの測定例（隣接2サンプルの絶対差、float full scale基準）:

| 音声・境界 | 提供された従来出力 | 修正後 | 提供された公式出力 |
|---|---:|---:|---:|
| 001・3秒 | 0.055756 | 0.001910 | 0.003723 |
| 001・5秒 | 0.068390 | 0.000853 | 0.000977 |
| 002・2秒 | 0.038910 | 0.000195 | 未提供 |

自然な音声にも隣接サンプル差があるため、この数値だけで全体の音質は評価できない。
聴感でのクリック完全除去は未確認。全ファイル一括処理との完全一致も保証しない。
詳しい測定値は `gnu_radio_verification.json`、比較WAVは
`VOICEACTRESS100_001_001_gr_context500.wav` と
`VOICEACTRESS100_001_002_gr_context500.wav`。

単体テスト11件、実モデル・GNU Radio QA 2件、および2つの提供音声で
正しい出力長・有限値・EOSでの自動終了を確認した。

## 利用

Encoderの `Context Each Side (ms)` は500が標準。0で従来方式に戻せる。
EncoderとDecoderは両方更新する。既存メッセージは修正版Decoderでも復号できる。
文脈モードはmetadataに `encoded_samples` と `crop_start` を加える。

1秒chunkなら最初の出力まで1.5秒分の入力＋推論時間が必要。
前後の文脈もtoken化して送るため、演算量・伝送token数が増える。
約1 kbpsを維持する低遅延ストリーミング方式ではない。
Audio Sinkでのリアルタイムunderflowは別途検証が必要。

このWindows側checkoutをWSLで使う場合:

```sh
cd /mnt/c/Users/nomurah/Documents/ChatGPT/gr-snac
source tools/activate-wsl.sh
cmake --install build-wsl-context
python /usr/bin/gnuradio-companion examples/snac_loopback.grc
```

GRCを開き直し、`input_path` / `output_path` を実ファイルの絶対パスにする。
元からあった `build-wsl` は `/home/ubuntu/src/gr-snac` を参照していたため、
今回の更新では `build-wsl-context` を別途構成して使用した。

再検証:

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 python tools/verify_context_audio.py
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 python tools/diagnose_boundaries.py
```
