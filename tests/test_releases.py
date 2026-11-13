import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import install_release
import release
import release_assets as assets


@pytest.fixture
def bundle(tmp_path):
    source = tmp_path / "download"
    source.mkdir()
    entries = {}
    for package in ("all", "qol", "coop"):
        path = source / assets.package_filename(package)
        path.write_bytes(f"new {package}".encode())
        entries[package] = {"file": path.name, "size": path.stat().st_size, "sha256": assets.digest(path)}
    doc = {"schema": 1, "tag": "v1.2.3", "revision": "a" * 40, "packages": entries}
    (source / assets.MANIFEST).write_text(json.dumps(doc))
    return source, doc


@pytest.mark.parametrize("change", [
    lambda doc: doc.update(schema=2),
    lambda doc: doc.update(tag="v9.9.9"),
    lambda doc: doc.update(packages={}),
    lambda doc: doc["packages"]["all"].update(file="../outside.bin"),
    lambda doc: doc["packages"]["all"].update(sha256="no checksum"),
    lambda doc: doc["packages"]["all"].update(size=0),
    lambda doc: doc["packages"].update({"../bad": {"file": "bad.bin"}}),
])
def test_manifest_rejects_invalid_assets(bundle, change):
    source, doc = bundle
    change(doc)
    (source / assets.MANIFEST).write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        assets.read_manifest(source / assets.MANIFEST, "v1.2.3")


def old_mods(tmp_path):
    target = tmp_path / "mods"
    target.mkdir()
    for name in ("HWP-old.bin", "HammerwatchPlus-All-local.bin", "other.bin"):
        (target / name).write_bytes(b"old")
    (target / "unpacked").mkdir()
    return target


def snapshot(target):
    return {p.name: p.read_bytes() if p.is_file() else None for p in target.iterdir()}


def test_install_replaces_only_hwp_binaries(bundle, tmp_path):
    source, doc = bundle
    target = old_mods(tmp_path)
    install_release.install(source, target, [doc["packages"]["all"]])
    assert snapshot(target) == {"HammerwatchPlus-All.bin": b"new all", "other.bin": b"old", "unpacked": None}


@pytest.mark.parametrize("dry_run,corrupt", [(True, False), (False, True)])
def test_no_changes_on_dry_run_or_corrupt_download(bundle, tmp_path, dry_run, corrupt):
    source, doc = bundle
    target = old_mods(tmp_path)
    before = snapshot(target)
    if corrupt:
        (source / "HammerwatchPlus-All.bin").write_bytes(b"bad")
        with pytest.raises(ValueError, match="mismatch"):
            install_release.install(source, target, [doc["packages"]["all"]])
    else:
        install_release.install(source, target, [doc["packages"]["all"]], dry_run)
    assert snapshot(target) == before


def test_partial_copy_rolls_back_and_unlocks(bundle, tmp_path, monkeypatch):
    source, doc = bundle
    target = old_mods(tmp_path)
    before = snapshot(target)
    copy = shutil.copy2

    def fail_second(src, dst):
        copy(src, dst)
        if src.name == "HWP-coop.bin":
            raise PermissionError("game holds file open")

    monkeypatch.setattr(install_release.shutil, "copy2", fail_second)
    with pytest.raises(PermissionError):
        install_release.install(source, target, [doc["packages"]["qol"], doc["packages"]["coop"]])
    assert snapshot(target) == before


def test_failed_rollback_preserves_backup(bundle, tmp_path, monkeypatch):
    source, doc = bundle
    target = old_mods(tmp_path)

    def fail_copy(*args):
        raise PermissionError("locked")

    rename = Path.rename

    def fail_restore(path, dst):
        if path.parent.name.startswith(".hwp-backup-"):
            raise PermissionError("restore locked")
        return rename(path, dst)

    monkeypatch.setattr(install_release.shutil, "copy2", fail_copy)
    monkeypatch.setattr(Path, "rename", fail_restore)
    with pytest.raises(OSError, match="recover old binaries"):
        install_release.install(source, target, [doc["packages"]["all"]])
    backup, = target.glob(".hwp-backup-*")
    assert (backup / "HWP-old.bin").read_bytes() == b"old"
    assert not (target / ".hwp-install.lock").exists()


@pytest.mark.parametrize("kind", ["lock", "directory", "symlink"])
def test_install_refuses_unsafe_paths(bundle, tmp_path, kind):
    source, doc = bundle
    target = old_mods(tmp_path)
    if kind == "lock":
        (target / ".hwp-install.lock").touch()
    elif kind == "directory":
        (target / "HWP-directory.bin").mkdir()
    else:
        try:
            (target / "HWP-linked.bin").symlink_to(target / "other.bin")
        except OSError:
            pytest.skip("symlinks unavailable")
    before = snapshot(target)
    with pytest.raises((ValueError, FileExistsError)):
        install_release.install(source, target, [doc["packages"]["all"]])
    assert snapshot(target) == before


