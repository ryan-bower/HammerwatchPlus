# GameLab on Linux (experimental)

The CLI's `list` and help commands run with native Python. Live game automation
uses the **existing Windows GameLab runtime under Wine**, not a rewrite of Win32
input or DLL injection. The pinned Proton backend passed `null-payload` and
`mod-all` on NixOS on 2026-10-31. Windows execution keeps its native backend.

## Prerequisites

### Pinned Linux host environment (Nix, including NixOS)

Requires x86-64 Linux, [Nix](https://nixos.org/download/), working OpenGL 3.2,
and Steam running and signed in to an account that owns the installed HoH2.
HoH1 is optional; doctor discovers its Windows or native Linux install, or asks
you whether you own it. Never bypass its save-confirmation or build-pin checks.

`flake.lock` pins GE-Proton 11-11, its FHS host environment, Xvfb, Python, uv
and the MinGW cross-compiler. This avoids the system's potentially 32-bit Wine
and bare Proton binaries with unresolved host-library dependencies. Plain Wine
is available via `nix develop .#wine`, but cannot authenticate with native Steam
on this machine; use the default Proton shell for live tests.

```sh
./gamelab.sh setup
./gamelab.sh doctor
./gamelab.sh doctor --fix
./gamelab.sh run null-payload --mode lab
./gamelab.sh run mod-all --mode lab
```

The launcher stages **only** `flake.nix` and `flake.lock` into a temporary Nix
source, keeping game assets, local runtime files and save backups out of the
Nix store. It works before committing the flake files and from any working
directory. Do not use `nix develop "path:$PWD"`: path flakes can include ignored
private files. After the flake files are tracked, `nix develop` is also available
as an interactive shell.

The setup script downloads CPython 3.11.9 x64 and pinned Windows wheels for
lz4, pefile and Pillow, verifies committed SHA-256 hashes, and installs them
under the gitignored `gamelab/env/userdata/linux/`. It uses relative Python search
paths, caches downloads, and refuses to overwrite differing runtime files
(except its managed `python311._pth`). It does not start Wine or touch saves.
Run it again after a partial setup; hash mismatches require investigating the
cached download, not disabling verification.

`doctor --fix` cross-compiles the capture DLL on the Linux host before entering
Wine. Override the host compiler with `HWP_MINGW_CC` if necessary. All save
confirmation and build checks still apply. The bridge detects this user's native
Steam process through `/proc`; Steam must be running and signed in. A detected
process is only a prerequisite, not proof that Wine can authenticate with Steam:
the smoke scenario must prove that interop and the remaining isolation checks.

### Manually managed runtime (advanced, not the verified setup)

The same Nix launcher can be used on other distributions. The overrides below
are for custom runtimes; bare Wine alone does not provide native-Steam interop.

- x86-64 Linux and Python 3.10+ (the pinned shell targets `x86_64-linux`).
- Wine (64-bit), its matching `wineserver`, and Xvfb on PATH.
  Override executable paths with `HWP_WINE`, `HWP_WINESERVER`, `HWP_XVFB`.
  The bridge prefers `wine64` when available, otherwise `wine`; Wine startup and
  cleanup both use the selected matching server, not an inherited `WINESERVER`.
- A **Windows** Python 3.10+ installation, with the project's Python dependencies
  (`lz4`, `pefile`, `pillow`), accessible from Linux. Set `HWP_WINE_PYTHON` to its
  Linux path, or place it at `gamelab/env/userdata/linux/python/python.exe`.
  The Linux `.venv` is not usable by Windows Python. An embedded Python runtime
  must enable `import site` and include the repo on its search path before
  `-m gamelab` can work.
- HoH2 installed through Steam, and the prerequisites reported by the Windows
  doctor (pinned build, toolchain, extracted SDK, confirmed saves).

```sh
export HWP_WINE_PYTHON=/path/to/windows/python.exe
python3 -m gamelab list
python3 -m gamelab doctor
python3 -m gamelab run null-payload --mode lab
python3 -m gamelab run mod-all --mode lab
```

`doctor` first checks the Linux runtime dependencies, then runs the existing
Windows doctor inside Wine. `--fix` is forwarded, not permission to bypass any
save confirmation, build pin, or Steam requirement. No runtime is downloaded
automatically. Missing dependencies return exit 2, without starting the game.

## Isolation and limitations

- Every Wine invocation uses a fresh **private Xvfb display** with TCP disabled.
  It never inherits the player's X11/Wayland display. Linux watch mode is refused.
- The default Proton prefix lives under `gamelab/env/userdata/linux/proton/pfx`
  (standalone Wine uses `gamelab/env/userdata/linux/wine64-prefix`), never in
  the player's Proton prefix. A host lock serializes access. Cleanup targets only
  this private Wine prefix. The existing GameLab game directory and Windows
  locks/assertions are still used.
- Linux Steam/install paths are passed as Wine `Z:` paths. The real game's Proton
  `AppData/Local` is discovered in the game's Steam library and passed through for
  backup discovery. An explicit `HWP_LOCALAPPDATA` overrides this; it must name the
  **real game's** appdata directory, not the private Wine prefix's appdata.
  Do not confirm saves until doctor's list includes all the player's save dirs.
- The pinned Nix/Proton runtime is verified on this machine, not every Linux/GPU
  combination. Plain Wine could not authenticate with native Steam here. The Nix
  shell builds the shim with the host MinGW cross-compiler; all desktop/job,
  injection, focus, capture and save assertions remain enforced.
- Xvfb may use software rendering on other machines. Both smoke scenarios must
  pass locally; never start the user's installed game directly as a fallback.
- Input stays as posted window messages. The boot sequence selects keyboard
  navigation with Down/Up before Return; it never warps a cursor or changes focus.
  `HWP_TRACE_INPUT=1` optionally logs received SDL events to the lab capture log.

## Historical setup probes (2026-10-29; superseded)

- `python3 -m unittest gamelab.test_linux -v`: host regressions, including an actual
  private Xvfb server and cleanup; no game involved.
- System Wine 11 here is 32-bit and refused the 64-bit Python executable. Using
  the installed Proton 7 Wine64 **binaries only**, with the bridge's separate
  prefix, ran CPython 3.11.9 and the Windows doctor successfully. This does not
  launch Steam's game or use its Proton prefix.
- Doctor found the pinned build and the real cloud/local/Proton backup paths,
  then returned exit 2: Python dependencies, Windows Steam/toolchain, SDK/shim,
  confirmed saves and smoke boot are not ready. HoH1 also awaits the user's answer.
  No game was launched and no saves were confirmed or changed.
- For that runtime, set `HWP_WINE` to `<Steam>/steamapps/common/Proton 7.0/dist/bin/wine64`;
  the matching sibling `wineserver` is selected automatically (or set
  `HWP_WINESERVER`). Proton's bare Wine binaries may lack host libraries outside
  Steam's runtime; this machine reported missing FreeType and a 32-bit loader.

The downloaded local Windows Python runtime is gitignored. Its official archive:
`https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip`, SHA-256
`009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b`.
The initial probe edited `python311._pth` by hand. The current setup script
generates portable relative search paths instead.

## Follow-up validation (2026-10-31)

- All 31 regression tests pass, including private Xvfb cleanup, matching Wine
  server selection, environment isolation, runtime integrity, launcher source
  isolation, job-query access rights and unsigned save-rotation selection.
- `./build.sh` builds all 30 module packages and `HammerwatchPlus-All.bin`
  natively. The pip fallback now handles an existing pip-less virtualenv.
- Both SDKs and all generated content are present; `./build.sh --check` passes.
- Repeating `./gamelab.sh setup` succeeded from cached downloads. A subsequent
  `./gamelab.sh doctor --fix` returned **green / exit 0**, reused the existing
  generated trees and smoke stamp, and did not boot another game.

| Live result | Evidence |
|---|---|
| PASS: fresh fixture, three boots | `null-payload 20261031-150725` (45.9 s) |
| PASS: all 326 exports, manifest matches | `export-datatables 20261031-150939` (179.2 s) |
| PASS: doctor's smoke | `null-payload 20261031-151334` (19 s) |
| PASS: all 30 content mods, exact enabled set | `mod-all 20261031-151727` (20.2 s) |
| PASS: repeat after setup/doctor/all-mod run | `null-payload 20261031-152035` (18.5 s) |
| PASS: all mods after full 64-bit timestamp fix | `mod-all 20261031-152227` (20.5 s) |

Town/end captures were inspected. All live runs above retained the original
containment, capture, teardown, user-data and focus assertions.

### Reproducible runtime work

- `gamelab.sh` now selects the locked Proton/FHS runtime. Setup downloads and
  verifies Windows Python and wheels; no manual embedded-Python path edits are needed.
- Both SDKs extract locally, the generated class units/HoH1 imports/pet dyes build,
  and real saves were backed up and re-hashed by the existing saves gate.
- Plain Wine cannot initialize native Steam here. Locked GE-Proton authenticates,
  initializes OpenGL, loads the menu and injects both capture/known-folder hooks.
- Job verification now opens processes with `PROCESS_QUERY_INFORMATION`, as
  required by `IsProcessInJob`; the limited access right failed under Wine.
- Windows Git provenance is collected on the Linux host. Bridge output/status
  files preserve diagnostics and the Windows exit code through Proton's launcher.
- Failed datatable exports are retried rather than treated as complete merely
  because `_index.json` exists.
- Menu input required explicitly selecting keyboard navigation, not longer key
  holds. The game's `WindowObject.as` otherwise sends Return to mouse hover.
- The all-mod gate caught a date-dependent save selector bug: offset 8 holds an
  eight-byte Unix-millisecond timestamp, not a float plus game-build number.
  Float ordering of the low word reverses when its sign bit is set, causing an
  old rotation to be patched while the game loads a newer one. Full unsigned
  64-bit selection also handles low-word rollover; no mod-set check was relaxed.

Run the host regressions without Steam or the game:

```sh
python3 -m unittest gamelab.test_linux tools.test_setup_gamelab_linux tools.test_export_datatables tools.test_linux_launcher tools.test_wine_queries tools.test_hps -v
```
