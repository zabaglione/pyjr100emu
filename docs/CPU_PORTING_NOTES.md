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

## 実機仕様を優先したJava版との差分
- RESETはPCを`FFFE`/`FFFF`のベクタ値へ設定するとともにIフラグをセットする。A、B、IX、SPおよびI以外の条件フラグはRESET値を規定しない。Java版はPCだけを設定し、Iフラグをセットしない。
- `ORAB extended` (`0xFA`) は、Java版の `add(B, ...)` ではなく他のアドレシングモードと同じ論理ORを実行する。
- `NEG` のCフラグは、演算前の値が `0x00` 以外ならセットし、`0x00`ならクリアする。Java版はこの極性が逆である。
- NMIとIRQは、割込み前のCCRをスタックへ退避した後、現在のIフラグをセットしてから割込みベクタへ移る。Java版はIフラグをセットしない。
- WAIは9サイクルの命令実行中にPC、IX、A、B、CCRをスタックへ退避してから待機する。WAI後のIRQ/NMI受付では再退避せず、Iフラグ設定とベクタ取得を4サイクルで行う。Java版は退避を割込み到来時まで遅延し、通常割込みと同じ12サイクルに待機ループの1サイクルを加算する。
- IRQ入力はイベントラッチではなくレベル信号として扱う。R6522からassertとdeassertの両方を受け取り、CPUは割込み受付時に線状態を消さない。線がassertされたままRTIでIフラグがクリアされれば、次の命令より先にIRQを再受付する。
- R6522のIERはbit 7による選択的set/clear、IFRのbit 7は読出し専用のIRQ状態として扱う。IER変更、IFR要因の解除、T1CH/SRアクセス、SRモード0、リセット、状態復元の各経路でCPUのIRQ線を同期する。Java版の直代入・解除漏れは踏襲しない。
- 根拠はMotorola『M6800 Programming Reference Manual』の命令定義および割込みシーケンスとする。MB8861Hで追加された5命令以外のMC6800互換命令については、Java版の誤りを互換仕様として維持しない。

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
- WAIのテストでは、9サイクル完了時点のスタック内容、IRQ/NMI受付後の4サイクル応答、再退避しないSP、Iフラグ、RTIによる復帰を確認する。
- IRQ線のテストでは、解除済み要求を後から受け付けないこと、assert継続中はRTI後に再受付すること、R6522のIFR/IER・リセット・状態復元が線状態へ即時反映されることを確認する。
- `RTI` と `RTS` のテストでは、スタックへ事前に設定した値が正しく復帰されるか、クロックが 10 / 5 加算されるかを検証する。
- 加算/減算・論理命令のテストでは、キャリーフラグ (CC/CH)、オーバーフローフラグ (CV)、ゼロ・ネガティブ判定が実機仕様と一致するかを確認する。Java版と異なる場合は一次資料を優先し、差分を本書へ記録する。
- 16 ビット命令では Direct/Indexed/Extended 各モードのリトルエンディアン読み書きと、Java 版が持つ既知のバグ (STS のフラグ参照など) まで含めて比較する。
- 分岐命令は条件別に PC が相対オフセットで更新されるか、BSR/JSR が PC を保存してジャンプするかを pytest で確認する。
- 命令テーブルはデータ駆動で検証し、Java 版のテストケース (存在する場合) や実行トレースを pytest に移植して再現する。
- 逐次移植フェーズでは未実装部分に `pytest.xfail` を用いて差分を可視化し、実装完了ごとに解除する。

## 参考資料
- 元リポジトリ: https://github.com/kemusiro/jr100-emulator-v2
- [Motorola M6800 Programming Reference Manual](https://www.bitsavers.org/components/motorola/6800/Motorola_M6800_Programming_Reference_Manual_M68PRM%28D%29_Nov76.pdf)
- [Motorola MC6800 Microcomputer System Design Data](https://www.bitsavers.org/components/motorola/6800/MC6800_Microcomputer_System_Design_Data_1976.pdf)
- JR-100 リファレンス: ハード仕様書、ROM ダンプ (datas/ 配下、非公開)
- テスト戦略: t-wada さんの TDD + ゆもつよメソッド
