# JR-100 Emulator

National JR-100のプログラムを、ブラウザまたはデスクトップで実行できるエミュレーターです。
BASIC／PROG形式のプログラム、BEEP音、仮想キーボード、ゲームパッドに対応しています。

利用には、利用者が用意したJR-100のシステムROMが必要です。

## ブラウザ版を使う

[JR-100 Web Emulatorを開く](https://zabaglione.github.io/pyjr100emu/)

インストールは不要です。
初回は次の順に操作します。

1. `Choose ROM`を押し、JR-100のシステムROMを選びます。
2. 必要に応じて`32K extended RAM`を有効にします。
3. `Load program`から実行したいプログラムを選びます。
4. 物理キーボードまたは画面上の仮想キーボードで操作します。

システムROMには、8192バイトのROMイメージ、またはJR-100のPROG形式で保存したROMを使用できます。
一度登録したROMは同じブラウザに保存され、次回から自動的に読み込まれます。

### 対応するプログラム

- PROG V1／V2：`.prg`、`.prog`
- BASICテキスト：`.bas`、`.txt`

BASICと実行入口が記録されたPROGは、読み込み後に自動で実行されます。
実行入口を判定できないPROGでは、`USR entry`へ16進数のアドレスを入力して`Run`を押してください。

### 主な操作

| 操作 | 動作 |
| --- | --- |
| 英字キー | JR-100の英大文字を入力 |
| `SHIFT` | 記号またはシフト側の文字へ切り替え |
| `CTRL`+`V` | ALPHAモードとGRAPHモードを切り替え |
| GRAPHモード中の`SHIFT` | シフト側のGRAPH文字へ切り替え |
| `CTRL`+`C` | BREAKを入力 |
| `Home`、矢印、`Delete`、`Insert`、`Backspace` | 対応するJR-100のCTRL操作を入力 |
| `ESC` | デバッガの表示を切り替え |

仮想キーボードは実機と同じ4段45キーの配置です。
画面上の`SHIFT`と`CTRL`は、クリックまたはタップで保持できます。

ゲームパッドは、仮想キーボード表示中にはキーの選択と入力に使われます。
ゲームのジョイスティックとして使う場合は、`Hide keyboard`で仮想キーボードを閉じてください。

BEEP音は`Sound on`のときに再生されます。
音が出ない場合は、画面を一度クリックするか、いずれかのキーを押してください。

### ブラウザに保存されるデータ

登録したROMと画面設定は、現在のブラウザ内に保存されます。
プログラムファイルは保存されないため、ページを開き直した後は再度選択してください。
選択したROMやプログラムをエミュレーターから外部へアップロードする処理はありません。

プライベートブラウズの終了やサイトデータの削除によって、保存したROMが消える場合があります。
元のROMファイルは手元にも保管してください。

## デスクトップ版を使う

デスクトップ版はPythonとPygameで動作します。
次の例はmacOSおよびLinux向けです。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m jr100emu.app \
  --rom /path/to/jr100rom.prg \
  --audio \
  --joystick \
  --scale 3
```

ROMを`datas/jr100rom.prg`へ配置した場合は、起動スクリプトも使用できます。

```bash
./run.sh
```

### 主な操作

| キー | 動作 |
| --- | --- |
| `F1` | BASIC／PROGファイルのロードメニューを開く |
| `F2` | メモリの16進表示を開く |
| `F12` | JR-100をリセット |
| `ESC` | デバッグモードへ切り替え |
| `N` | デバッグモードで1命令進める |
| `SPACE` | デバッグモードから実行へ戻る |

ロードメニューでは、矢印キーまたはゲームパッドで項目を選び、`ENTER`で読み込みます。
BASICプログラムを読み込んだ後は、READYプロンプトで`LIST`または`RUN`を入力できます。

キーボード操作を前提とするゲームでは、付属のゲームパッド設定を指定できます。

```bash
PYTHONPATH=src python -m jr100emu.app \
  --rom /path/to/jr100rom.prg \
  --audio \
  --joystick \
  --joystick-keymap datas/joystick_keymaps/starfire.json
```

ほかの起動オプションは、次のコマンドで確認できます。

```bash
PYTHONPATH=src python -m jr100emu.app --help
```

## 付属プログラム

`datas/`には、動作確認に使えるBASICとPROGファイルが入っています。

- `datas/doremi_scale.bas`：C5からC6までの音階
- `datas/twinkle_star.bas`：「きらきら星」
- `datas/sound_scale.prg`：機械語による音階演奏
- `datas/key_display.prg`：キー入力の確認

ブラウザ版では`Load program`、デスクトップ版では`F1`のロードメニューから選択してください。
BASICプログラムは、読み込み後に`RUN`で開始できます。

## 技術資料

実装、ローカルビルド、検証、ヘッドレスデバッグについては、次の文書を参照してください。

- [ブラウザ版の仕様](docs/WEB_EMULATOR.md)
- [ヘッドレスデバッグランナー](docs/HEADLESS_DEBUG_RUNNER.md)
- [実装メモ](docs/IMPLEMENTATION.md)

## ライセンス

このプロジェクトは[MIT License](LICENSE)のもとで公開されています。

## 謝辞

- [Java版JR-100 Emulator v2](https://github.com/kemusiro/jr100-emulator-v2)を公開し、詳細な実装を提供してくださったKenichi Miyata氏をはじめとする関係者の皆さま。
- Python版の移植と検証に協力いただいたコミュニティの皆さま。
