# MC6800 / MB8861H WAI動作調査

- 調査日: 2026-07-23
- 対象: MC6800互換部およびMB8861Hの`WAI`（opcode `$3E`）
- 目的: WAI実行時の退避時期、割込み受付時の動作、サイクル数を一次資料から確定し、Java版とPython版の実装を評価する

## 1. 結論

MC6800互換部として実装すべきWAI動作は次のとおりである。

1. WAI命令自身の実行中に、次命令を指すPCと、IX、A、B、CCRをスタックへ一度だけ退避する。
2. WAI命令は9サイクルであり、この9サイクルにレジスタ退避を含む。
3. WAIはIフラグを変更せず、その時点のIフラグを含むCCRをスタックへ退避する。
4. WAI待機中に受付可能なIRQを受けた場合、レジスタを再退避しない。現在のIフラグをセットし、IRQベクタへ移る。所要時間は追加4サイクルである。
5. WAI待機中にNMIを受けた場合も、レジスタを再退避しない。現在のIフラグをセットし、NMIベクタへ移る。所要時間は追加4サイクルである。
6. Iフラグがセットされた状態ではIRQを受け付けず、WAI待機を継続する。待機から抜けられるのはNMIまたはRESETである。
7. RTIはWAIが事前退避した状態を復元するため、PCはWAI直後の命令を指し、IフラグもWAI実行前の値へ戻る。

したがって、Java版の「WAIでは退避せず、割込み発生時に退避する」実装は実機仕様と異なる。調査開始時点のPython版もJava版と同様に、WAIでは退避せず、IRQ/NMI到来時に再退避して12サイクルを加算し、さらに待機ループの1サイクルを加算していた。現在のPython版は、WAI実行時に一度だけ退避し、WAI後のIRQ/NMIをともに「再退避なし、追加4サイクル」とするよう修正済みである。

## 2. 一次資料から確定できる動作

### 2.1 WAI実行時の退避時期と退避内容

Motorolaの『M6800 Microprocessor Applications Manual』Figure 1-3.4.2-7（印刷ページ1-37、PDFページ58）は、WAI経路を次の順序で示している。

1. WAI opcode `$3E`を実行する。
2. MPUレジスタをスタックへ退避する。
3. Wait Loopへ入る。
4. IRQまたはNMIを待つ。

同マニュアルの直後の説明（印刷ページ1-38、PDFページ59）は、WAIがMPU内容をスタックしてから割込みを待ち、ハードウェア割込みシーケンスからスタック時間を取り除く命令であると説明している。したがって、退避は割込み発生時ではなくWAI命令の実行中に完了する。

『M6800 Programming Reference Manual』のWAI命令記述（Appendix A、印刷ページA-76、PDFページ108）では、退避順序を次のように定義している。

| 書込み順 | 初期SPからの位置 | 内容 |
|---:|---:|---|
| 1 | `SP` | PCL |
| 2 | `SP - 1` | PCH |
| 3 | `SP - 2` | IXL |
| 4 | `SP - 3` | IXH |
| 5 | `SP - 4` | ACCA |
| 6 | `SP - 5` | ACCB |
| 7 | `SP - 6` | CCR |

各バイトの格納後にSPを1減算するため、完了後のSPは初期値から7減った値になる。CCRのbit 5からbit 0にはH、I、N、Z、V、Cを格納し、bit 7とbit 6は1として格納する。PCはWAI opcodeの次を指す値、すなわちWAIのアドレスに1を加えた値を退避する。

同マニュアルSection 3.2（印刷ページ3-3から3-4、PDFページ17から18）は、WAIで保存されるPCがWAIアドレス+1であり、その他のレジスタはWAI直前の命令を実行した結果であることも明記している。

一次資料:

