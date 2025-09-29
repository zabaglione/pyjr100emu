# Implementation Notes

開発者向けに、JR-100 エミュレーター Python 版の内部構造・移植方針・検証手順をまとめています。

## コア構成

- `src/jr100emu/cpu/cpu.py`
  - MB8861 (Motorola 6801 派生) 命令デコーダーと状態管理。
  - Java 版 `MB8861.java` に合わせた opcode テーブルを持ち、未定義命令は 1 クロックの NOP。
- `src/jr100emu/via/r6522.py`
  - R6522 VIA のポート／タイマ／シフトレジスタを移植。
  - `JR100EMU_TRACE_VIA_IFR` などの環境変数でトレース出力が可能。
- `src/jr100emu/jr100/computer.py`
  - メモリマップ、エクステンションポート、ディスプレイ・キーボード・サウンドなどを束ねる `JR100Computer` クラス。
  - `GamepadDevice` やデバイスイベントを `system/computer.py` のイベントキューで駆動。

## ゲームパッド

- `GamepadDevice` は Pygame 経由のポーリング結果を ExtendedIOPort（0xCC02）とキーボード行列へ反映。
  - JSON で方向ラベルと (row, bit) ペアを複数指定可能 (`--joystick-keymap`)。
  - 斜め方向は `up_left` 等が優先され、必要に応じて `up`/`left` を抑制。

## ファイル I/O

- PROG/BASIC テキスト読み込みは `emulator/file/program.py`、`emulator/file/data_file.py` に実装。
- PROG 保存は未実装（Java 版 `ProgFormatFile.java` 相当が TODO）。

## デバッグ

- デバッグオーバーレイ (`frontend/debug_overlay.py`) は CPU/VIA/スタック/VRAM スナップショットを表示。
- スナップショットは `snapshots/` 以下に JSON とメタ情報を保存。

## テスト

- `tests/integration/test_star_fire_headless.py` で ROM BASIC 起動～ STARFIRE の USR ルーチン実行を回帰チェック。
- `pytest` 実行時は `PYTHONPATH=src` の設定に注意。
- 追加の porting ノート: `docs/CPU_PORTING_NOTES.md`, `docs/VIA_PORTING_NOTES.md`, `docs/PORTING_PRINCIPLES.md`。

## 未対応・今後の課題

- PROG 書き出し、State 保存 (`StateSet`) の完全移植。
- ゲームパッド設定 UI (Java 版 `GamepadDialog`) の Python 化。
- VIA/CPU トレースの更なる自動テスト整備。
