#!/usr/bin/env python3
"""Build the static GitHub Pages artifact for the JR-100 web emulator."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]
WEB_SOURCE = ROOT / "web"
PYTHON_SOURCE = ROOT / "src" / "jr100emu"
DIST = WEB_SOURCE / "dist"
PYODIDE_VERSION = "0.26.4"


def build_dist() -> Path:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    for source in WEB_SOURCE.iterdir():
        if source.name in {"dist", "tests", "package.json"}:
            continue
        if source.suffix in {".html", ".js", ".css"}:
            shutil.copy2(source, DIST / source.name)

    zip_path = DIST / "python" / "jr100emu.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(PYTHON_SOURCE.rglob("*.py")):
            if "__pycache__" in source.parts:
                continue
            relative = source.relative_to(PYTHON_SOURCE.parent)
            info = zipfile.ZipInfo(str(relative))
            info.date_time = (2020, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())

    (DIST / "build-info.json").write_text(
        '{"pyodideVersion":"%s","romBundled":false}\n' % PYODIDE_VERSION,
        encoding="utf-8",
    )
    return DIST


def verify_dist(dist: Path) -> None:
    forbidden_names = {"jr100rom.prg", "boot.rom", "datas"}
    for path in dist.rglob("*"):
        if path.name in forbidden_names:
            raise RuntimeError(f"private ROM asset reached web artifact: {path}")
    with zipfile.ZipFile(dist / "python" / "jr100emu.zip") as archive:
        names = archive.namelist()
        if not names or any("datas/" in name for name in names):
            raise RuntimeError("web Python package contains private data assets")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="verify the generated artifact")
    args = parser.parse_args()
    dist = build_dist()
    if args.verify:
        verify_dist(dist)
    print(f"built {dist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
