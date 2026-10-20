"""Reads and writes the held guns' voxel models and builds the Firearms Specialist's new ones.

    python tools/make_gun_models.py                  # write the new guns' models
    python tools/make_gun_models.py --check          # every .model in mods/ and the vanilla
                                                     # equipment folder must round-trip
                                                     # byte-identical; write nothing
    python tools/make_gun_models.py --preview DIR    # side/top/front views of each gun -> DIR
    python tools/make_gun_models.py --dump NAME.model  # a model's voxels as text slices

The .model format (players/models/equipment/*.model) is the ozz-animation sample
framework's mesh archive, little endian:
- u8 1 (endianness), "ozz-sample-Mesh\\0", u32 version 1.
- parts: u32 count, u32 part version 1, then per part seven arrays, each a u32 count and
  its items: positions f32 xyz, normals f32 xyz, tangents f32 xyzw, uvs f32 uv,
  colors u8, joint_indices u16, joint_weights f32.
- triangle_indices u16, joint_remaps u16 (the skeleton joint the mesh rides; 19 is the
  right hand, 21 the left), inverse_bind_poses (16 f32 each).
- two strings, each a u32 one less than its length and then all of its bytes (no NUL):
  the material ("system/default.mat3d:player_model") and the texture ("character.tif",
  next to the model).

character.tif (128x128, 20 bytes a texel: RGBA then 16 mask bytes) is a palette: columns
0-15 are the dye slots (0 skin, 1 hair, 2-3 hat, 4-5 chest, 6-7 legs, 8 hand, 9-10 cape,
11-12 main hand, 13-14 off hand, 15 misc), each a grey ramp from row 0 (white) to row 7
(black) tinted by the slot's dye; columns 17-25 are fixed ramps (17 grey, 18 gold,
19 steel blue, 20 tan, 21 brown, 22 grey, 23 red, 24 green, 25 blue). A held weapon's
`color` dye is slot 11, its `color-secondary` slot 12. The v coordinate runs bottom up.

Our models (hwp_*) are 1 cm voxels written one quad per exposed face, each quad one texel:
voxels in x, y, z order, each voxel's open faces in FACES order. x is the barrel (the
muzzle at +x), y is up (the sights at +y, the grip down), z across. Vanilla models are
meshed some other way; --check round-trips them through the raw reader only.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EQUIP = ROOT / "mods" / "firearms" / "players" / "models" / "equipment"
VANILLA = ROOT / "gamecode" / "sdk" / "hoh2" / "players" / "models" / "equipment"
TAG = b"\x01ozz-sample-Mesh\x00"
VOXEL = 0.01
TEX = 128
RIGHT_HAND, LEFT_HAND = 19, 21

# ---------------------------------------------------------------- raw archive
PART_ARRAYS = (("positions", "f"), ("normals", "f"), ("tangents", "f"), ("uvs", "f"),
               ("colors", "B"), ("joint_indices", "H"), ("joint_weights", "f"))


class Mesh:
    def __init__(self):
        self.parts: list[dict[str, tuple]] = []
        self.triangles: tuple = ()
        self.remaps: tuple = ()
        self.bind_poses: tuple = ()      # 16 floats per joint
        self.material = "system/default.mat3d:player_model"
        self.texture = "character.tif"
        self.tail = b""                  # anything after (a few vanilla hair models carry a
                                         # second, empty mesh), kept as it is


def read_mesh(data: bytes) -> Mesh:
    if not data.startswith(TAG):
        raise ValueError("not an ozz-sample-Mesh archive")
    o = len(TAG)

    def u32():
        nonlocal o
        v = struct.unpack_from("<I", data, o)[0]
        o += 4
        return v

    def arr(fmt, per=1):
        nonlocal o
        n = u32()
        size = struct.calcsize(fmt)
        v = struct.unpack_from(f"<{n * per}{fmt}", data, o)
        o += n * per * size
        return v

    def string():
        nonlocal o
        n = u32() + 1
        v = data[o:o + n].decode("utf-8")
        o += n
        return v
    m = Mesh()
    if u32() != 1:
        raise ValueError("mesh version is not 1")
    nparts = u32()
    if nparts and u32() != 1:
        raise ValueError("part version is not 1")
    for _ in range(nparts):
        m.parts.append({name: arr(fmt) for name, fmt in PART_ARRAYS})
    m.triangles = arr("H")
    m.remaps = arr("H")
    m.bind_poses = arr("f", 16)
    m.material = string()
    m.texture = string()
    if o > len(data):
        raise ValueError("truncated")
    m.tail = data[o:]
    return m


def write_mesh(m: Mesh) -> bytes:
    out = bytearray(TAG)

    def arr(fmt, v, per=1):
        out.extend(struct.pack("<I", len(v) // per))
        out.extend(struct.pack(f"<{len(v)}{fmt}", *v))

    def string(s):
        b = s.encode("utf-8")
        out.extend(struct.pack("<I", len(b) - 1) + b)
    out.extend(struct.pack("<II", 1, len(m.parts)))
    if m.parts:
        out.extend(struct.pack("<I", 1))
    for p in m.parts:
        for name, fmt in PART_ARRAYS:
            arr(fmt, p[name])
    arr("H", m.triangles)
    arr("H", m.remaps)
    arr("f", m.bind_poses, 16)
    string(m.material)
    string(m.texture)
    return bytes(out) + m.tail


# ---------------------------------------------------------------- voxels
# (normal, tangent, corners as offsets from the voxel's min corner), in the order a voxel's
# faces are written
FACES = (
    ((1, 0, 0), (0, 1, 0, 1), ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1))),
    ((-1, 0, 0), (0, 1, 0, 1), ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0))),
    ((0, 1, 0), (1, 0, 0, 1), ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0))),
    ((0, -1, 0), (1, 0, 0, 1), ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),
    ((0, 0, 1), (1, 0, 0, 1), ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))),
    ((0, 0, -1), (1, 0, 0, 1), ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0))),
)


class Voxels:
    """A voxel model: {(x, y, z): (texel column, texel row)} on one joint."""

    def __init__(self, vox=None, joint=RIGHT_HAND):
        self.vox: dict[tuple[int, int, int], tuple[int, int]] = dict(vox or {})
        self.joint = joint

    def copy(self) -> "Voxels":
        return Voxels(self.vox, self.joint)

    def box(self, x0, x1, y0, y1, z0, z1, texel):
        """Fill (texel) or clear (None) the inclusive box."""
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    if texel is None:
                        self.vox.pop((x, y, z), None)
                    else:
                        self.vox[(x, y, z)] = texel
        return self

    def recolor(self, mapping, where=lambda v: True):
        for v, t in self.vox.items():
            if t in mapping and where(v):
                self.vox[v] = mapping[t]
        return self

    def bounds(self):
        ks = list(self.vox)
        return tuple((min(k[a] for k in ks), max(k[a] for k in ks)) for a in range(3))


def uv_of(texel):
    col, row = texel
    return (col + 0.5) / TEX, 1 - (row + 0.5) / TEX


def texel_of(u, v):
    return int(u * TEX), int((1 - v) * TEX)


def to_mesh(vx: Voxels) -> Mesh:
    pos, nrm, tan, uvs, tri = [], [], [], [], []
    n = 0
    for v in sorted(vx.vox):
        u, w = uv_of(vx.vox[v])
        for normal, tangent, corners in FACES:
            if tuple(v[a] + normal[a] for a in range(3)) in vx.vox:
                continue
            for c in corners:
                pos.extend(float(struct.unpack("<f", struct.pack("<f", (v[a] + c[a]) * VOXEL))[0]) for a in range(3))
                nrm.extend(float(x) for x in normal)
                tan.extend(float(x) for x in tangent)
                uvs.extend((u, w))
            tri.extend((n, n + 1, n + 2, n, n + 2, n + 3))
            n += 4
    m = Mesh()
    m.parts = [{"positions": tuple(pos), "normals": tuple(nrm), "tangents": tuple(tan), "uvs": tuple(uvs),
                "colors": (), "joint_indices": (0,) * n, "joint_weights": ()}]
    m.triangles = tuple(tri)
    m.remaps = (vx.joint,)
    m.bind_poses = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    return m


def from_mesh(m: Mesh) -> Voxels:
    """The voxels of a mesh in our voxel form; ValueError when it is not one."""
    if len(m.parts) != 1 or len(m.remaps) != 1:
        raise ValueError("not a one-part, one-joint mesh")
    p = m.parts[0]
    pos, nrm, uvs = p["positions"], p["normals"], p["uvs"]
    vx = Voxels(joint=m.remaps[0])
    shown = set()
    for q in range(len(pos) // 12):
        corners = [tuple(round(pos[(q * 4 + i) * 3 + a] / VOXEL) for a in range(3)) for i in range(4)]
        normal = tuple(int(nrm[q * 12 + a]) for a in range(3))
        lo = [min(c[a] for c in corners) for a in range(3)]
        v = tuple(lo[a] - (1 if normal[a] > 0 else 0) for a in range(3))
        t = texel_of(uvs[q * 8], uvs[q * 8 + 1])
        if vx.vox.get(v, t) != t:
            raise ValueError(f"voxel {v} has faces of two texels")
        vx.vox[v] = t
        shown.add((v, normal))
    # a voxel shut in on all six sides has no faces; a face missing from a voxel says the
    # cell beyond it is solid. Those hidden voxels take their finder's texel (they show
    # only if an edit opens them up).
    todo = list(vx.vox)
    while todo:
        v = todo.pop()
        for normal, _, _ in FACES:
            if (v, normal) not in shown:
                nb = tuple(v[a] + normal[a] for a in range(3))
                if nb not in vx.vox:
                    vx.vox[nb] = vx.vox[v]
                    todo.append(nb)
    return vx


def load(path: Path) -> Voxels:
    m = read_mesh(path.read_bytes())
    vx = from_mesh(m)
    if write_mesh(to_mesh(vx)) != write_mesh(m):
        raise ValueError(f"{path.name}: not in our voxel form")
    return vx


# ---------------------------------------------------------------- the new guns
# texels: (dye slot or fixed column, shade row 0 white .. 7 black)
C1 = lambda shade: (11, shade)      # the item's `color`
C2 = lambda shade: (12, shade)      # the item's `color-secondary`
GREY = lambda shade: (17, shade)
FRAME = lambda shade: (22, shade)
GOLDF = lambda shade: (18, shade)
RED = lambda shade: (23, shade)


def hand_cannon(glock: Voxels) -> Voxels:
    """The pistol's grip, trigger guard and frame where they are (the hand fits as it
    does), a 3x3x3 cylinder over the trigger, a two-voxel-tall barrel twice the slide's
    length, a flared muzzle ring and a hammer spur."""
    vx = Voxels({v: t for v, t in glock.vox.items() if v[1] < 0}, glock.joint)   # grip + guard
    vx.box(-1, 2, 0, 0, 0, 0, FRAME(4))                    # frame under the cylinder
    vx.box(-1, -1, 1, 2, 0, 0, C1(4))                      # back strap
    vx.box(-2, -2, 2, 3, 0, 0, GREY(5))                    # hammer spur
    vx.box(0, 2, 0, 2, -1, 1, C2(3))                       # cylinder
    for x in (0, 2):                                       # its flutes, darker at the ends
        vx.box(x, x, 0, 2, -1, -1, C2(4)).box(x, x, 0, 2, 1, 1, C2(4))
    vx.box(0, 2, 2, 2, 0, 0, C2(2))                        # its lit top
    vx.box(3, 10, 2, 2, 0, 0, C1(2))                       # barrel: the lit top rib
    vx.box(3, 10, 1, 1, 0, 0, C1(3))                       #   and its body
    vx.box(3, 8, 0, 0, 0, 0, C1(4))                        #   ejector shroud under it
    vx.box(10, 11, 1, 2, -1, 1, C2(3))                     # muzzle ring
    vx.box(10, 11, 2, 2, 0, 0, C2(2))
    vx.box(11, 11, 1, 1, 0, 0, GREY(7))                    # the bore
    vx.box(9, 9, 3, 3, 0, 0, GREY(5))                      # front sight
    vx.box(-1, -1, 3, 3, 0, 0, GREY(5))                    # rear sight
    return vx


def flame_rifle(rifle: Voxels) -> Voxels:
    """The rifle with its under-barrel launcher (the steel-blue tube at x 5-10, y -2..0,
    its black muzzle and the grip under it) swapped for a red fuel tank with steel end
    caps, a valve, a fuel line under the barrel and a nozzle with a gold pilot light below
    the muzzle. Stock, grip, magazine, trigger, receiver, handguard and barrel stay where
    they are, so the crossbow anims hold it as they hold the rifle."""
    vx = Voxels({v: t for v, t in rifle.vox.items()
                 if not (t[0] == 19 or (5 <= v[0] <= 10 and v[1] <= -1 and t[0] == 17))}, rifle.joint)
    vx.box(5, 6, 0, 0, 0, 0, C1(2))                        # close the handguard over it
    vx.box(5, 8, -3, -1, -1, 1, RED(3))                    # tank
    vx.box(5, 8, -1, -1, -1, 1, RED(2))                    #   its lit top
    vx.box(5, 8, -3, -3, -1, 1, RED(5))                    #   its dark belly
    for x in (5, 8):                                       #   steel end caps
        vx.box(x, x, -3, -1, -1, 1, GREY(4)).box(x, x, -1, -1, -1, 1, GREY(3))
    vx.box(9, 9, -1, -1, 0, 0, GREY(5))                    # valve
    vx.box(8, 11, 0, 0, 0, 0, GREY(3))                     # fuel line under the barrel
    vx.box(12, 13, 0, 0, 0, 0, GREY(5))                    # nozzle
    vx.box(12, 12, -1, -1, 0, 0, GREY(5))
    vx.box(13, 13, -1, -1, 0, 0, GOLDF(2))                 # pilot light
    return vx


def auto_rifle(rifle: Voxels) -> Voxels:
    """The rifle with no launcher: its curved box magazine (the grey voxels at x 1-4 under
    the receiver) a 6 cm drum 5 cm across, the launcher tube a perforated gunmetal shroud
    round the barrel, and the launcher's grip a wooden fore-grip where it was (x 6-7,
    under the handguard), so the crossbow anims hold it as they hold the rifle. Stock,
    pistol grip, trigger, receiver and muzzle stay where they are."""
    vx = Voxels({v: t for v, t in rifle.vox.items()
                 if not (t[0] == 19 or (1 <= v[0] <= 10 and v[1] <= -1 and t[0] == 17))}, rifle.joint)
    vx.box(5, 6, 0, 0, 0, 0, C1(2))                        # close the handguard over the tube
    for x in range(0, 6):                                  # drum: its axis across (z)
        for y in range(-6, 0):
            d = ((x - 2.5) ** 2 + (y + 3.5) ** 2) ** 0.5
            if d > 2.9:
                continue
            for z in range(-2, 3):
                face = abs(z) == 2
                if d > 2.0:
                    t = C2(3 if y >= -3 else 4)            # its rim, lit above
                elif face and d < 0.8:
                    t = GREY(3)                            # the winding hub
                else:
                    t = GREY(5) if face else GREY(6)
                vx.vox[(x, y, z)] = t
    vx.box(6, 7, -3, -1, 0, 0, C1(3))                      # fore-grip
    vx.box(6, 7, -4, -4, 0, 0, C1(4))
    vx.box(8, 12, 0, 2, -1, 1, GREY(5))                    # shroud round the barrel
    vx.box(8, 12, 1, 1, 0, 0, C2(3))                       #   the barrel inside it
    for x in (9, 11):                                      #   its cooling holes
        for v in ((x, 1, -1), (x, 1, 1), (x, 2, 0), (x, 0, 0)):
            vx.vox.pop(v, None)
    vx.box(10, 10, 3, 3, 0, 0, GREY(5))                    # front sight, up on the shroud
    vx.box(13, 13, 0, 2, -1, 1, GREY(6))                   # compensator
    vx.box(13, 13, 1, 1, 0, 0, GREY(7))                    #   its bore
    return vx


def builds() -> dict[str, Voxels]:
    glock = load(EQUIP / "hwp_glock_mh.model")
    rifle = load(EQUIP / "hwp_rifle.model")
    cannon = hand_cannon(glock)
    off = cannon.copy()
    off.joint = LEFT_HAND                                  # as hwp_glock_oh is hwp_glock_mh
    return {"hwp_hcannon_mh": cannon, "hwp_hcannon_oh": off, "hwp_flamerifle": flame_rifle(rifle),
            "hwp_autorifle": auto_rifle(rifle)}


# ---------------------------------------------------------------- tools
def model_paths():
    yield from sorted((ROOT / "mods").glob("*/players/models/equipment/*.model"))
    yield from sorted(VANILLA.glob("*.model"))


def check() -> int:
    bad = raw = vox = 0
    for p in model_paths():
        data = p.read_bytes()
        try:
            m = read_mesh(data)
        except ValueError as e:
            print(f"{p.relative_to(ROOT)}: {e}")
            bad += 1
            continue
        if write_mesh(m) != data:
            print(f"{p.relative_to(ROOT)}: raw round trip differs")
            bad += 1
            continue
        raw += 1
        if p.name.startswith("hwp_"):
            try:
                if write_mesh(to_mesh(from_mesh(m))) != data:
                    raise ValueError("voxel round trip differs")
                vox += 1
            except ValueError as e:
                print(f"{p.relative_to(ROOT)}: {e}")
                bad += 1
    print(f"{raw} models round-trip raw, {vox} hwp_ models through voxels" + (f"; {bad} failed" if bad else ""))
    return 1 if bad else 0


def palette():
    """character.tif as {(col, row): rgb}, the dye slots shown with sample dyes."""
    data = (VANILLA / "character.tif").read_bytes()
    off = 1551 if len(data) > 1551 + TEX * TEX * 20 else None
    # TinyTIFF: one strip; find its offset in the IFD
    ifd = struct.unpack_from("<I", data, 4)[0]
    for i in range(struct.unpack_from("<H", data, ifd)[0]):
        tag, _typ, _cnt, val = struct.unpack_from("<HHII", data, ifd + 2 + i * 12)
        if tag == 273:
            off = val
    dyes = {11: (0.62, 0.42, 0.26), 12: (0.72, 0.74, 0.80), 13: (0.62, 0.42, 0.26), 14: (0.72, 0.74, 0.80)}
    pal = {}
    for row in range(8):
        for col in range(26):
            o = off + (row * TEX + col) * 20
            r, g, b, _a = data[o:o + 4]
            k = dyes.get(col)
            pal[(col, row)] = (int(r * k[0]), int(g * k[1]), int(b * k[2])) if k else (r, g, b)
    return pal


def render(vx: Voxels, z=12):
    """Side (from +z), top (from +y) and front (from +x) views, the nearest voxel shown."""
    from PIL import Image, ImageDraw
    pal = palette()
    (x0, x1), (y0, y1), (z0, z1) = vx.bounds()
    w, h, d = x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1
    views = []
    for name, cols, rows, depth, key in (
            ("side", range(x0, x1 + 1), range(y1, y0 - 1, -1), range(z1, z0 - 1, -1), lambda c, r, k: (c, r, k)),
            ("top", range(x0, x1 + 1), range(z0, z1 + 1), range(y1, y0 - 1, -1), lambda c, r, k: (c, k, r)),
            ("front", range(z0, z1 + 1), range(y1, y0 - 1, -1), range(x1, x0 - 1, -1), lambda c, r, k: (k, r, c))):
        im = Image.new("RGBA", (len(cols) * z, len(rows) * z), (40, 40, 48, 255))
        dr = ImageDraw.Draw(im)
        for i, c in enumerate(cols):
            for j, r in enumerate(rows):
                for n, k in enumerate(depth):
                    t = vx.vox.get(key(c, r, k))
                    if t:
                        rgb = tuple(int(v * (1 - 0.12 * n)) for v in pal.get(t, (255, 0, 255)))
                        dr.rectangle((i * z, j * z, i * z + z - 1, j * z + z - 1), fill=rgb + (255,), outline=(20, 20, 24, 255))
                        break
        views.append((name, im))
    out = Image.new("RGBA", (sum(im.width for _, im in views) + 20 * len(views), max(im.height for _, im in views) + 16), (28, 28, 34, 255))
    dr = ImageDraw.Draw(out)
    x = 0
    for name, im in views:
        out.alpha_composite(im, (x, 14))
        dr.text((x + 2, 1), name, fill=(230, 230, 230, 255))
        x += im.width + 20
    return out


def dump(vx: Voxels):
    (x0, x1), (y0, y1), (z0, z1) = vx.bounds()
    keys = sorted(set(vx.vox.values()))
    lab = {k: chr(ord("a") + i) for i, k in enumerate(keys)}
    print(f"joint {vx.joint}, {len(vx.vox)} voxels, x {x0}..{x1} y {y0}..{y1} z {z0}..{z1}")
    print("  " + "  ".join(f"{v}={k}" for k, v in lab.items()))
    for zz in range(z0, z1 + 1):
        print(f"z={zz} (rows y from the top, columns x from {x0})")
        for yy in range(y1, y0 - 1, -1):
            print(f"  {yy:3d} " + "".join(lab.get(vx.vox.get((xx, yy, zz)), ".") for xx in range(x0, x1 + 1)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="round-trip every model, write nothing")
    ap.add_argument("--preview", metavar="DIR", help="write a preview PNG of each gun into DIR")
    ap.add_argument("--dump", metavar="MODEL", help="print a model's voxels")
    args = ap.parse_args(argv)
    if args.check:
        return check()
    if args.dump:
        dump(load(Path(args.dump)))
        return 0
    guns = builds()
    if args.preview:
        out = Path(args.preview)
        out.mkdir(parents=True, exist_ok=True)
        for name, vx in list(guns.items()) + [("hwp_glock_mh", load(EQUIP / "hwp_glock_mh.model")),
                                              ("hwp_rifle", load(EQUIP / "hwp_rifle.model"))]:
            render(vx).save(out / f"{name}.png")
            print("wrote", out / f"{name}.png")
        return 0
    for name, vx in guns.items():
        data = write_mesh(to_mesh(vx))
        if write_mesh(to_mesh(from_mesh(read_mesh(data)))) != data:
            raise SystemExit(f"{name}: does not read back")
        (EQUIP / f"{name}.model").write_bytes(data)
        print(f"wrote {(EQUIP / name).relative_to(ROOT)}.model ({len(vx.vox)} voxels)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
