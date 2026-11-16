# Starfront Phase 2 (the pull): the engine as built

Built 16 Nov 2026 on branch `claude/starfront`, on top of 1.10.2, against `BUILD-PROMPT.md` sections D, E, F and H, the settled points at the end of `DESIGN.md`, and what the real telescope showed that day. This note says what landed in `astro-import.py`, `test_v2.py`, `install-windows.ps1` and `selftest.py`, the exact words the commands print, where it differs from the brief and why, and what is not built. Plain words, no em dashes.

Nothing here is committed. `VERSION`, `CHANGELOG.md`, `README.md`, `PARITY.md`, `CLAUDE.md`, `HOW-IT-WORKS.md` and `config.example.json` are untouched (yours). Section G (the clear) is not built: this phase writes nothing on the telescope and deletes nothing anywhere.

## What it does, in short

1. The scan remembers which telescope it met and refuses a different one at the same address (the 16 Nov incident). A pull can never read from a stranger.
2. The telescope's address lives in one place, the guest sign-in happens by itself, a folder of stacks with no subs is shown as "stacks only", and "mixed settings" says what is mixed.
3. The scan runs once a day, decided by the 20 minute watch (after the roof is confirmed closed, or at sunrise). The two-hourly task is gone.
4. `--starfront-pull PROJECT` brings one project's FITS home with a verified copy per file, a second read of the local copy, a second read of the source, a receipt, a ship and a push.

Everything is in the one marked section `STARFRONT SOURCE` of the engine, just before `run_projects`. Three small changes sit outside it: `copy_file_verified` gained an optional `progress` callback (nothing else about the copy changed), the ship knows the Starfront camera's archive root, and the project layer tells a Starfront frame from a home frame at the same camera path.

## Commands

| Command | What it does | Exit |
|---|---|---|
| `--starfront-scan` | as before, plus the identity check, the guest sign-in, the new lines | 0, or 1 (tunnel down, listing incomplete, wrong device) |
| `--starfront-watch` | as before, plus the daily scan | 0, or 1 (tunnel down at night, or the daily scan ran and failed) |
| `--starfront-accept-device` | forgets the remembered telescope; the next scan remembers what it finds | 0 |
| `--starfront-pull PROJECT` | the pull | 0, or 1 (refused, stopped, or a file needs a look) |
| `--starfront-pull PROJECT --dry-run` | every guard, then what it would copy; changes nothing | 0, or 1 when a guard refuses |
| `--starfront-pull PROJECT --rehash-only` | only the second read of the source, for files already home | 0, or 1 (refused, stopped, or a mismatch) |
| `--starfront-target NAME HOURS` | unchanged | |

`PROJECT` is the MyWorks folder's base name, as the scan prints it: `M 45_mosaic`, not `M 45_mosaic_sub`. A name that differs only in upper and lower case is accepted when it is the only match.

On the PC (PowerShell):

    py -3 -X utf8 "$env:LOCALAPPDATA\BrettjoAstro\bin\astro-import.py" --starfront-pull "M 45_mosaic" --dry-run
    py -3 -X utf8 "$env:LOCALAPPDATA\BrettjoAstro\bin\astro-import.py" --starfront-pull "M 45_mosaic"
    py -3 -X utf8 "$env:LOCALAPPDATA\BrettjoAstro\bin\astro-import.py" --starfront-pull "M 45_mosaic" --rehash-only

All of them run on the PC (Windows) or in test mode; a Mac says so and exits 2, as in Phase 1. `--rehash-only` without `--starfront-pull` is refused (exit 2). While a pull holds the import lock, another import or ship says: `A pull from the Starfront telescope is running right now` (a new entry in `LOCK_HOLDER_TEXT`).

For the panel (not built here): `run_starfront_pull(project, dry_run=False, rehash_only=False, now=None, have_lock=False)` returns `{"ok", "project", "copied", "skipped", "problems", "stopped", "home", "reread", "dark", "dest", "shipped", ...}` or `{"ok": False, "refused": True, "reason": "..."}`. The panel takes the import lock for every job it runs, so it must pass `have_lock=True` (the pull then neither takes nor releases the lock). `run_starfront_accept_device()` returns True.

## Config keys

