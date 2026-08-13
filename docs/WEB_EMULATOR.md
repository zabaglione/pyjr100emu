# JR-100 Web Emulator

`web/`は、GitHub Pagesで配布する静的なブラウザ版です。エミュレーターの動作本体は`cpp/`のC++20コアであり、EmscriptenでWebAssemblyへコンパイルしてWeb Workerから呼び出します。CPU、メモリ、VIA、画面、サウンド、PROG/BASICローダーを含む実行ロジックにPythonやPyodideは使いません。

## ROMポリシー

実機ROMはリポジトリへ追加しません。ブラウザ版は次の形式を受け付けます。

- 現行のJR-100 `PROG`コンテナ（開始アドレス `0xE000`、ペイロード8192バイト）
- `0xE000`へ直接マッピングするraw 8192バイトROM

ROM未登録ではCPUを起動せず、選択したROMはIndexedDBへ保存します。設定値はlocalStorageへ保存します。アプリケーションコードはROMバイト列をサーバーへ送信しません。

プライベートブラウズ、容量制限、ブラウザのデータ削除によって保存が失われる場合があるため、配布版ではROMの再登録を常に可能にします。

## 入力

キーボードはJR-100の9行×5ビットを正規のデータ定義として扱います。物理キーボード、HTML仮想キーボード、Gamepad APIはすべて同じ入力ルーターを通ります。Worker側では短いタップを最低2フレーム、CTRL/SHIFTを最低4フレーム保持し、修飾キーを文字キーより1フレーム先にROMへ認識させます。

仮想キーボードは実機と同じ4段45キーの並びです。登録ROMの先頭1024バイトにある128文字×8バイトのフォントと、ROM内の通常／Shiftキーテーブルからキーを描画します。表示状態は次の4通りです。

| 状態 | 主表示 |
| --- | --- |
| 通常 | 英大文字と数字 |
| SHIFT | 対応するShift文字 |
| CTRL+V後のGRAPH | 通常側GRAPH文字 |
| GRAPH+SHIFT | Shift側GRAPH文字 |

CTRLのBASICショートカット名はキー上部へ表示します。CTRL+Vは入力モードをALPHAとGRAPHの間で切り替え、SHIFTの押下・解放と物理キーボード入力も仮想キー表示へ直ちに反映します。

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

## BEEPとVIA割込み

C++コアはVIA T1の周波数変更とPB7ゲートのON/OFFをCPUクロック時刻付きイベントとして記録し、44.1kHz、16bitモノラルの位相連続PCMへ変換します。フレームごとの状態値から発振音を作り直さないため、短いキーBEEPは一つの短い音区間になり、「びびびびび」と再トリガーされません。VIAのIRQはパルスではなくIFRとIERから算出するレベル信号としてCPUへ保持します。

この仕様はpygame版で確立した次の履歴をC++へ移したものです。

- `f638a35`: VIAの時刻付きサウンドイベントと位相連続PCM
- `9b11a18`: VIA IRQをCPUのレベル入力として扱う修正
- `99f1297`: ブラウザのBEEPをループ音源からPCMキューへ置換

各フレームのPCMはWorkerからWeb Audioへ渡します。Web側は最大1024サンプル、約23.2msの小容量キューへ蓄積し、512サンプル到達後にAudioWorkletの128サンプル処理量へ順次供給します。AudioWorkletが使えない環境だけ、512サンプル単位の連続`AudioBufferSourceNode`へフォールバックします。ブラウザの自動再生制限に対応するため、最初のクリックまたはキー入力でAudioContextを開始します。`Sound on/off`でミュート状態を切り替え、設定はlocalStorageへ保存します。

## PROG V1/V2

`Load program`はPROG V1/V2と、通常の`.bas`/`.txt` BASICテキストをメモリへ読み込みます。ファイルはブラウザ内で処理し、保存もアップロードもしません。

- BASICセクションとBASICテキストは、ROMのREADY待ち後に`RUN`を自動タイプします。
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
# Emscripten 6.0.6 and CMake are required.
python tools/build_web.py --verify
python -m http.server 8000 --directory web/dist
```

`http://127.0.0.1:8000/`を開き、実機ROMをファイル選択から登録します。WASMローダーとバイナリを含む実行資産はすべてPages artifact内にあり、外部CDNへ依存しません。GitHub PagesのworkflowはPythonテスト、C++ネイティブテスト、ブラウザモジュールテスト、WASM生成、ROM混入検査を通過してからPages artifactを公開します。

CIのカバレッジ閾値は、ブラウザ境界、JR-100モデル、ジョイスティックアダプターを対象に80パーセントで設定しています。Web artifactは合成raw ROMを使ったPlaywright smoke testで、ROM登録、Worker起動、BEEP PCM、Canvas画面、ROMフォント凡例、4段仮想キーボード、32K RAM、V2 PRG、デバッガ、IndexedDBからの再読み込みを確認します。実機ROMそのものはリポジトリとCIへ含めません。

実機ROMと非公開プログラムを必要とする既存の音声・BASIC・Starfire統合テストは、CIでは明示的に除外します。これらはROMを配置した開発環境で実行し、CIではROM不要のCPU/VIAテストと合成ROMのブラウザsmoke testを実行します。

実機ROMをローカルに配置した環境では、次の追加受入を実行できます。ROMはローカルHTTPサーバーから開いたページへファイル入力するだけで、外部へ送信しません。

```bash
python web/tests/real_rom_qa.py \
  --rom datas/jr100rom.prg \
  --program datas/sound_scale.prg \
  --program datas/twinkle_star.bas \
  --screenshot /tmp/jr100emu.png
```

この受入はREADY表示、通常／SHIFT／GRAPH／GRAPH+SHIFTの文字コード、CTRL+V、AudioWorklet選択、指定プログラム実行中の非ゼロPCM増加、デバッガを確認します。

C++コアとpygame版が使うPythonコアの音声を比較するには、次を実行します。既定で`sound_scale.prg`を1200フレーム、`twinkle_star.bas`を4000フレーム実行し、音区間数、サンプル数、各区間の推定周波数を照合します。命令を止める境界の数十クロック差があるためPCMの完全一致は要求しませんが、反復BEEPは音区間数の不一致として失敗します。

```bash
PYTHONPATH=src python tools/compare_audio.py
```

## 実装上の境界

- `cpp/include/jr100/core.hpp`: ROM検証済みのC++コア公開境界
- `cpp/src/`: CPU、メモリ、VIA、画面、PCM、ローダー実装
- `cpp/src/wasm_api.cpp`: C++コアを公開する小さなC ABI
- `web/worker.js`: C ABIとブラウザメッセージの境界
- `web/matrix-input-core.js`: 短打保持と修飾キー先行走査
- `web/input.js`, `web/keymap.js`: 物理・仮想・Gamepad入力の押下元統合と実機キー変換
- `web/audio.js`: Web AudioのPCMキュー
- `web/virtual-keyboard.js`: 実機配列とROMフォント凡例
- `web/storage.js`: ブラウザ内バイナリ保存と設定保存
- `tools/build_web.py`: C++コアをWASM化し、ROMを含まない静的artifactを生成

JR100_openFPGAはキーマップと実機の操作感を確認する資料としてのみ扱い、GPL-2.0-or-laterのソースコードはC++実装へ取り込んでいません。C++コアはこのリポジトリのPython版と公開されているJR-100仕様を基準に実装しています。
