# MC6800／R6522 IRQ入力調査

- 調査日：2026-07-23
- 対象：MB8861HのIRQ入力モデル、R6522のIRQ出力、Java版とPython版の接続
- 結論：R6522からCPUへ渡すIRQは、一回限りのイベントではなく、assertとdeassertを持つレベル信号として扱う必要がある

## 結論

MC6800のIRQ入力はアクティブLowのレベル検出である。
CPUが割込みを受理したこと自体では、外部のIRQ線は解除されない。
IRQ線がLowのままRTIやCLIによってIフラグがクリアされると、CPUは次の命令を実行する前にIRQを再受理する。

R6522のIRQ出力は、`IFR[6:0] & IER[6:0]`に一つでも有効な要因がある間Lowを維持する。
最後の有効要因をIFRからクリアするか、IERで無効にするとHighへ戻る。
したがって、R6522のIRQ出力変化をCPUへ接続するAPIは、`irq()`というイベント通知ではなく、`set_irq_line(asserted)`のような線状態の通知でなければならない。

調査開始時点のPython版は、R6522のassertだけをCPUの`irq()`へ通知し、deassertを捨てていた。
CPU側は`irq_requested`を割込み受理時にクリアしていた。
この組合せでは、実機と反対方向の二種類の誤動作が生じる。

- Iフラグがセットされている間にR6522がassertし、その後deassertすると、解除済みの要求がCPU側に残り、Iフラグをクリアした後に偽のIRQを受理する。
- CPUがIRQを受理した後もR6522がassertを維持している場合、RTI後に同じIRQを再受理しない。

現在のPython版は、CPUへassertとdeassertの両方を伝え、CPUが割込み受理時に線状態を消さない。
R6522のIFR／IER書込み、各レジスタアクセスによる割込み要因の解除、リセットと状態復元時の線状態同期も修正済みである。
今回確認したR6522からCPUまでのレベルIRQ経路は、一次資料と一致する状態になった。

## 一次資料

### MC6800のIRQ入力

Motorola『M6800 Microprocessor Applications Manual』の3-2.1節は、IRQ入力をレベル検出と明記し、論理0によって割込みシーケンスを開始すると説明している。
複数の割込み出力をwire-ORしてCPUのIRQ入力へ接続できることも同じ箇所に記載されている。

