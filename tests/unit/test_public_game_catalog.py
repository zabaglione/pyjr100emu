"""Public builds copy only catalogued, hash-verified original game artifacts."""

import hashlib
import importlib.util
import json
import zipfile
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


def fixture_guides(root):
    _, _, program = fixture_catalog(root)
    folder = root / "guide"
    folder.mkdir()
    names = [
        "index.html",
        "controls.html",
        "mister.html",
        "test-game.html",
        "language.js",
        "guide.js",
        "style.css",
        "LICENSE.txt",
        "downloads/test-game.prg",
        "downloads/README-en.txt",
        "downloads/README-ja.txt",
    ]
    files = {}
    for name in names:
        data = f"public guide fixture: {name}".encode()
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
        files[name] = hashlib.sha256(data).hexdigest()
    bundle = folder / "downloads/jr100-games-mister.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        for name in ("test-game.prg", "README-en.txt", "README-ja.txt"):
            archive.writestr(
                "JR100/" + name, (folder / "downloads" / name).read_bytes()
            )
        archive.writestr("JR100/LICENSE.txt", (folder / "LICENSE.txt").read_bytes())
    files["downloads/jr100-games-mister.zip"] = hashlib.sha256(
        bundle.read_bytes()
    ).hexdigest()
    manifest = {
        "schemaVersion": 1,
        "games": ["test-game"],
        "files": files,
        "sourcePrograms": [
            {k: program[k] for k in ("id", "path", "version", "entry", "sha256")}
        ],
    }
    (folder / "manifest.json").write_text(json.dumps(manifest))
    return folder, manifest


def test_guides_copy_only_manifest_files(tmp_path):
    folder, _ = fixture_guides(tmp_path)
    (folder / "notes-private.txt").write_text("not published")
    paths = build.guide_files(tmp_path)
    assert len(paths) == 13
    assert all(path.name != "notes-private.txt" for path in paths)


@pytest.mark.parametrize(
    "change", ["hash", "missing", "traversal", "catalog", "source"]
)
def test_stale_or_unsafe_guides_cannot_build(tmp_path, change):
    folder, manifest = fixture_guides(tmp_path)
    if change == "hash":
        (folder / "test-game.html").write_text("changed")
    elif change == "missing":
        del manifest["files"]["test-game.html"]
    elif change == "traversal":
        manifest["files"]["../private.txt"] = "0" * 64
    elif change == "catalog":
        manifest["games"] = ["another-game"]
    else:
        manifest["sourcePrograms"][0]["sha256"] = "0" * 64
    (folder / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError):
        build.guide_files(tmp_path)


@pytest.mark.parametrize("change", ["extra", "stale"])
def test_bundle_cannot_include_unlisted_or_different_programs(tmp_path, change):
    folder, manifest = fixture_guides(tmp_path)
    bundle = folder / "downloads/jr100-games-mister.zip"
    if change == "extra":
        with zipfile.ZipFile(bundle, "a") as archive:
            archive.writestr("JR100/boot.rom", b"unlisted private fixture")
    else:
        with zipfile.ZipFile(bundle, "w") as archive:
            for name in (
                "test-game.prg",
                "README-en.txt",
                "README-ja.txt",
                "LICENSE.txt",
            ):
                archive.writestr("JR100/" + name, b"stale data")
    manifest["files"]["downloads/jr100-games-mister.zip"] = hashlib.sha256(
        bundle.read_bytes()
    ).hexdigest()
    (folder / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="bundle"):
        build.guide_files(tmp_path)


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
        ("test-game", 44.533, False, True),
        ("test-game", 44.533, True, False),
        ("test-game", 30, True, True),
        ("memory-mosaic", 84.533, False, True),
        ("abyss-signal", 102.6, False, True),
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
