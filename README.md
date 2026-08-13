# JR-100 Emulator (Python Edition)

Python コアとブラウザ版を備えた JR-100 エミュレーターです。[Java 版 JR-100 Emulator v2](https://github.com/kemusiro/jr100-emulator-v2) をベースに、実機挙動を忠実に移植しました。Pygame を利用したデモアプリと、GitHub Pagesで動作するWeb Emulatorを同梱しています。

## すぐに試す

```bash
python -m venv .venv
source .venv/bin/activate
pip install pygame
PYTHONPATH=src python -m jr100emu.app --rom datas/jr100rom.prg --joystick --audio
```

テストや開発ツールを併用する場合は `pip install pytest` のように必要なパッケージを追加でインストールしてください。

## Web Emulator

ブラウザ版はPyodideのWeb WorkerからこのリポジトリのPythonコアを実行し、CanvasへJR-100の256×192画面を描画します。実機ROMの登録が必須で、ROM本体はIndexedDB、設定はlocalStorageへ保存します。アプリケーションからROMをサーバーへ送信する処理はありません。

Web Audioによるバッファ再生BEEP、実機配列の仮想キーボード、CTRLショートカット、Gamepad API、PROG V1/V2とBASICテキスト読込、16K/32K RAM切替、CPU/VIA/メモリデバッガを利用できます。仮想キーの文字・Shift・GRAPH凡例は登録した実機ROMのフォントデータから描画します。

```bash
python tools/build_web.py --verify
python -m http.server 8000 --directory web/dist
```

詳細は [docs/WEB_EMULATOR.md](docs/WEB_EMULATOR.md) を参照してください。`main`へのpush時は [.github/workflows/deploy-pages.yml](.github/workflows/deploy-pages.yml) がテスト、ROM混入検査、GitHub Pages公開を実行します。

起動後に `F1` キーで簡易ロードメニューを開き、`datas/` 内の BASIC (`.bas`) や PROG (`.prg`) ファイルを選択します。矢印キーやジョイスティックで項目を移動し、`ENTER` もしくはジョイスティックの決定ボタンで読み込みを実行してください。読み込みが完了すると READY プロンプトから `LIST` や `RUN` を利用できるようになります。

### BASIC 音楽サンプル

ROM BASIC の READY プロンプトで `F1` を押し、次のファイルを選択してから `RUN` を入力します。

- `datas/doremi_scale.bas`: C5 から C6 までのドレミ音階
- `datas/twinkle_star.bas`: 「きらきら星」全42音

各音のタイマー値は出力停止中に設定しているため、BASIC の `POKE` 実行間隔による途中の音程変化を発生させません。

主なオプション:

| オプション | 説明 |
| --- | --- |
| `--joystick` | ゲームパッド入力を実機ジョイスティック相当として`$CC02`へ反映 |
| `--joystick-config` | 軸/ボタンのマッピング JSON（`io/joystick.py` 準拠） |
| `--joystick-keymap` | ゲーム内キーに紐づくキーマトリクス JSON（例: `datas/joystick_keymaps/starfire.json`） |
| `--joystick-index`, `--joystick-name` | Pygame デバイスの絞り込み |
| `--audio` | ビープ音再生の ON/OFF |

### ゲームパッドの設定

標準ではホスト側ゲームパッドをJR-100のジョイスティック入力として`$CC02`へ直接反映し、キーボード行列には何も入力しません。キーボード操作を前提とするソフト向けの仮想パッドは、`--joystick-keymap` を明示して有効化してください。各値は `[row, bit]` 形式で JR-100 キーボード行列の行番号 (0〜8) とビット位置 (0〜4) を表します。行列に対応するキーは `src/jr100emu/app.py` の `KEY_MATRIX_MAP` を参照してください。例: `datas/joystick_keymaps/starfire.json`

ジョイスティックの既定マッピングは、左スティック（axis 0/1）、Hat 0、PygameのPS4 Controller用D-padボタン（上11、下12、左13、右14）を同時に受け付け、button 0をトリガーとして扱います。`--joystick-config`の各方向には従来の単一入力に加えて、複数の入力定義を配列で指定できます。`--write-joystick-template PATH`で複数入力形式のひな形を出力できます。

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

### ヘッドレス実行（機械語デバッグ）

迷路テストなど BASIC に戻らない機械語プログラムをコマンドラインから検証したい場合は、ヘッドレスランナーを利用できます。

```bash
PYTHONPATH=src python -m jr100emu.debug_runner \
    --program datas/jr100dev/samples/maze/tests/build/maze_init_test.prg \
    --start 0x0300 \
    --break-pc 0x0300 \
    --cycles 0 \
    --seconds 5 \
    --dump-range 0300:037F
```

`--break-pc` を指定しない場合は `--cycles` または `--seconds` の条件で終了します。時間制限のみで制御したい場合は `--cycles 0` を指定してください。ダンプは標準出力に 16×16 バイト形式で出力されるため、ファイルへ保存したい場合は `--dump out.txt` を併用してください。詳細な仕様は [docs/HEADLESS_DEBUG_RUNNER.md](docs/HEADLESS_DEBUG_RUNNER.md) を参照してください。

スタックポインタを独自に設定したい場合は `--stack-pointer 0xXXXX` を追加してください（既定値 `0x0244` は BASIC の `USR` 呼び出し時と同等です）。

## 仕組みや移植メモ

Java 版から Python 版へ移植した際の注意点や CPU/VIA の差分調査は開発者向けドキュメントにまとめています。

- [Implementation Notes (docs/IMPLEMENTATION.md)](docs/IMPLEMENTATION.md)

## ライセンス

このプロジェクトは [MIT License](LICENSE) のもとで公開されています。

## 謝辞

- Java 版 JR-100 Emulator v2 を公開し詳細な実装を提供してくださった Kenichi Miyata 氏をはじめとする関係者の皆さま。
- Python 版移植に協力いただいたコミュニティの皆さま。
