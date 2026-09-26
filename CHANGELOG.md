# Changelog

## 1.5.3 — 2026-09-26 — ready for the desktop app, and a status line

The web version carries on as it is. This release adds what the coming
desktop app (FITs Importer App, a separate repo) needs from the shared
engine and panel. The web version gets two things from it: a status line,
and a newer-ledger guard.

- **Status line.** The panel's header now says **"Everything is safe"**
  (green) or **"N frames only on the Mac"** (amber; "only on this PC" on
  Windows). It counts frames already cleared from a camera whose only
  verified copy is on this computer, the same count the ship summary gives.
  - Hover over a count to see what it means: "Cleared from the camera; the
    only verified copy is on this Mac until the PC's sweep checks it"
    ("this PC" on Windows).
  - It says "Nothing imported yet" on a new machine, and "Status unknown:
    the ledger can't be read" (amber) if the ledger can't be read, or if
    working the line out fails for any reason. It never says "safe" when
    it can't tell, and never keeps showing an earlier line.
  - It is light on memory. The panel never holds the ledger (about 100 MB)
    itself: the line is worked out by a short-lived `--status --json`
    process, and only when `ledger.json` changes. With a 116 MB ledger the
    idle panel stays at about 59 MB, as in 1.5.2.
  - Also available as `--status` (or `--status --json`),
    `GET /api/status`, and the `statusSummary` field of `/api/state`.
- **Newer ledger, older importer.** An older importer now refuses to work
  on a ledger written by a newer one, and changes nothing, instead of
  saving over it. This matters once the app and the web version share a
  computer. The refusal comes before anything is copied, tagged or deleted,
  on every path: an import, a SAFE clear, a discard, a ship, a restore from
  the mirror (a first run, or `--restore-ledger`), recovery from
  `ledger.json.bak`, and a ledger replaced while the importer waited for
  its lock.
- **Taking turns with the app.** The app will leave a note in the state
  folder while it is in charge (`app-takeover.json`). While that note is
  there:
  - the web watchers and Restart buttons stand aside;
  - the installers update files only: no watcher, no panel, no browser;
  - the install check says who is in charge.

  If the app was thrown away without handing back, the next web install
  notices, puts the web version back and keeps the note (renamed, never
  deleted). `--app-owner` answers the question for scripts. Only a note
  naming the app by a full path counts, so every script gets the same
  answer wherever it runs from. While the app is in charge, the
  installers end with one line: open the FITs Importer App. On Windows
  the Restart button's window then stays open for a few seconds, so the
  message can be read.
- **Stopping the panel stops only the web version's own panel.** The
  installers' and Restart buttons' stop commands now match only the web
  version's own files, never another program's Python.
- **Clearer "busy" messages.** A command that finds the importer busy now
  says what is busy, in the same words on the command line and on the
  panel: "Another import is already running", "The twice-daily ship to
  the PC is running right now", or "The panel is busy right now".
- **For the app:**
  - a notification hook;
  - the Windows watcher, now importable and able to run on the Mac too,
    with the 10-minute flap guard inside `poll_once` (a camera re-plugged
    within it gives a `rearrived` event, never a second arrival);
  - `POST /api/quit` (token required, refused while busy);
  - a proper way to start the panel from another program
    (`make_server` / `serve`; `make_server(0)` picks a free port);
  - `STATUS_CMD`, for the app's own status-line command;
  - a packaged app is never relaunched as a script.

**Mac / Windows:** the same on both. On Windows the installer's changes
(Startup shortcut, Restart button, panel start) follow the same three
cases as the Mac's. PowerShell lines changed: to be parse-checked on the PC.
The Windows installer's and Restart button's owner checks have tests that
run only on Windows (through `powershell.exe` and `cmd.exe`); on the Mac
they print SKIP.

495 end-to-end checks (375 engine + 120 panel), all green on the Mac.

## 1.5.2 — 2026-09-25 — the tests can never touch real data

Normal use is unchanged apart from the three small points below. This
release makes the test suites safe to run on a real Mac or PC.

- **Why:** the 1.5.1 suites, run for the first time on the real Mac, reached
  real things. They shipped 13 fake frames into the real archive (removed
  since, nothing overwritten). They moved the old iCloud `ASIAir Import` note
  folder. They showed real dialogs, notifications and Finder labels, and they
  asked the real panel on port 8765 whether it was running. On the PC they
  would have shipped into `E:\Astro Image Data` on every run, and sent
  Explorer's "Eject" to drive C:.
- **Test mode.** Setting `ASTRO_TEST_ROOT` to a folder marks a test run.
  The engine, panel, watcher and install check then:
  - keep every default inside that folder, including a pretend home;
  - stop before reading or writing anything if a setting points outside it;
  - never look at the real `/Volumes` or real drive letters;
  - never use port 8765;
  - write dialogs, notifications, Finder labels, ejects, share mounts,
    "open", PowerShell and the browser to a log instead of doing them.
  Every destructive step that follows a path from the ledger or the camera
  (ship, merge, renumber, discard, SAFE clear, tidy, previews, receipts)
  checks that path as well, including where a linked folder really leads.
