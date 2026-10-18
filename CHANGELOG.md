# Changelog

## 1.7.3 (2026-10-18): the ledger catches up with frames moved to the archive by hand

Installing 1.7.2 on the Mac, the ship's dry run listed 11,695 frames "missing on this computer": imported and verified between June and August, cleared from the cameras, their Mac copies gone, and never recorded as reaching the archive. They are on E: (2,966 Teddy Bear frames, 5,135 Veil frames and the rest, moved there by hand over the summer before the ship existed); the ledger was never told, so the Observatory, the Space view and the status line counted them as not on the archive.

- **`--adopt-archive`** (both computers). For each such frame the PC's inventory is searched for the same bytes: a row with the sha256 the PC's `--hash` computed is proof, and the ledger is marked as a ship marks an adopted copy (`archiveLocation`, `archiveShippedAt`, `archiveVerifiedAt` from the PC's hash time, `adoptedFromArchive`), with a "shipped" row (adopted) in this computer's own ship log so the PC's sweep keeps checking it. A copy with the same name and size the PC hasn't hashed yet is adopted only with `--hash-here`, by reading it back over the share (the ship's own standard; slow). A copy whose bytes differ is never adopted and is named. Nothing on the archive is created, renamed or removed; a dry run (the default) writes nothing anywhere; `--apply` writes the ledger. Safe to repeat.
- **The contract, five merges on Brett's word (18 Oct).** `contract/targets.json`: NGC 1893 (the cluster) into IC 410, now *Tadpoles Nebula*; NGC 6910 (the Rocking Horse cluster) into IC 1318, *Sadr Region*; NGC 7822 and Ced 214 into Sh2-171, now *Teddy Bear Nebula*; LDN 386 into M 16, *Eagle Nebula* (the Eagle is in the frame); the Squid (Ou 4, which the Seestar recorded as a Gaia star number) into Sh2-129, now *Flying Bat and Squid Nebulae*. Each pair was two projects in the Observatory for one picture; folder names that carried both codes ("Ced 214 and NGC 7822 complex (Sh2-171)") resolved to nothing. An unedited installed copy is updated by the installer; an edited one gets the new file beside it as `targets.json.new`. Run `--projects` (or the panel's Refresh) afterwards.
- Chain AA in the engine suite: dry run writes nothing; apply marks only the proven frames; the un-hashed one waits for `--hash-here`; the differing one never; the ship then has nothing to send again; idempotent; under the share's D7 rights nothing but this computer's own log and record is touched.

**After updating** (the Mac, where the frames were imported): install as for 1.7.2, then
```
/usr/local/bin/python3 ~/bin/astro-import.py --adopt-archive
```
reads the list and writes nothing. When it says what it would prove, `--adopt-archive --apply` records it; `--adopt-archive --apply --hash-here` also reads back the copies the PC hasn't hashed yet (hours over the share; the PC's nightly `--hash` closes that gap by itself over time, so it can also just wait). Mac / Windows: the same on both.

813 end-to-end checks (624 engine + 189 panel).

## 1.7.2 (2026-10-17): the Observatory, rebuilt

Brett's words on 16 and 17 Oct: "it's just a lot of text and numbers, like looking at Excel", "this type of thing is the right direction" (the scope timeline), "be creative and colourful", "the devil is in the detail", "dynamic impact that looks professional", and "there is a macro view, project view, micro view". Three design directions, then five detail reviews (type, colour, motion, truth of every label, layout), then one specification (`docs/ux-observatory-16oct/SPEC.md`). Nothing in the rules changes: the page reads, never writes.

