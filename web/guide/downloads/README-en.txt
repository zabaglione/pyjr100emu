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

Tested on MiSTer (SuperStation One), 18 September 2026, JR100_20260801.rbf:
FROST STEPS 1.7.2, GATE RUNNER 3.0.0, STAR LANCE 3.0.0, and NIGHT SWARM 3.0.0
autostarted and reached gameplay with standard 16 KB RAM. Movement/collection,
obstacle progression, shooting, and pulse attacks were checked respectively.
The device owner also confirmed STAR LANCE 3.0.0's physical pad controls and SE.
The updated STAR LANCE 4.0.0 has been tested in the emulator; its SS1 check is
still pending. The other three games' sound/pad input, all stages, and the
remaining 47 games have not been tested on SS1. Original JR-100 hardware
remains untested.

Copyright (c) 2026 zabaglione
RELIC DIVE co-developed with JR-800 Web Emulator contributors.
Copyright (c) 2026 JR-800 Web Emulator contributors (RELIC DIVE)
Distributed under the MIT License. See LICENSE.txt in this folder.
