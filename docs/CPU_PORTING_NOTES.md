# MB8861 移植ノート

## 参照ファイル
- `reference/jr100-emulator-v2/src/jp/asamomiji/emulator/device/MB8861.java`

## フィールド一覧
- レジスタ: `A`, `B` (byte), `IX`, `SP`, `PC` (short)
- フラグ: `CH`, `CI`, `CN`, `CZ`, `CV`, `CC` (boolean)
- 制御フラグ: `resetStatus`, `nmiStatus`, `irqStatus`, `haltStatus`, `haltProcessed`, `fetchWai`
- メモリアクセス: `MemorySystem m`

## 初期化
- コンストラクタ: `MB8861(Computer)` で `computer.getHardware().getMemory()` を取得し `m` に保持
- フィールドは Java デフォルト値でクリア (0 / false)
- `reset()` は `resetStatus = true`
- `halt()` は `haltStatus = true`
- `nmi()` は `nmiStatus = true`
- `irq()` は `irqStatus = true`

## 実行ループ要点 (`execute(long clocks)`)
- `initial_clock = computer.clockCount`
- ループ内で `resetStatus`, `haltStatus`, `fetchWai`, 割り込み状態を処理
- `fetchOp()` で命令を読み取り、巨大な `switch` で各オペコードを処理
- 割り込み処理では `pushAllRegisters()` とベクタ読込 (`VECTOR_NMI`, `VECTOR_IRQ`)
- 各命令はクロックを `computer.clockCount` に加算
- ループ終了で余剰クロックを返す

## ステート保存
- `saveState(StateSet)` / `loadState(StateSet)` で全フィールドを設定

## 次の作業メモ
- Python 実装では `dataclasses` でレジスタ構造体を表現
- `MemorySystem` 相当の API を Python 側で設計し、`load8`/`store8` 等を同名メソッドで再現
- `execute` は命令テーブルを辞書化するよりも `match`/if で Java のまま写経する方針
- 割り込み処理と命令デコーダを段階的に移植し、各フェーズでテストを追加する
- スタック退避／復帰 (`pushAllRegisters`/`popAllRegisters`) を Python で再実装済み。今後は `rti` などで呼び出し確認テストを追加する
- RTI/RTS/SWI/WAI 命令のハンドラを Python でも実装済み。次は命令デコーダへ全面展開し、クロック数と PC 変化を Java と照合するテストを整備する
- 8 ビット算術・論理命令 (AD[A|B], ADC, AND, OR, EOR, CMP, CLR, COM, INC/DEC, TST, DAA, NEG など) を移植済み。ストア命令 (STAA/STAB) と 16 ビットロード/比較/ストア (LDX/LDS/CPX/STX/STS/TXS/TSX)、分岐・ジャンプ命令 (BRA/Bcc/Bsr/JMP/JSR)、拡張ビット演算 (NIM/OIM/XIM/TMM)、ADX も写経済み。Java 版に追加の 16 ビット算術命令は無いので、次は VIA やサウンド/キーボード I/O の移植へ進む

## 進捗管理
- 主要コンポーネント (CPU, VIA, メモリ, I/O, デバッガ) ごとに移植完了チェックリストを作成し、差分が残る箇所を明記する。
- コミットメッセージには対応する Java ファイルとメソッドを列挙し、完全移植済みか部分移植かをタグ化する。
- `/compact` などの履歴圧縮コマンドを利用した場合でも本ドキュメントとチェックリストを更新し、方針を失わないようにする。

## テスト戦略メモ
- pytest のフィクスチャで `Computer` ダミーと `MemorySystem` モックを提供し、`load8`/`load16` などの呼び出しを検証する。
- 割り込みハンドリングのユニットテストを優先し、`reset`/`nmi`/`irq` 呼び出し後に PC とクロックが期待通り変化することを確認する。
- `RTI` と `RTS` のテストでは、スタックへ事前に設定した値が正しく復帰されるか、クロックが 10 / 5 加算されるかを検証する。
- 加算/減算・論理命令のテストでは、キャリーフラグ (CC/CH)、オーバーフローフラグ (CV)、ゼロ・ネガティブ判定が Java 版ロジックと一致するかを同じ入力で確認する。
- 16 ビット命令では Direct/Indexed/Extended 各モードのリトルエンディアン読み書きと、Java 版が持つ既知のバグ (STS のフラグ参照など) まで含めて比較する。
- 分岐命令は条件別に PC が相対オフセットで更新されるか、BSR/JSR が PC を保存してジャンプするかを pytest で確認する。
- 命令テーブルはデータ駆動で検証し、Java 版のテストケース (存在する場合) や実行トレースを pytest に移植して再現する。
- 逐次移植フェーズでは未実装部分に `pytest.xfail` を用いて差分を可視化し、実装完了ごとに解除する。

## 参考資料
- 元リポジトリ: https://github.com/kemusiro/jr100-emulator-v2
- JR-100 リファレンス: ハード仕様書、ROM ダンプ (datas/ 配下、非公開)
- テスト戦略: t-wada さんの TDD + ゆもつよメソッド
