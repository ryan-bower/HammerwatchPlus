"""Builds the audio picker page: python build.py -> out/picker.html (git-ignored).
Every event in slots.py is rendered offline by the game's FMOD (fmod.py) into one WAV, cut
per event, trimmed of silence and embedded in the page as a mono 16-bit WAV. The page is
published as an artifact with a shared store, like the icon picker: picks are read back from
it (collection "picks", one document per slot id: {choice: "now" | "a".. | "silent", event,
note}). It also writes art/specs/AUDIO.md from slots.py."""
import base64, io, json, sys, wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fmod  # noqa: E402
from slots import SLOTS  # noqa: E402

OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
FLOOR = 40          # |sample| below this (of 32767) is silence when trimming
PAD = 0.03          # seconds kept around the sound


def clip(a: np.ndarray) -> np.ndarray:
    loud = np.flatnonzero(np.abs(a.astype(np.int32)) > FLOOR)
    if not len(loud):
        return a[:0]
    p = int(PAD * fmod.RATE)
    return a[max(0, loud[0] - p):loud[-1] + p]


def wav_uri(a: np.ndarray) -> str:
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(fmod.RATE)
        w.writeframes(a.astype("<i2").tobytes())
    return "data:audio/wav;base64," + base64.b64encode(b.getvalue()).decode()


def audio_md():
    """art/specs/AUDIO.md: the same slots, for reading."""
    out = ["# Audio: the six 4th specializations (mods/specs)", "",
           "Every moment below plays (or could play) a sound. All options are vanilla FMOD events, so",
           "nothing new needs recording. **Now** is the mod's placeholder today (none: silent so far).",
           "Pick in the audio picker: `python tools/audio_pick/build.py` renders every option with the",
           "game's own FMOD (read only, from the install) into `tools/audio_pick/out/picker.html`, which",
           "is published as an artifact with a shared store; the picks are read back from it and wired",
           "in at the hook named. Options are in `tools/audio_pick/slots.py`.", ""]
    spec = None
    for sp, sid, name, what, hook, now, opts in SLOTS:
        if sp != spec:
            spec = sp
            out += [f"## {sp}", "", "| slot | moment | hook | now | options |", "|---|---|---|---|---|"]
        o = "<br>".join(f"{chr(97 + i)}: `{e}`" for i, e in enumerate(opts))
        out.append(f"| `{sid}` | **{name}**<br>{what} | {hook} | {f'`{now}`' if now else 'none'} | {o} |")
        nxt = SLOTS.index((sp, sid, name, what, hook, now, opts)) + 1
        if nxt == len(SLOTS) or SLOTS[nxt][0] != sp:
            out.append("")
    out += ["Left without a sound by choice: stack gains (Tailwind, Static Charge, Essence), the arrow",
            "catch, a brand passing on, Arcane Feedback banking, Mana Conduit. Vanilla stacks are silent too.", ""]
    (HERE.parents[1] / "art/specs/AUDIO.md").write_text("\n".join(out), encoding="utf-8", newline="\n")


def main():
    audio_md()
    events = sorted({e for s in SLOTS for e in ([s[5]] if s[5] else []) + s[6]})
    raw = OUT / "all.wav"
    st = fmod.Studio(raw)
    spans = {e: st.render("event:/sfx/" + e) for e in events}
    st.close()
    with wave.open(str(raw)) as w:
        allpcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    sounds, seconds = {}, 0.0
    for e, (a, b) in spans.items():
        c = clip(allpcm[a * fmod.BLOCK:b * fmod.BLOCK])
        seconds += len(c) / fmod.RATE
        sounds[e] = {"src": wav_uri(c) if len(c) else None, "s": round(len(c) / fmod.RATE, 2)}
    groups = []
    for spec, sid, name, what, hook, now, opts in SLOTS:
        g = next((g for g in groups if g["title"] == spec), None)
        if g is None:
            g = {"id": spec.lower(), "title": spec, "items": []}
            groups.append(g)
        choices = ([("now", now)] if now else []) + [(chr(97 + i), e) for i, e in enumerate(opts)]
        g["items"].append({"id": sid, "name": name, "desc": what, "hook": hook,
                           "opts": [{"k": k, "event": "event:/sfx/" + e, "short": e.split("/")[-1], **sounds[e]} for k, e in choices]})
    tpl = (HERE / "picker_tpl.html").read_text(encoding="utf-8")
    html = tpl.replace("/*DATA*/null", json.dumps(groups, separators=(",", ":")))
    (OUT / "picker.html").write_text(html, encoding="utf-8")
    silent = [e for e, v in sounds.items() if not v["src"]]
    print(f"{len(events)} events, {seconds:.1f} s of sound, page {len(html) / 1e6:.1f} MB -> {OUT / 'picker.html'}")
    if silent:
        print("silent:", silent)


if __name__ == "__main__":
    main()