- **The page says facts, never guesses from sentences.** The engine now gives it: each dataset's capture state and where it came from (the 14-night rule, or your `capture-state.json`); a **sample** state for quick looks and test snaps, kept out of the queue (your flag, never an hour rule; a sample with a master stays a project); an **exposure note** for frames whose headers carry none, so their hours add up and are marked as from your note; the unknown target names themselves and every count of what was not counted (names, frames, no scope, no night, duplicates, rows that are not light frames); every warning with a kind and a count; the scopes in the contract's order with their kind; what the last scan found still on a camera (files, targets, a failed eject) and when; the local time the page was built; and the night's facts (see next).
- **The three levels of the archive.** Macro: the archive. Project: one object across its scopes. Micro: one night. Each dataset carries one row per night: the morning it ended, frames and seconds, exposures, filters, gains, which computer imported it, how many copies the archive verified, its Day folder keys here and on the archive, what sits in that archive folder (autostacks, working files) and, for the ZWO scopes, the calibration linked that night in detail: darks with their exposures and gains, flats with their filters, biases, and how many the archive verified. A Seestar dataset says "in camera" rather than "not needed". The shared-Askar warning is a field (`masterOwnerUncertain`) naming the candidates, not a phrase.
- **The panel** saves a one-line summary of every scan (`last-scan.json` in the state folder) for the Observatory's "still on the camera" line; `GET /api/observatory/status` gives the Observatory's stamp and whether a rebuild is running; `GET /observatory?json=1` returns the dataset alone, so the page refreshes in place.
- **The page itself, rebuilt** (`astro-observatory.html`, same file, same slot, nothing loaded from the web). Top to bottom: a night-sky header with the hero, every number wearing its word, the share bar by scope with every slice labelled, one freshness line with a pill (live · N min ago, a day old, rebuilding…, updated just now, importer not answering) and the line that says what the last scan left on a camera (never a green tick when it wasn't checked); a legend that explains every colour and mark once; **Last night** (evening → morning, one row per scope); **Needs your attention** as jobs with counts and a verb each, from the record's own counts, a dealt-with job collapsing with Undo; **What each scope captured**: six lanes in one fixed order, a dot per night sized by hours, hollow when hours are unknown, the quiet band, ranges 30 / 90 / a year / everything, the dots sliding when the range changes and becoming week or month bins when they would touch; **What to do next** in three columns (Ready to process, Finish it, Still capturing) with the calibration mark on every ZWO card and quick looks listed under, never in; **Projects that moved lately** with a ring of hours by scope, one pill per scope, a mini timeline, and a header that opens a full-width panel: one lane per scope with its three marks (capture, processing, calibration) and a table of nights. Three levels like the disk: every dot, Day row or heatmap cell opens the **night panel** (frames, hours, exposure, filter, gain; the darks, flats and bias filed that night with their exposures, gains and filters and how many the archive verified; what sits in the Day folder on the archive; which computer imported it; Open folder), every lane opens the project, every scope name opens the scope's timeline. Colour means scope (from the contract), status is a glyph and a word (Still capturing, Ready to process, Finish it, Done, Quick look), warnings are ink on a warm wash. Dark by default, light when the system says so or by the toggle in the bar. Eight type sizes, three weights, one spacing ladder; breakpoints at 1100, 900 and 700; a View selector and nothing under 44 px to tap on a phone; one anchored tooltip on marks only, on hover, keyboard and touch. Motion that means something: a one-time load-in, dots that move, panels that slide open, a hero that counts up only when the record really changed, all off under reduced motion. Live refresh: inside the panel the page asks every 30 s whether the record changed and redraws in place with a toast saying what arrived. The other views (Targets, Coverage, Pipeline with a list under 900, Nights with a numeric legend, Sky, "Approximate footprints", Equipment, Data checks with the subtraction that explains every row) keep their logic in the new style.
- **Review of 17 Oct (engine and panel), fixed.** The other computer's nights carry their gain (it travels in the ledger snapshot from the next ship). A quick look never drives its project's state, the target's state or the pending count, and the Archive tab never lists one. The panel writes a scan summary only when a camera was scanned (so the page says "not checked", never "nothing left"), a failed eject is remembered in it, and what is still on a camera is this computer's own last scan even when the record shown is the PC's published copy. An unreadable row is not also counted as "not a light frame". The Observatory's stamp re-reads at least every ten minutes (the published copy ages out at 48 h). A corrupt `last-scan.json` reads as zeros, never a crash. `true` is not a sub length. One notice per warning, in the warnings' order.
- **Review of 17 Oct (the page), fixed.** Opening a second project while one was open threw and left its panel behind; "Timeline of its projects" from the Equipment tab did nothing on a fresh load; a real 80-second capture read "0.0 h" (minutes now, everywhere); a name with words after its code lost them; the night panel claimed calibration was "matched" even with none filed; a record without the new counts read "0 of 9 nights" and "0 verified" instead of "not in this record"; the engine's plain warnings vanished from Needs your attention on such a record; the strip binned nights by week on a phone at 30 nights; small buttons under 44 px on a phone; a missing-calibration line that read backwards; a camera name invented for the ZWO scopes; the last-night calibration fact cut short at the panel's width; the footer's retired words; "1 days", "1 need", "six scopes", a 0% share for real hours. Safari: no "instant" scrolls, ring arcs in real units, the count-up finishes on a hidden tab. Tooltips on marks only. The "still on a camera" line names the computer whose scan it was.
- **Review of 17 Oct (the three releases as a stack).** No rule broken: every path written under the archive is written by one computer in its own folder, the ship creates frames with exclusive create only, the SAFE gate still reads only this computer's ledger. Fixed: the Mac's panel looked at the share on every poll (the Dashboard's snapshot check and the Observatory's stamp); a stale mount with the PC asleep could stall it. Now the archive is looked at once a minute and every ten minutes respectively. The install order below is the review's.
- **Not in this release**: the Observatory as its own route with one scrollbar (it still opens in the panel's tab; the page is ready for it), an endpoint to mark a job dealt with or set a quick look or an exposure note from the page (the page shows the exact `capture-state.json` line to add), sensor temperature and binning per night, and Coverage's "not planned on this scope".

Mac / Windows: the same on both. The page is ready for Safari and Edge but was checked here in Chromium only: look at it once on each machine.

**After updating**, in this order (from the review of the three releases as a stack, 17 Oct):
1. **Mac first**, at a quiet hour (not 09:00 or 21:00, when the ship runs): unzip, then `cd ~/Downloads/importer-1.7.2 && bash install-scripts.sh`. The twice-daily ship starts a run by itself as soon as the installer finishes (it sends the calibration frames and the ZWO frames, so it can take a while): let it finish, then `--ship --dry-run` and `--ship` for what is left, and check `E:\Astro Image Data\_verify\mac\ledger-snapshot.json` is there.
2. **No camera into the PC until step 3 is done.** A PC on an older importer, or one that hasn't read the Mac's record yet, sees every frame the Mac holds as new.
3. **PC**, from a normal window (never "Run as administrator", and not right after logon): double-click `Install on Windows.cmd`; then in Terminal `Start-ScheduledTask -TaskName 'Astro archive sweep'`, so the PC reads the Mac's record, rebuilds the list and publishes it for the Mac's Observatory (the hashing after that runs for hours in the background; fine).
4. Self-test on both; if the PC's "drives checked" lists D:, add `"ASTRO_DRIVE_EXCLUDE": "D:"` to its config.json. Then both test suites on each computer.
5. Once: `--export-settings` on the Mac, `--import-settings --dry-run` then `--import-settings` on the PC.
6. Leave the FITs Importer App alone until it has merged this release: its engine is 1.5.3 and its ship still needs Delete on the archive.
To flag a quick look or give a sub length, edit `capture-state.json` as HOW-IT-WORKS shows (the page prints the exact line).

802 end-to-end checks (613 engine + 189 panel): chain OB4 and its review check in the engine suite, the "OB (1.7.2)" and "OB (review, 1.7.2)" checks in the panel suite. On Linux here: engine 609 passed, 4 skipped, the four Mac/PC-only lines as before; panel 189 passed.

## 1.7.1 (2026-10-16): two importing computers, one truth

On 14 and 16 Oct Brett plugged the Seestars and the ASIAir into the Chillblast and imported there. The PC had no ledger, so everything on the cameras looked new, and he decided the PC becomes a second importing computer. The rules stay: each computer keeps its own ledger and writes only its own files; the SAFE gate and DISCARD trust only the ledger of the computer doing it. The archive is the one truth: each computer leaves its record there, and every screen reads both.

- **The scan reads the other computer's record.** A frame the other computer imported *and verified* is not offered again: the row says "already backed up by the Mac" (or by the PC), "verified on the archive" or "not yet on the archive". Only a verified copy counts: a baseline row never does. Stacks, panels and riders are recognised too. Off with `ASTRO_OTHER_RECORD=off`. The record is the ledger snapshot each ship leaves in `_verify\<mac|pc>\`; it now carries every row (with whether its copy was verified), the calibration Library, the DISCARD register, the target names, the never-import list and the scope table, and is refreshed after every import, discard, merge and filter fix as well as every ship.
- **No clear and no discard on what the other computer holds.** On the panel such a row is a third state with no clear and no discard button; DISCARD from the command line refuses ("clear it from the Mac"), and a mix offers only the files no computer holds. The SAFE gate itself is unchanged. Frames you binned with DISCARD on one computer are not imported by the other.
- **One name, one folder.** A target name the other computer already saved is used without the question, and kept in this computer's own names file. The other computer's never-import list unticks a target here (it stays importable).
- **Counted once.** Calibration frames linked on both computers count once per night in the To process list. A night one computer's ship started into a Day folder stays in that Day whichever computer retries it (the Day seed now comes from every ship log).
- **A re-saved Seestar stack** whose name the archive already holds with different bytes is filed beside it as `<name>__pc.fit` (or `__mac`), both kept, nothing written over, and the ship stops reporting it as a problem every run.
- **Receipts on the archive.** Each ship copies this computer's AstroLog receipts into `_verify\<mac|pc>\receipts\<scope>\` (never written over), so AstroLog can read both computers' from one place. AstroLog itself still reads the Mac's Documents folder: that change is next, on the AstroLog side.
- **The panel** says a PC import is filed into E: at once; the scan card shows whose record it read and how old it is (and warns when the archive, or the record, isn't there); the Dashboard shows this computer's imports and the other's record together; "on this PC" and "on the Mac" come from the engine, so the same page is right on both machines; the calibration card counts the other computer's Library. Wording: "the ship to the archive", "missing on this computer", "backed up on this PC/Mac".
- **Windows**: `ASTRO_DRIVE_EXCLUDE` in config.json (for example `"D:"`) keeps a fixed drive out of the camera search; an import folder under OneDrive is warned about (Files On-Demand can move frames off the disk after import).
- **Adversarial review of this change (16 Oct), fixed.** A copy the other computer verified at import but no longer holds (its record says `here: false`) proves nothing: the frame is new again here. The Seestar scan names the record and its age too (the first-import line and the scan card were silent with only a Seestar plugged in). The other computer's scope table is read when a focal length is unknown here (this computer's table wins). A scan or a dry run adopts the other computer's target name in memory only; the import saves it. The beside-filing of a re-saved stack uses only a valid machine name and never the same suffixed name twice. The OneDrive check judges the import folders, not Documents. `ASTRO_DRIVE_EXCLUDE` accepts `D` as well as `D:`. Whether every file of a camera folder is the other computer's is decided where the SAFE gate's list is (by file name, on the server), not by counts on the page.
- **The panel (review of 16 Oct).** "Filed into the archive" is said only when the ship really finished; otherwise the banner says the ship didn't finish, or that the archive isn't reachable. The Dashboard is built in the background when the ledger or the other computer's record changes, never on a click, and keeps this computer's calibration count; the page re-loads it only when it is newer. Ticks and calibration pairings survive the rescans the panel itself triggers. A busy importer says so when a button is pressed early, and the Refresh rebuild shows as busy. A render error names itself in the target list instead of reading "panel disconnected". One poll in flight at a time; an older answer is dropped. A request marked cross-site by the browser is refused on the routes that cost or act; a folder named `.app` is never opened. "No record from the other computer" is said whenever the record can't be read. ASIAir rows say "backed up: N on this PC, M by the Mac". Space works like Enter on the To process rows; focus returns after a question card; the Report tab reloads when the report is ready; the Observatory note never sticks on "Working it out…"; calibration decisions are validated; the prompt hooks are reset after every operation; `/api/status` says "still working it out" instead of nothing.
- **The Observatory page (review of 16 Oct).** A dataset from another engine version (missing keys, a session with no hours, a target with no state or no declination) never blanks a tab; a corrupted saved tab or range is ignored; the drawer is a dialog (focus in, Esc, focus back, the page behind doesn't scroll, no tooltip left over); a scope only the sessions know gets a column and its colour; a share of nothing reads "—"; nights before 2015 or in the future are left out of the heatmap and the streaks and said; the quiet band never covers the whole timeline silently; the Coverage grid and the Targets rows fit the frame at every width; tooltips are built once per hover and hidden from screen readers (marks carry labels instead); a failed tab is retried on the next visit; long sky labels are cut with the full name on hover; empty charts say so; the Instagram leftovers are gone.
- **Robustness (review of 16 Oct).**
  - `--reconcile --no-checksum` no longer marks a row verified: the same size proves nothing (rule 2), so the row is `checksumSkipped`, the SAFE gate keeps the file unproven and the ship leaves it out, and the run says to reconcile without `--no-checksum`.
  - A frame the PC's sweep found damaged or missing on the archive (`_verify\pc\problems.jsonl`) goes back into the ship's to-do: its archive location moves into `archiveProblem`, the status line and the Space view count it as only on this computer (never "waiting"), the ship says how many are being re-sent, and a damaged copy at the path is left for the PC while the good one is filed beside it. The sweep checks such a path again once a ship sent the frame after the problem was noted.
  - A camera that cannot be read completely (a folder the walk could not open, a file it could not size) marks nothing cleared, and says so; a file that is there but unreadable is never taken for gone. A frame that re-appears on the camera stops counting as only on this computer (`reappearedAt`).
  - A camera unplugged mid-import (its volume gone, or three copies in a row failing) stops the run with one plain warning; nothing that failed is marked imported, what was copied is recorded, and no clear is offered.
  - A `ledger.json` that parses as something other than a ledger counts as unreadable (the `.bak`, else "status unknown", never a baseline over it); a row that is not a record is set aside under `malformedRows`; a never-import list or names file of the wrong shape is ignored, each with a warning naming what was dropped.
  - A frame name whose numbers don't parse (`…_1.2.3s_…`) no longer stops the scan: it is counted, named as unrecognised in the report, and imports by its FITS headers.
  - The ship plan lists each archive root once and looks a target folder up once, not once per frame.
  - A long import or ship saves the ledger at most once a minute (and at the end), and takes the `.bak` once per run.
  - The sweep tries a shipped frame's path as written, in NFC and in NFD before calling it MISSING.
  - A camera that stops answering while a scan lists it is the same clean "NOT scanned" refusal as the identity check, on the command line, in the report and on the panel.
  - The Mac's creation-date copy uses `os.stat` and looks SetFile up once; without SetFile nothing is run per frame.
  - The DISCARD refusal over files the other computer holds never sizes a file inside its message.
  - The SAFE gate calls a file it cannot stat unproven at once.
  - A lock older than a day is stale, whoever holds its process number; the lock names what holds it and the host.
  - `seestar_volume()` answers from a 1.5 s cache (scans look again).
  - Windows: paths over 240 characters get the `\\?\` prefix in the copy and the ship; a typed target name is capped at 80 characters.

**After updating** (both computers): install as for 1.7.0. On the PC, add `"ASTRO_DRIVE_EXCLUDE": "D:"` to `%LOCALAPPDATA%\Astro Import\config.json` if a data drive shows in the self-test's "drives checked". Bring the Mac's settings over once (`--export-settings` on the Mac, `--import-settings` on the PC: names, the never-import list, the scope table). The 14 to 16 Oct imports on the PC happened before the scan read the Mac's record, so those frames sit in both ledgers; the ship adopted the copies already on E: by their hash and opened no second folders, and the To process list counts a frame once. Mac / Windows: the same on both.

795 end-to-end checks (608 engine + 187 panel): chains OT and RB in the engine suite, OT and PR in the panel suite. On Linux here: engine 604 passed, 4 skipped, the four Mac/PC-only lines as before; panel 187 passed.

## 1.7.0 (2026-10-13): shipping without Delete, the PC's jobs in Python, the project layer and the Observatory

One release, built in four steps on the same branch and run as one. Nothing from any step has shipped before this.

**After updating, do this once** (both computers, in this order; the PC switched on and the share reachable):
1. Mac: unzip, then in Terminal `cd ~/Downloads/<the folder you got> && bash install-scripts.sh`. See the ship plan first, `/usr/local/bin/python3 ~/bin/astro-import.py --ship --dry-run` (this first ship also sends the calibration frames), then ship for real: `/usr/local/bin/python3 ~/bin/astro-import.py --ship`. The ship leaves the Mac's ledger snapshot on the archive (`_verify/mac/ledger-snapshot.json`; check it is there); the PC reads it from there. Double-click **Restart FITS Importer** on the Desktop and open the **Observatory** tab.
2. PC: unzip, double-click `Install on Windows.cmd` from a normal window (never "Run as administrator"; the installer refuses that and says what to do). Then in Terminal: `py -3 -X utf8 "$env:LOCALAPPDATA\BrettjoAstro\bin\astro-import.py" --projects`, or press **Refresh now** on the To process or Observatory tab, and reload the panel page. The Observatory shows the Mac's record once step 1's ship has run.
3. Run both test suites on each computer (see Testing below) before the branch is merged.

### Shipping without Delete, and the PC's own jobs in Python (3 Oct)

Phase 0 of the Sync View plan. The share's user can now be denied Delete on the archive (decision D7) without breaking anything, and the PC's side runs in the same Python engine as the Mac's.

- **The ship never deletes, renames or writes over anything on the archive.**
  - Each frame is created under its final name, and only if that name is free. Its bytes are read back before it counts as shipped. There are no more `.partial` or `.BAD` files.
  - The frame on this computer is checked against the ledger before anything is sent. A frame that changed since import is not sent at all.
  - Each computer's ship log now lives in its own folder: `_verify\mac\shipped.jsonl` on the Mac, `_verify\pc\shipped-pc.jsonl` on the PC. It has a "started" row before each frame and a "shipped" row after its read-back.
  - The old logs in `_verify` stay as history. They are read, never written.
- **A copy cut off half-way is set aside, not left as if it were the frame.**
  - It stays "started", never "shipped", so the frame isn't counted, and the Mac asks the PC for a sweep straight away.
  - The PC moves that copy, and only it, into `_Quarantine\ship-incomplete`, once no ship is running and ten minutes have passed. The Mac's next ship sends the frame again, to the same path and Day.
  - A copy that turns out whole and correct (only the row, or the read-back over the share, failed) stays where it is, and the Mac's next ship records it without sending it again.
  - A shipped frame the PC can't read just now (in use, or a read error) is read again by the next sweep, not written down as a problem.
  - Frames copied by hand, processing files and anything that doesn't look like that ship's copy are never moved: they become a line in `problems.jsonl` instead. Moving those copies aside is the one thing the PC moves by itself (agreed 3 Oct).
- **One ship at a time, with a lock that can't get stuck.** The lock is `_verify\lock\ship.lock`. The computer holding it renews it every minute. Another may break it after ten minutes without renewal, and notes that in its own log. A 1.6 importer's lock still counts. The ship also used to ship without the lock when it had to connect the share first; that's fixed.
- **Why the 865 ZWO frames never reached the archive, fixed.**
  - Calibration frames now ship with their lights, into the Day's `calibration\{biases,darks,flats}` (mosaics into the target's `calibration`). Before, the ship never sent calibration frames at all.
  - Frames that Collect Lights renamed into `lights/lights` are found by their original name at the end of the new one, with the same size and the ledger's bytes, and filed under the original name. Before, they were "missing on Mac".
- **A panel import ships straight away** when the share is already connected, as a Terminal import does. It never asks Finder to connect from the panel.
- **"Not reachable" says why:** the share isn't mounted, the folder has no camera folders, or `_verify\mac` can't be written (with a hint when macOS's Privacy & Security is the cause).
- **A ship that would leave the archive with less than 10 GB free sends nothing** and says so (`ASTRO_ARCHIVE_MIN_FREE_GB`).
- **The PC's sweep is Python now** (`--sweep`). `pc\sweep.ps1` and `pc\install_sweep.ps1` are retired.
  - It re-reads every shipped frame from the PC's own disk, bypassing Windows' cache (`FILE_FLAG_NO_BUFFERING`), from every computer's log.
  - It writes only in `_verify\pc`: `verified.jsonl`, `problems.jsonl`, `status.json` (the same fields as before, plus new ones), `quarantine.jsonl` and its log.
  - Copies a 1.6 ship left (`.partial`, `.BAD`) are listed, and moved into `_Quarantine\old-partials` only with `--sweep --move-old-partials`.
- **The PC's other jobs, for the Sync tab to come:**
  - `--inventory` lists the archive in generations (`_verify\pc\inventory-E-<time>.jsonl`, then `inventory-E.status.json`).
  - `--hash` keeps a hash cache, low priority and unbuffered, with a nightly re-read of a 30th of it to catch bit rot.
  - `--pc-tick`, every 5 minutes, writes a heartbeat and does what the Mac asked for. On the Mac, `--request sweep` or `--request inventory` asks.
  - `--pc-nightly` runs the sweep, the inventory and the hash.
- **The Windows installer** sets up "Astro archive sweep" (logon and 03:30, `--pc-nightly`) and "Astro sync requests" (every 5 minutes, `--pc-tick`), both Python, as you. It also makes the new folders under `_verify`.
- **The share's rights:**
  - On the PC, `pc\set-archive-rights.ps1` sets them. It only shows what it would do unless you add `-Apply`, saves today's rights first, and has `-Scratch` (a test folder only) and `-Undo`. It says if the share itself gives the share's user Full Control (Change is all the importer needs), and lists any folder the new rule can't reach.
  - On the Mac, `--check-share-rights` tries each allowed and refused operation in that test folder.
  - See PC-SYNC.md, Part C. Leave the rights as they are until both computers run 1.7.0.
- **Each computer has a short name and a label** (`ASTRO_MACHINE_ID`, `ASTRO_MACHINE_LABEL`) beside its id. A short name that breaks the rule (a to z, 0 to 9 and -, at most 32) stops anything that would write it.

### The project layer — "you captured this, now process it" (10 Oct)

Step 1 and step 2 of the Project Layer Spec, then a five-reviewer pass (safety, correctness, Mac/Windows parity, the panel, and the owner's eye) whose findings are folded in. Once frames ship to the archive they are safe but forgotten; now one regenerable file, `projects.json`, remembers per project what is ready to process, in progress, still capturing or done — derived from the facts, never typed in.

- **The contract ships beside the engine** (`contract/`): `targets.json` (one entry per object, with every catalogue code that is the same object — M 31 and NGC 224 are one Andromeda, NGC 7380 and Sh2-142 one Wizard; the common names Brett uses as aliases) and `scopes.json` (each scope, its archive root, and how a frame is recognised as it). Brett edits the installed copy; an update replaces it only while it is unedited (see 12 Oct), otherwise the newer shipped copy lands beside it as `targets.json.new`.
- **`--targets-draft`**: checks every target name in this computer's ledger, and in the other computer's ledger snapshot with its custom names, against the contract and writes `targets-draft.json` with the ones the contract doesn't know (and why, and how many frames), for Brett to add as targets or aliases. It never changes the contract.
- **`--projects`**: writes `projects.json` in the state folder (and a copy in Import Status, once this computer has published there). Per dataset (target + scope): nights, frames, integration, first and last session, where the frames are, the archive folder, and a status —
  - **capturing** while the last session is within the quiet period (14 observing nights, `ASTRO_QUIET_PERIOD_DAYS`);
  - **ready to process** once the quiet period has passed and nothing has been started;
  - **in progress** when the target's folder on the archive holds one of Brett's own masters (from the PC's inventory; every folder that is that target counts, even a renamed one; the Seestar's own `Stacked_*` files never do);
  - **done** when a finished picture in `Final Astro Images` names the target's code and, by filename or folder, the scope. A picture that names no scope counts only for an object with one dataset. A filename naming both Askars marks both.
  - "On this Mac" (or "on this PC") is checked on the disk right now, not remembered: Brett clears his own disks by hand. "On the archive" comes from the ledger. The other computer's frames show as "per its ledger".
  - The one human-set fact is `capture-state.json` (per dataset: auto, open or complete — the format is in HOW-IT-WORKS). A project rolls up to its least advanced dataset, and is flagged for the To-process list as soon as any dataset is ready.
  - Each ship leaves `ledger-snapshot.json` (this computer's ledger rows) in its own `_verify` folder on the archive, and the other computer's `--projects` reads it by itself: the PC's nightly list carries the Mac's sessions without anyone copying a file. A computer that has never imported (the PC, usually) says so and lists the other's. `--with-ledger FILE` adds any other snapshot; a frame in both is counted once (by its bytes). Merged and baseline rows that carry no night are dated from their filename; rows with no scope are warned about, not counted.
  - A ledger that can't be read writes nothing, and with nothing to list from anywhere a good `projects.json` is left alone: an empty list never replaces a good one.
- **`--pc-nightly` ends by rebuilding `projects.json`** from the fresh inventory, so the PC's To-process list is never older than last night. It is the one PC job that reads the ledger, and it only reads it.
- **Astro Desk starts with the projects.** The Archive tab now opens with **To process** and **In progress** from `projects.json`, newest capture first, with the date the list was worked out, its warnings and when the first capturing dataset becomes ready. Each row shows the scope, where the data is, hours and nights, and has an **Open in Explorer** (**Open in Finder** on the Mac) button straight to the target's folder on the archive — through the same archive-only open as before, which never runs anything it finds; it says when it has opened, and why when it can't. A row not yet on the archive says so. Without a `projects.json` the tab names the command to run. The 1.6.0 folder list, with states from the August Observatory scan, sits below as before.
- The installers put `contract/` beside the engine, and the self-test checks it is there. The 1.6.0 folder list, with states from the August Observatory scan, sits under the new sections.

**Found while building, for Brett (the spec asked for mismatches to be flagged):**
- No canonical target id or site existed anywhere; `targets.json` and `scopes.json` are the first.
- A second Seestar of the same model can't be told apart: the ledger records the camera model, never the unit. The Starfront S50 Pro and the Tenerife S30 Pro entries exist but are switched off; their frames count under Shinfield until the importer records the unit at import.
- The two Askars share one archive folder, so a master there that doesn't name the rig counts for both (and says so).
- `Final Astro Images` sits at the archive drive's root, outside the share the Mac mounts, so only the PC checks "done" by default.
- Receipts aren't read: the ledger already holds every session the receipts describe.
- The Mac's sessions reach the PC's rollup through the ledger snapshot each ship leaves on the archive (12 Oct); `--with-ledger` is for any other file.
- 55 of the 131 targets had no sky position after 12 Oct (most came from the Mac's draft); the 13 Oct review added 30 more, so about 25 still sit off the sky map and footprints until `ra` and `dec` are added.
- Open for Brett: whether "open" should beat an old final when a target is re-started for a new season (today the final wins); whether Sh2-171 (Teddy Bear) and NGC 7822 should be one target; colours for the S50 Pro and the Starfront S50 Pro; and the targets seed itself, built from the importer's own name list plus a merge pass, which wants his eye. 12 Oct: the Mac's `--targets-draft` listed 48 names the seed didn't know; 37 targets added (132 then; 131 after the 12 Oct merges), every name from the draft resolves except 'Unknown'. Flagged in the file's `review` note: 'NGC 1893 - Flaming Star' files under NGC 1893 (the Tadpoles' cluster) because the code wins; Fish on a Platter, Middle Heart and Markarian's Chain are name-only until Brett gives them a code; possible merges NGC 6910 with IC 1318 and NGC 6823 with NGC 6820.

### After the ten-reviewer pass (12 Oct)

Brett tried the first build on the PC and found no Dashboard and Open buttons that did nothing. Ten independent reviews (safety, correctness, parity, the panel, the installers, the tests, the docs, the contract, the owner's eye, the archive PC) went over the branch; everything that stood up is folded in. The main ones:

- **The PC's Dashboard works on a computer with no ledger.** It shows the Mac's record (from the ledger snapshot the ship leaves) with a banner saying so and how old it is. The error page is no longer refused inside the panel's frame.
- **Open in Explorer tells the truth.** After a reinstall the panel's old page carried a stale token and every button failed silently. The page now notices a restarted panel and asks to be reloaded; a button that fails says why under the row; one that works says "Opening…" then "Opened".
- **The list itself**: reasons on every row (why it's ready, what's in progress, where the final is), a **Refresh** button that rebuilds `projects.json` on the spot, a scope filter with counts, a legend, warnings you can't miss (an old snapshot, names the contract doesn't know, rows that couldn't be read), and the Done and Still-capturing sections folded away so To process is what you see first.
- **Safety and correctness in the rollup**: a frame in two ledgers is counted once even when its rows differ; a damaged ledger row is reported, not a crash; calibration masters (`master_dark…`) never count as "in progress"; a snapshot from a newer importer is a warning, not a guess; a snapshot older than 36 hours is flagged; `--pc-nightly` runs each step on its own, writes `_verify\pc\nightly-status.json`, and rebuilds the projects after the inventory so the list matches the disk; no computer ever replaces another computer's snapshot; a temporary file left by a crash is cleaned up; the ship log setting must be a plain `shipped….jsonl` name.
- **The contract**: Sadr region, Double Cluster (NGC 869 + 884 as one target), NGC 7822 with Ced 214, Barnard numbers written out, Caldwell numbers on many targets, Melotte 15 on the Heart; long catalogue forms (MESSIER 42, CALDWELL 25) and leading zeros (`NGC 0869`) resolve; scope aliases (`S30Pro`, `30P`); duplicate codes in the file are warned about.
- **The installers**: the Windows installer refuses an Administrator window (it leaves tasks nobody can replace) and prints the three `Unregister-ScheduledTask` lines when an old one is in the way; it takes the account name from Windows itself; the three tasks go through one helper; `sweep.ps1` is set aside only once the Python sweep task is really in place; a stuck sync tick is cut after 15 minutes. Both installers now update an **unedited** installed contract file in place (`contract/shipped.sha256` lists every shipped hash) and leave a `.new` beside the file only when it carries your edits. Mac: the Restart button loses its quarantine flag, the ship agent runs under `caffeinate` so the Mac can't sleep mid-ship, and stays off while the FITs Importer App is in charge. The Mac no longer asks Finder to connect to a PC that is off (a two-second check on port 445 first). `config.json` saved by Notepad (with a byte-order mark) is read.
- **The tests**: a crash half-way now still prints the summary with the crash in it; failure details are kept whole with the line number; skipped checks are counted; the real-rights D7 check is a failure, not a skip, when it can't be set up on a Mac or the PC; both suites print UTF-8 on Windows. New chain IN covers the installers' contract block, the Windows installer's rules, the host probe and the suite's own plumbing.

### The Observatory, fed from the same pass as projects.json (13 Oct)

The Astro Archive Observatory (the August dashboard built from a one-off scan of D:) is now the panel's **Observatory** tab on both computers, and the tabs now lead with the job: Panel, To process, Observatory, Dashboard, Report.

- `--projects` writes `observatory.json` beside `projects.json`, from one pass, and the tab reads it; the two views never disagree and a click costs nothing. `--observatory [FILE]` writes the same page as one standalone file (never under the archive, never over a record file or a file that isn't an Observatory page; `--dry-run` writes nothing). `astro-observatory.html` ships beside the engine; the page loads nothing from the web.
- **The PC's list reaches the Mac.** The PC's nightly job publishes its `projects.json` and `observatory.json` into its own `_verify\pc` folder, and the Mac's To process and Observatory tabs show the PC's complete list while it is under 48 hours old, saying so.
- **Calibration goes with the session** (Brett, 13 Oct): each ASIAir dataset carries the darks, flats and bias linked to its lights (from the Day folder's links, a mosaic's shared set on the target folder, and the archive copies the PC has verified), on the To process row, in the Observatory's drawer night by night and in its latest-sessions card; a ready set with no darks or flats linked says so in its reason. The Seestar calibrates itself and says so. The ledger snapshot now carries each light row's Day folder key and the calibration links, so the PC sees the Mac's. `projects.json` datasets gain `calibration`.
- **What each scope captured last** (Brett, 13 Oct): the Overview opens on it: the last three sessions on each scope, newest first (a session is one object on one night; with UK skies they can be days apart), each a click to the object. Then what to process next, and only then the headline figure and the stats (Brett, 13 Oct, later: "interesting, but not serving my purpose").
- **Click a scope for its timeline** (Brett, 13 Oct): on that first card, each scope's name is a button. It turns the card into a calendar of that scope's projects: one row per object, newest first, a dot per session sized by hours, a thin line across each project's span, the night-by-night activity on top, the quiet period as a shaded band on the right (a dataset whose last dot leaves it becomes To process) and the dataset's state as the dot at the end of each row. Ranges: the last 90 nights, a year, all time (remembered). Hover a dot for the session (hours, frames, filter, calibration); click a row for the object's story; "‹ all scopes" comes back. The hero's per-scope rows and each Equipment card open the same timeline.
- **The page**, after a ten-reviewer pass on the first cut: the four states in the To process list's words everywhere; To process and In progress are the first two figures; a warning strip at the top whenever something changes the answer (an old snapshot, names the contract doesn't know, finals not checked), and the count on the Data health tab; Data health says what was read and where every uncounted row went; every dataset in a target's drawer has **Open in Explorer / Finder** and **Show in To process**; a scope the page didn't know gets its contract colour instead of vanishing; a zero-exposure scope, an empty page or a target with no position can't freeze or blank a tab; the Instagram tracker and the August-era wording are gone.
- **The feed**: targets keyed by the contract's id (two objects sharing a plain name stay two); a Seestar's filter read from its filename and every frame accounted for in the filter mix; ASIAir mosaics flagged; `projects.json` entries carry a stable `key` and, for capturing datasets, the `ready_on` night; `sources.dropped` says why rows weren't counted.
- `contract/targets.json` gained `type`, `constellation`, `ra` and `dec`: the 77 targets the Observatory knew, checked against the catalogues (two region positions corrected, the Double Cluster placed), and 30 more positions added.

**Mac / Windows:** the ship, the calibration and Collect Lights fixes, the panel ship, the inventory of your own frames, the contract, both project commands, the Desk sections, the Observatory tab and `--observatory` are the same on both; on the Mac "in progress" and "done" have the same limits as `--projects`, which is why the PC's published list is preferred there. The PC's jobs (sweep, the archive's inventory and hashing, answering requests) run only on the archive PC, because only its own reads of its own disk count as proof; the Mac asks with `--request` and tries the share's rights with `--check-share-rights`. `Final Astro Images` and the archive inventory are the PC's by default: on the Mac `--projects` says finals were not checked unless `ASTRO_FINALS_DIR` points at a share of that folder, and "in progress" needs the share mounted. PARITY.md lists each difference and why.

717 end-to-end checks (556 engine + 161 panel), 155 new engine checks and 24 new panel checks since 1.6.0 (the panel's inline script and every script block of the Observatory page are parse-checked, and the Desk sections rendered, in node when node is installed; SKIP otherwise). On Linux every check runs except the real-ACL one and the Windows-only owner checks, and all pass except the four U1 and AP lines that only pass on a Mac or a PC (two self-test lines and two astropy ones). Three test bugs found on the PC on 11 Oct are fixed (chain P1 read the Mac's ship log instead of the PC's; the `--hash` check over-counted on Windows; the real-rights D7 check built the `icacls` user from USERDOMAIN/USERNAME, which test mode empties, and now asks `whoami`), and the self-test looks for the Restart button where Windows says the Desktop is (OneDrive on the PC). Last runs on Brett's machines were at an earlier commit (11 Oct: PC 496 engine + 148 panel, Mac 507 engine + 148 panel, all green); both suites must be run again on both computers at this release's commit. PC, 13 Oct, at c72af23: 544 engine checks passed, 0 failed, 9 skipped (the Mac-only lines), and 160 panel checks green; 1.7.0 installed there the same morning, the three tasks registering on the second run of the installer.

## 1.6.0 (2026-10-02): Astro Desk, the archive ready to process

- **A new Archive tab in the panel.** It answers "what haven't I processed yet, and where is it?" after weeks of cloud.
  - **Still to process:** every target folder on the archive that the Observatory last saw as captured, stacked or in processing, biggest first, with a search box. A tick shows every folder, finished ones too.
  - **Click a target** to see its state and the reason for it, hours, lights, nights and filters (from the Observatory's dataset), then what the folder holds: each night (Day folder) with its frame count, the masters, processed files, finished pictures and the Seestar's own live stacks.
  - **Buttons:** Open folder (then drag the nights into PixInsight WBPP, SyQon or Lightroom), Open on any master or picture (it opens in its usual app, so a master opens in PixInsight), Start Siril here (Siril starts with that folder as its working folder), and Copy path.
- **`/archive?target=&code=&scope=`** opens the panel straight on a target. AstroLog's project page links here on the PC.
- **Read-only.** The Archive tab never writes, moves or deletes anything in the archive. It doesn't even use the ship's write probe.
- **Safe opening.** Only folders and image files inside the archive open (FITS, XISF, TIFF, JPEG, PNG, PSD, PixInsight projects). Programs and shortcuts never do, and a path that climbs out of the archive, or a link pointing outside it, is refused. Every open needs the panel's per-launch token.
- **Two new settings** in `config.json`:
  - `ASTRO_SIRIL_EXE`: where Siril is (default `C:\Program Files\Siril\bin\siril.exe`).
  - `ASTRO_OBSERVATORY_DATASET`: the Observatory's dataset (default `E:\Astro Config Data\Observatory\dataset.json` on the PC). Its `D:\` paths are matched to this machine's archive by their last two folders, so the drive letter doesn't matter.

  Without the dataset the tab still lists every folder, just without states.

**Mac / Windows:** the same on both. On the Mac it works when the archive share is mounted. Windows opens with File Explorer and the file's default app; the Mac uses Finder.

538 end-to-end checks (401 engine + 137 panel), all passed on the Mac on 2 Oct 2026, including the 9 new engine checks and 10 new panel checks.

## 1.5.5 — 2026-09-27 — what you can delete from the Mac

- **Space on this Mac.** The dashboard (the Dashboard tab in the panel) has a new section at the top.
  - **What it shows:** how much of what the importer filed on this computer you can delete.
  - **Why it's safe:** a frame counts as **safe to delete** only when the PC's sweep has re-hashed its copy in the archive and it matched. That is the same proof that takes a frame out of the "only on the Mac" count.
  - **Everything else:**
    - Shipped but not yet re-checked: **waiting**.
    - Not in the archive: **only on this Mac**.
    - A different size from the one imported: **changed here**.
    - Anything in those folders that the importer didn't file, such as WBPP or PixInsight work, notes or a leftover `.partial`: **your other files**.

    All of these are always kept.
  - **Each target folder gets:**
    - a coloured bar
    - its path
    - one verdict: the whole folder is safe to delete, or which Day folders are safe on their own, or keep

    A folder that holds anything not safe is never called safe as a whole.
- **`--space`** prints the same thing as text, with the paths of the safe folders.
- **Read-only.** The importer never deletes anything from this computer. You delete green folders yourself in Finder or File Explorer.
- **When it can't tell,** for example because the ledger can't be read, it says so and marks nothing safe.
- **Moved frames are still counted.** Frames gathered into a `lights/` folder by hand or by Collect Lights are found as the ship finds them.
- **Other rows don't count as here.** Back-catalogue rows, and frames already gone from the Mac, are left out of the view.

**Mac / Windows:** the same on both ("this PC" and File Explorer on Windows).

519 end-to-end checks (392 engine + 127 panel), including the 7 new engine checks. Released with 1.6.0, whose full suites passed on the Mac on 2 Oct 2026.

## 1.5.4 — 2026-09-27 — clearer astropy errors, and a quicker panel start

A few small fixes. Normal use is unchanged.

- **When astropy won't load, the importer says why.** astropy is the
  library that reads FITS headers. If it can't be loaded, the message now
  gives the real error (a missing library file, say), not just "astropy
  not installed". When numpy is what fails (on Windows, usually "DLL load
  failed"), that's the line you see, not the first line of numpy's page of
  advice. It also gives the right command for the Python that's running:
  install astropy if it's missing, or reinstall it if it's there but broken.
  - On Windows the command is a line to paste into Terminal (PowerShell),
    `& "…\python.exe" -m pip install --user …`. It names python.exe even
    though the panel runs under pythonw.exe, which shows no pip output.
    Before, the command started with the quoted path alone, which
    PowerShell refuses. The installer's own hint has the same fix.
  - The install check (`selftest.py`) now checks astropy the same way and
    gives the same reason and command. Before, it said "pip install" for an
    astropy that was there but broken, and stopped with an error on any
    failure other than a missing module, skipping its other checks.
- **Nothing is copied until astropy loads.** An import now checks astropy
  before it copies anything, ASIAir and Seestar alike. Before, an ASIAir
  import copied the calibration frames into the Library first and then
  stopped at the first header, leaving them unrecorded; the next import
  took them over without checking their bytes.
- **Only that job fails; the panel stays up.** Before, a scan or import
  that hit this stopped with an empty banner, and the page's automatic
  rescan printed the same red lines again every second. Now:
  - the banner says what happened, for example "scanning failed: astropy
    could not be loaded (…). Install or repair it (the log shows the
    command), then restart the panel.";
  - the log explains once, and later jobs add no more red lines;
  - any other job the engine stops early also gets a banner that says so,
    instead of a blank one.

  On the command line the importer still stops with exit code 1, now with
  the real reason. In the coming desktop app there's no pip command to
  give: it says to reinstall the app, and the banner says to restart the
  app rather than the panel.
- **The panel starts without a network lookup.** Python's built-in web
  server looks up the computer's network name as it starts. The panel never
  uses that name, and in the coming desktop app on the Mac nothing answered
  the lookup, so the panel started 35 seconds late. The panel now skips it.
  How it listens is unchanged: this computer only, one panel per port. The
  Mac's setting that would let a second panel share the port now stays off
  by name, and the tests check it.

**Mac / Windows:** the same on both, except the form of the repair command:
a Terminal command on the Mac, a PowerShell line on Windows (checked on the
Mac by simulating Windows; paste-test it on the PC). The quicker start
matters most for the desktop app on the Mac. On Windows the panel keeps its
one-panel-per-port setting; the Windows half of the new check for that runs
on the PC.

512 end-to-end checks (385 engine + 127 panel), all green on the Mac.

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