- **One test environment.** Every test run starts from a short list of basic
  settings and a new temporary folder. Nothing else comes from the real
  shell or computer.
- **The one-time move of the pre-July folders** no longer moves into a folder
  that an environment variable points at. A test's temporary mirror did
  exactly that. A mirror chosen in `config.json` still counts.
- **The panel and the install check** read the panel's port from
  `ASTRO_PANEL_PORT` (the panel when `--port` isn't given), as the Windows
  watcher already did. A value that isn't a number now means the usual 8765
  everywhere, where it used to stop the watcher.
- **`/api/ping`** now names which panel is answering, so a test only talks
  to its own panel.
- **Test fixes:**
  - W1's install check failed on every Mac, because it filled its pretend
    install with the Windows file list.
  - Four tests fed a stray "y" into the eject question.
- **New chain I1:** 60 checks that the protections work.

**Mac / Windows:** the same test mode on both. It replaces `osascript`,
`diskutil` and `open` on the Mac, and PowerShell, Shell "Eject" and
`os.startfile` on Windows. Tests never mount disks or create drive letters.

421 end-to-end checks (328 engine + 93 panel), all green on the Mac.

## 1.5.1 — 2026-09-24 — install check fix

- **The Mac's install check reported a false FAIL** for `astro-watch.py`.
  That file is the Windows watcher and the Mac installer rightly doesn't
  install it; the Mac's watcher is `astro-watch.sh`. `selftest.py` now checks
  for exactly what each platform's installer installs.
- The check names this machine's ship log with the right separator on the
  Mac (it printed `_verify\shipped.jsonl`).
- New W1 checks compare the install check's file lists with
  `install-scripts.sh` and `install-windows.ps1`, and run the check from an
  installed folder rather than the source folder. That is how this slipped
  through: the check had only ever been run from the source folder.

**Mac / Windows:** same version on both; nothing else changed.

355 end-to-end checks (268 engine + 87 panel), all green.

## 1.5.0 — 2026-09-24 — the Windows 11 edition

The importer now runs on **Windows 11** as well as the Mac: one codebase,
one version number, the same capabilities. Everything that differs by
platform lives in one small layer at the top of the engine plus each
platform's installer and watcher. `PARITY.md` lists every capability and
setting on both, and the rules that keep them in step.

**Windows 11**
- Cameras arrive as drive letters and are recognised by what is on them:
  `Autorun\` is the ASIAir, `MyWorks\` is a Seestar.
- `Install on Windows.cmd` / `install-windows.ps1` needs no administrator
  rights. It:
  - finds Python and adds astropy if missing;
  - copies the importer to `%LOCALAPPDATA%\BrettjoAstro\bin`;
  - starts the camera watcher at logon (`astro-watch.py`);
  - puts **Restart FITS Importer** on the Desktop;
  - schedules the ship to `E:\Astro Image Data` at 09:30 and 21:30 (the
    Mac's run at 09:00 and 21:00) when that folder exists;
  - points an existing archive-sweep task at the new sweep, and updates the
    old sweep.ps1 in place so a task it can't see still runs the new one.
- Frames land on the C: workbench (`Documents\Astro`) and are shipped into
  the archive on E:, exactly as the Mac's ship does over the share.
- Windows toasts, Shell eject, console versions of the Terminal fallbacks,
  and `selftest.py` to check an install (on the Mac too).
- Windows pitfalls handled:
  - `os.kill(pid, 0)` *terminates* a process on Windows, so the lock's
    liveness check has its own safe version.
  - The consoles default to cp1252, so everything runs in UTF-8 mode.
  - pythonw has no console, so output goes to a log.
  - Empty card readers could pop "insert a disk" dialogs; these are
    suppressed.
  - Drive-root paths (`F:\`) are handled in the delete containment checks.

**Both platforms**
- **One computer ships into the archive at a time:** a lock on the archive
  (`_verify\ship.lock`), per-machine partial files, and each ship-log row
  written before its frame is stamped, so no frame is shipped without being
  swept.
- **Each computer keeps its own ledger:**
  - A `machine.json` identity per computer.
  - A mirror folder is owned by one machine; the importer refuses to publish
    into another's, and refuses to restore another computer's ledger unless
    you confirm it's the same computer, rebuilt.
  - Per-machine ship logs on the archive (`shipped.jsonl` for the Mac,
    `shipped-pc.jsonl` for the PC).
  - The PC's receipts carry `-pc` in the name.
- `--export-settings` / `--import-settings` carry custom target names, the
  never-import list, the scope table and portable config keys to the other
  computer. They add what's missing, never overwrite, and never touch the
  ledger.
- `--version`; the panel shows the same version as the engine.
- Ledger keys are always `/`-separated, so a Windows ledger describes a card
  exactly as a Mac ledger does.
- The PC sweep reads every `shipped*.jsonl` with shared reads. It writes
  UTF-8 even under Windows PowerShell 5.1, never stops on a malformed row or
  an unparseable name, and refuses any path that leaves the archive. It
  writes sizes as numbers, and the ship's read of `verified.jsonl` skips
  stray lines and accepts a size written as text.
- Review leftovers closed:
  - The astropy hint names the Python that's actually running.
  - The macOS disk-access hint points at the importer's own app first.
  - The no-ledger scan message matches the new first-run flow.

**Mac / Windows:** identical except where `PARITY.md` lists a difference by
design: Finder tags, the watcher's notification wording, macOS permissions,
and the Terminal dialogs.

352 end-to-end checks (265 engine + 87 panel), all green, including the new chain
W1 that simulates the Windows drive-letter layer. The PowerShell scripts parse
under PowerShell 7 and the sweep was run against a test archive. Not yet run on
real Windows: `selftest.py` and both suites on the PC are the first step
after installing there. (Since 1.5.2: never run the 1.5.0 or 1.5.1 suites
on a real Mac or PC. They have no test mode; run 1.5.2's or later.)

## 1.4.3 — 2026-09-24

The five-persona review of 1.4.2 (owner, data-safety auditor, maintainer,
security reviewer, new user) found two ways the SAFE clear could delete the
only copy of data — both older than 1.4.2 — plus a panel that sometimes said
"backed up" when it wasn't. This release fixes them. Each data-safety finding has a
regression test that fails on 1.4.2 and passes here.

**Data safety**
- **Two Seestars on the same target no longer share a ledger row.** Rows were
  keyed by the camera path alone; two units stamping a sub in the same second
  (at the same size, when the sensors match) made the second camera's frame
  read "already imported" — never copied, then cleared as SAFE — or overwrote
  the first camera's row. Every lookup is now camera-aware; the first camera
  keeps its row, another camera's row for the same path is kept beside it.
- **One stack per stacking *session*, not per night.** A second session on the
  same night — after a filter change, or a restarted stack whose N began
  again — was treated as "outranked", never copied, and cleared. A stack now
  only supersedes another when it continues it: same night, exposure and
  filter, a higher N *and* a later time. `--tidy-stacks` uses the same rule.
- **The SAFE clear checks again at the moment it deletes.** The panel's card
  can wait an hour; if the camera is swapped meanwhile, nothing is deleted.
  After a Yes the camera is re-identified, every folder re-checked, and only
  the files that passed are removed — never a blind folder delete.
- **A stack the camera re-saves in place at the same size** is recognised
  (the camera's file time is recorded at import), copied again, and never
  cleared while the Mac holds the older bytes.
- **Every command that writes the ledger takes the import lock** and re-reads
  the ledger under it (`--tidy-stacks`, `--merge-days`, `--renumber-day`,
  `--set-filter`, `--unbaseline`, `--refresh-metadata`, `--restore-ledger`,
  `--skip-target`/`--unskip-target`); each save uses its own temp file.
- `--no-checksum` copies are no longer "verified" (so they can't clear the
  camera). A new frame at a path you once discarded is checked by fingerprint,
  not name and size. Discard records left "still on camera" by a crash settle
  on the next scan. A card with no readable FITS (identity guessed) never flags
  another camera's frames as cleared. An unreadable ledger is never published
  over the mirror. `--clean-source-previews` is gone — it deleted JPEGs from
  the ASIAir, which this tool promises never to touch.
- Typed target names can't become paths (no `/ \ : < > " | ? *`, no leading
  dot), `--ship` refuses any path that would leave the archive, and a camera
  folder named `.._sub` is not a target.

