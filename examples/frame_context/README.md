# 1フレーム文脈の比較実験

1フレームは2,048 PCMサンプル（85.333 ms）。各フレームを1/2/4個のtoken、
計84 bitとして一度だけ送る構成を、オフラインで模擬した。
送信側では前後のPCMを使ってencodeし、中央フレームのtokenだけを残す。
受信側では受信済みのtoken列から前後のフレームを参照してdecodeする。
文脈tokenの重複送信はない。定常payloadは全条件で984.375 bit/s。
有限ファイル末尾の端数フレームはpaddingされる。

`tools/compare_frame_context.py` で、提供音声001/002を次の条件で比較した。

| ファイル末尾 | encode/decodeで使う過去 | 未来 |
|---|---:|---:|
| past1_future0 | 1フレーム | なし |
| past0_future1 | なし | 1フレーム |
| past1_future1 | 1フレーム | 1フレーム |
| past2_future2 | 2フレーム | 2フレーム |
| whole | ファイル全体を一括処理 | |

`comparison.json` は各階層のtoken一致率、フレーム境界での隣接サンプル差の
95パーセンタイル、一括復号とのRMSEを記録する。
自然な音声にも大きなサンプル差があるため、境界の数値が小さいほど高音質、とは限らない。
またモデルのNoiseBlockは推論時にも乱数を使うため、同じtokenでも復号波形の完全一致は要求しない。
token一致率も知覚音質の指標ではない。比較WAVで聴感確認すること。

片側だけの文脈では、もう一方の端の影響が残る。
前後1フレームでは一括推論からtokenが変わるが、片側のみより波形差は減った。
2フレームは約170.667 ms。500 msを必要最小値とする根拠はなく、より短い文脈で比較できる。
今回の001/002では、前後2フレームで全3階層のtokenが一括処理と100%一致した。
前後1フレームの一致率は001が85.3% / 81.4% / 78.4%、
002が94.3% / 85.2% / 77.0%だった。他の音声で同じ結果になる保証はない。

過去の保持は追加の先読み遅延を生まない。未来側の待ち時間はencoderとdecoderの
両方にあり、さらに入力フレーム蓄積・通信・推論時間も必要となる。
「未来1フレーム」は端から端までの遅延が85.333 msになるという意味ではない。

これは音質・token数の比較用実験で、無線のペーシング、パケット欠落、GNU Radio
のリアルタイム動作は未実装・未検証。通常のGRC設定は変更していない。

```sh
source tools/activate-wsl.sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 python tools/compare_frame_context.py
# 任意の過去:未来フレーム数でも比較可能
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 python tools/compare_frame_context.py --contexts 3:1 3:3
```
