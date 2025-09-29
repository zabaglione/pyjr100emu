# JR-100 Emulator (Python Edition)

Python で動作する JR-100 エミュレーターです。Java 版をもとに実機挙動を再現し、Pygame を利用したデモアプリを同梱しています。ROM/BASIC/PROG を読み込んで実行でき、ゲームパッド対応やデバッグオーバーレイなども備えています。

## すぐに試す

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m jr100emu.app --rom datas/jr100rom.prg --program datas/STARFIRE.prg --joystick --audio
```

主なオプション:

| オプション | 説明 |
| --- | --- |
| `--program` | PROG/BAS ファイルを読み込んで実行する |
| `--joystick` | ゲームパッド入力のポーリングを有効化 |
| `--joystick-config` | 軸/ボタンのマッピング JSON（`io/joystick.py` 準拠） |
| `--joystick-keymap` | ゲーム内キーに紐づくキーマトリクス JSON（例: `datas/joystick_keymaps/starfire.json`） |
| `--joystick-index`, `--joystick-name` | Pygame デバイスの絞り込み |
| `--audio` | ビープ音再生の ON/OFF |

### ゲームパッドの設定

標準では方向キーを I/J/K/L、トリガーを SPACE に割り当てています。8 方向を利用するタイトルでは `--joystick-keymap` を用いて JSON で上書きしてください。例: `datas/joystick_keymaps/starfire.json`

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
