# Maze Tests

`maze_init_test`、`maze_step_test`、`maze_stack_test` は迷路生成アルゴリズムを小さな部品ごとに検証するためのテスト用プログラムです。いずれも `.org $0300` から配置されるシンプルなアセンブリで、実機/エミュレーター上で `A=USR($0300)` を実行するとすぐに停止（`BRA HALT`）します。停止位置に到達した段階で RAM や VRAM をダンプし、生成結果を確認してください。

## ヘッドレスデバッグランナー

GUI を開かずに PROG ファイルを走らせてメモリダンプを取得する場合は、次のコマンドを利用できます。

```bash
PYTHONPATH=src python -m jr100emu.debug_runner \
    --program jr100dev/samples/maze/tests/build/maze_init_test.prg \
    --start 0x0300 \
    --break-pc 0x0300 \
    --cycles 0 \
    --seconds 5 \
    --dump-range 0300:037F
```

`--break-pc` で HALT ループのアドレスを指定しておくと所望の地点で止まり、標準出力に 16×16 バイト形式のダンプが出力されます。複数の領域をダンプしたい場合は `--dump-range 0600:061F --dump-range 0700:0710` のように繰り返し指定してください。
スタックポインタを変更したい場合は `--stack-pointer` オプションを使ってください（デフォルト値は BASIC の `USR` 呼び出し時と同じ `0x0244` です）。

## 1. maze_init_test.asm
* 目的: `MAZE_MAP` の境界が `#`、内部が空白になるかを検証する。
* 仕様:
  - `MAZE_MAP` は RAM $0300 から（`MAZE_CHAR_W * MAZE_CHAR_H` 分）。
  - 境界には ASCII `'#'`（0x23）、内部には `' '`（0x20）を書き込む。
  - 表示時に `__STD_TO_VRAM` などで変換すると、`# → 0x03`, `空白 → 0x40` となる前提。
* 確認手順:
  1. `make -C jr100dev/samples/maze/tests build/maze_init_test.prg`
  2. エミュレーターでロードし `A=USR($0300)` を実行。
  3. RAM $0300 ～ のダンプを取り、境界が `0x23`、内部が `0x20` か確認。

## 2. maze_step_test.asm
* 目的: 左上セル（(0,0)）から東方向へ 1 ステップ掘削できるかを検証する。
* 仕様:
  - `MAZE_MAP` と内部ワークは `maze_init_test` と同じく $0300 近辺の RAM を利用。
  - 掘削ロジックではセル座標をキャラクタ座標に変換し、現在セル・壁・隣接セルの 3 文字分を `' '` に開ける。
  - 掘削後、内部表現を VRAM $C100～ にコピー。`#→0x03`, `' '→0x40` に変換しているため、VRAM をダンプすると右方向に 3 文字分の空白が並ぶ。
* 確認手順:
  1. `make -C jr100dev/samples/maze/tests build/maze_step_test.prg`
  2. エミュレーターでロードし `A=USR($0300)` を実行。
  3. VRAM $C100～ をダンプし、先頭行の 3 文字分が 0x40（空白）に変わっていることを確認。

## 3. maze_stack_test.asm
* 目的: 生成ルーチンで用いているスタック操作（push/peek/pop）の状態遷移を確認する。
* 仕様:
  - スタック領域は RAM $0700～$070F を使用し、初期化時に `0xEE` で埋める。
  - `STACK_RESET` → `STACK_PEEK_CUR`（空）→ push×2 → peek → pop×2 → 空スタック pop の順に実行し、各段階の結果を RAM に残す。
  - 期待される RAM 値（16 進）:
    - $0600-$0607: `01 01 03 04 01 03 04 01`
    - $0608-$0613: `05 00 05 00 05 04 05 02 05 00 01 02`
    - $0614-$0616: `01 07 00`
    - $0700-$070F: `01 02 03 04 EE EE EE EE EE EE EE EE EE EE EE EE`
  * 確認手順:
  1. `make -C jr100dev/samples/maze/tests build/maze_stack_test.prg`
  2. エミュレーターでロードし `A=USR($0300)` を実行。
  3. RAM $0600～$0616 と $0700～$0710 をダンプし、各値が期待通りか確認。

