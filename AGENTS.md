# Repository Guidelines

## プロジェクト構成とモジュール配置
Pygame 版 の Python コア は `src/jr100emu/` に まとめ、 Java 版 の パッケージ 配置 を Python パッケージ に 対応 させる。
ブラウザ 版 の コア は `cpp/` に 置き、 CPU、VIA、メモリ、画面、PCM、ローダー を C++20 で 実装 する。公開 API は `cpp/include/jr100/core.hpp`、WASM 境界 は `cpp/src/wasm_api.cpp` に 限定 する。
Web フロントエンド は `web/` に 置き、`web/worker.js` から C++/WASM コア を 呼び出す。ブラウザ 実行 時 に Python や Pyodide を 使用 しない。
Python の CPU や VIA など の ステートマシン は `src/jr100emu/cpu/`, `src/jr100emu/via/` に 分離 し、 フロントエンド は `src/jr100emu/frontend/` で Pygame ループ を 管理 する。
ROM や サンプル プログラム は 既存 の `datas/` を 維持 し、 PROG 形式 と BASIC 形式 を サブディレクトリ に 整理 する。

## ビルド・テスト・開発コマンド
`python -m venv .venv` と `source .venv/bin/activate` で 仮想環境 を 用意 する。
依存 関係 は `pip install pygame pytest` を 基本 と し、 追加 した パッケージ は `requirements.txt` に 追記 する。
ローカル 実行 は `python -m jr100emu.app --rom datas/jr100rom.prg` を 想定 し、 オプション で `--prog datas/STARFIRE.prg` など を 指定 できる。
ブラウザ 版 は Emscripten と CMake を 用意 し、`python tools/build_web.py --verify` で `web/dist/` を 生成 する。
C++ の ネイティブ 検証 は `cmake -S cpp -B build/native`、`cmake --build build/native`、`ctest --test-dir build/native --output-on-failure` を 使用 する。

## コーディング スタイル と 命名 規約
Python コード は PEP8 を 基準 に 半角 スペース 四つ で インデント し、 行長 は 100 文字 を 上限 と する。
クラス 名 は PascalCase、 モジュール 名 は snake_case、 定数 は UPPER_SNAKE_CASE に 揃える。
Java 版 メソッド 名 は snake_case に 換算 し、 必要 な 個所 に 元 名称 を コメント で 残す。
`ruff format` と `ruff check` を フォーマッタ と リンター と して 採用 し、 CI でも 実行 する。
C++ は C++20、半角 スペース 四つ、PascalCase の 型、snake_case の 関数、末尾 `_` の private メンバー に 揃える。`-Wall -Wextra -Wpedantic -Werror` を ネイティブ と WASM の 両方 で 通す。

## テスト 指針
テスト は pytest で `tests/` 配下 に 追加 し、 ゆもつよ メソッド に 沿って 入力 値 と 期待 値 を 明文化 する。
CPU ステップ、 VIA タイマー、 キー入力、 VRAM 更新 は モジュール ごと に テスト ファイル を 分割 し、 フィクスチャ で 共通 初期 状態 を 再利用 する。
`t-wada` 流 TDD を 守り、 失敗 テスト を 先 に 書き、 最小 の 実装 で 緑 化 して から リファクタリング する。
`pytest --cov=src/jr100emu --cov-report=term-missing` で カバレッジ 80 パーセント 以上 を 維持 する。
C++ 回帰 テスト は `cpp/tests/`、ブラウザ の 純粋 JS テスト は `web/tests/*.test.mjs`、生成 artifact の 受入 は Playwright に 置く。実機 ROM は CI や Pages artifact に 含めず、ローカル 受入 だけ で 使用 する。
サウンド は pygame 版 と `sound_scale.prg`、`twinkle_star.bas` で 比較 し、VIA の 時刻付き イベント、IRQ レベル、音区間数、PCM 時間、推定 周波数 の 同等性 を 確認 する。

## コミット と プルリクエスト
コミット は Conventional Commits の `feat`, `fix`, `refactor`, `test` など を 使い、 要約 は 50 文字 以内 に 収める。
差分 説明 には 対応 する Java クラス や メソッド を 引用 し、 同等 性 を 明示 する。
プルリクエスト では 実行 コマンド、 動作 結果、 残課題 を 箇条書き し、 必要 に 応じて デバッグ メニュー の スクリーンショット を 添付 する。

## デバッグ と 設定
ESC キー で 呼び出す デバッグ メニュー は `src/jr100emu/debug/` で 管理 し、 CPU レジスタ、 VIA 状態、 スタック、 VRAM を 一覧 表示 する。
ジョイスティック は Pygame の `joystick` API を ラップ し、 拡張 ボード の アドレス 空間 に マッピング する 処理 を `io/joystick.py` に 置く。
トレース 深度 や スロットル 設定 は `config/debug.yaml` に 保存 し、 実行 時 に 読み込む。
