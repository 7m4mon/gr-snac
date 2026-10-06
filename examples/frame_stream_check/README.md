# 前後2フレーム・GRC実行結果

Encoder/Decoderの `Context Frames (each side)` は1または2、初期値2。
更新したGRCが生成したPythonコードを実際のGNU Radio schedulerで実行し、
VOICEACTRESS100_001_001.wavを処理した。

- 元音声: 206,905サンプル、8.6210417秒。
- 送信: 102フレーム、各1/2/4個の新規token、計714 token。
- 音声payload: 8,568 bit＝1,071 bytes。文脈は重複送信しない。
- 定常payload: 984.375 bit/s。
- `.snac`全体: 1,214 bytes（ヘッダー/末尾情報143 bytesを含む）。
- 最後の57サンプルも1フレームとして送るため、元音声秒数で割った
  有限ファイルのtoken rateは993.847 bit/s、ファイル全体は1,126.546 bit/s。

`encoded.snac` は新しいv2形式。フレームをまたいで12-bit tokenを詰め、
フレーム単位のbyte paddingやヘッダーを省いた。診断JSONは復号に不要。
`decoded_from_tokens.wav` は保存ファイルのみを別プロセスで復号したもの。
206,905サンプルでの復号とEOS終了を確認済み。

Python/GRC設定と保存ファイルの復号ツールはすべて初期値2。
`--context-frames 1` で保存ファイルを前後1フレーム参照で復号できる。
旧v1ファイルの読み込みも維持している。

この試験はファイル処理。リアルタイム無線のペーシングや欠落補間は未実装。
今回のCPUログでは1フレームの復号が85.3 msを超える場面があり、
リアルタイム送受信には処理の最適化または実行環境の検討が必要。