## 4. maze_neighbors_test.asm
* 目的: `FIND_NEIGHBORS` が未訪問セルのみを方向バッファに列挙できているかを事例ごとに検証する。
* 仕様:
  - ケース1: 中央セル (5,5)。北・南を訪問済みにして実行。結果は Count=2 / Dir=[DIR_E(1), DIR_W(3), 0xEE, 0xEE]。
  - ケース2: 左上セル (0,0)。未訪問のまま実行。結果は Count=2 / Dir=[DIR_E(1), DIR_S(2), 0xEE, 0xEE]。
  - ケース3: 右下セル (31,23)。北・西を訪問済みにして実行。結果は Count=0 / Dir=[0xEE, 0xEE, 0xEE, 0xEE]。
  - 結果は RAM $0600～$060E に順に出力される（Case1→Case2→Case3）。`TMP_DIR_BUF` 初期値は `0xEE`。
  - ケース1についてはデバッグ用に `TMP_DIR_COUNT` の推移を $0610-$0613 に書き出し（N/E/S/W 後で 0,1,1,2 に変化）、`LOAD_NEXT_VISITED` の戻り値を $0614-$0617 に格納する（北=01、東=00、南=01、西=00 の想定）。さらに訪問済みフラグそのものを $0618-$061B にコピーしているため、北/南=01・東/西=00 になっているかを直接確認できる。
* 確認手順:
  1. `make -C jr100dev/samples/maze/tests build/maze_neighbors_test.prg`
  2. エミュレーターでロードし `A=USR($0300)` を実行。
  3. RAM $0600～$060E をダンプし、上記の期待値と突き合わせる。

## 5. maze_wall_mark_test.asm
* 目的: `CLEAR_WALLS_BETWEEN` と `MARK_CUR_VISITED`/`MARK_NEXT_VISITED` が壁ビットと訪問フラグを正しく更新するかを検証する。
* 仕様:
  - ケースE: CUR=(1,1)、NEXT=(2,1)、方向 DIR_E。`MAZE_CELLS` の該当セルは `$0F → $0B`（東壁除去）、隣接セルは `$0F → $0E`（西壁除去）。訪問フラグは両セルとも `1`。
  - ケースN: CUR=(2,2)、NEXT=(2,1)、方向 DIR_N。結果は `$0F → $07`（北壁除去）、隣接セルは `$0F → $0D`（南壁除去）。訪問フラグは両セルとも `1`。
  - 実行後の RAM: `$0600-$0607 = 0B 0E 01 01 07 0D 01 01`。補助として `$0700` 付近のワークを利用するが、テスト終了時点では `TMP` 領域に値が残る。
* 確認手順:
  1. `make -C jr100dev/samples/maze/tests build/maze_wall_mark_test.prg`
  2. エミュレーターでロードし `A=USR($0300)` を実行。
  3. RAM $0600～$0607 をダンプし、上記期待値と一致するか確認する。

## 6. maze_carve_test.asm
* 目的: `CARVE_CUR_CELL` / `CARVE_PASSAGE` がキャラクタマップ上で通路を正しく開通させるかを確認する。
* 仕様:
  - ケース1: `CARVE_CUR_CELL` を CUR=(1,2) で実行。該当セルが `' '` (0x20) になり、他セルは `'#'` のまま。
  - ケース2: `CARVE_PASSAGE` を CUR=(1,1)、NEXT=(2,1)、方向 DIR_E で実行。CUR・壁・NEXT の 3 文字が `' '`、離れたセルは `'#'`。
  - ケース3: `CARVE_PASSAGE` を CUR=(2,2)、NEXT=(2,1)、方向 DIR_N で実行。同様に CUR・壁・NEXT が `' '`、別セルは `'#'`。
  - 実行後の RAM: `$0620-$0629 = 20 23 20 20 20 23 20 20 20 23`（16進表記で `' '`=0x20, `'#'`=0x23）。
* 確認手順:
  1. `make -C jr100dev/samples/maze/tests build/maze_carve_test.prg`
  2. エミュレーターでロードし `A=USR($0300)` を実行。
  3. RAM $0400～$0409 をダンプし、期待値と比較する。

## 7. 補足
* すべてのテストは `BRA HALT` で待機します。エミュレーターのステータスには PC=0300 台でループしているように見えますが、意図通りです。
* これらのテストを段階的に積み上げ、迷路生成本体のスタック操作・近傍探索などを順番に検証していく前提になっています。
* メモ: 6800 の `LDX`/`STX` は常に「高位→低位」の順で 16bit アドレスを読み書きします。テスト用ワークにポインタを構成する際も、必ず高位バイトを先に格納すること（`STAA TEMP_PTR` → 高位、`STAA TEMP_PTR+1` → 低位）。エンディアンの取り違えは再発防止のためここに記録します。
* メモ: 結果バッファへ値を書き込む際も常に拡張アドレッシング（`>` プレフィックス）を使い、0x00XX へのゼロページ書き込みを避ける。

## 8. クリーニング
```
make -C jr100dev/samples/maze/tests clean
```
