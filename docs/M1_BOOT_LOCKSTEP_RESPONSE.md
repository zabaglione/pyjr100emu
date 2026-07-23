# M1 BASIC起動照合要件への調査回答

- 調査日: 2026-07-23
- 対象: MiSTer側から提示された「M1 BASIC起動照合（ブートトレース）必要要件」
- 結論: `--boot`によるコールドブート照合は妥当。ただしRESET直後のCC、VIAのRESET状態、VIA差分の受入条件を修正する必要がある

## 指示対象対応表

| 出典 | 目的 | 具体対象 | 役割 | 前後関係 | 候補語 | 初出定義 |
|---|---|---|---|---|---|---|
| `Computer.reset()` | システムを再初期化する | クロック、CPUのRESET要求、登録デバイス | RESET処理を即時適用する | `tick(1)`より前 | システムリセット | `computer.reset()`呼出し内で即時実行されるシステムとデバイスの初期化 |
| `reset(); tick(1)` | 比較可能なCPU状態を作る | PC、Iフラグ、CPUクロック、VIA内部クロック | 最初の命令を実行せずRESETを確定する | システムリセット後、最初の命令前 | ブート比較開始境界 | PCがRESETベクタ値、I=1、CPUクロック=0で、最初の命令をまだ実行していない境界 |
| `debug_runner --boot` | 未定義値を排除する | A、B、IX、SP、H/N/Z/V/C | PythonとHDLへ同じ比較用初期値を与える | ブート比較開始境界の直後 | ブート比較規約 | ハードウェアRESETで値が保証されないレジスタとフラグを双方で同じ値へ正規化する規約 |
| VRAM `C100:C3FF` | BASIC起動完了を確認する | 表示コードの`READY`列とVRAM全体 | 起動完了の補助判定と最終比較を行う | ROM初期化処理後 | READY表示到達境界 | VRAMの所定位置に`READY`が完成した最初の命令境界 |
| TRACE_FORMAT v1 | VIA一致を判定する | ORA、ORB、DDR、ACR、PCR、IFR、IER、SR、T1/T2 | ソフトウェアから観測できるVIA状態を比較する | 各CPU命令の完了後 | 観測可能VIA状態 | TRACE_FORMAT v1へ出力されるVIAレジスタ、カウンタ、ラッチの集合 |
| R6522 `current_clock` | デバイス実行位置を管理する | Python内部のVIAクロック | CPUクロックへVIAを追従させる | CPU命令実行とデバイス更新の間 | VIA内部同期状態 | TRACE_FORMAT v1には含まれないエミュレータ内部の同期管理値 |

## 調査結論

提示要件のうち、次の方針は妥当である。

- `--boot`ではユーザープログラムをロードせず、ROMのRESETベクタから実行する
- 80,000サイクルのウォームアップを省略し、新規生成されたゼロRAMから開始する
- A、B、IX、SPを比較用に`0x0000`へ正規化する
- 固定サイクルによる初回測定と、ROM固有の入力待ちループPCによる再現実行を使い分ける
- CGRAM、VRAM、BASICワークエリアを最終メモリ比較へ含める
- バスアクセス位置の補正は、実際の発散を確認してから別途承認を得て着手する

次の3点は修正が必要である。

1. ブート開始CCは`0xC0`ではなく`0xD0`とする
2. 「VIAの全レジスタがRESETでゼロになる」という一般化を行わない
3. TRACE_FORMAT v1のVIAフィールド差分を、M1の既定条件として許容しない

## RESET処理の実装事実

`Computer.reset()`は「次のtickで実行される」のではない。
遅延0のイベントを登録した直後、`_schedule_event()`がイベントを処理するため、次の処理が`reset()`呼出し内で完了する。

- `clock_count=0`
- CPUへRESET要求を設定
- VIAを含む登録デバイスの`reset()`を呼び出す
- 実行中だった場合は周期タスクを再開する

CPUのRESET要求は続く`tick(1)`内で処理される。
このときCPUはRESETベクタからPCをロードしてCPUクロックを0に戻し、通常命令を実行せずに`execute()`を終了する。
その後、デバイス実行によりVIAの`current_clock`が0から1へ進む。

したがって、現在のPython実装におけるブート比較開始境界は次の状態である。

