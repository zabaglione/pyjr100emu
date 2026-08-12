# JR-100 Web Emulator

`web/` は、GitHub Pagesで配布する静的なブラウザ版です。エミュレーターの動作本体は `src/jr100emu/` の既存コアであり、PyodideのWeb Workerから呼び出します。

## ROMポリシー

実機ROMはリポジトリへ追加しません。ブラウザ版は次の形式を受け付けます。

- 現行のJR-100 `PROG`コンテナ（開始アドレス `0xE000`、ペイロード8192バイト）
- `0xE000`へ直接マッピングするraw 8192バイトROM

ROM未登録ではCPUを起動せず、選択したROMはIndexedDBへ保存します。設定値はlocalStorageへ保存します。アプリケーションコードはROMバイト列をサーバーへ送信しません。

プライベートブラウズ、容量制限、ブラウザのデータ削除によって保存が失われる場合があるため、配布版ではROMの再登録を常に可能にします。

## 入力

キーボードはJR-100の9行×5ビットを正規のデータ定義として扱います。物理キーボード、HTML仮想キーボード、Gamepad APIはすべて同じ入力ルーターを通ります。Worker側では短いタップを最低2フレーム、CTRL/SHIFTを最低4フレーム保持し、修飾キーを文字キーより1フレーム先にROMへ認識させます。

仮想キーボードは実機と同じ4段45キーの並びです。キー上の主文字、Shift文字、GRAPH文字は、登録ROMの先頭1024バイトにある128文字×8バイトのフォントと、ROM内の通常／Shiftキーテーブルから描画します。CTRLのBASICショートカット名はキー上部へ表示します。CTRL+VでGRAPHへ切り替わると、補助凡例もGRAPH文字へ切り替わります。

ホストキーボードは、入力結果が実機と一致するように変換します。たとえばホストのShift+AはJR-100のA、`!`はJR-100のShift+1になります。次の編集キーはJR-100のCTRL操作へ変換します。

| ホストキー | JR-100入力 |
| --- | --- |
| Home | CTRL+1 |
| Delete | CTRL+5 |
| Left / Down / Up / Right | CTRL+6 / 7 / 8 / 9 |
| Insert | CTRL+0 |
| Backspace | CTRL+-（RUBOUT） |
| CapsLock | JR-100のSHIFTを単独保持 |

ジョイスティックはJR-100拡張I/Oの次のactive-highビットへ接続します。

| 操作 | ビット |
| --- | ---: |
| Right | `0x01` |
| Left | `0x02` |
| Up | `0x04` |
| Down | `0x08` |
| Switch | `0x10` |

仮想キーボードはブラウザのタッチ操作に加えて、GamepadのSelect、D-pad、A/B/X、L1/R1から操作できます。

## BEEP

PythonコアのVIA T1サウンドイベントを44.1kHz、16bitモノラルPCMへ変換し、各フレームの画面と一緒にWorkerからWeb Audioへ渡します。Pygameミキサーには依存しません。ブラウザの自動再生制限に対応するため、最初のクリックまたはキー入力でAudioContextを開始します。`Sound on/off`でミュート状態を切り替え、設定はlocalStorageへ保存します。

## PROG V1/V2

`Load PRG`はPROG V1/V2をメモリへ直接読み込みます。ファイルはブラウザ内で処理し、保存もアップロードもしません。

- BASICセクションは、ROMのREADY待ち後に`RUN`を自動タイプします。
- V1機械語は、V1ヘッダの開始アドレスを`A=USR($hhhh)`で自動実行します。
- V2機械語は、PBINコメントの`entry=$hhhh`または`USR=$hhhh`を優先します。
- V2の正式形式には独立した実行エントリがないため、コメントがなければ最初のPBINロード先を推定値として表示します。画面には`PBIN start`と表示し、誤ってデータ領域を実行しないよう自動実行はしません。
- 推定値が実行入口ではないファイルは、`USR entry`を書き換えて`Run`を押します。コアをリセットしてから指定アドレスを自動タイプするため、誤った推定入口からも復帰できます。

自動タイプは実ROMのキーデバウンスに合わせ、ROM起動待ち約1.67秒、1文字あたり約0.23秒で入力します。実機ROMと`datas/sample.prg`を用いたローカル受入では、V2コメントの`entry=$0300`へ到達することをブレークポイントで確認しています。

## 拡張RAMとデバッガ

ROM読込前の`32K extended RAM`で、標準RAM `$0000-$3FFF`を`$0000-$7FFF`へ拡張します。変更時はブラウザ保存済みROMからコアを再生成します。

Webデバッガは次を表示・操作します。

- MB8861のA/B/IX/SP/PC/フラグとクロック数
- VIA 6522のポート、方向、ACR/PCR、割込み、T1/T2
- 指定アドレスから128バイトのメモリダンプ
- SP近傍のスタックとVRAM `$C100`へのメモリショートカット
- 単命令ステップ
- 複数の16bitブレークポイント

実行画面でESCを押すとデバッガの表示を切り替えます。BREAKは実機どおりCTRL+Cで入力します。

## ローカルビルド

```bash
python tools/build_web.py --verify
python -m http.server 8000 --directory web/dist
```

`http://127.0.0.1:8000/` を開き、実機ROMをファイル選択から登録します。Pyodideランタイムは固定バージョンをHTTPS CDNから取得します。GitHub PagesのworkflowはPythonテスト、ブラウザモジュールテスト、生成物のROM混入検査を通過してからPages artifactを公開します。

CIのカバレッジ閾値は、ブラウザ境界、JR-100モデル、ジョイスティックアダプターを対象に80パーセントで設定しています。Web artifactは合成raw ROMを使ったPlaywright smoke testで、ROM登録、Worker起動、BEEP PCM、Canvas画面、ROMフォント凡例、4段仮想キーボード、32K RAM、V2 PRG、デバッガ、IndexedDBからの再読み込みを確認します。実機ROMそのものはリポジトリとCIへ含めません。

実機ROMと非公開プログラムを必要とする既存の音声・BASIC・Starfire統合テストは、CIでは明示的に除外します。これらはROMを配置した開発環境で実行し、CIではROM不要のCPU/VIAテストと合成ROMのブラウザsmoke testを実行します。

実機ROMをローカルに配置した環境では、次の追加受入を実行できます。ROMはローカルHTTPサーバーから開いたページへファイル入力するだけで、外部へ送信しません。

```bash
python web/tests/real_rom_qa.py \
  --rom datas/jr100rom.prg \
  --screenshot /tmp/jr100emu.png
```

この受入はREADY表示、CTRL+V、ALPHA/GRAPH凡例切替、BEEP PCM、デバッガを確認します。

## 実装上の境界

- `BrowserCore`: ROM検証済みのJR-100コアとフレーム単位の操作
- `web/worker.js`: PyodideとPythonコアの境界
- `web/matrix-input-core.js`: 短打保持と修飾キー先行走査
- `web/input.js`, `web/keymap.js`: 物理・仮想・Gamepad入力の押下元統合と実機キー変換
- `web/audio.js`: Web AudioのPCMキュー
- `web/virtual-keyboard.js`: 実機配列とROMフォント凡例
- `web/storage.js`: ブラウザ内バイナリ保存と設定保存
- `tools/build_web.py`: Pythonソースを静的artifactへ梱包