| Key | Default | Notes |
|---|---|---|
| `SEESTAR_DEST_S50PRO_STARFRONT` | beside the home S50 Pro's folder: `<parent of SEESTAR_DEST_S50PRO>\Seestar S50 Pro (Starfront)` | New. With stock settings this is `~/Documents/Astro/Seestar S50 Pro (Starfront)`. In the test-mode guard, in `_live_workbench_roots()` and in the Space view. |
| `STARFRONT_SHARE`, `STARFRONT_SEESTAR_IP` | `\\10.15.10.212\EMMC Images`, `10.15.10.212` | Changed. Set only `STARFRONT_SEESTAR_IP` and the share is built from it (`\\IP\EMMC Images`). Set both and, when they name different hosts, the share's host is used for everything (the tunnel check too) and a CONFIG warning says they disagree. `sf_share_host()` is the one address. |
| `STARFRONT_CAMERA` | `ZWO Seestar S50 Pro (Starfront)` | Changed: a value that is a home camera's name is refused (the default is used, with a warning). |
| `STARFRONT_WORKERS` | 8 (1 to 32) | Now used: copies and source reads in parallel. |
| `STARFRONT_ROOF_CLOSED_HOURS` | 2 | Now used: the pull's roof guard. |
| `STARFRONT_STALL_SECONDS` | 120 | Now used: a copy that moves no bytes for this long is a dropped link. |

For today's address change on the PC, one line in `config.json` is enough, either of:

    "STARFRONT_SEESTAR_IP": "10.15.10.214"
    "STARFRONT_SHARE": "\\\\10.15.10.214\\EMMC Images"

Constants in the engine, not settings: `STARFRONT_ARCHIVE_ROOT = "S50P-Starfront"`, `SF_LEDGER_SAVE_EVERY = 25`, `SF_RETRY_WAITS = (5, 15, 45)`, `SF_LOCAL_FREE_MARGIN = 5 GB`.

## A1. Which telescope is this?

`starfront-status.json` gains `device`: `{darkHash, darkFiles, totalBytes, rememberedAt, share, seenAt}`. `darkHash` is the SHA-256 of the dark library's top-level `[name, size]` pairs, sorted; `totalBytes` is the share's storage size. The scan decides before it opens a single file:

| What the scan finds | Verdict | What happens |
|---|---|---|
| nothing remembered | new | remembered; `▸ Remembering this telescope: darklibrary of 12 files, 111.5 GB` |
| the same dark library (and storage size, when both were read) | match | the scan runs |
| a different fingerprint, but at least one file the last scan listed is still there at the same size and time | changed | accepted and remembered; `▸ The telescope's dark library has changed (darklibrary of 4 files, 111.5 GB); it still holds 4 of the files from the last scan, so it is the same telescope. Remembered.` |
| a different fingerprint and no such file (also when the last scan listed nothing) | wrong | the scan stops, exit 1, the three cache files untouched, alarm raised |
| a remembered telescope whose `darklibrary` cannot be listed | cannot tell | a listing failure: incomplete, caches untouched, exit 1, no alarm |

The refusal, on stderr:

    ✗ The device answering at \\10.15.10.212\EMMC Images is not the telescope the importer knows (remembered: darklibrary of 12 files, 111.5 GB; found: darklibrary of 0 files, 111.5 GB, and none of the 18 files the last scan listed). Nothing was counted and nothing was changed. Starfront may have given the telescope a new address: check it, and put the right one in config.json (STARFRONT_SEESTAR_IP or STARFRONT_SHARE). If the telescope itself was replaced or wiped, run --starfront-accept-device and scan again.

