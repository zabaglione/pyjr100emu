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


def fixture_catalog(root, game_id="test-game"):
    data = b"PROGfixture"
    artifact = root / f"games/{game_id}/1.0.0/{game_id}.prg"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(data)
    (root / "games/LICENSE.txt").write_text("Test fixture license")
    entry = {
        "id": game_id,
        "version": "1.0.0",
        "ramKiB": 16,
        "entry": 768,
        "path": f"games/{game_id}/1.0.0/{game_id}.prg",
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


def fixture_media(root, game_id="test-game"):
    _, _, program = fixture_catalog(root, game_id)
    folder = root / f"game-media/{game_id}"
    folder.mkdir(parents=True)
    assets = []
    for name in ("play.mp4", "demo-start.png", "demo-play.png", "demo-clear.png"):
        data = (
            b"\x00\x00\x00\x10ftypfixture"
            if name.endswith("mp4")
            else b"\x89PNG\r\n\x1a\nfixture"
        )
        (folder / name).write_bytes(data)
        assets.append(
            {
                "path": f"game-media/{game_id}/{name}",
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    entry = {
        "id": game_id,
        "prg_sha256": program["sha256"],
        "seconds": 30,
        "edited": False,
        "video": assets[0],
        "images": assets[1:],
    }
    manifest = root / "game-media/catalog.json"
    manifest.write_text(json.dumps({"schemaVersion": 1, "games": [entry]}))
    (root / "game-media/LICENSE.txt").write_text("Test fixture license")
    return manifest, entry


def test_media_allows_only_catalogued_assets(tmp_path):
    fixture_media(tmp_path)
    (tmp_path / "game-media/unlisted.bin").write_bytes(b"private fixture")
    files = build.media_files(tmp_path)
    assert len(files) == 6
    assert all(path.name != "unlisted.bin" for path in files)


@pytest.mark.parametrize(
    "patch",
    [
        {"seconds": 10},
        {"images": []},
        {"prg_sha256": "0" * 64},
        {"video": {"path": "../private.mp4", "sha256": "0" * 64}},
    ],
)
def test_incomplete_or_unsafe_media_cannot_build(tmp_path, patch):
    manifest, entry = fixture_media(tmp_path)
    manifest.write_text(json.dumps({"schemaVersion": 1, "games": [entry | patch]}))
    with pytest.raises(RuntimeError):
        build.media_files(tmp_path)


@pytest.mark.parametrize(
    ("game_id", "seconds", "edited", "allowed"),
    [
        ("peg-garden", 44.533, False, True),
        ("peg-garden", 90, False, True),
        ("peg-garden", 30, True, False),
        ("peg-garden", 44.533, True, False),
        ("seed-merge", 55.6, False, True),
        ("seed-merge", 90, False, True),
        ("seed-merge", 30, True, False),
        ("seed-merge", 55.6, True, False),
        ("test-game", 44.533, False, False),
    ],
)
def test_full_length_game_media(tmp_path, game_id, seconds, edited, allowed):
    manifest, entry = fixture_media(tmp_path, game_id)
    entry.update(seconds=seconds, edited=edited)
    manifest.write_text(json.dumps({"schemaVersion": 1, "games": [entry]}))
    if allowed:
        assert len(build.media_files(tmp_path)) == 6
    else:
        with pytest.raises(RuntimeError, match="invalid duration"):
            build.media_files(tmp_path)
