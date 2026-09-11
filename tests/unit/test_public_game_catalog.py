"""Public builds copy only catalogued, hash-verified original game artifacts."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "public_web_build", Path(__file__).resolve().parents[2] / "tools/build_web.py"
)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def fixture_catalog(root):
    data = b"PROGfixture"
    artifact = root / "games/test-game/1.0.0/test-game.prg"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(data)
    (root / "games/LICENSE.txt").write_text("Test fixture license")
    entry = {
        "id": "test-game",
        "version": "1.0.0",
        "ramKiB": 16,
        "entry": 768,
        "path": "games/test-game/1.0.0/test-game.prg",
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    manifest = root / "games/catalog.json"
    manifest.write_text(json.dumps({"schemaVersion": 1, "games": [entry]}))
    return artifact, manifest, entry


def test_unlisted_assets_are_not_copied(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    artifact, _, _ = fixture_catalog(source)
    (source / "games/unlisted.bin").write_bytes(b"not in catalog")
    build.copy_games(source, target)
    assert sorted(
        str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()
    ) == [
        "games/LICENSE.txt",
        "games/catalog.json",
        "games/test-game/1.0.0/test-game.prg",
    ]
    assert (target / artifact.relative_to(source)).read_bytes() == artifact.read_bytes()


@pytest.mark.parametrize(
    "patch",
    [
        {"path": "../private.prg"},
        {"ramKiB": 32},
        {"entry": 0xC000},
        {"version": "../1"},
        {"sha256": "0" * 64},
    ],
)
def test_invalid_catalog_cannot_build(tmp_path, patch):
    _, manifest, entry = fixture_catalog(tmp_path)
    manifest.write_text(json.dumps({"schemaVersion": 1, "games": [entry | patch]}))
    with pytest.raises(RuntimeError):
        build.catalog_files(tmp_path)


def test_modified_artifact_cannot_build(tmp_path):
    artifact, _, _ = fixture_catalog(tmp_path)
    artifact.write_bytes(b"PROGmodified")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        build.catalog_files(tmp_path)