**Discard and clear**
- A discard on a **mix** now offers exactly the never-backed-up files and
  leaves the backed-up ones (tonight's cloudy frames on a target whose earlier
  nights are imported; stray JPEGs beside imported subs) — 1.4.2 refused,
  which left no way out on the panel.
- Discard reaches mosaic panel sets and mode folders (Lunar, Solar, …) by
  their camera folder name.
- **clear…** on any row the panel shows as backed up runs the SAFE clear on
  demand; the SAFE card now lists the folders and says what SAFE means.
- The never-import question after a discard now says what it really does
  (every *future* session would be skipped); the panel lists never-import
  targets that have new frames under "NOT backed up", with **import again**.

**Panel**
- Row pills come from the SAFE check: a target with an orphan JPEG or a failed
  copy says **NOT backed up · N files**, never "backed up". "All backed up"
  only appears when it's true. Imported panel sets and mode folders stay listed.
- The panel only accepts requests from its own page: exact origin (another
  localhost port is refused), JSON only, a per-launch token, answers must
  name their card; it can't be framed by another site; bodies are capped and
  type-checked.
- Card titles say what they're asking; no raw `[y/N]`; Enter/Escape work;
  focus lands on the safe button; a banner confirms a discard or clear; the
  result line never shows a previous operation's verdict.
- "Panel disconnected" no longer flashes after every scan (a JavaScript error
  wiped the scan time). Works at phone width; muted text and the red button
  meet contrast guidelines; screen-reader labels on every row action.
- A first-time user can import from the panel with no ledger (the first import
  starts one); the baseline is now clearly "only if you already have copies".
  "Refresh report" works without a camera.

**Filing and reports**
- An import that brings two nights of subs files them as two Day folders.
- The report's first block is labelled as the ASIAir's; discards list the
  nights they were shot.
- Watcher, panel and Terminal-fallback logs moved from `/tmp` to
  `~/Library/Logs`; the watcher's state to Application Support.