The alarm is a new kind, `starfront-device`, in `ALARM_KINDS`, raised through `_alarm_set` (so: the status line, the panel, the Observatory's status line, one notification and one push, repeated at most once a day). Short text: `Check the Starfront telescope: the device at its address is not the one the importer knows`. It clears by itself on the next scan that finds the right telescope: `✓ The device at the Starfront telescope's address is the telescope the importer knows again.` The status file also keeps `deviceMismatch: {at, found, share}` while it stands.

`--starfront-accept-device` prints:

    ▸ Forgotten: the telescope with a darklibrary of 12 files, 111.5 GB, remembered on 2026-11-06.
    ▸ Forgotten too: the list of 18 files from the last scan, as a way to recognise the telescope. The files in the state folder stay where they are; the next scan writes its own lists over them.
    ▸ The next scan remembers whatever telescope it finds at \\10.15.10.214\EMMC Images. Nothing already pulled is touched.

It writes one field, `device: {acceptNext: true, acceptedAt, forgot, forgotInventoryFiles}`, and deletes or renames nothing. The next scan then treats the old inventory and header caches as empty, keeps the old per-project status under `previousProjects`, remembers the device it finds and writes its own lists.

A wrong device also refuses a pull (and raises the alarm), with `Nothing was copied` in place of `Nothing was counted`. So does a telescope never remembered: `Run a scan first`.

## A2. The address in one place

`sf_share_setting(share, ip)` decides at load (a `STARFRONT_SEESTAR_IP` that is not an address or a computer's name is ignored, with a warning); `sf_unc_host(path)` reads the host out of a UNC path (also the long `\\?\UNC\host\share` form); `sf_share_host()` is what the tunnel probe connects to on port 445 and what the tunnel's messages name. The warning:

    STARFRONT_SHARE points at 10.15.10.212 and STARFRONT_SEESTAR_IP says 10.15.10.214: they disagree. The share's address (10.15.10.212) is the one used, for the tunnel check too. Set only one of the two, or make them the same

## A3. Guest sign-in by itself

`sf_guest_session(share)`: when a listing of the share fails with access denied (a `PermissionError`, or Windows error 5, 86, 1219, 1326 or 2202), it runs, once per host per run:

    net use \\HOST\IPC$ /user:guest ""
    net use "\\HOST\EMMC Images" /user:guest ""

and the listing is tried once more (`sf_signed_in`). Windows only; elsewhere it does nothing. In test mode `net` is never run: the call is recorded in `os-calls.jsonl` as kind `net-use` with both commands. The scan's listing, the pull's listing and the watch's night listing all go through it. On success it prints `▸ Signed in to the telescope's share as guest (10.15.10.214).`

The password is empty because the Seestar has none (FACTS section 1); nothing is stored anywhere.

## A4. Stacks-only folders

A MyWorks folder with stacks (or mosaic panels) and no `_sub` folder at all has status `stacks-only`: `targetHours`, `percent` and `eta` are null, it is never ready and never pushed, a target set for it is ignored, and a pull of it is refused. It stays in the record's project list. Its line:

    ▸ M 42: stacks only (1 stack, 0.05 GB)

A folder of stacks that also has a `_sub` folder (empty so far) is still `collecting` at 0 h. The unit card leaves stacks-only folders out (they have no nights).

## A5. Mixed settings say what is mixed

Every project record has `flagNotes` (a dict, empty when there is nothing to say). For `mixed-settings`:

    "flagNotes": {"mixed-settings": "exposure 10.0s and 30.0s; gain 80 and 200"}

and on the scan's line: `flags: mixed-settings (exposure 10.0s and 30.0s; gain 80 and 200)`. The kinds are `exposure ...`, `filter ...` and `gain ...`, joined with `; `; three values read `10.0s, 30.0s and 60.0s`; a sub whose name carries no filter reads `none in the name`. Gain comes from the one header read per project per night, as before.

## A6. The scan runs once a day

`run_starfront_watch` decides. For each site night (named by its evening, in `STARFRONT_TZ`) the scan runs once, at the first watch run where either

- the roof file has said closed on two readings in a row after it said open that night, or
- the sun is up at the site (then the night is the one that ended that morning).

The status file keeps `dailyScanNight` (the last night done), `dailyScanAt`, `dailyScanLastTry`, `dailyScanTryNight` and `daily: {night, sawOpen, closedRun}`.

- Daytime with nothing owed: `▸ Daytime at the site (the sun is 42 degrees up): nothing to do.` No tunnel, nothing read, as before.
- Daytime with the night's scan owed: the watch runs the scan (which brings the tunnel up through `ensure_tunnel`), then exits at once again on later runs.
- A scan that fails is not marked done. The next try is at most once an hour, and the night is given up when the sun sets again at the site.
- No scan starts while a pull runs (the import lock held by a pull, or a project marked `pulling` by a process that is still alive). A mark left by a pull that died does not hold it up.
- A scan by hand (`--starfront-scan`, or the panel's Scan now) always works. When it succeeds in the window where the daily one was due, it counts as that night's scan.

The watch's lines when it runs the daily scan (the scan's own lines come between the first and the last):

    ▸ Daily scan for the night of Thu 5 Nov: the roof has been closed on two readings in a row.
    ✓ Daily scan done for the night of Thu 5 Nov.

    ▸ Daily scan for the night of Fri 6 Nov: the sun is up at the site.
    ⚠ The daily scan for the night of Fri 6 Nov did not finish ([WinError 64] ...). The watch tries again in about an hour, until the next evening at the site.

    ▸ The daily scan for the night of Fri 6 Nov is still owed. The last try was 20 min ago, so this run waits (one try an hour).
    ▸ A pull from the telescope is running, so the daily scan waits for the next watch run.

(The year is added to the date when it is not the current year.)

Limit to know: the scan runs once per night. If the roof closes, the scan runs, and the roof then opens again the same night, the later subs are counted by the next night's scan.

The installer: section 6b registers only `Astro Starfront watch` (every 20 minutes, the same settings as before) and takes the old `Astro Starfront scan` task away when `Get-ScheduledTask` finds it, quietly when it is not there, with the usual administrator advice when Windows refuses. The file is still UTF-8 with a BOM and CRLF (checked byte by byte after the edit). `pwsh` is not on this machine, so the script has not been parse-checked: please run the installer once on the PC. `selftest.py` lists only the watch task.

The watch task's time limit stays at 10 minutes, as asked. The real scan took 77 s; a scan that ever took over 10 minutes would be cut off by Task Scheduler (nothing would be harmed: the caches are written only at the end, and the watch tries again in an hour).

### Where the morning digest would hook in (not built)

`BUILD-PROMPT.md` section J asks for one push after Texas dawn ("Night 6 Nov: M 42 +2.3 h (14.1 of 20), ... roof open 5.5 h, Seestar full in about 9 nights"). The daily scan is the place:

- Build the text in a new `sf_morning_digest(night, scan, roof_rows, tz)` from `scan["projects"][i]["nights"]` (the entry whose `night` is the night just ended gives the "+2.3 h"; `hours` and `targetHours` give "14.1 of 20"), `sf_roof_open_hours(...)` for that night, and `scan["storage"]["fullInNights"]`.
- Send it from `run_starfront_watch`'s daytime branch, right before the "nothing to do" exit and right after `sf_daily_scan` returns ok: when `dailyScanNight` is the night that ended this morning and a new status field `digestNight` is older, push once and set `digestNight`. That covers both cases: a scan that ran at sunrise (the digest follows it in the same run) and a scan that ran in the night after the roof closed (the digest waits for the first daytime run, so it is always "after dawn").

## B. The pull

### Guards, in the order they are checked, each a refusal in one sentence (`✗ Pull refused: ...`, exit 1)

1. `the starfront-pause flag is set (a ticket or night work is open at Starfront). Remove the flag file when that is over, then pull.`
2. `the importer has not met the telescope yet. Run a scan first (--starfront-scan), then pull.`
3. `it is night at the site (the sun is 74 degrees below the horizon). A pull runs only in Texas daytime, so the telescope is left alone while it works.` Daytime is the sun above the horizon (`sf_sun_altitude` over 0), as the brief says.
4. `the tunnel to Starfront is down: <reason>.` (`ensure_tunnel`)
5. `the B15 roof is open. A pull waits until the roof has been closed for 2 hours.`
6. `the roof could not be read (<why>), and a pull needs to know the roof is closed.`
7. `the B15 roof has been closed for 0.5 h as far as the importer has seen, and a pull waits for 2 hours. Try again later.`
8. `another job holds the import lock (it is named above). Wait for it to finish, then pull.` (the lock is `acquire_lock("starfront-pull")`; the holder's lock is left alone)
9. a ledger that cannot be read, is from a newer importer, or is missing while the mirror holds one (`Restore it first (--restore-ledger), then pull.`)
10. `the telescope's share could not be listed (<error>).`
11. the wrong device (the A1 words, with `Nothing was copied`), or `the telescope's dark library has changed since the last scan. Run a scan first (--starfront-scan), so the importer can check it is the same telescope, then pull.`
12. `there is no project called 'M 99' on the telescope. It holds: M 42, M 45_mosaic, NGC 1499_mosaic.`
13. `M 42 holds only the Seestar's own stacks, with no saved subs, so there is no project to pull.` Also: `<name> has no FITS files on the telescope yet, so there is nothing to pull.` and `the project's name (<name>) can't be used as a folder name on this computer.`
14. `this computer has 3.1 GB free where the frames go (<folder>), and M 45_mosaic needs 20.8 GB with 5.0 GB to spare. Make room first, then pull.`

How "closed for how long" is worked out (`sf_roof_closed_hours`): from the roof log, the first of the unbroken run of closed readings that ends with this one. The roof file's own time is used instead when it is the same on two closed readings in a row (then it is the time of the change), or when this is the first closed reading. A file time that moves while the roof stays closed is only a refresh time, and the readings decide. A time with no zone is read as the later of UTC and the site's clock. A first closed reading with no time counts as 0 h, so the first pull after a morning with no night readings may be refused once and work two hours later. The roof file's real format is still unknown (rollout step 1); this was written to be safe with either kind of time in it.

### A dry run

    ▸ M 45_mosaic → C:\...\Seestar S50 Pro (Starfront)\M 45 - Pleiades (mosaic)
    ▸ 13 files to bring home (37 KB, 3 nights); 0 already home and checked.
      M 45_mosaic_sub Day 1 (night of 2026-11-03): 4 subs, 11 KB
      M 45_mosaic_sub Day 2 (night of 2026-11-04): 4 subs, 11 KB
      M 45_mosaic_sub Day 3 (night of 2026-11-05): 4 subs, 11 KB
      1 stack, 3 KB
      dark library: 12 of 12 files would be copied to C:\...\Seestar S50 Pro (Starfront)\darklibrary (35 KB)
    ▸ Dry run: every guard passed. Nothing was copied and nothing was changed.

A dry run takes and releases the import lock, reads the roof (one more row in `starfront-roof.jsonl`) and notes the tunnel's last good time, as any look does. It writes nothing else.

### What is copied, and where

- `.fit` only: subs from `<Project>_sub` (kind `sub`), panel stacks from `<Project>_pt` for a mosaic (kind `panel`), and every `.fit` in the stacks folder `<Project>` (kind `stack`). Never a JPG, a thumbnail or anything else.
- Into `SEESTAR_DEST_S50PRO_STARFRONT`, laid out as the home Seestar import lays out a project: `<display name>\<Project>_sub Day N\` for subs, the stacks at the project's root, `panels\` for mosaic panels. The display name comes from `seestar_display` (never a prompt).
- One Day folder per site night (`sf_night_from_stamp`, in `STARFRONT_TZ`). A night already numbered keeps its Day (from the ledger's Starfront rows, then from the folders on disk, so a pull that was cut short does not split a night); a new night gets the next number.
- A file whose ledger row is this camera's, verified, at the same size and the same modification time (to the nanosecond, `cameraMtimeNs`) is home and is skipped without being copied.
- A sub or panel whose file changed on the telescope after it was pulled is not copied over the copy that is home: it is listed as a problem. A stack the Seestar saved again is copied again (the home rule for stacks), and the earlier row is kept inside the new one.

### Ledger rows

Written with the same helper as the home import (`_seestar_ledger_add`), so every usual field is there (`filename, size, sha256, origin: "import", device: "seestar", target, displayName, sourceType, camera, scope, exposureSeconds, night, dayNumber, importedAt, dest, verifiedAtImport, cameraMtime`, `subCount` for a stack), plus:

| Field | Meaning |
|---|---|
| `camera` | `STARFRONT_CAMERA`, from the configuration, never from a header |
| `site` | `Starfront` |
| `night` | the site's night |
| `filter` | from the file name |
| `cameraMtimeNs` | the telescope file's modification time, exact |
| `localRehash`, `localRehashedAt` | how the second local read was made (`unbuffered` on Windows) and when |
| `sourceRehashed`, `sourceSha256`, `sourceRehashedAt`, `sourceRead` | the proof of the second read of the source (`sourceRehashed` is false until then) |
| `clearBlocked`, `sourceMismatches`, `setAside` | after a source mismatch (below) |
| `earlier` | the row this one replaced, slim, when a file was fetched again |

Keys: the plain camera path, or `<path>|cam=ZWO Seestar S50 Pro (Starfront)` when another camera's row already holds that path, exactly as two home Seestars are kept apart (`State.key_for`).

### The copies

`STARFRONT_WORKERS` threads copy (`sf_run_jobs`); the main thread alone adds ledger rows and saves the ledger (after every 25 files and at the end, so a pull that is cut short keeps what it finished). Each file:

1. `copy_file_verified` (a `.partial`, the hash taken while copying, the copy read back, the rename), through `_sf_local_copy`.
2. The local copy is hashed again with `hash_file_unbuffered` and must equal the stream's hash (and the size must equal the listing's). If not: the copy is moved (never deleted) into `<Starfront folder>\_Quarantine\starfront-mismatch\<its own path>`, as the PC's sweep sets an unfinished archive copy aside; no ledger row is written; the file is listed as a problem; nothing on the telescope is touched.

    ⚠ Light_M 81_30.0s_IRCUT_20261105-210300.fit: the local copy did not read back the same a second time. It was set aside and not recorded; the file stays on the telescope. Pull again to fetch it afresh.

A dropped link is either one of the Windows errors 53, 59, 64, 67, 121, 1231 or a copy that moves no bytes for `STARFRONT_STALL_SECONDS`. On a drop: `ensure_tunnel`, then that file again after 5, 15 and 45 seconds:

    ⚠ The link dropped while copying Light_M 33_30.0s_IRCUT_20261105-210100.fit (OSError: [WinError 64] ...). Trying it again in 5 s (try 2 of 4).

A fourth drop of one file stops the pull: no new file is started, the copies in flight finish or fail by themselves, the ledger is saved, no `.partial` is left, and the command ends with exit 1:

    ⚠ The pull stopped: the link to the telescope dropped 4 times while copying <file> (...).
    ✗ M 33: the pull stopped part way. 3 of 4 files are home and recorded. Run it again to carry on from there.

The same sentence goes out as a push. Running it again copies only what is not home.

### The second read of the source

After the copies, every file of the project that is home and not yet proven is read again from the telescope with `hash_file_unbuffered` and compared with its row's `sha256`. It is proof only when the read was unbuffered: then the row gets `sourceRehashed: true`, `sourceSha256`, `sourceRehashedAt`, `sourceRead: "unbuffered"`. The first file says whether this computer can read past its cache; if it cannot, the rest are not read at all (it would double the traffic and prove nothing):

    ▸ Reading 13 files again from the telescope, to prove the copies (this doubles the traffic).
    ✓ Source check: all 13 files read again from the telescope and matched.
    ▸ Source check: this computer read the telescope's file through its own cache, so the second read proves nothing here and was not counted (the share would not allow a read past the cache).
    ▸ Source check: 9 of 13 files proven. Run --starfront-pull with --rehash-only to finish it.

A source file that reads differently from its copy: the local copy is set aside as above, the row gets `verifiedAtImport: false`, `sourceRehashed: false`, `clearBlocked: "source-mismatch"` and an entry in `sourceMismatches` (`at, sourceSha256, sourceSize, read, copySha256, setAside`), the file is a problem of the pull, and the project is not marked pulled:

    ⚠ <file>: read again from the telescope it is not the file that was copied. The local copy was set aside (<where>). The file stays on the telescope, and the importer will not clear it. Pull again to fetch it afresh.

`--rehash-only` runs this step alone, under the same guards. It is not yet known whether Windows will allow an unbuffered read on the Seestar's share: the first real pull will say (the "through its own cache" line above is what you would see if it does not).

### Afterwards

- The dark library: every file under the telescope's `darklibrary` (up to four folders deep) is copied to `<Starfront folder>\darklibrary\`, verified and read back the same way, only when new or changed. A dark that changed keeps its earlier copy under `darklibrary\_earlier\<time>\`. `▸ Dark library: 2 files copied, 10 already here (...).`
- The receipt, as the Seestar import writes one, in `<receipts>\Seestar S50 Pro (Starfront)\seestar-[pc-]<time>.json`:

      {"version": 1, "source": "seestar-import", "via": "starfront-pull",
       "telescope": "Seestar S50 Pro (Starfront)", "site": "Starfront", "timezone": "America/Chicago",
       "importedAt": "2026-11-16T164700", "hours": 0.06, "nights": ["2026-11-05", "2026-11-06"], "nightCount": 2,
       "panelsCopied": 1, "complete": true,
       "project": {"name": "M 45_mosaic", "filesHome": 9, "hoursHome": 0.06, "filesOnTelescope": 9, "sourceRehashed": 9},
       "sessions": [{"targetDisplayName": "M 45 - Pleiades (mosaic)", "seestarProjectName": "M 45_mosaic",
                     "isMosaic": true, "dayNumber": 1, "night": "2026-11-05", "framesCopied": 4, "framesInFolder": 4,
                     "hours": 0.03, "stackedCount": 7, "stacks": [{"night", "subCount", "filename"}],
                     "fitsFolderPath": "...\\M 45_mosaic_sub Day 1"}, ...]}

  One session per Day folder this pull copied into. `hours` and `nights` are what this pull brought; `framesInFolder` is the Day's total in the ledger. A pull that stopped part way still writes a receipt for what came home, with `complete: false`.
- The ship: `ship_after_import(state)`, the same call the home import makes. `SHIP_ROOTS` now knows the Starfront camera: `S50P-Starfront`, the contract's `archive_root`. Before this change a Starfront row would simply never have shipped.
- The status file's entry for the project: `status` is `pulling` (with `pullPid`) while it runs, then `pulled-awaiting-clear` when every `.fit` of the project is home, else what it was before; `pulled: {files, hours, subs, of}`, `sourceRehashed` (a count), `pulledAt`, `pulledSignature`.
- The push (and the same as a desktop notification): `M 45_mosaic pulled and verified` when the proof is complete, `M 45_mosaic pulled; source check still to do` when it is not, the "stopped part way" sentence when it stopped, and `M 81: 1 file needs a look after the pull (listed in the importer's output). Nothing on the telescope was changed.` when a file was a problem.
- The mirror and `projects.json` / `observatory.json` are refreshed (by the ship when it ran, else directly).

The lines of a clean pull:

    ✓ 13 files came home and were checked twice on this computer (37 KB).
    ▸ Reading 13 files again from the telescope, to prove the copies (this doubles the traffic).
    ▸ Dark library: 12 files copied, 0 already here (...\darklibrary).
    ✓ Source check: all 13 files read again from the telescope and matched.
    ✓ AstroLog receipt saved → Seestar S50 Pro (Starfront)/seestar-pc-2026-11-16T164700.json
    ✓ M 45_mosaic pulled and verified (13 files, 0.1 h).

A second pull with nothing new: `▸ M 45_mosaic: everything on the telescope is already home (13 files, 0.1 h).`

### "Pulled" and a project that keeps growing

`pulled-awaiting-clear` stands only while the telescope holds exactly what the pull saw (`pulledSignature`, a mark of every `.fit`'s path, size and time; the scan computes the same mark as `signature`). When the project has grown, the next scan judges it by its hours again (`collecting` or `ready`) and still says what is home: `... [collecting]  home: 9 files, 0.1 h`. A second pull then copies only the new files.

### Nothing is written on a share, and darks are never deleted

Every write the section makes goes through `_sf_local_makedirs`, `_sf_local_copy` or `_sf_local_move`, and each asks `sf_guard_write(path, deleting=False)` first. It refuses (`StarfrontRefused`) any path on the telescope's share or the roof share, whatever the write, and, for a deletion, any path under a `darklibrary` folder, on the telescope or on this computer. A dark may only move inside its own dark library folder (the earlier copy, or a bad copy set aside under `darklibrary\_Quarantine\`). There is no delete call in the section at all; a test reads the source for one.

## The record (`observatory.json`)

- `starfront.projects[]`: `status` may now be `stacks-only`, `pulling` or `pulled-awaiting-clear`; every project carries `pulled: {files, hours}`, `sourceRehashed` (a count), `pulledAt`, `flagNotes` and `signature`. These come from the status file at build time, so a pull shows without waiting for the next scan.
- `starfront`: `device: {remembered, words, rememberedAt, mismatchAt}`, `dailyScanNight`, `darklibraryHome`.
- The unit card. Once pulled rows exist, the ordinary logic makes a card for `S50P-STARFRONT` from the ledger. `sf_unit_and_scope` then rebuilds that one card from both sources and puts it back after the home S50 Pro's, with the Phase 1 label `S50 Pro · Starfront`, `site`, `starfront: true` and `short`: a project that is home is shown by its ledger rows (the project layer's hours, nights and state), and a project still on the telescope (`collecting`, `ready`, `pulling`) by the scan's facts. The scope entry keeps the ledger's numbers and gains `site` and `starfront`.
- `starfront_panel_status()` gains `device`, `deviceMismatchAt`, `dailyScanNight`, `pulling`.

## For whoever owns the page and the panel

Nothing in `astro-observatory.html` or `astro-app.py` was touched, and the panel suite is green as it is. Things the page does not know yet:

- `stacks-only`: the page's `sfStatus()` falls back to the word itself and draws a 20 h target bar at 0 %. It wants its own word ("Stacks only") and no bar. `targetHours` and `percent` are null for it.
- `flagNotes["mixed-settings"]` is there to show beside the flag.
- `pulled`, `sourceRehashed`, `pulledAt` per project, and `starfront.device` / `starfront.dailyScanNight`.
- The panel has no Pull button, no dry run and no accept-device button. `run_starfront_pull(..., have_lock=True)` is the call to make under the panel's own lock.
- The page still says "on, every 2 hours from the PC" (`astro-observatory.html`, the Starfront view's "Scanning" row). It is once a day now; `starfront.dailyScanNight` says which night the last daily scan was for.

## Test hooks (test mode only)

`ASTRO_TEST_SF_NOW` (an ISO time the commands take as now), `ASTRO_TEST_SF_DISK` (`total,used,free` in bytes for the share), `ASTRO_TEST_SF_DENY_ONCE` (the share's first listing is refused), `ASTRO_TEST_SF_DROP` and `ASTRO_TEST_SF_STALL` (a part of a file name, `:N` for the first N tries: that copy fails with error 64, or moves no bytes), `ASTRO_TEST_SF_TIME_SCALE` (multiplies the stall time and the 5, 15, 45 s waits), `ASTRO_TEST_SF_SLOW_MS` (each copy takes this long, so copies overlap), `ASTRO_TEST_SF_CORRUPT_LOCAL` (a part of a file name: one byte of that local copy is changed after the engine's own check), `ASTRO_TEST_UNBUFFERED` (`1`: the source read counts as unbuffered, `0`: as buffered). Phase 1's hooks are unchanged.

## Tests

Chain SF in `test_v2.py` went from 49 to 115 checks: 65 new ones under the heading "Chain SF, Phase 2", and one more in the Phase 1 part (the installer check became two). One of the new checks is skipped on Windows (it would make Windows try to reach a made-up address). The new checks were also run against copies of the engine with one thing broken at a time (identity always matching, the write guard switched off, no second local read, a buffered read counted as proof, the ship not knowing the camera, the daily scan never due, the path identity without the camera, stacks-only not special, every file kind copied, proven files not skipped): each was caught by at least one check.

Existing checks whose expectation was changed, on purpose:

1. Chain IN, "install-windows.ps1 registers all five tasks": now four (`Register-AstroTask` is called 4 times), with the reason in its name.
2. Chain SF, "the watch in daytime ... exits at once": the fixture now marks the night's scan as done first (one line), because a daytime watch with a scan owed now runs it. The expectation itself is the same.
3. Chain SF, "the Starfront listing never calls os.walk or os.listdir ... functions are prefixed": the name rule also allows a class named `Starfront<Word>` (for `StarfrontRefused`).
4. Chain SF, the installer check: was "registers 'Astro Starfront scan' and 'Astro Starfront watch'", now two checks: only the watch is registered, and the old scan task is unregistered when found.
5. Chain SF, the selftest check: lists only the watch.

Nothing in chain W1 needed changing (it reads section 7, which is untouched). No check in `test_app.py` was changed.

## Where this differs from the brief, and why

1. **Identity, two cautions added.** (a) With nothing remembered but a list of files from an earlier scan, a device holding none of those files is refused too. Without this, the first scan after the update would have remembered whichever device answered, the stranger included. (b) An empty dark library is the same on every Seestar of a model, so a match on an empty one also needs one known file when the last scan listed any. Both can only refuse more, never less; `--starfront-accept-device` is the way out.
2. **A changed dark library refuses a pull** until a scan has accepted it ("Run a scan first"). Only a scan ever updates what is remembered.
3. **The default Starfront folder** is beside the home S50 Pro's folder rather than a fixed `~/Documents/Astro/...`. With stock settings it is the same place; on a PC whose workbench was moved in `config.json`, 100 GB of frames follow the workbench instead of landing in Documents (which on your PC may be under OneDrive).
4. **A free-space guard** on this computer's disk was added to the pull (5 GB to spare). Not in the brief; a project is 20 to 40 GB.
5. **The skip rule is stricter**: same path, size and camera, and also the same modification time. A file saved again at the same size is not taken for the one already home.
6. **A changed sub is reported, not overwritten.** A changed stack is copied again, as the home import does.
7. **Every stack `.fit` is copied**, not only the "keepers" the home import picks. The brief says stacks' `.fit` from the stacks folder; `--tidy-stacks` does not look at this folder.
8. **No hidden `.imported_files` manifest** is written in the project folder (the home import writes one; nothing reads it for a Seestar). One less write.
9. **The receipt has one session per Day folder**, each with `night` and `hours`, plus `framesInFolder`, `via`, `timezone`, `nightCount`, `panelsCopied`, `complete` and `project`. `nights` is the list of nights, not a count.
10. **Two more pushes** than the two named: the "stopped part way" sentence, and "N file(s) need a look".
11. **`clearBlocked` stays on a row for good**, also after a later pull has fetched the file afresh and proved the new copy (the new proof is recorded beside it). The brief says the row is marked so Phase 3 can never clear that file; whether a later, clean proof should lift the mark is a Phase 3 decision.
12. **`copy_file_verified` gained a `progress` argument** so a stall can be seen. With it left out, the function is byte for byte what it was.
13. **The stall is cooperative.** Python cannot stop a thread that is stuck inside a read. The stalled try is told to stop and clears its own `.partial` the moment the read returns; the file is not tried again while that try is still alive, and a try that never returns ends the pull with a line naming the file. On Windows a dead link normally fails a read by itself within a minute or two.
14. **The project layer's frame identity** (`_row_idents`) now carries the camera for Starfront rows. It used to treat "same camera path and same size" as the same frame whatever the camera, and every S50 Pro sub is the same size, so a Starfront sub and a home sub stamped in the same second would have been counted once. Home rows are identified exactly as before.
15. **`ALARM_KINDS` order**: `starfront-device` is last, so an archive alarm still leads the status line when both stand.
16. **A dry run reads the roof and the tunnel** (one roof log row, the tunnel's last good time). It cannot check those guards otherwise.
17. **The roof's "closed for 2 hours"** is worked out as described above, because the roof file's format is still unknown.

## Not built

- Section G, the clear, and anything that writes on the telescope. `STARFRONT_AUTO_CLEAR` is still read and unused. Nothing sets `clearedFromCamera` on a Starfront row.
- The panel's Pull button and the page's new states (another worker's).
- The morning digest (section J) and the newest-stack thumbnail.
- A guest sign-in for the roof share (`\\172.16.5.21\sfro-customer` wants user guest with the password guest; the engine does not type passwords). If Windows refuses that share, the roof reads "unknown" and a pull is refused with the reason.
- The alpaca roof feed as a fallback.
- The `seestar-wormhole` assessment (DESIGN says Phase 2 reports on it): not done.
- A source mismatch found by `--rehash-only` after the frame was already shipped leaves the earlier copy on the archive (nothing is ever removed there). The copy fetched afresh then has the same archive name and different bytes, which the ship reports as a problem. It wants a decision (file it beside the first, as re-saved stacks are) before Phase 3.
- Not tested, because it cannot be on this machine: `net use` for real, `sc` for real, an unbuffered read over SMB, the installer's new lines under PowerShell, and the whole pull against the real share. The first real `--dry-run` and the first real pull are rollout stop 3.

## For your documents and the project map

- `PARITY.md`: the pull, `--starfront-accept-device` and the daily scan are PC only, like the scan; new key `SEESTAR_DEST_S50PRO_STARFRONT`; `STARFRONT_SEESTAR_IP` alone now sets the share; the two-hourly task is gone.
- `config.example.json`: the same keys.
- `CLAUDE.md`: the layout note for this build (the alarm kind, the hooks, chain SF's count), and the engine total: 811 checks on this machine (745 before, plus 66).
- The project map: the receipt format link (AstroLog will meet a new telescope name, `Seestar S50 Pro (Starfront)`, and the new fields `site`, `hours`, `nights`); the archive layout link (a new root, `S50P-Starfront`); the Observatory record link (the new project fields and statuses); and the open question of whether an unbuffered read works on the Seestar's share.
