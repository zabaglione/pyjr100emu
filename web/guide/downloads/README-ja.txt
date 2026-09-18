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

STAR LANCE 4.0.0を含む全51作品を、MiSTer（SuperStation One）実機で確認済みです。
2026年9月18日、実機所有者がJR100_20260801.rbfを使用し、全作品の起動・
物理パッド操作・音を確認しました。確認範囲は起動・操作・音で、全ステージの
踏破を示すものではありません。オリジナルのJR-100実機では未確認です。
確認した版の一覧:
https://github.com/zabaglione/jr100dev/blob/main/docs/guide/ss1-verification-2026-09-18.md

Copyright (c) 2026 zabaglione
RELIC DIVEはJR-800 Web Emulator contributorsとの共同制作です。
Copyright (c) 2026 JR-800 Web Emulator contributors (RELIC DIVE)
MITライセンスで配布します。同じフォルダーのLICENSE.txtを参照してください。
