# M1 BASICブート照合に向けたCPU RESET仕様調査

- 調査日：2026-07-23
- 対象：MC6800および、その互換部を持つものとして扱うMB8861H
- 目的：M1ブートトレースの比較開始状態を、RESETに関する一次資料と比較用規約に分離して定義する

## 1. 結論

M1の比較開始状態に関する結論は次のとおりである。

| 項目 | 一次資料から確定できる内容 | M1での扱い |
|---|---|---|
| Iフラグ | RESETシーケンス中に1へセットされる | 1とする |
| H/N/Z/V/C | RESET後の定義値は確認できない | 比較用に0へ正規化する |
| CCのbit 7/6 | プログラミングモデル上は常に`11` | 上記正規化後のトレース値は`$D0` |
| A/B/IX/SP | RESET後の定義値は確認できない | 比較用にすべて0へ正規化する |
| PC | RESETベクタからロードされる | `memory[$FFFE] << 8 \| memory[$FFFF]` |
| RESETベクタ | `$FFFE`が上位、`$FFFF`が下位 | ビッグエンディアン |
| スタック退避 | RESETでは行わない | RESET前のSPやメモリへ依存させない |
| RESET保持時間 | 電源投入時は電源安定後8クロック以上。動作中の再RESETは3回以上の完全なφ2パルス | トレースの命令クロックへ加算しない |
| 最初の命令 | ベクタ読出し後、新PCからopcodeをフェッチする | opcode実行前を比較開始境界とする |

したがって、I以外の可変フラグを0へ正規化する場合、`CC=$C0`は採用できない。
`$C0`はI=0を意味し、RESETがIをセットするというMC6800仕様と矛盾する。
プロジェクトの`11HINZVC`形式で比較用に正規化した値は`CC=$D0`である。

ただし、`$D0`のうちRESET仕様として確定している可変フラグはIだけである。
H/N/Z/V/Cを0とする部分は、A/B/IX/SPを0とするのと同じくロックステップ比較のための規約であって、実機がゼロに初期化するという意味ではない。

## 2. RESETが変更するCPU状態

### 2.1 Iフラグ

Motorola『M6800 Microprocessor Applications Manual』Section 3-2.3は、RESETシーケンスを次の順序で説明している。

1. Interrupt Maskをセットする。
2. `$FFFE/$FFFF`からProgram Counterをロードする。
3. 初期化プログラムへ移る。

同資料Figure 3-2.3-1にも、RESET経路としてIフラグのセットとPCのロードだけが示されている。
したがって、RESETベクタが指す最初の命令を実行する前にI=1となる。

『MC6800 Microcomputer System Design Data』も、RESETルーチン中はInterrupt Maskがセットされ、プログラムがクリアするまでIRQを受け付けないと説明している。

根拠：

