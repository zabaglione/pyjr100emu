JR-100 ゲーム集 — MiSTer FPGA用・全51作品

1. ZIPを展開し、中のJR100フォルダーをMiSTerのSDカードのgames/へコピーします。
   USBストレージを使用している場合は、そちらのgames/JR100/へ置きます。
2. JR-100コアを起動してREADYを待ち、コアのメニューで
   Autostart loaded programをYesにします。配布PRGにはUSR=$0300を設定済みです。
3. Load PRGでゲームを選び、タイトル画面でRETURNを押すと遊べます。
   READYで止まる場合は、A=USR($0300)を入力してRETURNを押してください。

標準RAM 16KB用です（Extended RAMはOff）。JR-100コアと、自分で用意した
BASIC ROM（games/JR100/boot.rom）が必要です。どちらもこのZIPには含みません。
PRGはブラウザー版と同じプログラムデータに、自動起動用コメントを追加したものです。

画像・遊び方・動画・個別ダウンロード:
https://zabaglione.github.io/pyjr100emu/guide/
初回設定・SuperStation One / Console Modeの案内:
https://zabaglione.github.io/pyjr100emu/guide/mister.html
JR-100コア・ROMの設定:
https://github.com/MiSTer-devel/JR100_MiSTer

Console ModeのLoad GameにはMGLランチャーが必要です。このPRGはJR-100コアの
Load PRGから読み込みます。Console Modeのランチャーではありません。

2026年9月18日、SS1実機とJR100_20260801.rbf、標準RAM 16KBで確認しました。
FROST STEPS 1.7.2・GATE RUNNER 3.0.0・STAR LANCE 3.0.0・NIGHT SWARM 3.0.0の
自動起動と本編開始、各作品の移動・取得、障害物の進行、射撃、パルス攻撃を
確認しています。上記4作品の記載した版は、実機所有者による物理パッド操作と
SEの確認も済んでいます。改修後のSTAR LANCE 4.0.0はエミュレーターで検証しており、
SS1での再確認は未実施です。各作品の全ステージを通した確認と、残り47作品の
SS1動作確認は未実施です。
オリジナルのJR-100実機でも未確認です。

Copyright (c) 2026 zabaglione
RELIC DIVEはJR-800 Web Emulator contributorsとの共同制作です。
Copyright (c) 2026 JR-800 Web Emulator contributors (RELIC DIVE)
MITライセンスで配布します。同じフォルダーのLICENSE.txtを参照してください。