def test_cli_pins_latest_tag_and_downloads_only_selected(bundle, tmp_path, monkeypatch):
    source, doc = bundle
    calls = []

    def fake_gh(*args):
        calls.append(args)
        if args[:2] == ("release", "view"):
            return json.dumps({"tagName": "v1.2.3", "isDraft": False})
        assert args[2] == "v1.2.3"
        destination = Path(args[args.index("--dir") + 1])
        for index, arg in enumerate(args):
            if arg == "--pattern":
                shutil.copy2(source / args[index + 1], destination)
        return ""

    monkeypatch.setattr(install_release, "gh", fake_gh)
    target = tmp_path / "installed"
    assert install_release.main(["--mods-dir", str(target)]) == 0
    assert snapshot(target) == {"HammerwatchPlus-All.bin": b"new all"}
    assert len(calls) == 3
    assert "HWP-qol.bin" not in calls[-1]


def release_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "REPO", tmp_path)
    (tmp_path / "dist").mkdir()
    (tmp_path / "packages.json").write_text(json.dumps({"packages": [{"id": "qol"}]}))
    for name in ("HWP-qol.bin", "HammerwatchPlus-All.bin", "HWP-stale.bin"):
        (tmp_path / "dist" / name).write_bytes(b"binary")
    calls = []

    def fake_run(*args, capture=False):
        calls.append(args)
        if args[:3] == ("git", "rev-parse", "HEAD"):
            return "a" * 40
        if args[:2] == ("gh", "api"):
            return "[]"
        return ""

    monkeypatch.setattr(release, "run", fake_run)
    return calls


def test_release_tests_builds_and_uploads_before_publishing(tmp_path, monkeypatch):
    calls = release_checkout(tmp_path, monkeypatch)
    assert release.main(["v1.2.3"]) == 0
    output = tmp_path / "dist/releases/v1.2.3"
    doc = assets.read_manifest(output / assets.MANIFEST, "v1.2.3")
    assets.verify_assets(output, list(doc["packages"].values()))
    assert {p.name for p in output.iterdir()} == {assets.MANIFEST, "HWP-qol.bin", "HammerwatchPlus-All.bin"}
    assert calls.index((sys.executable, "scripts/test.py")) < calls.index((sys.executable, "tools/build.py"))
    create = next(i for i, call in enumerate(calls) if call[:3] == ("gh", "release", "create"))
    upload = next(i for i, call in enumerate(calls) if call[:3] == ("gh", "release", "upload"))
    assert "--draft" in calls[create]
    assert create < upload < len(calls) - 1
    assert calls[-1][:3] == ("gh", "release", "edit")


def test_build_only_does_not_contact_github(tmp_path, monkeypatch):
    calls = release_checkout(tmp_path, monkeypatch)
    assert release.main(["v1.2.3", "--build-only"]) == 0
    assert not any(call[0] == "gh" for call in calls)


def test_failed_upload_never_publishes(tmp_path, monkeypatch):
    calls = release_checkout(tmp_path, monkeypatch)
    run = release.run

    def fail_upload(*args, **kwargs):
        if args[:3] == ("gh", "release", "upload"):
            raise OSError("upload failed")
        return run(*args, **kwargs)

    monkeypatch.setattr(release, "run", fail_upload)
    with pytest.raises(OSError):
        release.main(["v1.2.3"])
    assert not any(call[:3] == ("gh", "release", "edit") for call in calls)


def test_dirty_release_refused_before_build(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "run", lambda *args, **kwargs: " M mods/file.as")
    with pytest.raises(ValueError, match="dirty"):
        release.main(["v1.2.3", "--build-only"])


@pytest.mark.parametrize("tags,expected", [
    ([], "v0.1.0"),
    (["unrelated", "v1.0.0-rc.1"], "v0.1.0"),
    (["v0.3"], "v0.3.1"),
    (["refs/tags/v0.9.9", "refs/tags/v0.10.2", "refs/tags/v0.10.1"], "v0.10.3"),
    (["v1.2.9", "v2.0.0", "v3.0.0-rc.1"], "v2.0.1"),
])
def test_next_release_tag(tags, expected):
    assert release.next_tag(tags) == expected


@pytest.mark.parametrize("build_only", [False, True])
def test_versionless_release(tmp_path, monkeypatch, build_only):
    calls = release_checkout(tmp_path, monkeypatch)
    run = release.run

    def with_tags(*args, **kwargs):
        if args[:3] == ("git", "tag", "--list") or "--paginate" in args:
            calls.append(args)
            return "refs/tags/v0.9.9\nrefs/tags/v0.10.2\nrefs/tags/v0.11.0-rc.1\n"
        return run(*args, **kwargs)

    monkeypatch.setattr(release, "run", with_tags)
    assert release.main(["--build-only"] if build_only else []) == 0
    output = tmp_path / "dist/releases/v0.10.3"
    assets.read_manifest(output / assets.MANIFEST, "v0.10.3")
    if build_only:
        assert not any(call[0] == "gh" for call in calls)
    else:
        assert any("--paginate" in call for call in calls)
        create = next(call for call in calls if call[:3] == ("gh", "release", "create"))
        assert create[3] == "v0.10.3"
