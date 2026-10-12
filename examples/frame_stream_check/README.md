# フレーム単位の音声処理とtoken保存

GNU Radio schedulerで、前後2フレームを参照するEncoder/Decoderとtokenファイル保存を検証します。
各2048 samples（85.333 ms）から1/2/4個の新規tokenだけを送り、文脈は重複送信しません。

| 指標 | 結果 |
|---|---:|
| 入力音声 | 206905 samples、8.621秒 |
| フレーム / token数 | 102 / 714 |
| 音声payload | 8568 bit、1071 bytes |
| 定常payload | 984.375 bit/s |
| 保存ファイル全体 | 1214 bytes |

末尾の57 samplesも1フレームとして送るため、この有限ファイルのpayload rateは993.847 bit/sです。
ヘッダー・末尾情報を含むファイル全体は1126.546 bit/sで、定常payloadとは区別します。
保存tokenだけから206905 samplesを復号し、EOSで正常終了することを確認しました。

```sh
python tools/decode_snac_file.py examples/frame_stream_check/encoded.snac examples/frame_stream_check/decoded_from_tokens.wav --context-frames 2
```

同じモデルの重みが別途必要です。前後1フレームは`--context-frames 1`で比較できます。
CPUでは1フレームの復号が85.3 msを超える場面があり、リアルタイム運転や欠落補間は未検証です。
詳細なサイズは`encoded.snac.json`に記録しています。
