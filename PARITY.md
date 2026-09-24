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
     (`py -3 -X utf8 test_v2.py`, `py -3 -X utf8 test_app.py`).
   - The release zip is one package with both installers, built from one commit.
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
| Ship to the archive + PC verification sweep | ✓ over SMB | ✓ local E: | engine (+ `pc/sweep.ps1`) |
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
| `ASTRO_SHIP_LOG` | this machine's ship log | `shipped.jsonl` | `shipped-pc.jsonl` |
| `ASIAIR_VOLUME` / `SEESTAR_VOLUME` | pin a camera path by hand | auto | auto (drive letters) |
| `SEESTAR_IMPORT_SUB_JPEGS` | import per-sub previews | `false` | `false` |

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
- **Archive ship logs:** the Mac appends to `_verify\shipped.jsonl`, the PC
  to `_verify\shipped-pc.jsonl`. The sweep reads every `shipped*.jsonl`
  (shared reads, UTF-8, skipping malformed rows) and is the only writer of
  `verified.jsonl`, `problems.jsonl` and `status.json`.
- **Shipping into one archive:** only one computer ships at a time. A
  lock on the archive (`_verify\ship.lock`, stale after 6 hours) makes the
  other wait until its next run. Each machine also names its partial copies
  after itself (`….mac.partial` / `….pc.partial`), and the two schedules are
  half an hour apart.
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

## Release checklist

1. Bump `VERSION` in `astro-import.py`, and add a CHANGELOG entry with a
   "Mac / Windows" line.
2. Update this page if a capability, setting or platform detail changed.
3. Run `test_v2.py` and `test_app.py` on the build machine.
4. On the PC, run `selftest.py` and both suites.
5. Build one zip from one commit, containing both installers.
6. Push to GitHub.
