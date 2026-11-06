"""Archive extraction containment in disposable pytest output trees."""
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import hwr_archive as hwr


def extract(tmp_path, names, *, out=None, no_manifest=True, filter=None):
    archive = tmp_path / "input.bin"
    entries = [hwr.Entry(name, hwr.TYPE_TEXT, len(data), 0, data) for name, data in names]
    hwr.Archive("hoh2", 4, 0, {"name": "temporary"}, entries).write(archive)
    args = SimpleNamespace(archive=str(archive), outdir=str(out or tmp_path / "out"),
                           filter=filter, png=False, no_manifest=no_manifest)
    hwr.cmd_extract(args)


def test_parent_escape_does_not_write(tmp_path):
    canary = tmp_path / "outside.txt"
    canary.write_bytes(b"keep")
    with pytest.raises(ValueError, match="extraction"):
        extract(tmp_path, [("../outside.txt", b"changed")])
    assert canary.read_bytes() == b"keep"


def test_absolute_owned_target_rejected(tmp_path):
    canary = tmp_path / "absolute.txt"
    canary.write_bytes(b"keep")
    with pytest.raises(ValueError, match="extraction"):
        extract(tmp_path, [(str(canary.resolve()), b"changed")])
    assert canary.read_bytes() == b"keep"


@pytest.mark.parametrize("name", [
    "../escape", "a/../../escape", "..\\escape", "a\\..\\..\\escape",
    "C:/escape", "C:\\escape", "C:escape", "\\\\server\\share\\escape", "//server/share/escape",
    "\\escape", "/escape", "safe:stream", "safe/file:stream", "NUL", "a/CON.txt", "AUX.bin",
    "a/file.", "a/file ", "", ".", "a/..", "bad\x00name",
])
def test_unsafe_names_refused_without_io(tmp_path, name):
    # Pure validation prevents the old unsafe CLI ever seeing real drive/UNC paths.
    with pytest.raises(ValueError, match="extraction"):
        hwr.extraction_paths(tmp_path / "out", [name])


@pytest.mark.parametrize("names", [["a/file", "a/./file"], ["a/file", "a\\file"], ["a/file", "a//file"], ["same", "same"]])
def test_normalized_duplicates_refused(tmp_path, names):
    with pytest.raises(ValueError, match="duplicate"):
        hwr.extraction_paths(tmp_path / "out", names)


