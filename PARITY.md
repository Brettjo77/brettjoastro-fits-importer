# Mac and Windows: one importer, kept in step

From 1.5.0 the FITS Importer runs on **macOS** and **Windows 11**. Both are
built from **one codebase**, carry **one version number**, and must have
**the same capabilities**. This page is the contract that keeps them that
way. Every release updates it.

## The rules

1. **One engine, one panel, one version.** `astro-import.py` and
   `astro-app.py` are the same files on both platforms. `VERSION` in the
   engine is the only version number; the panel, `--version`, the self-test
   and the changelog all read or quote it.
2. **Platform differences live in one place.** They are confined to the
   *platform layer* at the top of the engine, plus each platform's installer,
   watcher and restart button. The layer covers finding camera drives,
   checking whether a process is running, notifications, ejecting,
   opening files, the Terminal-fallback dialogs and the default folders.
   Everything else (the SAFE rule, the ledger, discard, ship, the panel) is
   the same code.
3. **A feature isn't done until it works on both.** Any change that touches
   the platform layer, the installers or anything in the table below updates
   this page in the same commit. A capability that one platform genuinely
   can't have is listed under "Differences by design", with the reason.
4. **Both test runs pass before a release.**
   - `test_v2.py` and `test_app.py` run on the build machine. Chain W1
     simulates the Windows drive-letter layer, so it runs everywhere.
   - On the Windows PC: `selftest.py`, then the same two suites
     (`py -3 -X utf8 test_v2.py`, `py -3 -X utf8 test_app.py`). The engine
     total is a little lower there: a few Mac-only checks print SKIP, and two
     Windows-only ones run instead.
   - The release zip is one package with both installers, built from one commit.
   - Every test runs in test mode (`test_env_helper.make_env`), so it can't
     touch the real archive, state, cameras, installs or the panel on 8765.
     On Windows the proof that nothing ran is the `os-calls.jsonl` records;
     the Mac additionally has the `EXECUTED` stand-ins and `sandbox-exec`.
     Suites from before 1.5.2 have no test mode: never run them on a real
     Mac or PC.
5. **Each computer keeps its own ledger.** Ledgers are never shared, and no
   file is ever written by both machines (see "Per-machine data").

## Capabilities