- [M6800 Microprocessor Applications Manual](https://www.bitsavers.org/components/motorola/6800/M6800_Microprocessor_Applications_Manual_1975.pdf)
- 文書ページ3-2、PDFページ111、3-2.1「INTERRUPT REQUEST (IRQ)」

同書のQ11とQ12は、線がLowのままなら、CLIまたはRTIでIフラグがクリアされた後にIRQが開始されること、RTI直後の通常命令は実行されないことを明記している。

- 同書、文書ページA-12、PDFページ706、Q11およびQ12

ただし、MC6800は単純な組合せレベル入力だけではない。
同じQ10によると、2 MPUサイクル以上継続するIRQパルスを内部ラッチで認識する。
したがって、実機仕様は「レベルを保持する外部線」に加え、「一定時間以上のパルスを捕捉する内部回路」を含む。

今回のR6522接続では、R6522自身が要因を処理するまでIRQをLowに保持するため、CPU側で線状態を維持すれば主要な実機挙動を再現できる。
将来、短いパルスを出す別のIRQ源を追加する場合は、2サイクル以上のパルス捕捉を別途モデル化する必要がある。

MB8861H固有のIRQ入力がMC6800から変更されたことを示す一次資料は、今回の調査では確認できなかった。
本プロジェクトがMB8861HのMC6800互換部分へMC6800仕様を適用する方針であるため、IRQ入力にも上記仕様を採用する。

### R6522のIRQ出力

Rockwell『R6522 Versatile Interface Adapter』は、割込みフラグと対応する割込み許可ビットがともに1になると、IRQ出力がLowになると説明している。
IRQ出力はopen-collectorであり、他デバイスとwire-ORできる。

IFRのbit 7は独立したフラグではなく、次の論理式で決まるIRQ出力状態である。

```text
IRQ = IFR6 & IER6
    | IFR5 & IER5
    | IFR4 & IER4
    | IFR3 & IER3
    | IFR2 & IER2
    | IFR1 & IER1
    | IFR0 & IER0
```

bit 7は直接クリアできない。
すべての有効なIFR要因をクリアするか、有効な割込みをIERで無効にしたときに解除される。

- [Rockwell R6522 Versatile Interface Adapter](https://www.princeton.edu/~mae412/HANDOUTS/Datasheets/6522.pdf)
- 文書ページ2-49、PDFページ14、「Interrupt Operation」「Interrupt Flag Register (IFR)」、Figure 29

IERへの書込みは単純なレジスタ置換ではない。
書込み値のbit 7が1なら、bits 6から0のうち1のビットをセットし、0なら1のビットをクリアする。
書込み値の0のビットは、対応するIERビットを変更しない。

- 同書、文書ページ2-49、PDFページ14、「Interrupt Enable Register (IER)」、Figure 30

この仕様から、IFRが先にセットされている状態でIERを有効化すればIRQは直ちにassertされ、IRQがassertされている状態で最後の対応IERビットを無効化すれば直ちにdeassertされる。

### IFRの解除条件

IFRへ1を書いたビットは、対応する割込みフラグをクリアする。
bit 7は独立したフラグではないため、bit 7への1は無視される。
したがって、`0x80`の書込みはどの要因もクリアせず、`0xff`の書込みはbits 6から0をすべてクリアする。

Figure 29は、個別レジスタアクセスによる解除条件も定めている。

| 割込み要因 | 解除するアクセス |
|---|---|
| Timer 1 | T1 Low-Order Counterの読出し、またはT1 High-Order Counterへの書込み |
| Timer 2 | T2 Low-Order Counterの読出し、またはT2 High-Order Counterへの書込み |
| Shift Register | SRの読出しまたは書込み |
| CA1 | ORAの読出しまたは書込み |
| CA2 | ORAの読出しまたは書込み。ただし独立割込み入力モードを除く |
| CB1 | ORBの読出しまたは書込み |
| CB2 | ORBの読出しまたは書込み。ただし独立割込み入力モードを除く |

- [Rockwell R6522 Versatile Interface Adapter](https://www.princeton.edu/~mae412/HANDOUTS/Datasheets/6522.pdf)
- 文書ページ2-49、PDFページ14、Figure 29

Timer 1の詳細図では、Register 4であるT1 Low-Order Counterの読出しと、Register 5であるT1 High-Order Counterへの書込みがT1フラグをリセットすると明記されている。
Register 7であるT1 High-Order Latchへの書込みには、Rockwell版資料ではフラグ解除の記載がない。

- 同書、文書ページ2-42、PDFページ7、Figure 12およびFigure 13

Shift Registerは、SRの読出しまたは書込みによってフラグをリセットする。
モード0ではSR割込みフラグが論理0に保持されるため、ACRでモード0へ切り替えた場合も、残っているSRフラグをクリアする必要がある。

- 同書、文書ページ2-46、PDFページ11、「SR Mode 0」「SR Mode 1」「SR Mode 2」
- 同書、文書ページ2-47、PDFページ12、「SR Mode 3」「SR Mode 5」

R6522へResetを入力すると、T1／T2のラッチとカウンタおよびSRを除く内部レジスタが0になり、チップからの割込みが無効になる。
Reset前にIRQがassertされていれば、CPUへdeassertを伝えなければならない。

- 同書、文書ページ2-37、PDFページ2、「RESET (RES)」

## Java版の実装

参照したJava版は`kemusiro/jr100-emulator-v2`のコミット`ca1e8ee9d6db60b900c65d31ef8f8965a90a4cf3`である。

Java版`R6522.processIRQ()`は、`IER & IFR & 0x7f`からIFR bit 7を導出し、状態遷移時に`handlerIRQ(1)`または`handlerIRQ(0)`を呼ぶ。
R6522内部のIRQ状態計算は、レベル信号を表現できる構造になっている。

- [Java版R6522.javaの`processIRQ()`](https://github.com/kemusiro/jr100-emulator-v2/blob/ca1e8ee9d6db60b900c65d31ef8f8965a90a4cf3/src/jp/asamomiji/emulator/device/R6522.java#L121-L177)

一方、Java版`JR100R6522`は`handlerIRQ()`をオーバーライドしていない。
そのため、Java版ではR6522のIRQ出力がJR-100のCPUへ接続されていない。

- [Java版JR100R6522.java](https://github.com/kemusiro/jr100-emulator-v2/blob/ca1e8ee9d6db60b900c65d31ef8f8965a90a4cf3/src/jp/asamomiji/emulator/jr100/JR100R6522.java)

Java版CPUの`irq()`は`irqStatus = true`を設定し、割込みを受理すると`irqStatus = false`へ戻す。
これはレベル線ではなく、一回限りのイベントラッチとしての実装である。

- [Java版MB8861.javaの`irq()`](https://github.com/kemusiro/jr100-emulator-v2/blob/ca1e8ee9d6db60b900c65d31ef8f8965a90a4cf3/src/jp/asamomiji/emulator/device/MB8861.java#L267-L275)
- [Java版MB8861.javaのIRQ受付](https://github.com/kemusiro/jr100-emulator-v2/blob/ca1e8ee9d6db60b900c65d31ef8f8965a90a4cf3/src/jp/asamomiji/emulator/device/MB8861.java#L842-L874)

Java版のIER書込みは`IER = value`という直代入であり、bit 7によるset／clear規則を実装していない。
書込み後に`processIRQ()`も呼ばない。

- [Java版R6522.javaのIER書込み](https://github.com/kemusiro/jr100-emulator-v2/blob/ca1e8ee9d6db60b900c65d31ef8f8965a90a4cf3/src/jp/asamomiji/emulator/device/R6522.java#L831-L841)

Java版のIFR書込みは、bit 7が1なら書込み値を`0x7f`へ置き換える。
このため`0x80`の書込みで全割込み要因を誤ってクリアする。
Timer 1 High-Order Counterへの書込みと、SRモード0でのSRアクセスも、必要なフラグ解除を実装していない。

- [Java版R6522.javaのIFR書込み](https://github.com/kemusiro/jr100-emulator-v2/blob/ca1e8ee9d6db60b900c65d31ef8f8965a90a4cf3/src/jp/asamomiji/emulator/device/R6522.java#L729-L841)

Java版はPython版の移植元として有用だが、CPUとR6522のIRQ接続、IFR／IER書込みおよび一部レジスタアクセスによるフラグ解除については、実機仕様の正解として採用できない。

## Python版の評価

### 調査開始時点のIRQ線

調査開始時点の`src/jr100emu/jr100/r6522.py`は、`handler_irq(1)`だけをCPUの`irq()`へ渡し、`handler_irq(0)`を無視していた。
`src/jr100emu/cpu/cpu.py`は、IRQ受付時に`irq_requested`をクリアしていた。

この構造では、解除済みIRQの偽受理と、assert継続中の再受理漏れが発生する。

### 修正後のIRQ線

現在の実装は次の構造へ移行している。

- R6522の`handler_irq(state)`がassertとdeassertの両方をCPUへ渡す。
- CPUの`set_irq_line(asserted)`が線状態を保持する。
- CPUはIRQを受理しても線状態をクリアしない。
- R6522がdeassertした時点でCPUの線状態をクリアする。

これにより、解除済みIRQの偽受理と、assert継続中の再受理漏れを解消した。
`CPUStatus.irq_requested`は、変更後には「未処理イベント」ではなく「IRQ線がassert中」を意味するため、将来は`irq_line_asserted`への改名を検討した方がよい。

互換用の`irq()`が`set_irq_line(True)`だけを呼ぶ場合、その呼出しは一回限りのIRQイベントではなく、「外部IRQ線をassertし、別途deassertされるまで維持する」という意味になる。
この契約は`irq()`と`set_irq_line()`のdocstringおよび`docs/CPU_PORTING_NOTES.md`へ記録した。
テストや将来の割込み源は、`irq()`を一回限りのイベント通知として使ってはならない。

### 調査開始時点のIER書込み

調査開始時点の`src/jr100emu/via/r6522.py`は、Java版と同じく`self._state.IER = value`と直代入していた。
書込み後に`process_irq()`を呼ばない。

この実装には次の問題があった。

- `0x80 | mask`で指定ビットだけを有効化するR6522本来の書込みを、レジスタ全体の置換として処理する。
- `mask`で指定ビットだけを無効化する書込みを、指定値そのものへの置換として処理する。
- 無効中に立っていたIFR要因を後から有効化しても、IRQをassertしない。
- assert中の最後の有効要因をIERで無効化しても、IRQをdeassertしない。

現在は次のset／clear処理を実装し、書込み直後にIRQ状態を再評価する。

```text
if value & 0x80:
    IER |= value & 0x7f
else:
    IER &= ~(value & 0x7f)
IER &= 0x7f
process_irq()
```

調査開始時点のテストには、bit 7を付けずに`0x40`を書いてTimer 1割込みを有効化するケースがあった。
実機では`0x40`はTimer 1許可ビットのクリア命令であり、有効化には`0xc0`を書かなければならない。
このテストも実機形式へ修正済みである。

### 調査開始時点のIFR書込みとレジスタアクセス

調査開始時点のIFR書込みもJava版を踏襲し、書込み値のbit 7が1なら`0x7f`へ置き換えていた。
このため、`0x80`単独の書込みで全要因を誤ってクリアしていた。

レジスタアクセスとIFR解除の調査開始時点における照合結果は次のとおりである。

| アクセス | 調査開始時点のPython版 | 判定 |
|---|---|---|
| T1CL読出し | T1フラグをクリア | 一致 |
| T1CH書込み | T1フラグをクリアしない | 不一致 |
| T1LH書込み | T1フラグをクリアしない | Rockwell版資料と一致 |
| T2CL読出し | T2フラグをクリア | 一致 |
| T2CH書込み | T2フラグをクリア | 一致 |
| SR読出し／書込み | シフト動作モードでは初期化処理を通じてクリアするが、モード0ではクリアしない | 不一致 |
| ORA読出し／書込み | CA1と、独立入力以外のCA2をクリア | 一致 |
| ORB読出し／書込み | CB1と、独立入力以外のCB2をクリア | 一致 |
| IORANH読出し／書込み | CA1／CA2をクリアしない | 一致 |

### 修正後のIFR書込みとレジスタアクセス

現在は次の処理を実装済みである。

- IFR書込みではbit 7を無視し、`value & 0x7f`で指定した要因だけをクリアする。
- T1CH書込みでTimer 1フラグをクリアする。
- SRの読出しと書込みで、モードによらずSRフラグをクリアする。
- ACRでSRモード0を選択すると、シフト動作を停止してSRフラグをクリアする。
- 調査開始時点から正しかったT1CL、T2CL、T2CH、ORA、ORB、IORANHの挙動を維持する。

### 調査開始時点のリセットと状態復元

調査開始時点のR6522の`reset()`はIFRとIERを0へ戻すが、変更前のIRQ出力がassert中でもCPUへdeassertを通知しなかった。
状態復元も、CPUの`irq_requested`とR6522のIFR／IERを別々に復元し、復元後の線状態を再計算していなかった。

### 修正後のリセットと状態復元

現在は、R6522のリセット前にIRQがassertされていればCPUへdeassertを通知する。
`R6522.load_state()`は、復元値のIERとIFRを7ビットへ正規化し、`IFR & IER`からIRQ状態を再計算してCPUへ強制通知する。
これにより、VIAだけをリセットした場合と、`R6522.load_state()`の完了時点で、CPUとR6522の線状態が一致する。

## 実施した修正と残る課題

今回実施した修正は次のとおりである。

1. CPUにIRQ線状態を設定するAPIを追加し、割込み受付時には線状態をクリアしない。
2. JR-100のR6522接続からassertとdeassertの両方をCPUへ渡す。
3. IERのbit 7によるset／clear書込みを実装し、書込み後にIRQ状態を再評価する。
4. IFR書込みではbit 7を無視し、bits 6から0で指定した要因だけをクリアする。
5. T1CH書込みとSR読出し／書込みで、対応するIFR要因をクリアする。
6. ACRでSRモード0を選択したとき、SRフラグをクリアする。
7. VIAリセット時にIRQをdeassertし、状態復元後にIRQ線を強制同期する。

短いIRQパルスの内部ラッチは、この修正とは分けて扱う。
JR-100のR6522はIRQを保持するため、今回のCPU／VIA接続における必須条件ではない。
将来、短いパルスを出す別のIRQ源を追加する場合に検討する。

`CPUStatus.irq_requested`から`irq_line_asserted`への改名は、状態ファイルとの互換性を考慮して今回は見送った。
これは可読性の課題であり、今回確認したR6522の実行互換性を妨げる未修正ではない。

## 回帰テスト

### CPU単体

- IRQ線をassertし、Iフラグが0ならIRQを受理する。
- IRQ線をassertしたままRTIでIフラグを0へ戻すと、通常命令を挟まず再度IRQを受理する。
- Iフラグが1の間にIRQ線をassertしてからdeassertし、その後Iフラグを0へ戻してもIRQを受理しない。
- WAI中にIフラグが0でIRQ線をassertすると、WAIから復帰する。
- WAI中にIフラグが1ならIRQ線をassertしても待機を継続し、deassert後に偽のIRQを受理しない。

### R6522単体

- 対応IERが有効なIFR要因をセットすると、IFR bit 7が1になりIRQをassertする。
- 最後の有効なIFR要因をクリアすると、IFR bit 7が0になりIRQをdeassertする。
- 複数の有効要因があるとき、一つだけをクリアしてもIRQを維持する。
- IFR要因を先にセットし、IERへ`0x80 | mask`を書いて有効化するとIRQをassertする。
- IRQ assert中にIERへ`mask`を書いて最後の要因を無効化すると、IFR要因を残したままIRQをdeassertする。
- IER書込みの0ビットが、対応する既存IERビットを変更しない。
- IFRへ`0x80`を書いてもbits 6から0を変更せず、`0xff`ならすべてクリアする。
- T1CL読出しとT1CH書込みがT1フラグをクリアし、T1LH書込みはクリアしない。
- T2CL読出しとT2CH書込みがT2フラグをクリアする。
- SRの読出しと書込みが、ACRのモードによらずSRフラグをクリアする。
- ACRでSRモード0を選択すると、既存のSRフラグをクリアする。
- ORA／ORBアクセスによるCA／CBフラグ解除が、独立割込み入力モードの要因を保持する。

### CPU／VIA統合

- Timer 1のIFR／IERによるassertがCPUへ伝わる。
- CPUがIRQを受理した後もTimer 1要因をクリアしなければ、RTI後に再受理する。
- Timer 1 Low Counter読出しでIFR要因をクリアするとCPU側もdeassertし、その後は再受理しない。
- IRQ assert中にIERでTimer 1を無効化するとCPU側もdeassertする。
- VIAリセットと状態復元の後、CPUの線状態が`IFR & IER`と一致する。
