import json

import pytest

from tools import build


def module(mid, requires=(), **kw):
    return dict(id=mid, requires=list(requires), library=kw.get("library", False),
                shared=kw.get("shared", False), dev=kw.get("dev", False), local_only=kw.get("local_only", False))


def graph(tmp_path, monkeypatch, modules, packages=None, bench=()):
    path = tmp_path / "packages.json"
    packages = packages if packages is not None else [{"id": "one", "mods": ["feature"]}]
    path.write_text(json.dumps({"packages": packages, "all": {"file": "All"}, "bench": list(bench)}), encoding="utf-8")
    monkeypatch.setattr(build, "PACKAGES", path)
    return build.load_packages(modules)


def test_valid_diamond_preserves_dependency_order_and_deduplicates(tmp_path, monkeypatch):
    modules = [module("base", library=True), module("left", ["base"], library=True),
               module("right", ["base"], library=True), module("feature", ["left", "right"])]
    packages, _ = graph(tmp_path, monkeypatch, modules)
    assert packages[0]["closure"] == ["base", "left", "right", "feature"]


@pytest.mark.parametrize("modules", [
    [module("feature", ["feature"])],
    [module("feature", ["lib"]), module("lib", ["feature"], library=True)],
])
def test_cycles_refused(tmp_path, monkeypatch, modules):
    with pytest.raises(SystemExit, match="cycle"):
        graph(tmp_path, monkeypatch, modules)


def test_unknown_dependency_refused(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="unknown module"):
        graph(tmp_path, monkeypatch, [module("feature", ["missing"])])


def test_cross_package_unshared_dependency_refused(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="must work alone"):
        graph(tmp_path, monkeypatch, [module("feature", ["other"]), module("other")],
              [{"id": "one", "mods": ["feature"]}, {"id": "two", "mods": ["other"]}])


@pytest.mark.parametrize("flags,bench", [
    ({"library": True, "dev": True}, ()),
    ({"shared": True, "dev": True}, ()),
    ({"library": True, "local_only": True}, ()),
    ({"shared": True, "local_only": True}, ()),
    ({"shared": True}, ("dependency",)),
])
def test_forbidden_dependencies_cannot_ride_library_or_shared_flags(tmp_path, monkeypatch, flags, bench):
    with pytest.raises(SystemExit, match="dev|local-only|bench"):
        graph(tmp_path, monkeypatch, [module("feature", ["dependency"]), module("dependency", **flags)], bench=bench)


def test_shared_feature_can_ride_another_package(tmp_path, monkeypatch):
    packages, _ = graph(tmp_path, monkeypatch, [module("feature", ["shared"]), module("shared", shared=True)],
                        [{"id": "one", "mods": ["feature"]}, {"id": "two", "mods": ["shared"]}])
    assert packages[0]["closure"] == ["shared", "feature"]
    assert packages[1]["closure"] == ["shared"]
