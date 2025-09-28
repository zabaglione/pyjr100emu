# JR-100 ハードウェア統合メモ

## 追加クラス
- `jr100emu.jr100.display.JR100Display`: フォント切替など VIA から叩かれるインターフェイスを実装。
- `jr100emu.jr100.keyboard.JR100Keyboard`: 16×8 キーマトリクスの状態管理、押下/解放 API を提供。
- `jr100emu.jr100.sound.JR100SoundProcessor`: VIA からの周波数設定とライン制御を記録するスタブ。
- `jr100emu.memory`: Java 版の MemorySystem/Memory を移植し、8bit/16bit アクセスと未マップ領域 (0xd000=0xaa) を再現。
- `jr100emu.emulator.file.program`: PROG/BASIC ローダと `ProgramInfo` を提供し、Java 版 DataFile 群を移植。
- `jr100emu.jr100.hardware.JR100Hardware`: 上記コンポーネントとメモリを束ね、VIA などから参照可能にした。
- `jr100emu.system.computer.Computer`: VIA との結線・tick メソッドを備えた簡易 Computer 基底クラス。
- `jr100emu.jr100.computer.JR100Computer`: ROM・RAM・VIA を初期化し、MB8861 を電源投入直後の状態に整える統合クラス。ユーザープログラム読込 API を追加。
- `jr100emu.frontend.debug_overlay.DebugOverlay`: pygame デモ用のデバッグ HUD。CPU/VIA/スタック/VRAM プレビューとトレースを描画し、ESC で呼び出すメニューに利用。

### デバッグメニュー（pygame デモ）操作

- `ESC`: デバッグメニューの表示／閉鎖。表示中は CPU 実行を一時停止。
- `SPACE`: デバッグメニューを閉じて実行再開。
- `N`: `STEP_CYCLES` 分だけ CPU をステップ実行し、トレースを更新。
- `S`: 現在のメモリ・CPU/VIA レジスタ・クロックをメモリ内スナップショットとして保存し、`snapshots/slot*.json` に書き出し。
- `R`: メモリ内スナップショットを復元。未保存の場合は上記ファイルがあれば読み込み、それ以外はステータス表示のみ。
- `1-4` / `↑↓`: スナップショットスロット（`slot0`〜`slot3`）を切り替え。
- `[`/`]`: スナップショット履歴を時刻順に移動。
- `P`: 履歴項目のプレビューをHUDに表示（差分とメタ情報を確認）。
- `L`: 履歴項目を読み込み、現在のスロットへ復元。
- `C`: 選択中スロットのコメント編集（Enter 保存 / Esc キャンセル、Shift+Enterで改行）。
- `D`: 選択中スロットのスナップショットとメタデータを削除。
- `--audio`: デモ起動時に指定すると pygame.mixer を使用したスクエア波出力を有効化。
- `Q`: デバッグメニュー表示中にアプリケーションを終了。

## テスト
- `tests/unit/test_r6522.py` で JR100R6522 と新ハードウェアを統合し、フォント切替、キーマトリクス、サウンド周波数キャッシュを検証。
- `tests/unit/test_keyboard_matrix.py` で押下/解放操作がマトリクスへ反映されることを確認。
- `tests/unit/test_display_render.py` および `tests/unit/test_display_pygame.py` で VRAM からのピクセル生成と pygame Surface への描画を検証。
- `tests/unit/test_memory_system.py` で User 定義 RAM/VRAM のディスプレイ連携と JR100Computer のメモリ構成を確認。
- `tests/unit/test_integration_cpu_via.py` で キー入力→VIA→メモリ読み出しと Timer1 IRQ→CPU.IRQ の経路を検証。
- `tests/unit/test_rom_loading.py` で PROG 形式 ROM 読み込みとリセットベクタ設定、環境変数による ROM 指定を確認。
- `tests/unit/test_program_loading.py` で BASIC テキストおよび PROG バイナリのロード、デモ用ヘルパの例外処理を検証。
- `tests/unit/test_debug_overlay.py` でデバッグ HUD の描画とトレース保持を確認。
- `jr100emu.app` は JR100Computer を用いる pygame ループとなり、実 ROM を読んだ CPU 実行を画面描画と同期させる。

## 次段階
- ROM/BASIC ローダからのユーザプログラム読み込みとメモリ配置を Java 版と同等に移植。
- pygame デバッグメニュー (ESC) を実装し、CPU レジスタ・VIA 状態・VRAM 表示・命令トレースを提供。
- サウンド再生の実装 (pygame ミキサー等) と実機タイミング再現を検討。
