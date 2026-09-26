# BrettjoAstro FITS Importer: working rules

A backup-first importer for Seestar and ASIAir cameras, on macOS and Windows 11.
It copies frames with byte-for-byte verification, records every file in a
ledger, and only then offers to clear the camera. The owner, Brett, is an
astrophotographer, not a developer. Explain changes in plain words, give
commands he can paste, and go one step at a time.

## Layout

- `astro-import.py`: the engine (scan, import, ledger, SAFE clear, discard, ship, report, dashboard). `VERSION` lives here.
- `astro-app.py`: the control panel at http://127.0.0.1:8765. It uses a per-launch token and exact origin checks, and accepts JSON only.
- Watchers: `astro-watch.sh` (macOS, launchd `WatchPaths /Volumes`) and `astro-watch.py` (Windows, Startup-folder shortcut, polls drive letters).
- Installers:
  - Mac: `install-scripts.sh`, launched by `Install BrettjoAstro FITS Importer.command`.
  - Windows: `install-windows.ps1`, launched by `Install on Windows.cmd`.
  - Plus the `BrettjoAstro FITS Importer.app` wrapper and the LaunchAgent plists.
- `selftest.py`: the install check on both platforms. `INSTALLED` lists what each installer puts beside it.
- `pc/sweep.ps1`: runs on the archive PC. It re-hashes shipped frames and is the only writer of `_verify/verified.jsonl`.
- `PARITY.md`: the Mac/Windows contract. Read it before touching anything platform-related.
- `HOW-IT-WORKS.md`, `INSTALL.md`, `PC-SYNC.md`, `README.md`, `CHANGELOG.md`: the user docs. Keep them true.

## Rules that are never broken

1. **Nothing is ever deleted from the ASIAir.** It is the backup of record.
2. **A camera file is deleted only when the ledger proves a verified copy of those bytes, from that camera.** Brett must also have confirmed, with default No. The SAFE gate (`_seestar_unproven_files`) re-checks at the moment of deletion and deletes only the files it checked.
3. **Discard** (deleting frames that were never backed up) needs the typed word DISCARD. The files are recorded in the ledger before they are deleted.
4. **Ledger rows are never removed,** only marked. Every command that writes the ledger takes the lock.
5. **Nothing on the archive is ever overwritten.** The archive's naming and Day numbering win, and Day = night (noon-to-noon).
6. **Each computer keeps its own ledger. No file is ever written by two machines.** This covers per-machine ship logs, partial files and receipts, and there's a lock on the archive while shipping.
7. **Brett deletes files on his own disks himself.** At most, suggest `mv … ~/.Trash/`.
8. **Never handle credentials.** Brett signs in to GitHub and everything else himself. No tokens in files, commits or command lines.
9. **Ask Brett before any push to GitHub, and before anything irreversible.**

## Mac and Windows stay in step

- One codebase and one `VERSION`, released as one zip for both platforms.
- Platform differences live only in the platform layer near the top of `astro-import.py` (`_drive_roots`, `refresh_camera_volumes`, `pid_alive`, `notify`, `eject_volume`, `open_path`, `_platform_bootstrap` and so on), plus each platform's installer, watcher and restart button.
- A change isn't done until it works on both. Update `PARITY.md` in the same commit when a capability, setting or platform detail changes. A capability on only one platform is listed there with its reason.
- On Windows, never call `os.kill(pid, 0)`: it terminates the process. Use `pid_alive()`.

## Testing

- Mac: `/usr/local/bin/python3 test_v2.py` (engine, 375 checks) and `/usr/local/bin/python3 test_app.py` (panel, 120 checks). Use python.org's Python, which has astropy; Apple's `python3` may not.
- **Tests run in test mode, always** (1.5.2). Build every environment a test starts with `test_env_helper.make_env(root)`. Call `teh.isolate_runner()` at the top of a test file, before it loads the engine in-process. With `ASTRO_TEST_ROOT` set:
  - the engine, panel, watcher and self-test refuse any path outside the root, and never use port 8765;
  - dialogs, notifications, ejects, mounts and "open" are written to `<root>/os-calls.jsonl` instead of happening. Check them with `teh.os_calls()`.

  The 1.5.1 suites, run on the real Mac on 25 Sep 2026, shipped fake frames into the real archive before this existed.
- Tests never run the installers, the `.command`/`.cmd` files or `astro-watch.sh`. They never mount disks or create drive letters: simulate cameras with folders inside the root (`*_VOLUME`, `ASTRO_DRIVE_ROOTS`). Brett's real watcher and panel would otherwise pick them up.
- On the Mac, while changing the engine, it's worth also running the suites under `sandbox-exec` with a profile that refuses writes outside the temp folders and the repo, and refuses `osascript`/`open`/`diskutil`. Then a new leak fails loudly instead of touching real data.
- Windows: `py -3 -X utf8 selftest.py`, then `py -3 -X utf8 test_v2.py` and `py -3 -X utf8 test_app.py`.
- Chain W1 in `test_v2.py` simulates the Windows drive-letter layer on any OS (`ASTRO_DRIVE_ROOTS`).
- Every fix gets a test that fails without the fix. Both suites must be fully green before anything is delivered.
- Test an installer or the self-test from an *installed* layout, not only from the source folder. 1.5.1 fixed a bug that slipped through this way.
- `.ps1` files are UTF-8 with a BOM, and CRLF. Parse-check them with `pwsh` if it's installed; otherwise check on the PC.
- Commands in the docs that Brett types on Windows use PowerShell syntax (`$env:LOCALAPPDATA`, and `& "path\python.exe"` for a quoted exe).

## Releasing

1. Bump `VERSION`. Add a CHANGELOG entry with a "Mac / Windows" line. Update the check counts in README and CHANGELOG, and update PARITY.md if needed.
2. Both suites green. Then commit.
3. Build the zip from the commit: `git archive --prefix=importer-X.Y.Z/ HEAD`, remove `.gitignore`, keep the executable bits on `.command`, `.sh`, `.py` and the app's `launcher`, then zip.
4. Push only when Brett says yes.
