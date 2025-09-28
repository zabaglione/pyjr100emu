# Repository Guidelines

## プロジェクト構成とモジュール配置
エミュレータ コア は `src/jr100emu/` に まとめ、 Java 版 の パッケージ 配置 を Python パッケージ に 対応 させる。
CPU や VIA など の ステートマシン は `src/jr100emu/cpu/`, `src/jr100emu/via/` に 分離 し、 フロントエンド は `src/jr100emu/frontend/` で Pygame ループ を 管理 する。
ROM や サンプル プログラム は 既存 の `datas/` を 維持 し、 PROG 形式 と BASIC 形式 を サブディレクトリ に 整理 する。

## ビルド・テスト・開発コマンド
`python -m venv .venv` と `source .venv/bin/activate` で 仮想環境 を 用意 する。
依存 関係 は `pip install pygame pytest` を 基本 と し、 追加 した パッケージ は `requirements.txt` に 追記 する。
ローカル 実行 は `python -m jr100emu.app --rom datas/jr100rom.prg` を 想定 し、 オプション で `--prog datas/STARFIRE.prg` など を 指定 できる。

## コーディング スタイル と 命名 規約
Python コード は PEP8 を 基準 に 半角 スペース 四つ で インデント し、 行長 は 100 文字 を 上限 と する。
クラス 名 は PascalCase、 モジュール 名 は snake_case、 定数 は UPPER_SNAKE_CASE に 揃える。
Java 版 メソッド 名 は snake_case に 換算 し、 必要 な 個所 に 元 名称 を コメント で 残す。
`ruff format` と `ruff check` を フォーマッタ と リンター と して 採用 し、 CI でも 実行 する。

## テスト 指針
テスト は pytest で `tests/` 配下 に 追加 し、 ゆもつよ メソッド に 沿って 入力 値 と 期待 値 を 明文化 する。
CPU ステップ、 VIA タイマー、 キー入力、 VRAM 更新 は モジュール ごと に テスト ファイル を 分割 し、 フィクスチャ で 共通 初期 状態 を 再利用 する。
`t-wada` 流 TDD を 守り、 失敗 テスト を 先 に 書き、 最小 の 実装 で 緑 化 して から リファクタリング する。
`pytest --cov=src/jr100emu --cov-report=term-missing` で カバレッジ 80 パーセント 以上 を 維持 する。

## コミット と プルリクエスト
コミット は Conventional Commits の `feat`, `fix`, `refactor`, `test` など を 使い、 要約 は 50 文字 以内 に 収める。
差分 説明 には 対応 する Java クラス や メソッド を 引用 し、 同等 性 を 明示 する。
プルリクエスト では 実行 コマンド、 動作 結果、 残課題 を 箇条書き し、 必要 に 応じて デバッグ メニュー の スクリーンショット を 添付 する。

## デバッグ と 設定
ESC キー で 呼び出す デバッグ メニュー は `src/jr100emu/debug/` で 管理 し、 CPU レジスタ、 VIA 状態、 スタック、 VRAM を 一覧 表示 する。
ジョイスティック は Pygame の `joystick` API を ラップ し、 拡張 ボード の アドレス 空間 に マッピング する 処理 を `io/joystick.py` に 置く。
トレース 深度 や スロットル 設定 は `config/debug.yaml` に 保存 し、 実行 時 に 読み込む。