**Install and docs**
- `INSTALL.md` is now a newcomer's install guide; Brett's PC runbook is
  `PC-SYNC.md` and is optional. The ship agent is installed only when an
  archive URL is configured (or it was already installed); the example
  config no longer carries Brett's share address.
- The installer survives `|` or `&` in your home path; restarting only stops
  the running panel, never an editor with the file open.

339 end-to-end checks (252 engine + 87 panel), all green. New chain S22 and
panel checks T13–T14; T8 extended for the new request rules.

## 1.4.2 — 2026-09-24

Two things Brett asked for twice, and the ship log moved somewhere that
survives a reboot.

- **JPEG previews are no longer imported.** The S50 Pro writes a JPEG beside
  every sub; since 1.3.0 each one was copied, verified, ledgered — and from
  1.4.0 shipped to the PC — as a "rider" (about 2,250 so far, 734 from one
  Elephant Trunk mosaic). The rule now: *a JPEG that is a preview of a proven
  frame is not data.* A preview whose FIT twin (same name, same folder) is
  ledger-verified is not imported, not shipped, and does not block the SAFE
  cleanup offer. A JPEG with **no** FIT beside it is the only copy of
  whatever it shows: it is never silently ignored — it is listed as "on
  camera, NOT handled" on the panel, in the report and in the watcher's
  attention count, and it keeps its folder out of SAFE. The stack's own JPG
  and Solar/Lunar/Planetary/Scenery JPEGs still import as before. Riders
  already in the ledger stay where they are (nothing is deleted) and simply
  stop shipping. `SEESTAR_IMPORT_SUB_JPEGS=1` in config restores the old
  behaviour.
- **Discard: delete a Seestar target from the camera without importing it.**
  For the three-frames-before-cloud nights. A quiet *discard…* link on each
  Seestar target row (and `--discard "<target>" [--night YYYY-MM-DD] [--reason
  "..."] [--dry-run]` in Terminal). It is the one path in the tool that
  destroys frames with no backup, so: Seestar only — the ASIAir is refused
  outright; it sorts the target's files with the same gate the SAFE cleanup
  uses, and if *everything* is already backed up it simply hands over to the
  ordinary SAFE clear (default No) — until now that offer only ever appeared
  at the end of an import, so a declined one could never be reached again;
  a mix of backed-up and never-backed-up files is refused untouched, with
  the way forward (`--night` for the unimported night, or import first); a
  red card that says what the files are and
  that they were never backed up; confirmation by **typing DISCARD** — a
  click or a "yes" is not enough; every file is hashed and recorded in the
  ledger's separate `discarded` register *before* it is deleted. Nothing in
  that register ever counts as backed up; the report lists it under
  "Deliberately discarded from camera (NEVER backed up — by your choice)";
  and if the same bytes ever turn up again they are recognised, not offered
  as new. After a whole-target discard it offers to add the target to the
  never-import list. Refused, too, before a first import has created a
  ledger — the ledger is what remembers a discard.
- **Target rows say what the files are.** A Seestar row used to read "1
  frames · 47 MB" for a 458-sub stack. Rows now read, for example, "3 subs
  (1.5 min integration)" or "1 stack of up to 458 subs", with the unit
  ("stack", "frames") beside the size.
- **Ship log moved to `~/Library/Logs/astro-ship.log`.** `/tmp` is wiped on
  reboot, which is what lost the evidence after the September power cut. The
  installer now writes the ship agent with your home path substituted.

Not in this release, despite the 22 Sep runbook: clearing the ~3,700 Teddy
Bear "missing on Mac" ship warnings. Those are bookkeeping for frames the
rescue kit already put on E:; the fix depends on the PC sweep's records and
moves to 1.4.3.

**Hardened after an adversarial review of this release** (before it left
the building):
- The preview exemption applies only to per-sub previews in a `_sub`
  folder, and only with riders off. A Lunar/Solar JPEG is data — if its copy
  fails, the folder stays NOT SAFE (the first draft would have cleared it).
  The FIT twin is matched whatever the extension's case (`.FIT`).