| Capability | macOS | Windows 11 | Shared code |
|---|---|---|---|
| Import ASIAir (lights + calibration library) | ✓ | ✓ | engine |
| Import Seestar S30 / S30 Pro / S50 / S50 Pro | ✓ | ✓ | engine |
| Byte-for-byte verified copies, ledger, receipts | ✓ | ✓ | engine |
| SAFE clear (checked again at deletion) | ✓ | ✓ | engine |
| Discard (typed DISCARD, recorded first) | ✓ | ✓ | engine |
| JPEG preview rules, one stack per session, Day per night | ✓ | ✓ | engine |
| Ship to the archive: each frame created under its final name only if that name is free, read back, never deleted, renamed or written over there; "started" and "shipped" rows in the machine's own log (1.7.0, D7) | ✓ over SMB | ✓ local E: | engine |
| Calibration frames ship with their lights, into the Day's `calibration\{biases,darks,flats}`; Collect Lights copies (`lights/lights`, prefixed names) are found by name, size and ledger hash (1.7.0) | ✓ | ✓ | engine |
| A panel import ships straight away when the share is up (1.7.0) | ✓ (a mounted share; never asks Finder to connect) | ✓ local E: | panel + engine |
| "Not reachable" says why (not mounted, no camera folders, `_verify` folder not writable) | ✓ | ✓ ("the folder isn't there") | engine |
| The archive PC's own jobs: `--sweep` (re-reads shipped frames unbuffered, sets aside copies a ship never finished), `--inventory` and `--hash` of the archive, `--pc-tick`, `--pc-nightly` (1.7.0) | — asks with `--request` (see below) | ✓ Scheduled Tasks "Astro archive sweep" (logon, 03:30) and "Astro sync requests" (every 5 min) | engine + installer |
| Inventory and hash cache of this computer's own frame folders (`--inventory --root`, `--hash --root`) | ✓ | ✓ | engine |
| Short name and label for the computer (`ASTRO_MACHINE_ID`, `ASTRO_MACHINE_LABEL`), checked before anything is written | ✓ | ✓ | engine |
| The share's rights for D7: tried with `--check-share-rights`, set with `pc\set-archive-rights.ps1` | ✓ tries them | ✓ sets them | engine + PC script |
| Control panel (localhost:8765, token, same UI) | ✓ | ✓ | panel |
| Report, dashboard, mirror | ✓ | ✓ | engine |
| Camera detection | `/Volumes/…` | drive letters, by what's on them (`Autorun\` / `MyWorks\`) | platform layer |
| Auto-open panel when a camera is plugged in | launchd + `astro-watch.sh` | Startup-folder `astro-watch.py` | platform |
| Notifications | Notification Centre | Windows toast | platform layer |
| Eject from the panel / CLI | `diskutil` | Shell "Eject" | platform layer |
| Twice-daily ship | LaunchAgent, 09:00 / 21:00 | Scheduled Task, 09:30 / 21:30 | installers |
| Restart button on the Desktop | `.command` | `.cmd` | installers |
| Install / update | `install-scripts.sh` | `Install on Windows.cmd` / `install-windows.ps1` | installers |
| Install check (`--toast` tries a notification) | `selftest.py` | `selftest.py` | self-test |
| Move settings between computers | `--export-settings` / `--import-settings` | same | engine |
| Terminal fallback (`--pick`, naming) | AppleScript dialogs | numbered list / prompt in the console | platform layer |
| Status line ("Everything is safe" / "N frames only on the Mac" or "…on this PC", with a tooltip; `--status [--json]`, `GET /api/status`, and the `statusSummary` field of `/api/state`). Worked out by `--status --json` in a short-lived child process, only when `ledger.json` changes (`STATUS_CMD` lets the app use its own command; a frozen app works it out in-process) | ✓ | ✓ | engine + panel |
| Space on this computer (dashboard section and `--space`): read-only; "safe to delete" only for frames whose archive copy the PC has re-hashed; never deletes | ✓ Finder | ✓ File Explorer | engine |
| Astro Desk, the Archive tab (1.6.0): read-only list of what is still to process, a target's nights, masters and pictures; opens folders and image files inside the archive only (never programs or shortcuts, token required); Start Siril here (`siril -d <folder>`, detached) | ✓ when the share is mounted; Finder, `open` | ✓ local E:; File Explorer, `os.startfile` | engine + panel |
| Quit the panel from another program (`POST /api/quit`: token, JSON and origin rules; 409 `busy` while an operation runs or a question card is up) | ✓ | ✓ | panel |
| Stands aside while the desktop app is in charge (`app-takeover.json`, with an absolute `appPath`; `--app-owner`) | ✓ watcher, Restart, installer, app wrapper | ✓ watcher, Restart, installer | engine + installers |
| Test mode (`ASTRO_TEST_ROOT`): everything stays inside one folder, and dialogs, notifications, ejects, mounts and "open" are logged, not done | ✓ | ✓ | engine, panel, watcher, self-test |
| Refuses a ledger written by a newer importer: changes nothing, before any copy, clear, discard, ship or restore | ✓ | ✓ | engine |
| astropy that won't load: the job stops (`FitsUnavailable`, exit 1 on the command line) with the line that says why (never numpy's page of advice) and the install or repair command for the running Python, said once. An import checks it before it copies anything (ASIAir lights and calibration frames, Seestar). In the panel only that job fails, with a banner, and the panel stays up; the install check gives the same reason and command. In the desktop app (frozen) it says to reinstall the app, and the banner to restart the app (1.5.4) | ✓ `python3 -m pip …` | ✓ a PowerShell line for Terminal, `& "…\python.exe" -m pip install --user …` (python.exe, never the panel's pythonw.exe) | engine + panel + self-test |
| The panel binds without a reverse DNS lookup (no `socket.getfqdn`), keeping one panel per port (1.5.4) | ✓ no `SO_REUSEPORT` | ✓ `SO_EXCLUSIVEADDRUSE`, no `SO_REUSEADDR` | panel |

## Settings (config.json)

The same keys on both, in `config.json` next to the ledger:

- **macOS:** `~/Library/Application Support/Astro Import/`
- **Windows:** `%LOCALAPPDATA%\Astro Import\`

| Key | Meaning | macOS default | Windows default |
|---|---|---|---|
| `ASIAIR_DEST` | ASIAir frames | `~/Documents/Astro/ZWO ASI AIR` | `%USERPROFILE%\Documents\Astro\ZWO ASI AIR` (C: workbench) |
| `ASIAIR_CAL_LIBRARY` | calibration library | `~/Documents/Astro/ASIAir Calibration Library` | same under `%USERPROFILE%\Documents\Astro` |
| `SEESTAR_DEST_S30` / `_S30_ORIG` / `_S50` / `_S50PRO` | Seestar trees | `~/Documents/Astro/Seestar …` | same under `%USERPROFILE%\Documents\Astro` |
| `ASIAIR_STATE` | ledger folder | `~/Library/Application Support/Astro Import` | `%LOCALAPPDATA%\Astro Import` |
| `ASIAIR_MIRROR` | published copy of the ledger | `~/Documents/Astro/Import Status` | same (**must differ** from the other machine's) |
| `ASIAIR_RECEIPTS` | AstroLog receipts | `~/Documents/Astro/astrolog-receipts` | same; PC receipts are named `…-pc-…` |
| `ASIAIR_EQUIPMENT` | scope table | `~/Documents/Astro/equipment.json` | same |
| `ASTRO_ARCHIVE_MOUNT` | the archive | `/Volumes/AstroImageData` | `E:\Astro Image Data` |
| `ASTRO_ARCHIVE_URL` | share to mount on demand | empty (set for SMB) | not used (the archive is local) |
| `ASTRO_ARCHIVE_LABEL` | how the archive is named in messages | `E:\Astro Image Data` | same |
| `ASTRO_SHIP_LOG` | this machine's ship log, in its folder under `_verify` | `shipped.jsonl` | `shipped-pc.jsonl` |
| `ASTRO_SHIP_FOLDER` | that folder (1.7.0) | `mac` | `pc` |
| `ASTRO_MACHINE_ID` | the computer's short name (a to z, 0 to 9 and -, at most 32), in log rows and request names | `mac` | `pc` |
| `ASTRO_MACHINE_LABEL` | the name people read | `Mac` | `PC` |
| `ASTRO_ARCHIVE_MIN_FREE_GB` | a ship that would leave less free on the archive sends nothing | `10` | `10` |
| `ASTRO_PC_HASH_MINUTES` | the nightly hash stops at a file after this long | not used | `360` |
| `ASIAIR_VOLUME` / `SEESTAR_VOLUME` | pin a camera path by hand | auto | auto (drive letters) |
| `SEESTAR_IMPORT_SUB_JPEGS` | import per-sub previews | `false` | `false` |
| `ASTRO_SIRIL_EXE` | Siril, for "Start Siril here" | `/Applications/Siril.app/Contents/MacOS/Siril` | `C:\Program Files\Siril\bin\siril.exe` |
| `ASTRO_OBSERVATORY_DATASET` | the Observatory's dataset (states, hours) | `~/Library/Application Support/Astro Import/observatory-dataset.json` | `<archive drive>\Astro Config Data\Observatory\dataset.json` |

Paths never cross between machines. `--export-settings` / `--import-settings`
carry the portable part instead: custom target names, the never-import list,
the scope table, and the non-path keys.

## Per-machine data (never shared)

- **Ledger, history, locks, identity:** in each machine's state folder.
  `machine.json` holds a stable id for that computer.
- **Mirror:** each machine publishes only to a mirror folder it owns
  (`mirror-owner.json`). It refuses to publish into another computer's. It
  refuses to restore another computer's ledger as its own, unless you confirm
  that it is the same computer, rebuilt.
- **Archive ship logs (1.7.0):** each machine writes only in its own folder
  under `_verify`: the Mac `_verify\mac\shipped.jsonl` (and its requests in
  `_verify\mac\requests`), the PC `_verify\pc\shipped-pc.jsonl`. The old
  logs in `_verify` are history: read, never written again.
- **What the PC writes:** everything in `_verify\pc` (the share's user may
  only read there): `verified.jsonl`, `problems.jsonl`, `status.json`,
  `quarantine.jsonl`, the sweep logs, the inventory generations and
  `inventory-E.status.json`, `pc-heartbeat.json` and `responses\`. The
  PC's sweep is the only writer of `verified.jsonl`. It still reads the old
  `_verify\verified.jsonl` and `problems.jsonl`, for one release.
- **Shipping into one archive:** only one computer ships at a time. The lock
  is `_verify\lock\ship.lock`: the holder renews it every minute, and
  another computer may break it after ten minutes without renewal, noting
  that in its own log. A 1.6 lock (`_verify\ship.lock`) still stops a ship
  for 6 hours. There are no partial copies any more: a frame is created
  under its final name, and an unfinished one is set aside by the PC. The
  two schedules are half an hour apart.
- **Hash cache and inventory of a computer's own frames:** in its own state
  folder (`hash-cache.jsonl`, `inventory-<short name>.jsonl`).
- **Receipts:** the PC's carry `-pc` in the name, so one receipts folder can
  take both machines' receipts without a clash.

## Differences by design

- **Finder "done" tags** on imported ASIAir folders are macOS-only. NTFS has
  no Finder labels; the ledger is the real record on both.
- **The Windows watcher's notification** names the camera but not the new
  frame counts. The panel shows the counts a second later.
- **macOS permissions (TCC, Full Disk Access, the app wrapper)** have no
  Windows equivalent, and Windows needs none of it.
- **The Terminal fallback dialogs** are AppleScript on the Mac and plain
  console prompts on Windows. The panel is the main route on both.
- **The archive PC's jobs** (the sweep, the archive's inventory and hashing,
  the heartbeat, answering requests) run only on the PC: only its own reads
  of its own disk count as proof that a frame is safe (spec P1). The Mac asks
  for a sweep or an inventory with `--request`, and never reads the archive
  to prove anything.
- **Unbuffered reads and background disk priority** are Windows-only, for
  those jobs. Elsewhere a read is ordinary and is recorded as "buffered".
- **The owner check on the PC's own files** is Windows-only: file owners
  don't travel over SMB (decision 10).
- **A sweep request after a ship leaves an unfinished copy** is the Mac's:
  the PC's own unfinished copies wait for its next sweep (logon, 03:30).
- **`--check-share-rights`** runs on the Mac, because it tests the share
  from the Mac's side; the PC sets the rights (`pc\set-archive-rights.ps1`).
- **Connecting the share:** a Terminal import asks Finder to connect it
  first; a panel import ships only if it is already connected. On the PC
  the archive is a local disk.

## Release checklist

1. Bump `VERSION` in `astro-import.py`, and add a CHANGELOG entry with a
   "Mac / Windows" line.
2. Update this page if a capability, setting or platform detail changed.
3. Run `test_v2.py` and `test_app.py` on the build machine.
4. On the PC, run `selftest.py` and both suites.
5. Build one zip from one commit, containing both installers.
6. Push to GitHub, once Brett says yes.
