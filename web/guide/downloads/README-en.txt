JR-100 GAMES FOR MISTER FPGA — 51 GAMES

1. Extract the ZIP and copy its JR100 folder into games/ on your MiSTer SD card.
   If MiSTer uses USB storage, use games/JR100/ on that device instead.
2. Start the JR-100 core and wait for READY. In the core menu, set
   Autostart loaded program to Yes. These .prg files include USR=$0300 hints.
3. Choose Load PRG, select a game, and press RETURN at its title to play.
   If it stays at READY, type A=USR($0300) and press RETURN.

Use standard 16 KB RAM (Extended RAM off). You need the JR-100 core and
your own BASIC ROM, configured as games/JR100/boot.rom. Neither is included.
The .prg files contain the same program data as the browser games, with
MiSTer autostart comments added.

Screenshots, rules, videos, and individual downloads:
https://zabaglione.github.io/pyjr100emu/guide/
Setup and SuperStation One / Console Mode instructions:
https://zabaglione.github.io/pyjr100emu/guide/mister.html
JR-100 core and ROM setup:
https://github.com/MiSTer-devel/JR100_MiSTer

Console Mode's Load Game needs an MGL launcher. These .prg files load through
the JR-100 core's Load PRG menu; they are not Console Mode launchers.

All 51 games, including STAR LANCE 4.0.0, have been tested on MiSTer
(SuperStation One). On 18 September 2026, the device owner confirmed startup,
physical gamepad controls, and sound for every game, using JR100_20260801.rbf.
These checks cover startup, controls, and sound; they do not constitute an
all-stage playthrough. Original JR-100 hardware remains untested.
Tested versions:
https://github.com/zabaglione/jr100dev/blob/main/docs/guide/ss1-verification-2026-09-18.md

Copyright (c) 2026 zabaglione
RELIC DIVE co-developed with JR-800 Web Emulator contributors.
Copyright (c) 2026 JR-800 Web Emulator contributors (RELIC DIVE)
Distributed under the MIT License. See LICENSE.txt in this folder.