@pytest.mark.skipif(os.name != "nt", reason="Windows aliases are case insensitive")
def test_windows_case_alias_refused(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        hwr.extraction_paths(tmp_path / "out", ["A/file", "a/FILE"])


def test_preflight_rejects_all_paths_before_overwriting_existing_file(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    keep = out / "keep.txt"
    keep.write_bytes(b"original")
    with pytest.raises(ValueError, match="extraction"):
        extract(tmp_path, [("keep.txt", b"replacement"), ("../escape.txt", b"escape")])
    assert keep.read_bytes() == b"original"
    assert not (tmp_path / "escape.txt").exists()


def test_normal_files_backslashes_and_manifest(tmp_path):
    extract(tmp_path, [("nested/a.txt", b"one"), ("nested\\b.txt", b"two")], no_manifest=False)
    out = tmp_path / "out"
    assert (out / "nested/a.txt").read_bytes() == b"one"
    assert (out / "nested/b.txt").read_bytes() == b"two"
    manifest = json.loads((out / hwr.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["meta"] == {"name": "temporary"}
    assert set(manifest["files"]) == {"nested/a.txt", "nested\\b.txt"}


def test_filter_excludes_unselected_unsafe_name(tmp_path):
    extract(tmp_path, [("safe.txt", b"yes"), ("../escape", b"bad")], filter=r"^safe")
    assert (tmp_path / "out/safe.txt").read_bytes() == b"yes"
    assert not (tmp_path / "escape").exists()


def directory_link(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
        return "symlink"
    except OSError:
        if os.name != "nt":
            pytest.skip("directory links unavailable")
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
        if result.returncode:
            pytest.skip("directory symlink/junction unavailable: " + result.stderr.strip())
        return "junction"


def test_existing_directory_link_cannot_escape_output(tmp_path):
    out, outside = tmp_path / "out", tmp_path / "owned-outside"
    out.mkdir()
    outside.mkdir()
    keep = outside / "keep.txt"
    keep.write_bytes(b"original")
    directory_link(out / "link", outside)
    with pytest.raises(ValueError, match="escapes"):
        extract(tmp_path, [("link/keep.txt", b"overwrite")])
    assert keep.read_bytes() == b"original"


def test_existing_directory_link_inside_output_still_extracts(tmp_path):
    out = tmp_path / "out"
    target = out / "target"
    target.mkdir(parents=True)
    directory_link(out / "link", target)
    extract(tmp_path, [("link/file.txt", b"inside")])
    assert (target / "file.txt").read_bytes() == b"inside"


def test_manifest_symlink_outside_output_refused(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    keep = tmp_path / "manifest-canary.txt"
    keep.write_bytes(b"original")
    try:
        (out / hwr.MANIFEST).symlink_to(keep)
    except OSError:
        pytest.skip("file symlinks unavailable")
    with pytest.raises(ValueError, match="escapes"):
        extract(tmp_path, [("safe.txt", b"content")], no_manifest=False)
    assert keep.read_bytes() == b"original"
    assert not (out / "safe.txt").exists()


def test_manifest_name_collision_refused_before_extract(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        extract(tmp_path, [(hwr.MANIFEST, b"archive-owned")], no_manifest=False)
    assert not (tmp_path / "out" / hwr.MANIFEST).exists()



@pytest.mark.parametrize("reverse", [False, True])
def test_archive_file_ancestor_conflict_refused_before_overwrite(tmp_path, reverse):
    out = tmp_path / "out"
    out.mkdir()
    keep = out / "keep.txt"
    keep.write_bytes(b"original")
    rows = [("keep.txt", b"replacement"), ("keep.txt/child", b"child")]
    with pytest.raises(ValueError, match="ancestor|conflict"):
        extract(tmp_path, list(reversed(rows)) if reverse else rows)
    assert keep.read_bytes() == b"original"


def test_manifest_ancestor_conflict_refused_before_any_write(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    keep = out / "keep.txt"
    keep.write_bytes(b"original")
    with pytest.raises(ValueError, match="ancestor|conflict"):
        extract(tmp_path, [("keep.txt", b"replacement"), (hwr.MANIFEST + "/child", b"child")], no_manifest=False)
    assert keep.read_bytes() == b"original"
    assert not (out / hwr.MANIFEST).exists()


@pytest.mark.parametrize("collision", ["directory", "parent-file"])
def test_existing_filesystem_conflict_refused_before_any_write(tmp_path, collision):
    out = tmp_path / "out"
    out.mkdir()
    keep = out / "keep.txt"
    keep.write_bytes(b"original")
    if collision == "directory":
        (out / "collision").mkdir()
        name = "collision"
    else:
        (out / "collision").write_bytes(b"parent")
        name = "collision/child"
    with pytest.raises(ValueError, match="directory|file|ancestor|conflict"):
        extract(tmp_path, [("keep.txt", b"replacement"), (name, b"bad")])
    assert keep.read_bytes() == b"original"
    if collision == "parent-file":
        assert (out / "collision").read_bytes() == b"parent"


@pytest.mark.parametrize("manifest", [False, True])
def test_existing_hardlink_cannot_modify_outside_owned_canary(tmp_path, manifest):
    out = tmp_path / "out"
    out.mkdir()
    keep = out / "keep.txt"
    keep.write_bytes(b"original")
    canary = tmp_path / "owned-outside-canary.txt"
    canary.write_bytes(b"external-original")
    name = hwr.MANIFEST if manifest else "linked.txt"
    try:
        os.link(canary, out / name)
    except OSError as error:
        pytest.skip("hardlinks unavailable: " + str(error))
    rows = [("keep.txt", b"replacement")] + ([] if manifest else [(name, b"overwrite")])
    with pytest.raises(ValueError, match="hardlink|linked"):
        extract(tmp_path, rows, no_manifest=not manifest)
    assert keep.read_bytes() == b"original"
    assert canary.read_bytes() == b"external-original"