- [Motorola, M6800 Microprocessor Applications Manual, 1975](https://www.bitsavers.org/components/motorola/6800/M6800_Microprocessor_Applications_Manual_1975.pdf)
- [Motorola, M6800 Microcomputer System Design Data, 1976](https://www.bitsavers.org/components/motorola/6800/MC6800_Microcomputer_System_Design_Data_1976.pdf)
- [Motorola, M6800 Programming Reference Manual M68PRM(D), November 1976](https://www.bitsavers.org/components/motorola/6800/Motorola_M6800_Programming_Reference_Manual_M68PRM%28D%29_Nov76.pdf)

### 2.2 WAI待機中のIRQ

『M6800 Programming Reference Manual』Section 3.3.4（印刷ページ3-5から3-6、PDFページ19から20）は、通常のIRQではMPU状態をスタックへ退避するが、直前にWAIを実行している場合はWAIによってPCとMPU状態がすでに退避済みなので再退避しないと明記している。その後にIフラグをセットし、IRQベクタをPCへロードする。

同マニュアルSection 3.3.5とWAI命令記述は、WAI自身がIフラグを変更せず、IRQを受け付けた時点で初めてIフラグをセットすることを示している。したがって、スタック上のCCRには割込み受付後のI=1ではなく、WAI実行時のIの値が保存される。

WAI実行時にI=1だった場合、IRQには応答しない。Section 3.3.5は、状態退避後に実行を停止し、NMIまたはRESETだけが実行を再開できると明記している。

### 2.3 WAI待機中のNMI

『M6800 Microprocessor Applications Manual』Figure 1-3.4.2-7では、WAIは先に一度だけ共通の「Stack MPU Register Contents」を通ってWait Loopへ入る。Wait LoopからNMIを受けた経路は、再びスタック処理へ戻らず、そのままNMIベクタ`$FFFC/$FFFD`とIフラグ設定へ進む。

同図は通常実行中のNMIについてはスタック処理を通る別経路を示しているため、WAI後のNMIが再退避を省略することは図の経路上も明確である。また、同マニュアルの説明はWAIが「hardware interrupt」のスタック時間を取り除くとしており、IRQだけに限定していない。

『M6800 Microcomputer System Design Data』の割込み説明（印刷ページ16、PDFページ18）は、IRQとNMIのシーケンスはベクタ以外同一で、WAI後はスタック処理がすでに完了していると説明している。同資料Figure 14（印刷ページ18、PDFページ20）は入力を「IRQ or NMI」と明記し、WAIの9サイクルで7バイトを退避した後、割込み受付時にはスタック書込みを行わずIフラグ設定とベクタ読出しへ進むタイミングを示している。

NMIはIフラグの状態にかかわらず受付可能である。『M6800 Microprocessor Applications Manual』Section 3-2.2（印刷ページ3-4、PDFページ113）は、通常のNMIシーケンスを「現在命令を完了し、レジスタをスタックし、Iフラグをセットし、`$FFFC/$FFFD`からベクタを取得する」と説明している。WAI後はこのうちスタック処理だけがすでに完了している。

### 2.4 Iフラグをセットする順序

通常のIRQでは、一次資料が次の順序を明示している。

1. 割込み前の状態をスタックへ退避する。
2. 現在のIフラグをセットする。
3. 割込みベクタをPCへロードする。

WAI経路では手順1がWAI命令の9サイクル内で先に完了している。WAIはIフラグを変更しないため、IRQまたはNMIを受け付けた後に現在のIフラグをセットする。したがってRTIは、スタック上に残っているWAI実行時のIフラグを復元できる。

『M6800 Microprocessor Applications Manual』Figure 1-3.4.2-7は、WAIからIRQ/NMIベクタへ向かう経路がスタック処理を再通過せず、「Set Interrupt Mask (CCR 4)」を経て割込みプログラムへ進む構造を示している。

### 2.5 サイクル数

『M6800 Programming Reference Manual』のWAI命令表は、WAIを9サイクルと定義している。同マニュアルFigure 4-1（印刷ページ4-2、PDFページ26）の注記は、通常の割込み時間が命令終了から12サイクルであるのに対し、WAI後は4サイクルであると明記している。

『M6800 Microcomputer System Design Data』Table 8（印刷ページ38、PDFページ40）は、WAIのcycle 1をopcode fetch、cycle 2を次opcodeのread、cycle 3から9をPCL、PCH、IXL、IXH、A、B、CCRのwriteとして示している。同資料の実行時間表（印刷ページ34、PDFページ36）も、通常の割込み時間を12サイクル、WAI後を4サイクルとしている。

『M6800 Microprocessor Applications Manual』AppendixのQ20（印刷ページA-14、PDFページ708）も、WAI後に割込みシーケンスを開始するために4 MPUサイクル必要と回答している。

命令単位エミュレータでは、次の加算モデルになる。

| 状況 | 加算サイクル |
|---|---:|
| WAI命令の実行と事前退避 | 9 |
| WAI待機中の1サイクル分の経過 | 1ずつ |
| WAI後の受付可能なIRQからベクタ移行 | 4 |
| WAI後のNMIからベクタ移行 | 4 |
| 通常実行中のIRQまたはNMI | 12 |

割込みがWAI実行直後からすでに受付可能な場合は、WAIの9サイクルと割込み移行の4サイクルを合わせ、割込みルーチン開始まで13サイクルとなる。

### 2.6 IRQがI=1の場合と信号の性質

IRQはレベル検出であり、I=1の間は応答しない。『M6800 Programming Reference Manual』Section 3.3.4は、I=1の間は通常プログラムを実行し続け、I=0になって初めてIRQへ応答するとしている。一方、WAI中は命令を実行しないため、I=1のままWAIへ入るとソフトウェアでIをクリアできない。結果としてNMIまたはRESETが必要になる。

実装上は、IRQを永久に残るイベントとしてではなく、IRQ入力線のアサート状態として扱う必要がある。I=1の間にIRQ線が非アサートへ戻った場合、後からIが0になったことだけを理由に、すでに解除されたIRQを受付してはならない。これはWAIだけでなく通常実行時にも関係する入力モデル上の注意点である。

NMIは負エッジで開始され、Iフラグではマスクされない。

## 3. 資料間の表現差

『M6800 Programming Reference Manual』Section 3.3.4は、WAI後のIRQについて「すでに退避済みなので再退避しない」と明記している。一方、Section 3.3.2および3.3.2のNMI説明は、一般的なNMIが状態を退避すると説明するだけで、直前がWAIだった場合の例外を文章では繰り返していない。

このため同マニュアルのNMI節だけを単独で読むと、WAI後のNMIも再退避するように解釈できる余地がある。しかし、次の一次資料上の証拠を総合すると、これはNMI節でWAI例外を省略した編集上の曖昧さと判断できる。

- 『M6800 Microprocessor Applications Manual』Figure 1-3.4.2-7は、WAI後のNMIを再退避なしでNMIベクタへ接続している。
- 同マニュアルはWAIがハードウェア割込みのスタック時間を取り除くと説明し、IRQだけに限定していない。
- 『M6800 Microcomputer System Design Data』Figure 14はIRQとNMIを同じWAI解除入力として扱い、解除後にスタックwrite cycleがないことをタイミング図で示している。
- 『M6800 Programming Reference Manual』のサイクル表は、WAI後の「interrupt time」を通常12サイクルから4サイクルへ短縮するとし、IRQだけに限定していない。

したがって、実装仕様としてはWAI後のIRQとNMIをともに「再退避なし、追加4サイクル」とする。

## 4. Fujitsu MB8861H資料について

富士通の一次資料として、星川竜輔ほか「MB8861 8ビットマイクロプロセサ」（『Fujitsu』Vol.27 No.5、1976年、pp.887-903）の書誌を確認したが、公開された本文には到達できなかった。

- [国立国会図書館サーチの書誌](https://ndlsearch.ndl.go.jp/books/R000000004-I1718286)

このため、本調査ではFujitsu資料からWAIの詳細動作を直接確認したとは扱わない。MB8861Hの追加命令ではないMC6800互換命令WAIについて、Motorolaの一次資料を実装根拠とする。将来Fujitsuの命令マニュアルまたは上記論文本文を入手できた場合は、MB8861H固有差分の有無を再確認する。

## 5. Java版の実装評価

参照したJava版は`kemusiro/jr100-emulator-v2`のcommit `ca1e8ee9d6db60b900c65d31ef8f8965a90a4cf3`である。

- [Java版MB8861.java](https://github.com/kemusiro/jr100-emulator-v2/blob/ca1e8ee9d6db60b900c65d31ef8f8965a90a4cf3/src/jp/asamomiji/emulator/device/MB8861.java)

Java版の相違点は次のとおりである。

| 項目 | Java版 | 一次資料による仕様 |
|---|---|---|
| WAI実行時 | `fetchWai = true`のみ | 7バイトを退避してから待機 |
| WAIの9サイクル | 9を加算するが退避しない | 退避を含む9サイクル |
| WAI後IRQ | 割込み時に退避し、12サイクルを加算 | 再退避せず4サイクル |
| WAI後NMI | 割込み時に退避し、12サイクルを加算 | 再退避せず4サイクル |
| 割込み後Iフラグ | 元実装はセットしない | 退避後にセット |

さらにWAI待機分岐の末尾で無条件に1サイクルを加算するため、割込みを処理した反復では12に1を加えた13サイクルを消費する。NMIとIRQの判定が独立した`if`であり、Iフラグもセットしないため、両要求が同時に立っている場合は同じ反復で二重退避し、後のIRQベクタでNMIベクタを上書きする可能性もある。

Java版は互換性比較対象としては有用だが、WAIと割込みについては実機仕様の正解として採用できない。

## 6. Python版の実装評価

調査時の対象は`src/jr100emu/cpu/cpu.py`である。

現在の設計で維持すべき点:

- `_fetch_op()`がPCをWAI直後へ進めた後、`_wai()`が`_push_all_registers()`を呼ぶ。
- `_wai()`はIフラグを変更しない。
- WAI命令へ9サイクルを加算する。
- WAI後のIRQでは再退避せず、IフラグをセットしてIRQベクタへ移り、4サイクルを加算する。
- WAI後のNMIでも再退避せず、IフラグをセットしてNMIベクタへ移り、4サイクルを加算する。
- I=1のIRQでは`fetch_wai`を解除しない。

追加で注意すべき点:

- `irq_requested`は現在booleanの要求ラッチとして扱われ、VIAのIRQ解除時にCPU側へ解除が伝わらない。実機IRQはレベル入力なので、マスク中に発生して解除済みのIRQを将来誤って受付する可能性がある。この問題はWAIの事前退避修正とは別に、IRQ線のassert/deassertモデルとして検討する。
- WAI中のアイドル時間を1サイクルずつ進める現在の方式は、命令単位エミュレータとして妥当である。ただし、割込みを受付した反復で追加のアイドル1サイクルを加えてはならない。

## 7. 必要な回帰テスト

最低限、次のテストを固定する。

1. WAIを9サイクル実行した直後、SPが7減り、PC+1、IX、A、B、CCRが正しい順で保存されている。
2. WAIはIフラグを変更せず、スタック上のCCRにWAI実行前のIが保存される。
3. I=0でWAI後にIRQを与えると、SPをさらに減らさず4サイクルでIRQベクタへ移り、現在のIが1になる。
4. WAI後のIRQからRTIすると、PC、各レジスタ、SP、IがWAI直後の状態へ戻る。
5. I=1でWAI後にIRQを与えても、PCとSPを変えずWAIを継続する。
6. I=0とI=1の双方で、WAI後のNMIがSPをさらに減らさず4サイクルでNMIベクタへ移る。
7. WAI後のNMIからRTIすると、WAI直後の状態へ戻る。
8. WAI待機中に割込みがない場合、PC、SP、レジスタを変えず、経過クロックだけが増える。
9. 通常実行中のIRQ/NMIは7バイトを退避し、退避後にIをセットし、12サイクルを消費する。
10. IRQ線をレベル入力として扱う場合、I=1の間にassertしてdeassertしたIRQを、後からI=0になった際に受付しない。

## 8. 実装判断

WAIに関してはJava版との一致よりMotorola一次資料との一致を優先する。採用仕様を短く表すと次のようになる。

```text
WAI:
  PC already points to the next instruction
  push PC, IX, A, B, CCR
  keep I unchanged
  enter wait
  cycles += 9

IRQ while waiting and I == 0:
  do not push again
  set I
  load IRQ vector
  leave wait
  cycles += 4

IRQ while waiting and I == 1:
  remain waiting

NMI while waiting:
  do not push again
  set I
  load NMI vector
  leave wait
  cycles += 4
```
