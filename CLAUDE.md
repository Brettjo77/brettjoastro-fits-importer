# BrettjoAstro FITS Importer: working rules

A backup-first importer for Seestar and ASIAir cameras, on macOS and Windows 11.
It copies frames with byte-for-byte verification, records every file in a
ledger, and only then offers to clear the camera. The owner, Brett, is an
astrophotographer, not a developer. Explain changes in plain words, give
commands he can paste, and go one step at a time.

## The project map

This repo is one part of Brett's astrophotography pipeline. The shared map of every project, and of the links between them (receipts, the archive layout, night dates, the app fork), is a Claude Doc:

https://claude.ai/code/artifact/53e55b0a-4c92-4427-a3f4-ada548ad5960

- Always refer to it (Brett, 3 Oct 2026). Read it with the Claude Docs tools at the start of every session, and check it whenever a task touches another project or anything another tool reads.
- Before you finish, update it if the work changed a project's state, a link between projects or an open question: small, targeted edits, and a row at the top of its Change log.
- If the Claude Docs tools aren't available, tell Brett what the map needs changing.

## Layout

- `astro-import.py`: the engine (scan, import, ledger, SAFE clear, discard, ship, report, dashboard). `VERSION` lives here.
- `astro-app.py`: the control panel at http://127.0.0.1:8765. It uses a per-launch token and exact origin checks, and accepts JSON only.
- Watchers: `astro-watch.sh` (macOS, launchd `WatchPaths /Volumes`) and `astro-watch.py` (Windows, Startup-folder shortcut, polls drive letters).
- Installers:
  - Mac: `install-scripts.sh`, launched by `Install BrettjoAstro FITS Importer.command`.
  - Windows: `install-windows.ps1`, launched by `Install on Windows.cmd`.
  - Plus the `BrettjoAstro FITS Importer.app` wrapper and the LaunchAgent plists.
- `selftest.py`: the install check on both platforms. `INSTALLED` lists what each installer puts beside it.
- `app-takeover.json` in the state folder (1.5.3): the owner record. Only the desktop app (FITs Importer App, a separate repo built on this one) writes it, while it's in charge, and only a record naming the app by an absolute `appPath` counts. While it's there, the web watchers, Restart buttons and installers stand aside. `--app-owner` gives every script the same answer, and a web install that finds the app gone renames the record aside, never deletes it.
- For the app, 1.5.3 added `NOTIFY_FN` (engine), `make_server`/`serve`, `STATUS_CMD` and `POST /api/quit` (panel), and made `astro-watch.py` importable (`poll_once`, on the Mac too). The app relies on them: keep them working and tested.
- 1.5.4: the panel binds without `socket.getfqdn` (U12: it stalled the packaged app's start for 35 s). When astropy won't load, `get_fits()` raises `FitsUnavailable`, a `SystemExit` so the `except Exception` guards around header reads can't swallow it; it says why once per process (`.why`, the line under numpy's advice page) and how to fix it (`.how`: a PowerShell `& "…\python.exe"` line on Windows; reinstall the app when `sys.frozen`). `run_import` and `run_seestar_import` call it before any copy, and `selftest.py` uses it too. The panel's `_run` catches it, and any other `SystemExit`, and fails only that job. Tests read the version from the engine's `VERSION`, so a release changes only that line.
- 1.7.0 (decision D7, phase 0 of the Sync View plan): the ship creates each archive file under its final name with exclusive create, reads it back, and never deletes, renames or overwrites on the archive. Each computer writes only in its own `_verify` folder: the Mac `_verify/mac/` (`shipped.jsonl` with started / shipped / failed / not-created rows, and `requests/`), the PC `_verify/pc/`. The ship lock is `_verify/lock/ship.lock`, renewed every 60 s and breakable after 10 min; a 1.6 `_verify/ship.lock` still counts for 6 h.
- The PC's side is the engine, in Python (`pc/sweep.ps1` is retired): `--sweep` (unbuffered re-reads into `_verify/pc/verified.jsonl`, of which it is the only writer; sets aside "started, never shipped" copies), `--inventory`, `--hash`, `--pc-tick` (every 5 min: heartbeat and the Mac's requests) and `--pc-nightly`. The Mac has `--request` and `--check-share-rights`. `pc/set-archive-rights.ps1` sets the share's rights (dry run unless `-Apply`). Platform pieces: `hash_file_unbuffered`, `background_io`, `file_created_at`, `owner_trusted`.
- `PARITY.md`: the Mac/Windows contract. Read it before touching anything platform-related.
- `HOW-IT-WORKS.md`, `INSTALL.md`, `PC-SYNC.md`, `README.md`, `CHANGELOG.md`: the user docs. Keep them true.

## Rules that are never broken

