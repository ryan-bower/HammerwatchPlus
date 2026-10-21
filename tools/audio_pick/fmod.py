"""The game's own FMOD Studio (fmodstudio.dll 2.2.11, from the install, read only) through
ctypes: the event list of the install's banks, and an event rendered offline to a WAV.

    fmod.py list [<filter>]            # every event path (in master.strings.bank)
    fmod.py render <event> <out.wav>   # one event, played once and written out

Nothing is written outside the given path: the banks are opened read only and the output
mode is FMOD's non-realtime WAV writer (no sound plays)."""
from __future__ import annotations

import ctypes as C
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from gamelab import env  # noqa: E402

FMOD_VERSION = 0x00020211          # the install's 2.2.11 (fmodstudio.dll file version)
OUTPUT_WAVWRITER_NRT = 5           # FMOD_OUTPUTTYPE
STUDIO_INIT_ALLOW_MISSING_PLUGINS, STUDIO_INIT_SYNCHRONOUS_UPDATE = 0x2, 0x4
PLAYBACK_STOPPED = 2
SAMPLES_LOADED, SAMPLES_ERROR = 3, 4   # FMOD_STUDIO_LOADING_STATE
STOP_ALLOWFADEOUT = 0
RATE = 22050
BLOCK = 1024                       # samples a block
BANKS = ("master.bank", "master.strings.bank", "sfx.bank")


class FmodError(RuntimeError):
    pass


def _ok(r, what):
    if r != 0:
        raise FmodError(f"{what}: FMOD_RESULT {r}")


class Studio:
    """One Studio system with the sfx banks loaded. wav=None: no output (listing only)."""

    def __init__(self, wav: Path | None = None):
        game = env.install()
        os.add_dll_directory(str(game))
        self.core_dll = C.CDLL(str(game / "fmod.dll"))
        self.dll = C.CDLL(str(game / "fmodstudio.dll"))
        self.sys = C.c_void_p()
        _ok(self.dll.FMOD_Studio_System_Create(C.byref(self.sys), C.c_uint(FMOD_VERSION)), "System_Create")
        core = C.c_void_p()
        _ok(self.dll.FMOD_Studio_System_GetCoreSystem(self.sys, C.byref(core)), "GetCoreSystem")
        _ok(self.core_dll.FMOD_System_SetOutput(core, C.c_int(OUTPUT_WAVWRITER_NRT if wav else 4)), "SetOutput")   # 4: NOSOUND_NRT
        _ok(self.core_dll.FMOD_System_SetSoftwareFormat(core, C.c_int(RATE), C.c_int(2), C.c_int(0)), "SetSoftwareFormat")  # FMOD_SPEAKERMODE_MONO
        _ok(self.core_dll.FMOD_System_SetDSPBufferSize(core, C.c_uint(BLOCK), C.c_int(4)), "SetDSPBufferSize")
        self.blocks = 0                 # blocks mixed so far: in NRT mode each update mixes one
        name = C.c_char_p(str(wav).encode("mbcs")) if wav else None
        _ok(self.dll.FMOD_Studio_System_Initialize(self.sys, C.c_int(64), C.c_uint(STUDIO_INIT_ALLOW_MISSING_PLUGINS | STUDIO_INIT_SYNCHRONOUS_UPDATE),
                                                   C.c_uint(0), name), "Initialize")
        self.banks = []
        for b in BANKS:
            h = C.c_void_p()
            _ok(self.dll.FMOD_Studio_System_LoadBankFile(self.sys, str(game / "res/assets/sound" / b).encode("mbcs"), C.c_uint(0), C.byref(h)), f"LoadBankFile {b}")
            self.banks.append(h)
        self.dll.FMOD_Studio_System_FlushCommands(self.sys)

    def events(self) -> list[str]:
        out = []
        for b in self.banks:
            n = C.c_int()
            _ok(self.dll.FMOD_Studio_Bank_GetEventCount(b, C.byref(n)), "GetEventCount")
            if not n.value:
                continue
            arr = (C.c_void_p * n.value)()
            got = C.c_int()
            _ok(self.dll.FMOD_Studio_Bank_GetEventList(b, arr, n, C.byref(got)), "GetEventList")
            for i in range(got.value):
                buf = C.create_string_buffer(512)
                ln = C.c_int()
                if self.dll.FMOD_Studio_EventDescription_GetPath(C.c_void_p(arr[i]), buf, 512, C.byref(ln)) == 0:
                    out.append(buf.value.decode())
        return sorted(set(out))

    def update(self):
        self.dll.FMOD_Studio_System_Update(self.sys)
        self.blocks += 1

    def render(self, event: str, max_ms: int = 3000) -> tuple[int, int]:
        """Plays the event once (a looping one is stopped, with its fade, at max_ms), then lets
        the tail ring out; returns the blocks [first, end) of the WAV it fills."""
        desc = C.c_void_p()
        _ok(self.dll.FMOD_Studio_System_GetEvent(self.sys, event.encode(), C.byref(desc)), f"GetEvent {event}")
        # the samples load asynchronously: wait for them, or the first blocks are silent
        _ok(self.dll.FMOD_Studio_EventDescription_LoadSampleData(desc), "LoadSampleData")
        ls = C.c_int()
        for _ in range(2000):
            self.update()
            self.dll.FMOD_Studio_EventDescription_GetSampleLoadingState(desc, C.byref(ls))
            if ls.value in (SAMPLES_LOADED, SAMPLES_ERROR):
                break
        inst = C.c_void_p()
        _ok(self.dll.FMOD_Studio_EventDescription_CreateInstance(desc, C.byref(inst)), "CreateInstance")
        _ok(self.dll.FMOD_Studio_EventInstance_Start(inst), "Start")
        first = self.blocks
        block = BLOCK / RATE * 1000
        t, stopped = 0.0, False
        st = C.c_int()
        while t < max_ms + 2000:
            self.update()
            t += block
            self.dll.FMOD_Studio_EventInstance_GetPlaybackState(inst, C.byref(st))
            if st.value == PLAYBACK_STOPPED and t > 50:
                break
            if t >= max_ms and not stopped:
                self.dll.FMOD_Studio_EventInstance_Stop(inst, C.c_int(STOP_ALLOWFADEOUT))
                stopped = True
        self.dll.FMOD_Studio_EventInstance_Release(inst)
        for _ in range(8):              # the mixer's latency and any reverb tail
            self.update()
        end = self.blocks
        self.dll.FMOD_Studio_EventDescription_UnloadSampleData(desc)
        return first, end

    def close(self):
        self.dll.FMOD_Studio_System_Release(self.sys)


def main(argv):
    if argv[:1] == ["list"]:
        s = Studio()
        for e in s.events():
            if len(argv) < 2 or argv[1] in e:
                print(e)
        s.close()
    elif argv[:1] == ["render"] and len(argv) == 3:
        s = Studio(Path(argv[2]))
        a, b = s.render(argv[1])
        print((b - a) * BLOCK * 1000 // RATE, "ms")
        s.close()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
