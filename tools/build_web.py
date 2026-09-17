#!/usr/bin/env python3
"""Build the static GitHub Pages artifact for the JR-100 web emulator."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_SOURCE = ROOT / "web"
CPP_SOURCE = ROOT / "cpp"
WASM_BUILD = ROOT / "build" / "web-wasm"
DIST = WEB_SOURCE / "dist"


def build_wasm() -> tuple[Path, Path]:
    emcmake = shutil.which("emcmake")
    cmake = shutil.which("cmake")
    if emcmake is None or cmake is None:
        raise RuntimeError("Emscripten and CMake are required to build the web core")
    subprocess.run(
        [
            emcmake,
            cmake,
            "-S",
            str(CPP_SOURCE),
            "-B",
            str(WASM_BUILD),
            "-DCMAKE_BUILD_TYPE=Release",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [cmake, "--build", str(WASM_BUILD), "--target", "jr100_wasm", "-j", "4"],
        cwd=ROOT,
        check=True,
    )
    javascript = WASM_BUILD / "jr100-core.js"
    wasm = WASM_BUILD / "jr100-core.wasm"
    if not javascript.is_file() or not wasm.is_file():
        raise RuntimeError("Emscripten did not produce the expected web core")
    return javascript, wasm


def catalog_files(web_root: Path) -> list[Path]:
    games_root = web_root / "games"
    manifest = games_root / "catalog.json"
    catalog = json.loads(manifest.read_text(encoding="utf-8"))
    if catalog.get("schemaVersion") != 1 or not isinstance(catalog.get("games"), list):
        raise RuntimeError("invalid public game catalog")
    paths = [manifest, games_root / "LICENSE.txt"]
    seen = set()
    for game in catalog["games"]:
        game_id, version = game.get("id", ""), game.get("version", "")
        if not re.fullmatch(
            r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", game_id
        ) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
            raise RuntimeError("invalid public game identity")
        expected = f"games/{game_id}/{version}/{game_id}.prg"
        if game_id in seen or game.get("path") != expected or game.get("ramKiB") != 16:
            raise RuntimeError("invalid public game path or RAM requirement")
        seen.add(game_id)
        if (
            not isinstance(game.get("entry"), int)
            or not 0x300 <= game["entry"] < 0x3000
        ):
            raise RuntimeError("invalid public game entry")
        artifact = web_root / expected
        data = artifact.read_bytes()
        if not 8 <= len(data) <= 65536 or data[:4] != b"PROG":
            raise RuntimeError("invalid public game artifact")
        if hashlib.sha256(data).hexdigest() != game.get("sha256"):
            raise RuntimeError("public game hash mismatch")
        paths.append(artifact)
    if not paths[1].is_file():
        raise RuntimeError("public game license is missing")
    return paths


def copy_games(source: Path, destination: Path) -> None:
    for path in catalog_files(source):
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def build_dist() -> Path:
    javascript, wasm = build_wasm()
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    for source in WEB_SOURCE.iterdir():
        if source.name in {"dist", "tests", "package.json"}:
            continue
        if source.suffix in {".html", ".js", ".css"}:
            shutil.copy2(source, DIST / source.name)

    copy_games(WEB_SOURCE, DIST)
    shutil.copy2(WEB_SOURCE / "presentation.mp4", DIST / "presentation.mp4")
    wasm_dist = DIST / "wasm"
    wasm_dist.mkdir()
    shutil.copy2(javascript, wasm_dist / javascript.name)
    shutil.copy2(wasm, wasm_dist / wasm.name)
    (DIST / "build-info.json").write_text(
        json.dumps({"core": "C++/WASM", "romBundled": False}, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    return DIST


def verify_dist(dist: Path) -> None:
    forbidden_names = {"jr100rom.prg", "boot.rom", "datas", "jr100emu.zip"}
    for path in dist.rglob("*"):
        if path.name in forbidden_names or path.suffix == ".py":
            raise RuntimeError(
                f"private or Python runtime asset reached web artifact: {path}"
            )
    expected_games = set(catalog_files(dist))
    actual_games = {p for p in (dist / "games").rglob("*") if p.is_file()}
    if actual_games != expected_games:
        raise RuntimeError("unlisted asset reached the public game directory")
    worker = (dist / "worker.js").read_text(encoding="utf-8").lower()
    if "pyodide" in worker or "python/" in worker:
        raise RuntimeError("worker still references the Python/Pyodide runtime")
    wasm = dist / "wasm" / "jr100-core.wasm"
    if wasm.read_bytes()[:4] != b"\x00asm":
        raise RuntimeError("web core is not a valid WebAssembly binary")
    if not (dist / "wasm" / "jr100-core.js").is_file():
        raise RuntimeError("Emscripten loader is missing from the artifact")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify", action="store_true", help="verify the generated artifact"
    )
    args = parser.parse_args()
    dist = build_dist()
    if args.verify:
        verify_dist(dist)
    print(f"built {dist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