- Discard picks its target by the camera folder name (`M 76_sub`), which is
  unique on the card; the panel shows the link only on DSO target rows (not
  on a mosaic's panels row or a Lunar/Solar row, whose names can collide).
  A typed name that matches two targets is refused with the folder names.
- Discard refuses if a second Seestar is mounted, or if any folder or file
  it would delete resolves outside the camera (a link on the card).
- Every discard record is written "still on camera" and flipped only after
  its delete succeeds. A delete that fails is reported as PARTIAL (exit 1),
  the frame keeps showing as new work, and the report doesn't count it.
- A discard record only hides frames from the camera it came from.
- On the panel, the first answer to a question card wins; a double click can
  no longer overwrite a typed DISCARD (or be overwritten by one).
- A folder literally named `_sub` is not a target (it once adopted the whole
  MyWorks folder); it is reported as not handled.
- Integration adds up each sub's own exposure, so a mixed 10 s / 30 s night
  reads right.

301 end-to-end checks (234 engine + 67 panel), all green. New chains S19
(previews), S20 (discard, including the SAFE hand-over, the mixed case and
every review fix) and S21 (what the preview exemption may not cover); S16
kept as the opt-in rider path; panel checks T10–T12.

## 1.4.1 — 2026-09-19

Hardening from the first real ship (11,261 files), which met a power cut
half way through.

- **A stale share is now detected.** After the PC went down, the SMB mount
  still listed folders from cache but refused writes, and the ship run died
  with a traceback on `makedirs`. The reachability check now also writes and
  removes a scratch file under `_verify`, so a dead mount reads as "not
  reachable" and the run is a quiet no-op. If the share dies mid-run, the run
  stops cleanly; what shipped is recorded, the rest waits.
- **Frames moved out of their Day folder are found.** The ledger says where a
  frame was put; Collect Lights or a hand tidy may have gathered it into a
  flat `lights/` folder since. `--ship` now looks for the file by name and
  size anywhere under the target folder before calling it missing. On this
  archive that turns 5,161 "missing on Mac" lines into shipped frames,
  including the whole ASIAir July to August run (Ced 214, Middle Heart, Veil,
  Fish Head, Lion) that had never reached the PC.
- **Targets match by name when the camera's token differs.** `LDN 1163 -
  Lion Nebula` now joins the archive's `Lion Nebula (Sh2-132)` rather than
  opening `Lion Nebula (LDN 1163)`; `C 9 - Cave Nebula` joins
  `Cave Nebula (Sh2-155)`. A display with no separator that contains an
  existing folder's code (`SH2-171 Teddy Bear`) also matches. Generic names
  (Globular Cluster, Open Cluster) never match by name. This is a stopgap
  until the shared targets table; folders already created by 1.4.0 under the
  old rule are left where they are.
- Resuming after an interruption is unchanged and safe: the ledger is saved
  every 50 files, `shipped.jsonl` is appended only after a verified copy,
  and a re-run adopts anything already on the archive with matching bytes.

249 end-to-end checks (193 engine + 56 panel), all green. New chain P4 pins
both the moved-file lookup and the name match.

## 1.4.0 — 2026-09-19

The Mac and the PC stay in sync on their own.

The Mac takes frames off the cameras and holds the ledger; the Chillblast
holds the archive and does the processing. Until now the gap between them
was crossed by hand, one bespoke copy at a time. 1.4.0 makes it a standing
part of the tool.

**`--ship` (Mac).** Files every frame that is verified on this Mac and not
yet verified on the archive into `E:\Astro Image Data` over the mounted
share (`/Volumes/AstroImageData`). Ledger-driven, so it needs no folder
scan and cannot be fooled by frames you have flattened into `lights`
folders by hand. The archive's own naming and numbering win: a target that
already exists there is reused whatever the Mac calls it; a night that
already has a Day folder there is merged into it; a new night takes the
next free number. So `M 27 - Dumbbell Nebula` on the Mac lands in
`S30P\Dumbbell Nebula (M 27)\M 27_sub Day 3\`, and the ASIAir's
`lights\<target> Day N` level becomes the archive's flat
`ZWO Askar Scopes\<Name (CODE)>\<Name (CODE)> Day N\` (mosaic panels keep
their panel folder). Loose stacks stay loose at the target root, mode
folders (Lunar, Solar...) go to the scope root, anything else goes to the
`_Working Files` shelf. Every copy goes through a `.partial` name, is read
back from the share and compared to the ledger hash, and only then is the
entry stamped `archiveLocation` + `archiveShippedAt` and a line appended to
the archive's `_verify\shipped.jsonl`. A file already on the archive with
the same bytes is adopted; one with different bytes is reported and left
alone. Nothing is deleted anywhere, ever. `--dry-run` lists the plan.
Quiet no-op when the share is not mounted.

**Runs by itself.** After every import, while the lock is still held, the
engine ships what just arrived if the share is up (`--no-ship` to skip).
A new LaunchAgent, `com.brettjohnson.astro-ship`, runs `--ship` at 09:00 and
21:00 (and on wake if the Mac slept through one). With `ASTRO_ARCHIVE_URL`
in `config.json` the engine mounts the share on demand via Finder and the
keychain, so the connection does not have to be kept open. The installer
loads the agent.

**The PC verifies independently (`pc\sweep.ps1`).** A scheduled task (at
logon and 03:30, `pc\install_sweep.ps1`) re-hashes every shipped file from
E: in a fresh process and appends the good ones to `_verify\verified.jsonl`,
the bad or missing ones to `_verify\problems.jsonl`, and a summary to
`_verify\status.json`. The Mac's next `--ship` reads `verified.jsonl` and
stamps `archiveVerifiedAt`. That stamp, not the Mac's own read-back, is
what "Safe" will mean from here on. The ship report ends with the count of
frames cleared from a camera and not yet PC-verified: the number that
should read zero.

**Known in this release.** Back-catalogue ledger rows (origin `backfill`)
are skipped; `--repoint` will reconcile them against the archive by hash
later. Frames you have moved by hand out of their Day folders on the Mac
are reported as "missing on Mac" and skipped (they are already on the
archive from the Cyprus import; the same `--repoint` will stamp them). The
Mac's own Day numbering can put two nights of one import run in one Day
folder; the archive numbering corrects that on the way in. Target naming
falls back to the `Name (CODE)` rule when no matching archive folder
exists; the shared targets table will replace that rule.

247 end-to-end checks (191 engine + 56 panel), all green. New chains P1 to
P3 pin: dry run names the archive target and copies nothing; a same night
merges into the archive's existing Day and a new night takes the next
number; stacks land loose; pre-existing archive files are untouched; ledger
stamps and `shipped.jsonl` lines per file; a `filed` receipt; re-run ships
nothing; `verified.jsonl` from the PC stamps exactly the listed files;
nothing on the Mac is deleted or moved; an ordinary import ships by itself
when the share is up; ASIAir frames take the archive's flat Day convention;
an import with the share down neither ships nor complains; `--ship` on an
unreachable share is a quiet no-op; a conflicting
archive file is reported, left untouched and not stamped.

## 1.3.1 — 2026-09-17

One stack per night, and the archive is never pruned.

**The bug this closes (data loss, live).** Since 1.0 the Seestar import kept
only the single highest `Stacked_N` per target and then deleted every other
`Stacked_*.fit` (plus JPG and thumbnail) at the destination whose name
differed. Two consequences: the stack from every earlier night was removed
as each new one arrived, so "Day 1's stack, Day 2's stack" never existed on
disk; and because the camera's `N` restarts when a project is recreated after
a clear, a fresh low-N stack would have deleted the archived cumulative stack
of all the nights before it, silently, logged as one grey line. Reported by
Brett on 12 Sep 2026 (`Importer_Backlog.md` item 3).

- **Never delete at the destination.** The removal loop is gone. An import
  only ever adds files to the archive. Deletion is Brett's hand.
- **One keeper per observing night.** Stacks on the camera are grouped by the
  night in their filename stamp (noon-to-noon, the same rule as subs) and the
  highest `N` within each night is imported and verified. Different nights'
  stacks coexist at the target root under their own stamped names.
- **Ledger entries for stacks carry `night` and `subCount`** (the camera's
  running N), so the archive can answer "how deep was each night's stack"
  and the dashboard can chart integration growth for free.
- **Receipts list the per-night stacks** (`sessions[].stacks[]` with night,
  subCount, filename). `stackedCount` stays as the overall highest.
- **Same-night supersession is reported, never acted on.** When a later
  import brings a higher `N` for a night that already has an archived stack,
  the older one is left in place and named in the log.
- **`--tidy-stacks`** lists archived stacks outranked by a higher stack from
  the *same* night in the same target folder and offers to remove them (and
  their JPG siblings). Typed `DELETE`, default keep, `--dry-run` lists only.
  Ledger rows are kept and marked `tidiedAt`, never removed. Stacks from
  different nights are never offered.
- **SAFE gate exemption narrowed to match.** A stack on the camera is only
  treated as disposable when a higher stack from the *same night* in the
  same folder is itself ledger-verified. The old exemption was per directory
  and unconditional. Milky Way folders still never exempt (one keeper per
  session).
- **Receipt filenames can no longer collide.** Two runs inside the same
  second (a quick re-run) used to overwrite each other's receipt; a `-2`
  suffix now keeps both.

232 end-to-end checks (176 engine + 56 panel), all green. New chain S18
pins: both nights' stacks archived and the same-night loser not; ledger
night and subCount; SAFE not blocked by a verified-outranked same-night
stack; archived stacks survive an import whose camera stack has a lower N;
nothing ever logged as removed; same-night higher stack imported with the
older reported and left in place; `--tidy-stacks` dry-run lists only the
same-night loser, a non-DELETE answer keeps everything, DELETE removes it
and marks the ledger row.

Already on the PC archive: the E: layout has always allowed several loose
`Stacked_*.fit` per target, so earlier nights' stacks may still exist there
even where the Mac copy lost them. Worth checking before assuming history
is gone.

## 1.3.0 — 2026-09-05

The Seestar S50 Pro joined the family — the fourth camera, and the second
dual-camera model (260mm f/5.2 telephoto + 63° wide-angle, both 4K). Before
release, the whole application went through two adversarial review rounds
(an astrophotographer's eye and an engineer's eye); everything they caught
is fixed below.

**S50 Pro**
- Recognised from its FITS identity with the Pro check deliberately ahead of
  the bare-S50 check (the original-S30 lesson: a Pro variant must never be
  misfiled into its base model's tree). Spacing/case variants all map to the
  same camera, and token matching is bounded so "S50 PRO-anything-else" can
  never sneak in.
- Its **own destination tree** (`Seestar S50 Pro/`), own per-target day
  numbering, own presence tracking — four cameras, four clean stories.
- Four-worlds modes (Lunar / Solar / Planetary / Scenery, photo and video)
  import — and not just for the S50 family: **every** model now backs up
  whatever mode folders it carries (an S30 Pro's Moon shots were silently
  ignored before; review finding).
- Reconcile/verify walk the new tree; Milky Way pairing, night continuation,
  SAFE cleanup, and the panel inherit the new camera automatically.

**Identity honesty (review findings)**
- Model detection now takes **one vote per project folder** instead of
  trusting the first FITS file `os.walk` happens upon — a stale leftover
  from another camera can no longer classify the whole volume.
- **Mixed identities on one volume refuse the import** outright, naming the
  folders; an **unrecognised identity refuses** rather than guessing a tree
  (a ledger that never forgets must never memorise a wrong camera).
- MyWorks folders this tool does not understand are **loudly listed** — on
  the panel, in the report, in the watcher summary — as "on camera, NOT
  backed up", instead of hiding behind "Nothing new. Every frame is backed
  up." A second mounted Seestar is announced too (one camera at a time).
- Volume discovery now matches any `/Volumes/Seestar*` name, so a unit that
  mounts as "Seestar 1" (or a future model's own name) is still found.

**SAFE now means every file (review finding, the big one)**
- The cleanup gate previously ignored JPEGs and unknown file types when
  deciding a folder was SAFE — it could delete a Solar shot's JPEG that had
  never been backed up. Now **every file gates** (only camera thumbnails,
  macOS litter, and superseded stacks are exempt), Solar/Lunar/etc. **JPEG
  siblings are imported, verified, and ledgered** like any frame, and the
  stacked keeper's JPEG rides along verified instead of best-effort.
- Clearing a folder flags **only the scanned camera's** ledger entries —
  relpaths repeat across Seestars, and one unit's cleanup must not falsify
  another's presence record.

**Panel + engine hardening (review findings)**
- The panel server now refuses requests with a non-local Host or foreign
  Origin (drive-by-POST / DNS-rebinding shield), and every answer carries
  the id of the question it answers — a stale click can never resolve a
  later, more dangerous card.
- Panel "Report" takes the same lock as imports (a report save can no longer
  race a running CLI import); the lock itself is created atomically.
- Ledger writes fsync before the atomic rename; a corrupt `ledger.json`
  recovers loudly from its `.bak` instead of falling through to a baseline
  offer.
- Milky Way sessions now use the same ledger-aware, night-continuing Day
  numbering as everything else (an interrupted MW import resumes into the
  same night; archiving MW folders no longer restarts numbering).
- Unparseable calibration filenames in `Autorun/` force a NOT-SAFE verdict
  and are named in the report (they used to vanish from the arithmetic).
- Non-DSO modes appear as ordinary tickable rows on the panel — no more
  invisible riders on an import — and `--targets` governs them too.

**Second review round (fresh adversarial pass on the revision)**
- **Fixed a data-loss bug the first revision introduced**: the SAFE gate's
  superseded-stack exemption was wrong for Milky Way folders, which hold one
  keeper *per session* — an unledgered lower-N keeper could have been
  deleted on a Yes. MW/panel/mode folders now never exempt stacks; only DSO
  project dirs (where import itself enforces keep-highest) do. A test
  reproduces the exact scenario.
- Stack/keeper JPGs are registered in the scan's relpath set, so a report
  right after an import can no longer falsely mark them "cleared from
  camera"; the report's per-target SAFE verdict now runs the same
  every-file walk as the cleanup gate; a blocked folder **names** the
  unproven files instead of going quiet.
- **Stack-only projects import** (sub-frame saving is OFF by default on
  Seestars): a project folder with `Stacked_*.fit` and no `_sub` sibling
  imports through the normal path — naming, keep-highest, JPG rider.
  (MilkyWay stack-only folders stay visibly "NOT handled" — their
  per-session keepers don't fit keep-highest.)
- Identity votes filter AppleDouble litter *before* sampling (a Finder-
  touched card could burn the tries and fall back to a guess); loose root
  FITs vote too; the refusal is a clean message — never a traceback — on
  every path (import, --baseline, --pick), and the panel keeps scanning the
  other camera.
- The watcher notification and the panel's green banner no longer say "all
  backed up" over unhandled folders (new ATTENTION count in the scan tags);
  project-dir matching is exact ("M 8" can no longer adopt "M 81"'s
  folder); non-.fit strays in Autorun weigh on its verdict; reconcile can
  upgrade baselined JPEG/video media; --pick lists mode folders and
  --targets accepts both their names; the destination preview shows mode
  imports; Origin "null" is refused; a corrupt ledger with no usable .bak
  refuses to baseline over itself, and a recovery no longer overwrites the
  good .bak.

**First light (2026-09-05, 724 frames, flawless identity) taught us one thing**
- The S50 Pro writes a **JPEG preview beside every sub** — no earlier Seestar
  did. The every-file SAFE gate caught them on night one (refused cleanup and
  named all 724, exactly as designed). Now they import as **verified,
  ledgered riders** into their sibling FIT's Day folder — including catch-up
  for FITs imported before this existed (a ledger sibling lookup supplies
  the right Day folder, so a later night can never misfile them). Its sub
  names also carry the filter (IRCUT/LP) — first Seestar to tell us.
- JPEG-only and stack-only work now shows as an importable row on the panel
  and in the picker, and counts in the watcher summary.
- The S50 Pro also **re-saves its stack after a session** (an annotation
  pass on shutdown). A camera stack that changed since it was ledgered is
  now re-copied atomically and re-verified — before, it was skipped and the
  SAFE gate (rightly) blocked the folder forever. MW keepers get the same
  treatment.
- The panel's Activity log folds ANY progress bar into one updating line,
  matched by shape rather than a hardcoded label list (the 319-stacked-
  JPEG-bars incident).

222 end-to-end checks (166 engine + 56 panel), all green — including the
fourth-camera chain, the every-file SAFE gate with the MW-keeper repro,
camera-scoped clearing, the identity refusals, MW night continuation,
stack-only imports, JPEG riders fresh + catch-up, the re-saved-stack
refresh, and the panel's Host/Origin and stale-answer shields.

## 1.2.0 — 2026-08-18

A second Seestar joined the family and a yanked USB cable taught the importer
some manners.

- **Original Seestar S30 support**: detected from its own FITS identity, with
  its own destination tree (`Seestar S30/`), its own per-target day numbering,
  and its own camera-presence tracking — two Seestars shooting the same target
  never interleave. Proven live on first contact: five targets, clean scan,
  correct tree.
- **Night continuation for Seestar imports**: an interrupted/resumed import
  now lands in the *same observing night's* Day folder instead of fragmenting
  one night across several (the rule the ASIAir path always had).
- **Repair commands**: `--merge-days "<target>" N M …` folds split Day folders
  back together (files moved, ledger rewritten, empties removed, root-dwelling
  stacks left in place); `--renumber-day "<target>" FROM TO` renames a Day and
  its ledger entries to close numbering gaps.
- **Friendlier install**: a double-clickable
  `Install BrettjoAstro FITS Importer.command` for the download-ZIP route — no
  terminal, no git required.
- **HOW-IT-WORKS.md**: the entire logic in plain English for astronomers —
  the backup-first promise, the ledger, Day folders, calibration consent,
  what SAFE means, and what can never happen.

179 end-to-end checks (133 engine + 46 panel), all green — including a
two-Seestar simulation and the interrupted-night resume.

## 1.1.0 — 2026-08-14

Two weeks of nightly real-world use (a Mac rebuild included) fed straight back
into the tool.

**Panel**
- Calibration **pairing preview with consent checkboxes**: the scan runs the real
  matching gates and shows which bias/dark/flat sets pair with which target;
  everything pre-ticked, unticking skips the link (frames still back up), and
  ticked pairings import with no interruptions. Only questionable pairings still
  ask — and the question now names the set, its date and rotation versus the
  lights' ("self-describing cards").
- **"Where files will land"**: live destination tree computed by the same
  Day-numbering code the import uses; updates as you tick. Tests pin that the
  preview equals the folders the import then creates.
- One-page app layout (page never scrolls; panes do), camera storage as a live
  header meter, wider Activity log with hanging indents and `~`-shortened paths,
  date-ordered target and inventory lists (newest first, last-shot dates shown),
  calibration summary card with new-set breakdown, collapsible backed-up
  inventory.
- **Completion banner** (frames, targets, duration — survives rescans until
  dismissed), tab-title flip, and a macOS notification with chime.
- Scope badges read the *incoming* frames' focal length, so multi-rig targets
  are labelled by tonight's setup, not their history.

**Engine**
- `--set-filter "<target>" "<filter>" [--night YYYY-MM-DD]` records the true
  glass when the ASIAir filename carries no filter token.
- Panel pre-consent map (`CAL_DECISIONS`) honoured at link time; CLI behaviour
  unchanged when empty. Probation-mark hygiene between match runs.

**macOS permissions, solved properly**
- All launchers prefer **python.org Python** when installed (Apple's Python is a
  platform binary: silently denied removable-volume access from background
  launches and never allowed to ask; python.org Python asks once).
- New **app wrapper** (`BrettjoAstro FITS Importer.app`) — ad-hoc signed by the
  installer — gives the panel a stable, grantable identity; the watcher launches
  the panel through it.
- Desktop **Restart FITS Importer.command**: one double-click, Terminal context,
  always works.
- The panel's permission hint now names the exact binary macOS is blocking.

**Watcher**
- Camera *swaps* always announce (flap guard now applies per camera set, not
  globally); honest notification wording when the pre-scan is blocked; panel
  launches route through the app wrapper when present.

**Installer v5**
- Installs and signs the app wrapper, installs the Desktop restart button,
  checks astropy against the preferred Python, documents the permission model.

166 end-to-end checks (120 engine + 46 panel), all green.

## 1.0.0 — 2026-07-25

First public release as **BrettjoAstro FITS Importer**.

- One engine, one ledger, one panel, one watcher for ZWO ASIAir **and** Seestar (S30 Pro / S50)
- SHA-256-verified, crash-safe copies; lifetime ledger; honest backup report; HTML dashboard
- ASIAir: per-scope recognition, calibration library with configuration-matched hard-links,
  ask-before-linking gate for questionable flats, mosaic support, backup-of-record stance
- Seestar: CREATOR-based model detection, full MyWorks semantics, Milky Way ↔ DSO session
  pairing, keep-highest stacks, S50 non-DSO modes, SAFE-aware cleanup (default No)
- Generalised for any Mac: $HOME-derived paths + optional config.json overrides
- 136 end-to-end checks against simulated cameras
- Proven on real hardware the day of release: 686-frame Seestar import, verified and
  safely cleared from the camera
