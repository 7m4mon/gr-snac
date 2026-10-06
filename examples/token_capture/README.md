# SNAC中間ファイルの実測

2026-10-06、WSL / GNU Radio 3.10.1.1、CPUでGRC生成コードを実行。
入力: VOICEACTRESS100_001_001.wav、24 kHz mono、206,905サンプル（8.6210417秒）。

| 設定 | token数 | token本体 bit/s | .snac全体 bytes | .snac全体 bit/s |
|---|---:|---:|---:|---:|
| 前後500 ms（現行設定） | 1428 | 1987.69 | 2468 | 2290.21 |
| 文脈なし（従来方式） | 728 | 1013.33 | 1416 | 1313.99 |

- `encoded.snac`: 現行設定で保存した12-bit tokenファイル。
- `encoded.snac.json`: ファイルサイズ・元音声秒数・bitrateの記録。
- `reconstructed.wav`: GRCのDecoder出力。
- `decoded_from_tokens.wav`: 別プロセスで `encoded.snac` だけを読み込んで復号した音声。
- `encoded_no_context.snac` / `.json`: 文脈なしの比較用。
- `reconstructed_no_context.wav`: 文脈なしの復号音声。境界クリックが起こり得る。

現行ファイルだけから206,905サンプルを復号できることを確認済み。
ファイルには音声PCMを保存していない。同じSNACモデルの重みは復号側に別途必要。
`.snac` はこのプロジェクト独自の形式で、一般の音楽プレイヤーでは直接再生できない。
JSONのサイズは`.snac`全体のbitrateには含めない（診断用で、復号には不要）。
token本体は1個12 bit。ファイル全体にはヘッダー324 bytesと、文脈ありの
今回の例ではチャンク末尾の合計2 bytes相当のbit paddingも含まれる。

GRCを開き直し、`token_path` を指定して実行すると同じ形式で保存される。
既定では作業ディレクトリの `encoded.snac` を上書きする。
