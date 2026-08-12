# JR-100 Web Emulator

`web/` は、GitHub Pagesで配布する静的なブラウザ版です。エミュレーターの動作本体は `src/jr100emu/` の既存コアであり、PyodideのWeb Workerから呼び出します。

## ROMポリシー

実機ROMはリポジトリへ追加しません。ブラウザ版は次の形式を受け付けます。

- 現行のJR-100 `PROG`コンテナ（開始アドレス `0xE000`、ペイロード8192バイト）
- `0xE000`へ直接マッピングするraw 8192バイトROM

ROM未登録ではCPUを起動せず、選択したROMはIndexedDBへ保存します。設定値はlocalStorageへ保存します。アプリケーションコードはROMバイト列をサーバーへ送信しません。

プライベートブラウズ、容量制限、ブラウザのデータ削除によって保存が失われる場合があるため、配布版ではROMの再登録を常に可能にします。

## 入力

キーボードはJR-100の9行×5ビットを正規のデータ定義として扱います。物理キーボード、HTML仮想キーボード、Gamepad APIはすべて同じ入力ルーターを通ります。

ジョイスティックはJR-100拡張I/Oの次のactive-highビットへ接続します。

| 操作 | ビット |
| --- | ---: |
| Right | `0x01` |
| Left | `0x02` |
| Up | `0x04` |
| Down | `0x08` |
| Switch | `0x10` |

仮想キーボードはブラウザのタッチ操作に加えて、GamepadのSelect、D-pad、A/B/X、L1/R1から操作できます。

## ローカルビルド

```bash
python tools/build_web.py --verify
python -m http.server 8000 --directory web/dist
```

`http://127.0.0.1:8000/` を開き、実機ROMをファイル選択から登録します。Pyodideランタイムは固定バージョンをHTTPS CDNから取得します。GitHub PagesのworkflowはPythonテスト、ブラウザモジュールテスト、生成物のROM混入検査を通過してからPages artifactを公開します。

CIのカバレッジ閾値は、ブラウザ境界、JR-100モデル、ジョイスティックアダプターを対象に80パーセントで設定しています。Web artifactは合成raw ROMを使ったPlaywright smoke testで、ROM登録、Worker起動、Canvas画面、仮想キーボード、IndexedDBからの再読み込みを確認します。実機ROMそのものはリポジトリとCIへ含めません。

実機ROMと非公開プログラムを必要とする既存の音声・BASIC・Starfire統合テストは、CIでは明示的に除外します。これらはROMを配置した開発環境で実行し、CIではROM不要のCPU/VIAテストと合成ROMのブラウザsmoke testを実行します。

## 実装上の境界

- `BrowserCore`: ROM検証済みのJR-100コアとフレーム単位の操作
- `web/worker.js`: PyodideとPythonコアの境界
- `web/input.js`: 物理・仮想・Gamepad入力の押下元統合
- `web/storage.js`: ブラウザ内バイナリ保存と設定保存
- `tools/build_web.py`: Pythonソースを静的artifactへ梱包
