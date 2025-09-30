# JR-100 Emulator (Python Edition)

Python で動作する JR-100 エミュレーターです。[Java 版 JR-100 Emulator v2](https://github.com/kemusiro/jr100-emulator-v2) をベースに、実機挙動を忠実に移植しました。Pygame を利用したデモアプリを同梱し、ROM/BASIC/PROG の実行やゲームパッド対応、デバッグオーバーレイなどを備えています。

## すぐに試す

```bash
python -m venv .venv
source .venv/bin/activate
pip install pygame
PYTHONPATH=src python -m jr100emu.app --rom datas/jr100rom.prg --joystick --audio
```

テストや開発ツールを併用する場合は `pip install pytest` のように必要なパッケージを追加でインストールしてください。

起動後に `F1` キーで簡易ロードメニューを開き、`datas/` 内の BASIC (`.bas`) や PROG (`.prg`) ファイルを選択します。矢印キーやジョイスティックで項目を移動し、`ENTER` もしくはジョイスティックの決定ボタンで読み込みを実行してください。読み込みが完了すると READY プロンプトから `LIST` や `RUN` を利用できるようになります。

主なオプション:

| オプション | 説明 |
| --- | --- |
| `--joystick` | ゲームパッド入力のポーリングを有効化 |
| `--joystick-config` | 軸/ボタンのマッピング JSON（`io/joystick.py` 準拠） |
| `--joystick-keymap` | ゲーム内キーに紐づくキーマトリクス JSON（例: `datas/joystick_keymaps/starfire.json`） |
| `--joystick-index`, `--joystick-name` | Pygame デバイスの絞り込み |
| `--audio` | ビープ音再生の ON/OFF |

### ゲームパッドの設定

標準では方向キーを I/J/K/L、トリガーを SPACE に割り当てています。8 方向を利用するタイトルでは `--joystick-keymap` を用いて JSON で上書きしてください。各値は `[row, bit]` 形式で JR-100 キーボード行列の行番号 (0〜8) とビット位置 (0〜4) を表します。行列に対応するキーは `src/jr100emu/app.py` の `KEY_MATRIX_MAP` を参照してください。例: `datas/joystick_keymaps/starfire.json`

```json
{
  "up_left": [5, 3],
  "up": [5, 4],
  "up_right": [8, 3],
  "left": [6, 3],
  "right": [8, 2],
  "down_left": [7, 4],
  "down": [8, 0],
  "down_right": [8, 1],
  "switch": [0, 2]
}
```

### デバッグオーバーレイ

実行中に `ESC` キーでデバッグモードへ切り替え、CPU レジスタや VRAM プレビューを確認できます。ステップ実行 (`N`)、スナップショット保存 (`S`)、読み込み (`L`) に対応しています。

## 仕組みや移植メモ

Java 版から Python 版へ移植した際の注意点や CPU/VIA の差分調査は開発者向けドキュメントにまとめています。

- [Implementation Notes (docs/IMPLEMENTATION.md)](docs/IMPLEMENTATION.md)

## ライセンス

このプロジェクトは [MIT License](LICENSE) のもとで公開されています。

## 謝辞

- Java 版 JR-100 Emulator v2 を公開し詳細な実装を提供してくださった Kenichi Miyata 氏をはじめとする関係者の皆さま。
- Python 版移植に協力いただいたコミュニティの皆さま。
