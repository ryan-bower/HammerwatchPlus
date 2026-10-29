"""A key step's "typed" (gamelab/winproc.py): the press another keyboard layout makes. The game
must see the key's position (SDL scancode) and the layout's character as SDL sends them:
KEYDOWN, TEXTINPUT, KEYUP. Offline: the mailslot writes are captured, nothing is sent."""
import struct
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gamelab import winproc  # noqa: E402

HWND = 0x1234


def events(sent):
    out = []
    for data in sent:
        kind = struct.unpack_from("<I", data)[0]
        if kind == winproc.SDL_TEXTINPUT:
            out.append(("text", data[4:].decode("utf-8")))
        else:
            _, sc, sym, mod = struct.unpack("<IiiH", data)
            out.append(("down" if kind == winproc.SDL_KEYDOWN else "up", sc, sym, mod))
    return out


@pytest.fixture
def shim():
    sent = []
    with patch.dict(winproc._SHIM_SLOTS, {HWND: 1}), \
            patch.object(winproc, "_shim_send", lambda h, d: sent.append(d)), \
            patch.object(winproc.time, "sleep", lambda s: None):
        yield sent


def test_azerty_a_is_the_q_position_typing_a(shim):
    winproc.key(HWND, winproc.VK["q"], typed="a")
    assert events(shim) == [("down", 20, ord("a"), 0), ("text", "a"), ("up", 20, ord("a"), 0)]


def test_plain_key_sends_no_text(shim):
    winproc.key(HWND, winproc.VK["q"])
    assert events(shim) == [("down", 20, ord("q"), 0), ("up", 20, ord("q"), 0)]


def test_non_ascii_character(shim):
    # the key at [ on a German layout types ü
    winproc.key(HWND, winproc.VK["e"], typed="ü")
    assert events(shim)[1] == ("text", "ü")
    assert events(shim)[0][2] == 0xFC


def test_modifier_is_held_around_the_typed_key(shim):
    winproc.key(HWND, winproc.VK["e"], mods=(winproc.VK["shift"],), typed="E")
    ev = events(shim)
    assert ev[0][:2] == ("down", 225) and ev[-1][:2] == ("up", 225)
    assert ("text", "E") in ev
    assert ev[1] == ("down", 8, ord("e"), 0x0001)


@pytest.mark.parametrize("bad", ["", "x" * 32])
def test_typed_must_fit_an_sdl_text_event(shim, bad):
    with pytest.raises(ValueError):
        winproc.key(HWND, winproc.VK["q"], typed=bad)
    assert shim == []


def test_typed_without_shim_input_refuses():
    posted = []
    with patch.object(winproc.u32, "PostMessageW", lambda *a: posted.append(a)):
        with pytest.raises(RuntimeError, match="shim_input"):
            winproc.key(0x9999, winproc.VK["q"], typed="a")
    assert posted == []


@pytest.mark.parametrize("name,sc", [("f13", 104), ("f24", 115), ("scrolllock", 71), ("printscreen", 70)])
def test_extra_keys_send_their_sdl_scancode(shim, name, sc):
    winproc.key(HWND, winproc.VK[name])
    assert [e[:2] for e in events(shim)] == [("down", sc), ("up", sc)]