```text
computer.clock_count = 0
cpu.PC = memory[0xFFFE] << 8 | memory[0xFFFF]
cpu.I = 1
via.current_clock = 1
CPUの最初の通常命令は未実行
```

ここでの`tick(1)`は、実機の物理RESETシーケンスを1クロックで再現するという意味ではない。
Pythonエミュレータ内で保留中のCPU RESETを確定し、デバイス同期を成立させる操作である。

## CPU RESET状態

MotorolaのMC6800一次資料は、RESETシーケンス中にInterrupt Maskをセットし、`FFFE`と`FFFF`からPCをロードすると明記している。
`FFFE`が上位8ビット、`FFFF`が下位8ビットである。

- [Motorola M6800 Programming Reference Manual](https://www.bitsavers.org/components/motorola/6800/Motorola_M6800_Programming_Reference_Manual_M68PRM%28D%29_Nov76.pdf)、3.3.1
- [Motorola M6800 Microcomputer System Design Data](https://www.bitsavers.org/components/motorola/6800/MC6800_Microcomputer_System_Design_Data_1976.pdf)、RESET説明およびInitialization of MPU After Restart

一方、RESETによるA、B、IX、SP、H、N、Z、V、Cの定義値は確認できない。
そのため、次の値をブート比較規約として採用する。

```text
A  = 0x00
B  = 0x00
IX = 0x0000
SP = 0x0000
CC = 0xD0
PC = memory[0xFFFE] << 8 | memory[0xFFFF]
```

`CC=0xD0`のうち、I=1はRESET仕様である。
H/N/Z/V/C=0は未定義値を排除するための比較規約であり、実機がCC全体を`0xD0`へ初期化するという意味ではない。

公開アクセス可能な富士通MB8861H一次資料ではRESETシーケンスを独立確認できなかった。
本プロジェクトではMB8861HのMC6800互換部分へMC6800仕様を適用する方針に基づき、このRESET仕様を採用する。

## R6522 RESET状態

RockwellのR6522一次資料では、RESETによって内部レジスタを0にするが、次の保存領域は例外とされている。

- Timer 1のカウンタとラッチ
- Timer 2のカウンタとラッチ
- Shift Register

RESETはタイマ、シフト動作、割込みを無効化するが、上記の保存内容そのものはクリアしない。

- [Rockwell R6522 Versatile Interface Adapter](https://library.defence-force.org/books/content/datasheet/rockwell_r6522_via.pdf)、RESET (RES)
- [Rockwell Electronic Devices Division Data Book](https://bitsavers.computerhistory.org/components/rockwell/_dataBooks/1981_Rockwell_Electronic_Devices_Division_Data_Book.pdf)、R6522/R6522A Pin Descriptions

したがって、要件にある「VIAは全レジスタゼロ」は一般のRESET仕様としては不正確である。

ただし、M1のコールドブートでは新規生成されたVIA状態のカウンタ、ラッチ、SRが元から0である。
その状態へRESETを適用するため、ブート比較開始境界では結果的にすべて0となる。
MiSTer側も次の二つを区別する必要がある。

- FPGA構成直後のコールドスタート: T1/T2カウンタ、ラッチ、SRを比較規約として0から開始してよい
- 実行中のRESET: T1/T2カウンタ、ラッチ、SRを保持し、制御レジスタと動作許可をリセットする

## ウォームアップの扱い

`debug_runner`の従来の80,000サイクル実行後に`reset()`しても、メインRAM、VRAM、CGRAMはクリアされない。
これはコールドブートではなく、ROMを一度実行してメモリを変更した後のウォームRESETになる。

M1では次の順序を採用する。

1. `JR100Computer`を新規構築する
2. CPU通常命令を実行しない
3. `computer.reset()`を呼び出す
4. `computer.tick(1)`でCPU RESETを確定する
5. ブート比較規約を適用する
6. 必要なら初期メモリイメージを保存する
7. 命令境界トレースを開始する

## READY判定の実測

ユーザー所有の`datas/jr100rom.prg`を使用し、修正後の`--boot`でコールドブートを実行した。

- `READY`表示コード列の位置: VRAM `C140:C144`
- 最初に列が完成した命令境界: CPUクロック555,309
- その時点のPC: `F729`
- 入力待ちループ候補`F7C1`への初回到達: CPUクロック559,712
- 600,000サイクル実行後のVRAMで`READY`を確認

これらの数値とPCは手元のROM固有情報であり、公開コードへ固定値として組み込まない。
初回測定では600,000サイクル以上を指定し、VRAM全体の一致と`READY`の所定位置を確認する。
その後のローカル再現実行では、使用ROMから測定した入力待ちループPCを`--break-pc`へ渡す。

`--cycles`は、指定値と完全に同じCPUクロックで命令途中に停止するものではない。
指定クロック以上となる最初の命令境界で停止する。
両側は同じ停止規約を使う必要がある。

## VIA差分のM1判定

TRACE_FORMAT v1へ出力されるVIAフィールドは、ORA、ORB、DDR、ACR、PCR、IFR、IER、SR、T1/T2カウンタ、ラッチである。
これらはソフトウェアから観測できる状態であり、単なる内部実装値ではない。

そのため、VIAフィールドだけが発散した場合もM1達成とはしない。
`--cpu-only`は次の原因分類に使用する診断モードとする。

```text
全フィールド比較で発散
└─ CPUのみ再比較
   ├─ CPUも発散
   │  └─ CPU命令、割込み、VIA依存制御フローを調査
   └─ CPUは一致
      └─ 最初に異なるVIAフィールドと、そのレジスタへ至るアクセス時刻を調査
```

例外を検討できるのは、TRACE_FORMAT v1へ含まれない`current_clock`などの内部同期値だけが異なり、観測可能VIA状態、IRQ、CPU制御フロー、メモリに影響しないことを証明できた場合である。
その場合も既定の許容条件にはせず、差分内容を記録してユーザー承認を得る。

## バス位置オフセット

VIAの`load8()`と`store8()`には、現時点で0固定の`delay`変数が存在する。
ただし、M1実測前にバス位置補正を導入する根拠にはならない。

次の順序を維持する。

1. 補正なしでブートトレースを比較する
2. 最初の発散命令とVIAアクセスを特定する
3. 発散がCPU命令内のバスアクセス位置によるものか確認する
4. ユーザー承認後、VIA領域アクセスだけを対象に補正する
5. VIAのサイクル単位試験と既知のサウンド試験で回帰確認する

全メモリアクセスへの一般化は、VIA限定の補正で不足すると確認されるまで行わない。

## pyjr100emu側の対応

調査に基づき、次の修正を行った。

- MB8861のRESET処理でIフラグをセット
- `debug_runner --boot`を追加
- `--boot`では`--rom`を必須化し、`--program`と`--start`を禁止
- `--boot`では80,000サイクルのウォームアップを省略
- RESETベクタのPCを維持し、A/B/IX/SPと未定義フラグを比較用に正規化
- ブート開始CCを`0xD0`へ設定
- R6522 RESETでT1/T2カウンタ、ラッチ、SRを保持
- CPU RESET、ブートCLI、初期レジスタ、CC、引数競合、R6522 RESETの回帰試験を追加

## MiSTer側へ返す修正文

以下をM1要件へ反映してほしい。

> ブート比較開始境界は、RESET処理が完了し、PCが`FFFE/FFFF`のベクタ値、Iフラグが1、最初の通常命令が未実行の状態とする。A、B、IX、SPおよびI以外の条件フラグはハードウェアRESETで値が保証されないため、比較規約としてA=B=0、IX=SP=0、H=N=Z=V=C=0へ正規化する。したがって比較開始CCは`0xD0`とする。
>
> pyjr100emuの`computer.reset()`は呼出し内でクロックとデバイスを即時リセットする。続く`tick(1)`はCPUの保留RESETを処理してPCをベクタへ設定し、CPU命令を実行せず、VIAを1内部ティック進める。この操作を実機RESETの1クロック再現とは解釈しない。
>
> R6522のRESETはT1/T2カウンタ、ラッチ、SRを保持する。M1のコールド生成時にはこれらの初期値も0なので、比較開始時は結果的に0となる。実行中RESETまで全レジスタを0にする実装にはしない。
>
> TRACE_FORMAT v1のVIAフィールドは観測可能状態であるため、差分が残る場合はM1達成としない。`--cpu-only`は原因分類にのみ使用する。TRACE_FORMATへ含まれない内部同期値だけの差分を許容する場合は、外部状態への無影響を証明し、別途承認を得る。