- [Motorola, M6800 Microprocessor Applications Manual, 1975](https://www.bitsavers.org/components/motorola/6800/M6800_Microprocessor_Applications_Manual_1975.pdf)
  - Section 3-2.3、Figure 3-2.3-1
  - 印刷ページ3-4から3-5、PDFページ113から114
- [Motorola, MC6800 Microcomputer System Design Data, 1976](https://www.bitsavers.org/components/motorola/6800/MC6800_Microcomputer_System_Design_Data_1976.pdf)
  - 「Processor Controls」の「Reset」
  - 印刷ページ16、PDFページ18

### 2.2 CC全体

MC6800のCondition Code Registerを外部へ表現するときのビット配置は`11HINZVC`である。
RESETでI=1になることは確定できるが、参照した一次資料にはH/N/Z/V/CのRESET値が記載されていない。

このため、実機RESET直後のCC全体を一意の8bit値として確定することはできない。
M1で未定義の可変フラグを0へ正規化する場合に限り、次の比較値になる。

```text
bit: 7 6 5 4 3 2 1 0
     1 1 H I N Z V C
     1 1 0 1 0 0 0 0 = $D0
```

根拠：

- 『MC6800 Microcomputer System Design Data』
  - Figure 11のプログラミングモデル
  - 印刷ページ29、PDFページ31

### 2.3 A/B/IX/SP

参照した一次資料は、RESET後のA、B、IX、SPに数値を定義していない。
RESETフローで明示的に変更されるのはIフラグとPCであり、レジスタのスタック退避も行わない。

『M6800 Microprocessor Applications Manual』は、RESETで到達した初期化プログラムがStack Pointerなどのシステム初期値を設定すると説明している。
この説明からも、SPを含む一般レジスタの利用前にソフトウェアで初期化する必要がある。

したがって、M1でA/B/IX/SPを0とすること自体は妥当だが、次のように位置付ける必要がある。

> A、B、IX、SPはハードウェアRESETで値が保証されないため、ロックステップ比較規約として双方を0へ正規化する。

特に`SP=$0000`は実機RESET仕様ではない。

## 3. RESETベクタとエンディアン

一次資料はRESETベクタを次のように定義している。

```text
$FFFE -> PCH
$FFFF -> PCL
```

したがって、PCは次の式で得られる。

```text
PC = (memory[$FFFE] << 8) | memory[$FFFF]
```

これはビッグエンディアンである。

根拠：

- 『M6800 Microprocessor Applications Manual』
  - Figure 3-2.3-1
  - 印刷ページ3-5、PDFページ114
- 『MC6800 Microcomputer System Design Data』
  - Figure 9「Initialization of MPU After Restart」
  - `$FFFE`を上位8bit、`$FFFF`を下位8bitと明記
  - 印刷ページ27、PDFページ29
- [Motorola, M6800 Programming Reference Manual M68PRM(D), November 1976](https://www.bitsavers.org/components/motorola/6800/Motorola_M6800_Programming_Reference_Manual_M68PRM%28D%29_Nov76.pdf)
  - Section 3.3.1
  - 印刷ページ3-4、PDFページ18

## 4. RESETのタイミングと命令境界

### 4.1 8クロックの意味

電源投入時の「8クロック」はRESET解除後にCPUが消費する命令クロック数ではない。
VCCが4.75Vへ達してから、MPUを再始動可能な状態へ安定させるためにRESETを保持する最低時間である。

動作中に再初期化する場合は、RESETを最低3回の完全なφ2パルスにわたってアサートする。
RESETはクロックに対して非同期に入力できるため、解除位相を含めて単一の「RESET命令サイクル数」へ置き換えることはできない。

根拠：

- 『MC6800 Microcomputer System Design Data』
  - 「Processor Controls」の「Reset」およびFigure 12
  - 印刷ページ16から17、PDFページ18から19
- 『M6800 Microprocessor Applications Manual』
  - Section 4-1.3およびFigure 4-1.3-1
  - 印刷ページ4-13から4-16、PDFページ160から163

### 4.2 RESET解除後のバス順序

RESET解除がセットアップ条件を満たすと、CPUは次の順序で再始動する。

1. `$FFFE`からPC上位byteを読む。
2. `$FFFF`からPC下位byteを読む。
3. 合成した新PCをアドレスバスへ出し、最初のopcodeをフェッチする。
4. そのopcodeの命令を実行する。

Motorola資料はopcode fetchを命令の第1サイクルとしている。
したがって、M1で必要な「最初の命令をまだ実行していない状態」は、ベクタからPCを確定した後、最初のopcodeを実行する前の論理的な命令境界として定義できる。

ただし、実機のバス上に独立した休止サイクルが存在するという意味ではない。
ベクタ読出しの直後に、新PCからのopcode fetchが続く。

### 4.3 RESET確定操作

Python側で`reset(); tick(1)`を使ってRESET要求を処理し、最初の命令を実行する前の状態を作ることは、エミュレータAPI上の操作としては成立する。

しかし、これを次のように説明してはならない。

> 実機のRESETシーケンスが1クロックで完了する。

`tick(1)`はエミュレータ内部で保留中のRESETを確定させるための操作であり、RESET保持時間、2byteのベクタ読出し、最初のopcode fetchという実機バスサイクルを再現したものではない。
実機バスシーケンスを命令クロックへ計上せず、RESET完了状態へ移す比較上の境界操作である。

M1でCPUクロックを0から記録する場合、その0は「実機で電源投入から0クロック」ではなく、次の比較エポックを表す。

> RESETベクタによるPC確定後、最初の命令実行前をclock 0とする。

VIAのサイクル位相を比較する場合は、このCPUトレース上のエポックと、VIAを何内部ティック進めた状態にするかを別々に明記する必要がある。

## 5. M1比較開始状態の推奨定義

一次資料による仕様と比較用正規化を区別したうえで、M1の開始状態を次のように定義する。

| フィールド | 開始値 | 根拠区分 |
|---|---:|---|
| A | `$00` | 比較用正規化 |
| B | `$00` | 比較用正規化 |
| IX | `$0000` | 比較用正規化 |
| SP | `$0000` | 比較用正規化 |
| H/N/Z/V/C | 0 | 比較用正規化 |
| I | 1 | RESET仕様 |
| CC | `$D0` | `11HINZVC`形式で上記を合成 |
| PC | `memory[$FFFE:$FFFF]` | RESET仕様 |

比較開始状態の文章定義は次のとおりである。

> RESET処理が完了し、I=1、PCが`$FFFE/$FFFF`のベクタ値となり、最初の命令をまだ実行していない命令境界をM1ブートトレースの開始点とする。
> ハードウェアRESETで値が保証されないA、B、IX、SP、H、N、Z、V、Cは、ロックステップ比較規約として0へ正規化する。

この定義を採用する場合、MiSTer側とpyjr100emu側の両方で`CC=$D0`を使用する必要がある。

## 6. MB8861Hについて確定できなかった点

公開アクセス可能な富士通公式MB8861Hデータシートまたはハードウェアマニュアルは、今回の調査では発見できなかった。

富士通発行の一次資料として、星川竜輔ほか「MB8861 8ビットマイクロプロセサ」（『Fujitsu』Vol.27 No.5、1976年、pp.887-903）の書誌は確認できるが、公開された本文には到達できない。

- [国立国会図書館サーチの書誌](https://ndlsearch.ndl.go.jp/books/R000000004-I1718286)

したがって、次の点は区別して扱う。

- 本書で一次資料から確定したのはMC6800のRESET仕様である。
- MB8861HのRESET動作にMC6800からの固有差分がないことは、富士通一次資料では独立確認できていない。
- MB8861HのMC6800互換部分へMC6800仕様を適用するというプロジェクト方針に基づく限り、I=1とビッグエンディアンRESETベクタを採用する。
- 将来、富士通のデータシートまたは上記技術記事本文を入手した場合は、RESET固有差分の有無を再確認する。

この制約は`CC=$C0`を支持する根拠にはならない。
今回確認できた一次資料の範囲では、RESET後のI=0を正当化する資料はない。

## 7. 一次資料一覧

1. [Motorola, M6800 Microprocessor Applications Manual, 1975](https://www.bitsavers.org/components/motorola/6800/M6800_Microprocessor_Applications_Manual_1975.pdf)
2. [Motorola, MC6800 Microcomputer System Design Data, 1976](https://www.bitsavers.org/components/motorola/6800/MC6800_Microcomputer_System_Design_Data_1976.pdf)
3. [Motorola, M6800 Programming Reference Manual M68PRM(D), November 1976](https://www.bitsavers.org/components/motorola/6800/Motorola_M6800_Programming_Reference_Manual_M68PRM%28D%29_Nov76.pdf)
4. [国立国会図書館サーチ「MB8861 8ビットマイクロプロセサ」書誌](https://ndlsearch.ndl.go.jp/books/R000000004-I1718286)