1. **Nothing is ever deleted from the ASIAir.** It is the backup of record.
2. **A camera file is deleted only when the ledger proves a verified copy of those bytes, from that camera.** Brett must also have confirmed, with default No. The SAFE gate (`_seestar_unproven_files`) re-checks at the moment of deletion and deletes only the files it checked.
3. **Discard** (deleting frames that were never backed up) needs the typed word DISCARD. The files are recorded in the ledger before they are deleted.
4. **Ledger rows are never removed,** only marked. Every command that writes the ledger takes the lock.
5. **Nothing on the archive is ever overwritten.** The archive's naming and Day numbering win, and Day = night (noon-to-noon).
6. **Each computer keeps its own ledger. No file is ever written by two machines.** This covers per-machine ship logs, partial files and receipts, and there's a lock on the archive while shipping.
7. **Brett deletes files on his own disks himself.** At most, suggest `mv … ~/.Trash/`. One named exception (agreed 3 Oct 2026, decision 18): the PC's sweep moves a copy that a ship started and never finished into `_Quarantine\ship-incomplete\`, and only those. `--move-old-partials` moves 1.6 partials only when Brett runs it. Nothing is deleted either way.
8. **Never handle credentials.** Brett signs in to GitHub and everything else himself. No tokens in files, commits or command lines.
9. **Ask Brett before any push to GitHub, and before anything irreversible.**

## Mac and Windows stay in step

- One codebase and one `VERSION`, released as one zip for both platforms.
- Platform differences live only in the platform layer near the top of `astro-import.py` (`_drive_roots`, `refresh_camera_volumes`, `pid_alive`, `notify`, `eject_volume`, `open_path`, `_platform_bootstrap` and so on), plus each platform's installer, watcher and restart button.
- A change isn't done until it works on both. Update `PARITY.md` in the same commit when a capability, setting or platform detail changes. A capability on only one platform is listed there with its reason.
- On Windows, never call `os.kill(pid, 0)`: it terminates the process. Use `pid_alive()`.

## Testing

- Mac: `/usr/local/bin/python3 test_v2.py` (engine, 483 checks) and `/usr/local/bin/python3 test_app.py` (panel, 139 checks). Use python.org's Python, which has astropy; Apple's `python3` may not.
- **Tests run in test mode, always** (1.5.2). Build every environment a test starts with `test_env_helper.make_env(root)`. Call `teh.isolate_runner()` at the top of a test file, before it loads the engine in-process. With `ASTRO_TEST_ROOT` set:
  - the engine, panel, watcher and self-test refuse any path outside the root, and never use port 8765;
  - dialogs, notifications, ejects, mounts and "open" are written to `<root>/os-calls.jsonl` instead of happening. Check them with `teh.os_calls()`.

  The 1.5.1 suites, run on the real Mac on 25 Sep 2026, shipped fake frames into the real archive before this existed. Never run a suite from before 1.5.2 on a real Mac or PC.
- Tests never run the installers, the `.command`/`.cmd` files or `astro-watch.sh` whole. Chain U1 runs only each script's marked `app-owner check` block, copied into the test root, with a fake engine and stub commands. Tests never mount disks or create drive letters: simulate cameras with folders inside the root (`*_VOLUME`, `ASTRO_DRIVE_ROOTS`). Brett's real watcher and panel would otherwise pick them up.
- On the Mac, while changing the engine, it's worth also running the suites under `sandbox-exec` with a profile that refuses writes outside the temp folders and the repo, and refuses `osascript`/`open`/`diskutil`. Then a new leak fails loudly instead of touching real data.
- Windows: `py -3 -X utf8 selftest.py`, then `py -3 -X utf8 test_v2.py` and `py -3 -X utf8 test_app.py`. The engine total is a little lower there than on the Mac: the checks that need bash or shell scripts print SKIP on Windows, and the two Windows-only owner checks run instead.
- Chain W1 in `test_v2.py` simulates the Windows drive-letter layer on any OS (`ASTRO_DRIVE_ROOTS`).
- Chains D7 and PC simulate the archive share's D7 rights with `teh.no_delete_env(root, archive)`: a `sitecustomize` on `PYTHONPATH` refuses deletes, renames and writes outside the allow-list and records each refusal in `<root>/denied.jsonl` (`teh.denied`). The D7 checks run as the Mac on every OS (`ASTRO_SHIP_FOLDER=mac`); the PC's jobs run in test mode on any OS.
- Every fix gets a test that fails without the fix. Both suites must be fully green before anything is delivered.
- Test an installer or the self-test from an *installed* layout, not only from the source folder. 1.5.1 fixed a bug that slipped through this way.
- `.ps1` files are UTF-8 with a BOM, and CRLF. Parse-check them with `pwsh` if it's installed; otherwise check on the PC.
- Commands in the docs that Brett types on Windows use PowerShell syntax (`$env:LOCALAPPDATA`, and `& "path\python.exe"` for a quoted exe).

## Releasing

1. Bump `VERSION`. Add a CHANGELOG entry with a "Mac / Windows" line. Update the check counts in README, CHANGELOG and the Testing section above, and update PARITY.md if needed.
2. Both suites green. Then commit.
3. Build the zip from the commit: `git archive --prefix=importer-X.Y.Z/ HEAD`, remove `.gitignore`, keep the executable bits on `.command`, `.sh`, `.py` and the app's `launcher`, then zip.
4. Push only when Brett says yes.
