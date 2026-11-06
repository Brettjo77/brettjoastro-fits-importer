# Starfront: code map for the build

Read-only survey of branch `claude/starfront` (engine `VERSION = "1.9.0"`, `astro-import.py:54`), made on 6 Nov 2026 to check every reference in `docs/starfront/BUILD-PROMPT.md` against the code. Every claim below carries a `file:line`. Line numbers are for this branch as it stands; a later edit above a line moves it.

Files: `astro-import.py` (the engine, 12,987 lines), `astro-app.py` (the panel, 2,993), `test_env_helper.py` (521), `test_v2.py` (7,812), `test_app.py` (2,799), `install-windows.ps1`, `contract/scopes.json`, `docs/ux-observatory-25oct/PHASE2-CONTRACT.md` and `PHASE2-RECORD-FIELDS.md`.

Short verdict: the brief's REUSE list is real, every named function exists, and most of the design fits. The things the code contradicts are collected in section 5; the three that change the design are (a) the SAFE clear removes the emptied top-level folders today, (b) `copy_file_verified` deletes its `.partial` on failure and never resumes it, and (c) the live Observatory record is written by `run_projects` through `observatory_from`, not by `run_observatory`, and `E:\Astro Config Data\Observatory\dataset.json` is a different, older file.

---

## 1. The REUSE list, confirmed or corrected

### scan_seestar (`astro-import.py:8474` to `8720`)

- Finds the volume with `seestar_volume(force=True)` (8475, defined at 8315), identity with `seestar_model_ex(vol)` (8477).
- Walks `MyWorks`: every `*_sub` folder (8541 onwards) with its subs through `_fits_files(sub_dir)` which is a full `os.walk` (8459 to 8472), the sibling project folder's stacks at depth 1 (8563), the stack JPGs (8569 to 8574), the per-sub JPGs (8579 to 8586), orphans (8592 to 8596); stack-only projects (8619 to 8648); `*_mosaic_pt` panel sets (8650 to 8659); the non-DSO mode folders (8666 to 8687); everything else goes into `unhandled` (8689 to 8707), so a `darklibrary` folder would be listed there as "NOT handled".
- `fentry` (8483 to 8491) does one `os.stat` per file and records `path, relpath, filename, size, mtime`. Over a VPN that is one round trip per file; the brief's incremental `starfront-inventory.json` is new code, nothing here caches.
- Free space: `shutil.disk_usage(vol)` at 8710, in a try/except OSError. On Windows this call accepts a UNC root.
- Returns (8714 to 8720): `device, volume, model, camera, dest, targets, panel_sets, non_dso, relpaths (a set), disk, other, unhandled, identityGuessed, incomplete, extra_volumes`.
- `is_new` (8518 to 8528) asks `state.is_imported(relpath, size, camera)` (1565) and `_camera_changed` (8808), and the other computer's record (`other_record()`, 4104).

### seestar_model_ex and _seestar_creator_model (`8359` to `8434`; `8339` to `8355`)

- Identity comes from FITS `CREATOR` headers: up to three `.fit` files per top-level `MyWorks` folder are opened with astropy (8376 to 8395, the header read at 8387), plus loose files at the root (8396 to 8409). Two identities or an unknown one raise `RuntimeError` (8411 to 8421). No readable header: a folder-name guess, flagged `guessed` (8422 to 8428).
- The camera name is `f"ZWO Seestar {model}"` (8429) and the destination is picked by model (8430 to 8433): the S50 Pro goes to `SEESTAR_DEST_S50PRO` (`330`).
- Consequence for Starfront: this function would name the Texas unit `ZWO Seestar S50 Pro`, the same as the home S50 Pro, and send it to the home destination. The brief is right to take the camera name from the share path and never call this for Starfront. It also reads headers over the VPN, which the brief wants to avoid.

### _seestar_file_night (`8817` to `8827`), _sub_meta (`8850` to `8861`), observing_night (`1181` to `1185`)

See section 2. In one line: both are naive local-clock parses followed by "subtract 12 hours", no timezone anywhere.

### _seestar_day_number (`8829` to `8848`)

Counts `"<label> Day n"` folders on disk under the destination project folder (8831 to 8833), takes the larger of that and `state.max_day_number(target, device="seestar", camera=camera)` (8834 to 8836, defined at 1576), then continues the previous Day when a night in `incoming_files` already sits in it (8840 to 8847, with a bare `os.listdir(prev_dir)` at 8845 on the local destination). Numbering is per target per camera per destination folder. A separate Starfront destination root plus a distinct camera name keeps its Days apart from the home S50 Pro's, as the brief says in D.

### copy_file_verified (`2115` to `2152`)

- Streams `src` into `dst + ".partial"` hashing the stream as it goes (2126 to 2130), fsyncs (2131 to 2132), `shutil.copystat` (2133), checks size (2134 to 2136), then re-hashes the partial with `_hash_dest_uncached` and compares (2138 to 2142), `os.replace(partial, dst)` (2143), `preserve_creation_time` (2144, Mac only).
- On ANY exception the partial is removed and the exception re-raised (2146 to 2151). There is no resume: a restarted copy starts from zero. The brief's "restartable: copy_file_verified with .partial files" is true only in the sense that a failed file leaves no partial behind and is copied again whole next run, because it never reached the ledger.
- `dst` goes through `_win_long` (2120, defined 342 to 353), which prefixes `\\?\` or `\\?\UNC\` for paths over 240 characters.
- Single stream, blocking. The brief's parallel workers wrap this per file; note `State.add_file` (1596) and `_dirty` are not thread-safe, so ledger rows must be added from one thread.

### hash_file_unbuffered (`565` to `584`) and the read mode

- Returns `(sha256, size, read)`. On Windows it tries `_win_hash_unbuffered` (587 to 640): `CreateFileW` with `FILE_FLAG_NO_BUFFERING` into a page-aligned buffer, and returns `"unbuffered"` (640). When the volume refuses with error 87 it returns `None` (613 to 615, 629 to 630) and the caller falls through to an ordinary Python read that reports `"buffered"` (579 to 584). On the Mac and Linux it is always the ordinary read, `"buffered"`.
- A UNC path is passed to `CreateFileW` as given (603 to 605: only a non-UNC path gets the `\\?\` prefix), so a Starfront source file can be opened unbuffered over SMB and the mode reported honestly. Whether the SMB redirector honours `NO_BUFFERING` on that share is for rollout step 1 to confirm; if it refuses, every re-hash will say `"buffered"` and the brief's rule ("a re-hash counts only if unbuffered") would block every clear.
- The docstring (566 to 570) says "a file on THIS computer's own disk": the function was written for the archive sweep, not for a share.

### _hash_dest_uncached (`2090` to `2105`)

Opens the file and sets `fcntl.F_NOCACHE` only when the `fcntl` module imports and has that flag (2095 to 2099). macOS has it; Linux's `fcntl` has no `F_NOCACHE`; Windows has no `fcntl` module at all, so the import fails and the read is a normal cached read. Confirmed: it bypasses the cache only on the Mac. On the PC the post-copy check in `copy_file_verified` re-reads the just-written `.partial` from the cache, which is why the brief adds a later `hash_file_unbuffered` pass.

### _seestar_ledger_add (`8722` to `8747`)

Writes one row with: `filename, size, sha256, origin "import", device "seestar", target, displayName, sourceType, camera, scope (camera without "ZWO "), exposureSeconds, night, dayNumber, importedAt, dest, verifiedAtImport True` (8724 to 8731), `cameraMtime` as the float `st_mtime` (8732 to 8739), `subCount` for stacks (8740 to 8741), then `state.add_file(relpath, **entry)` (8742). `sourceType` values in use: `sub, stack, panel, media, sub-jpg, stack-jpg, mw, mw-stack, mw-jpg`. There is no `site`, `sourceRehashed` or `sourceSha256` field anywhere in the engine today (grep finds none).

### State.add_file (`1596` to `1604`) and State.key_for (`1548` to `1558`)

`add_file`: a row with `origin "import"` and `verifiedAtImport` but no `sha256` is downgraded to `verifiedAtImport False, checksumSkipped True` (1599 to 1602); the camera is taken from `fields["camera"]` only when `device == "seestar"` (1603); the key is `key_for(relpath, cam)`.

`key_for`, quoted:

```
def key_for(self, relpath, camera=None):
    if camera is None or not self.ledger:
        return relpath
    files = self.ledger["files"]
    q = relpath + CAMERA_KEY_SEP + camera
    if q in files:
        return q
    e = files.get(relpath)
    if e is None or _row_camera(e) in (None, camera):
        return relpath
    return q
```

`CAMERA_KEY_SEP = "|cam="` (1320). The plain key belongs to whichever camera got there first; a second camera's row for the same path is keyed `"<path>|cam=<camera>"`. `_row_camera` (1326 to 1329) treats a Seestar row with no camera as the S30 Pro. `ledger_relpath` (1322) strips the suffix. So with the camera name `ZWO Seestar S50 Pro (Starfront)` a Texas sub at `MyWorks/M 42_sub/x.fit` and a home S50 Pro sub at the same path get two rows, and `is_imported` (1565 to 1574) answers per camera. That is the whole "Starfront and home rows don't collide" guarantee; it rests on the camera string being different.

### mark_cleared (`1614` to `1657`)

Given the relpaths seen on ONE device (and camera), flags every row of that device/camera not in the set as `clearedFromCamera True, clearedNoticedAt` (1632 to 1634) and un-flags rows that are back (1637 to 1642). An empty set never clears (1621 to 1622). Called from `State.seestar_seen` (1659 to 1679) only when the scan is complete and the identity wasn't guessed (1668 to 1671). A Starfront scan that calls `seestar_seen` with its own camera name keeps the home S50 Pro's rows untouched.

### history_event (`1521` to `1528`)

Appends `{"v", "ts", "event", **fields}` to `history.jsonl` in the state folder; a write failure only warns. No lock.

### _atomic_write_json (`1290` to `1318`)

Writes `<path>.<pid>.<thread>.tmp`, fsyncs, then `os.replace` with up to 40 retries a quarter-second apart when a reader holds the file (1299 to 1311); removes its own tmp on failure. Right for `starfront-inventory.json` and `starfront-targets.json` in `STATE_DIR`.

### seestar_safe_cleanup (`9510` to `9629`) and _seestar_unproven_files (`9385` to `9477`)

See section 3 for the gate step by step. The mtime tolerance the brief calls "15-minute multiples up to 14 h" is `_mtime_close` (8794 to 8806), quoted:

```
def _mtime_close(a, b):
    try:
        d = abs(float(a) - float(b))
    except (TypeError, ValueError):
        return True
    if d <= 2:
        return True
    q = d % 900
    return d <= 14 * 3600 + 2 and (q <= 2 or q >= 898)
```

Used by `_camera_changed(e, mtime)` (8808 to 8813), which only judges rows that carry `cameraMtime`. Note the first branch: a row whose `cameraMtime` isn't a number counts as unchanged. The brief's EXACT mtime rule for Starfront has to be a separate comparison (and compare `st_mtime_ns`, as the inventory row does at 6545, not the float).

### _jpeg_twin_proven (`9479` to `9508`)

A JPG in a folder is exempt when a same-stem `.fit`/`.fits` sits in the same folder (listed with `os.listdir(root)` at 9490, inside try/except OSError at 9489 to 9495, so a listing failure means "no twin" and the JPG blocks) and that FIT's row is `verifiedAtImport` at the current size with an unchanged camera mtime (9500 to 9507). The exemption is applied only in `_sub` folders and only while `SEESTAR_IMPORT_SUB_JPEGS` is off (9461 to 9469). The rule holds unchanged for a Starfront `_sub` folder.

### run_ship (`5588` to `5613`) and _ShipLock (`5132` to `5173`)

`run_ship` needs a ledger (5590), a valid machine slug (5594), a reachable archive (`_ship_mount`, 5599, defined 5408), then takes `_archive_ship_lock` (5607, defined 5175) and runs `_run_ship` (5651, called at 5612) under it, releasing in `finally`. `_ShipLock` renews `_verify/lock/ship.lock` every `SHIP_LOCK_RENEW_S` (60 s, 5114) on a daemon thread (`_loop`, 5170 to 5173; `renew`, 5153) and sets `lost` if the file stops being ours. On the PC the archive is local `E:\Astro Image Data` (`ARCHIVE_MOUNT` default, 290 to 291); a panel import on the PC ships C: to E: at once through `ship_after_import` (5617 to 5640, called from the panel at `astro-app.py:655`). Receipts reach the archive through `publish_receipts` (5813 to 5850), exclusive create into `_verify/<side>/receipts/<scope>/`.

### notify (`1058` to `1093`) and NOTIFY_FN (`998`)

Order: `NOTIFY_FN` if set (the desktop app sets it; nothing in this repo does) (1062 to 1067); test mode records `{"kind": "notify", message, title, sound}` in `os-calls.jsonl` and returns (1068 to 1070); Windows runs a PowerShell toast through `_powershell(_WIN_TOAST, ...)` (1071 to 1079; `_powershell` at 470 to 481 also only records in test mode; `_WIN_TOAST` at 484 to 493); Mac uses `osascript display notification` (1081 to 1093); Linux does nothing. The web panel does not receive `notify()` output: it captures stdout, and calls `eng.notify` itself after an import (`astro-app.py:665`); the watcher calls it too (`astro-watch.py:181, 187`). There is no HTTP client anywhere in the engine (no `urllib`, `http.client` or `requests` import), so the brief's `NOTIFY_PUSH_URL` POST is new code; it must be recorded in test mode like every other side effect, never sent.

### run_observatory vs run_projects / observatory_from: which is live

- `run_projects` (12441 to 12505) is the live path: `build_projects` (11158) with `collect`, then `observatory_from(doc, collect, state, pending=read_scan_summary())` written to `observatory.json` in the state folder (12491 to 12494), beside `projects.json`. It runs at the end of `--pc-nightly`, from the panel's `/api/projects/rebuild` (`astro-app.py:1566` to `1598`), and after ships. The panel's `/observatory` (`astro-app.py:1408`) serves the page with `load_observatory(prefer_published=True)` (12334).
- `run_observatory` (12235 to 12290) is `--observatory [FILE]`: a standalone HTML file through `build_observatory` (12187 to 12191), which calls the same `observatory_from`. It is a convenience export, not the record the panel and the phone read.
- `E:\Astro Config Data\Observatory\dataset.json` is `OBSERVATORY_DATASET` (853 to 857), the August 2026 scan's file read by `load_observatory_dataset` (4622 to 4630) for the Archive tab's folder list (`archive_index`, 4632). Nothing writes it; it is not the Observatory's live dataset. The brief's item 2 should target `observatory_from`.
- `observatory_from` (11840 to 12185) builds, per dataset: `sessions[]` one per night (11917), `targets[].programmes[]` (the `prog` dict, 11973 to 12003, phase 2 fields at 12001 to 12003), `unit_rows` (12004 to 12005), the `units` list through `_obs_units(out_scopes, contract, unit_rows, in_window)` (12055) and the return dict at 12140 to 12185 (`"units"` and `"thisMonth"` at 12172, `"recordsUpTo"` 12173, `"activeWindow"` 12174, `"scopes"`, `"targets"`, `"sessions"` at 12176).
- `_obs_units` (11806 to 11838): one unit per Seestar scope in `out_scopes` (11826 to 11829, label from `_scope_short`, 11108), the two Askars collapsed into "ZWO" (11830 to 11837); scopes with `"unit"` in `match` are skipped at 11816. `_obs_unit` (11761 to 11804) carries `current, moreReady, strip, latestDone`. Where a Starfront unit card goes: once Starfront rows resolve to the `S50P-STARFRONT` scope (see `resolve_scope` below) a unit card appears by itself with `kind "seestar"` (scope kind is decided by "seestar" in `match.camera`, 11847 to 11851). A `starfront` section (projects with hours, targets, ETA, storage, last scan, roof log) is a new top-level key beside `"units"` at 12172; the page (`astro-observatory.html`) must learn to read it. `PHASE2-RECORD-FIELDS.md` opens with the rule: everything additive to `observatory/1`, nothing removed or renamed, because the iOS app reads this record. The dataset summary keys are fixed (`_obs_dataset_summary`, 11748; PHASE2-RECORD-FIELDS section 4) and `nextAction` has a fixed vocabulary (section 5); a Starfront "Pull" next action would be an addition to that table.
- The Explore views (CLAUDE.md, 1.9.0 paragraph; `PHASE2-CONTRACT.md` "Page"): the page opens on the status line and `units[]` cards; everything else sits behind Explore (Ready to process, Imaging nights, What each scope captured, Sky, Footprints, Coverage, Equipment, Data checks, Archive, Pipeline, Targets). Layer 2 is `openUnit`, layer 3 `openProjectLayer`. A Starfront view would be one more Explore entry reading the new section, and the Starfront unit's card would read `units[]` like any Seestar.

### resolve_scope (`10705` to `10727`)

Quoted, the part that matters:

```
for s in contract["scopes"]:
    mt = s.get("match") if isinstance(s.get("match"), dict) else {}
    if "unit" in mt:
        continue
    mc = mt.get("camera") or ""
    hit = (cam and cam == mc) or (scope and "ZWO " + scope == mc) \
        or (scope and scope == s.get("name"))
    if not hit:
        continue
    if mt.get("scope") and mt["scope"] != scope:
        continue
    return s
```

Yes: any entry whose `match` has a `unit` key (even `null`) is skipped (10717). `scopes_for_root` (10729 to 10733) and `_obs_units` (11816) skip them the same way. The match is an exact string compare on `camera`, so the new camera name must equal `match.camera` character for character. First hit wins in file order: the home `S50P` entry sits above `S50P-STARFRONT`, which is fine once their cameras differ.

### load_contract (`10534` to `10581`)

Reads `CONTRACT_DIR/targets.json` and `scopes.json` (`CONTRACT_DIR` at 862, beside the engine or `ASTRO_CONTRACT_DIR`), `utf-8-sig`, and keeps only entries with a string `id` (10552). `default_site` from scopes.json (10553 to 10554). A missing or malformed file is a warning, never a crash.

### contract/scopes.json, the S50P-STARFRONT entry (lines 94 to 105 of the file)

```
{"id": "S50P-STARFRONT", "name": "Seestar S50 Pro (Starfront, Texas)",
 "archive_root": "S50P", "site": "Starfront", "colour": null,
 "match": {"camera": "ZWO Seestar S50 Pro", "unit": null},
 "note": "Switched off until the importer records the unit a frame came from."}
```

Three things the brief's "remove the unit key" leaves out: `match.camera` must change at the same time (otherwise the entry would also match the home S50 Pro), `archive_root` is `"S50P"` here but the brief wants a new archive root (D says `S50P-Starfront`), and the file's own `note` and `about_sites` text (lines 3 and 119) say "leave unit in place". `contract/shipped.sha256` must list the new file's hash or the installers will leave the new copy beside an edited one as `.new` (the file's header comment; CLAUDE.md 1.7.0). There is no `timezone` key on any scope entry and nothing in the engine reads one; it would be new.

### The config loader (`244` to `266`, `812` to `894`)

- `_DEF_STATE`: `%LOCALAPPDATA%\Astro Import` on Windows, `~/Library/Application Support/Astro Import` on the Mac (244 to 247). `_CONFIG_PATH` is `ASIAIR_CONFIG` or `<state>/config.json` (248 to 249). The file is read once at import with `utf-8-sig` (252 to 260); not a dict becomes `{}`.
- Readers: `_env_path(var, default)` for paths (262 to 266; in test mode a default outside the root becomes `<root>/unset/<var>`); the plain pattern `os.environ.get(var) or _CONFIG.get(var)` for strings (for example `SEESTAR_VOLUME_ENV`, 318); `_env_flag` for booleans (812 to 819, true for `1/true/yes/on`); `_env_rule(var, default, lo, hi)` for whole numbers in a range, with a `CONFIG_WARNINGS` note when out of range (878 to 894). Precedence everywhere: environment variable, then config.json, then the default.
- A new key like `STARFRONT_VPN_MODE` (`always | on-demand | never`) has no helper: either the plain pattern plus a check against the three words (with a `CONFIG_WARNINGS` note like `_env_rule`), or a small `_env_choice` beside `_env_rule`. `STARFRONT_AUTO_CLEAR` is an `_env_flag`; the hour and second thresholds are `_env_rule`s; the share root is an `_env_path` whose test-mode default must sit in the root, and it must be added to `_test_root_guard`'s list (211 to 240) so a test can never point it at a real share.
- `config.example.json` documents every key and says "See PARITY.md for every key on both platforms": new keys go in both.

### Camera detection on Windows: _drive_roots (`362` to `411`), refresh_camera_volumes (`413` to `432`), seestar_volume (`8315` to `8331`)

- `_drive_roots` returns `ASTRO_DRIVE_ROOTS` entries when the variable is set (367 to 369); otherwise, on Windows outside test mode, every drive LETTER from `GetLogicalDrives` that is removable, or fixed and not ours and not a system drive (391 to 409). A UNC path can never come out of the search.
- `refresh_camera_volumes` is for the ASIAir only (`Autorun` folder, 428 to 431). `_volumes_named_seestar` (8291 to 8311) on Windows is "any drive root carrying `MyWorks`" (8296 to 8301).
- `seestar_volume` first checks `SEESTAR_VOLUMES` (8323 to 8326), which is `[SEESTAR_VOLUME]` when that env var or config key is set (318 to 321), by `os.path.isdir(cand/MyWorks)` only. So yes: a UNC path such as `\\10.15.10.212\EMMC Images` could be given as `SEESTAR_VOLUME` today and the whole ordinary Seestar path would run over it (the panel's `_camera_ok` at `astro-app.py:208` would call it a camera). That must not be done: the identity vote would read FITS headers over the VPN, the camera would be the home name (rows would share keys with the home S50 Pro, the very hazard `key_for` exists for), the destination would be the home S50 Pro folder, and the eject button would try to eject it. Starfront needs its own setting (say `STARFRONT_SHARE`) and its own scan, never `SEESTAR_VOLUME`.

### Test-mode guards: _within (`165` to `173`), _confine (`205` to `208`), _test_root_guard (`211` to `240`)

- `_within` resolves both paths with `realpath` and `normcase` and asks `os.path.commonpath([p, r]) == r`; a `ValueError` (different drives on Windows) is `False` (170 to 173). A UNC root and a `C:\...` test root are different drives, so a UNC path is never inside the test root; on the Mac or Linux a `\\server\share` string is just a relative name that resolves under the current folder, also outside. `_test_root_guard` refuses any configured path outside the root before anything runs (236 to 240); `_confine` refuses at the moment of use for paths that come from the ledger or the camera (205 to 208; the SAFE clear calls it at 9525 and 9528).
- Therefore Starfront tests cannot use a UNC root at all: they point the share setting at a folder inside the root (exactly how `make_env` sets `SEESTAR_VOLUME` to `<root>/Seestar`, `test_env_helper.py:66`) and the Starfront code must treat "the share root" as any folder, never requiring a `\\` prefix. The brief's "a UNC path escaping MyWorks is refused" test is a `..` relpath against that local root, checked with the same `realpath(...).startswith(real_root + os.sep)` pattern the clear uses at 9586 to 9591.

### The Windows scheduled tasks (`install-windows.ps1`)

- The installer refuses an Administrator window (43 to 55) unless `-AllowElevated` (23); it names the three tasks to unregister.
- One principal for all tasks: `New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Limited` (229). Never highest privileges.
- `Register-AstroTask` (230 to 242) runs `pythonw -X utf8 "<bin>\astro-import.py" <arg>` (232) with `-Force`.
- Tasks: `BrettjoAstro FITS Importer ship` (244 to 251): Daily 09:30 and 21:30, `-StartWhenAvailable`, 6 h limit, `IgnoreNew`, only when an archive is set. `Astro archive sweep` (270 to 273): at logon and Daily 03:30, 8 h limit, runs `--pc-nightly`. `Astro sync requests` (283 to 291): a Daily 00:00 trigger repeating every 5 minutes for a day plus at logon, 15 min limit, `-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries`, runs `--pc-tick`.
- The watcher is not a task: a Startup-folder shortcut (183 to 190).
- The brief's H ("scheduled tasks that may start the service run with highest privileges") contradicts the Limited principal and the admin-window refusal. `sc start` on a service needs elevation. The fitting answer is to make the WireGuard tunnel service auto-start (Brett runs the one admin command once; the tool only checks `sc qc` / `sc query`), and to register any elevated task by hand, never from the installer.

### The panel's job runner (`astro-app.py`)

- `App._run(label, fn, need_camera=True)` (241 to 328): `_camera_ok` first unless `need_camera=False` (208 to 217: `refresh_camera_volumes` then `ASIAIR_VOLUME` or `seestar_volume()`); `oplock.acquire(blocking=False)` (244), a refusal puts "The importer is busy" in `last_result`; `status` flips before the request returns (252); a daemon thread (`work`, 256 to 327) sets `eng.PROMPT_FN = self.on_prompt` and `eng.EVENT_FN = self.on_event` (257 to 258), redirects stdout and stderr into `App.write` (261), and for `importing / reporting / discarding / clearing / saving` takes the engine's own `import.lock` with `eng.acquire_lock(what="panel")` (262 to 272; `acquire_lock` at `astro-import.py:1792`). `finally` releases both locks, clears the hooks, sets idle and refreshes the status line and dashboard (315 to 326).
- The HTTP side answers at once with `_started(ok)` (1234 to 1241); the POST handlers are at 1498 to 1533 (`/api/clear` at 1528: `APP.do_clear(name)` at 749 to 767 calls `eng.run_clear` and maps `cleared / kept / refused` to a banner).
- Question cards: the engine's `safe_input` (`astro-import.py:1027` to `1043`) calls `PROMPT_FN({"kind": "confirm", "prompt", "default"})`; `App.on_prompt` (97 to 113) stores `{id, kind, prompt, default, expect}` and blocks the worker on an Event for up to 3600 s; the page polls `GET /api/state` (1360; JS at 2780) which carries `question`, renders it (`renderQuestion`, 2292 to 2340) and POSTs `/api/answer {id, value}` (1600 to 1606) into `App.answer` (115 to 130: the id must match, first answer wins). Yes sends `"y"`, No sends `"n"` (2338 to 2339); a typed word uses `expect` (2312 to 2318). With no card (`/api/projects/rebuild`) the engine gets `None` and `safe_input` returns the default (1582 to 1585; `astro-import.py:1032`).
- Progress: `show_progress` prints `\r  <label> [bar] n/m (p%)` (`astro-import.py:1017` to `1025`); `App.write` (70 to 88) collapses successive lines of the same label into one log entry by shape (78 to 86). `emit("phase", ...)` (`astro-import.py:1000`) reaches `App.on_event` (94) as `phase`. A long Starfront pull reports exactly this way: plain `info()` lines, `show_progress(done, total, label="Pulling")`, `emit`.
- The status line is computed in a child process (`STATUS_CMD` 855, `compute_status` 865 to 880: `astro-import.py --status --json`) so the panel never keeps the ledger in memory.

### The receipt writer

- Seestar receipt (`astro-import.py:9360` to `9368`): `{"version": 1, "source": "seestar-import", "telescope": <scope name>, "importedAt", "sessions": [...]}` into `RECEIPT_BASE/<scope>/seestar-[pc-]<stamp>.json` (`RECEIPT_BASE` 846; `_unique_receipt_path` 1274 to 1287 adds `pc-` on Windows, 1272).
- Session fields (9038 to 9044): `targetDisplayName, seestarProjectName, isMosaic, dayNumber, framesCopied, stackedCount, stacks [{night, subCount, filename}], fitsFolderPath`; Milky Way sessions (9186 to 9189) carry `isMilkyWay, pairedDso`. Panel sets and mode folders write no session. The ASIAir receipt's sessions (3256 to 3264; the receipt itself at 3281 to 3294) also carry `sourceType` and `scope`.
- No `site`, no hours, no nights, no camera. A Starfront receipt with `site`, `hours`, `nights` is additive, but `telescope` is what AstroLog keys on, and `Seestar S50 Pro (Starfront)` would be a new scope name to it: that is a link between projects, so the project map and AstroLog's receipt reader need telling.

### Ledger and inventory row fields for a Seestar sub

- Ledger row (above, `_seestar_ledger_add`): key `MyWorks/<target>_sub/<file>.fit` or `...|cam=<camera>`; `device "seestar"`, `camera`, `scope`, `target` (the camera folder name without `_sub`, e.g. `M 42`), `displayName`, `sourceType "sub"`, `night` (from the header's DATE-OBS), `exposureSeconds` (header EXPTIME), `dayNumber`, `size`, `sha256`, `cameraMtime` (float seconds), `importedAt`, `dest`, `verifiedAtImport`; later `clearedFromCamera / clearedNoticedAt` (1633 to 1634, 9617 to 9618) and the ship's `archiveLocation, archivePath, archiveShippedAt, archiveVerifiedAt` (3769).
- PC inventory row (`6543` to `6554`, schema `inventory-row/1`): `relpath, size, mtimeNs, camera, rig, target, night (from the filename stamp), nightSource, day, kind, retired, sha256, hashedBy, read, hashedAt`. `read` is the `"unbuffered" / "buffered"` word from `hash_file_unbuffered`, so the word the brief wants to gate on already has a home in the archive records.

### The bare listing calls in the clear gate (the brief says "around lines 9404 and 9424")

Corrected lines:

- `_seestar_unproven_files`: `for root, _dd, fnames in os.walk(d):` at 9423 (the verified-stacks pass) and at 9438 (the main pass). Both have no `onerror`, so a folder that cannot be listed is skipped silently: its files are neither proven nor unproven nor collected. The gate does not STOP; those files simply aren't deleted, and nothing says a folder went unread. A file that was listed but cannot be stat'ed IS counted unproven (9446 to 9453).
- `_jpeg_twin_proven`: `os.listdir(root)` at 9490, inside try/except (safe: a failure blocks the JPG).
- `seestar_safe_cleanup`, delete phase: `os.walk(d)` at 9604 (silent) and a bare `os.listdir(root)` at 9609 inside the empty-folder sweep. An `OSError` there propagates out of the function AFTER `os.remove` ran (9593 to 9598) and BEFORE the rows are flagged (9613 to 9619) and the ledger saved (9627). The next scan's `mark_cleared` would catch up, but the brief's "any listing error means STOP" needs its own walk with `onerror` and the ledger flagged per removed file as it goes.

---

## 2. The night rule

- `NIGHT_PIVOT_HOURS = 12` (934). `observing_night(dt)` (1181 to 1185): `(dt - timedelta(hours=12)).strftime("%Y-%m-%d")` on a NAIVE datetime. No timezone, no conversion.
- `_seestar_file_night(filename)` (8817 to 8827): `_SEESTAR_STAMP_RE = (20\d{6})-(\d{6})` (8815) on the filename, `datetime.strptime(..., "%Y%m%d%H%M%S")` (8824), then `observing_night`. Whatever clock the Seestar wrote into the name is taken as is.
- `_sub_meta(path)` (8850 to 8861): astropy header, `EXPTIME` (8854), `DATE-OBS[:19]` parsed naive (8855 to 8856), `observing_night` (8858). This is the value stored as the ledger row's `night` (8729, via the call at 8946 to 8947). Day folders are grouped by the FILENAME stamp (`by_night` at 8914 to 8916, `_seestar_day_number`), so today a row's `night` and its Day folder come from two different clocks and nobody checks they agree; the brief's rollout step 1 check (stamp against DATE-OBS) is the right first question. `_row_night` (10747 to 10758) prefers the row's `night` and falls back to the filename; the inventory row uses the filename only (6543).
- Timezone use anywhere: only `timezone.utc` for lock and ship timestamps (5119 to 5130, 3994, 6668) and `now.astimezone()` for the Observatory's `generatedAtLocal` / `timezone` (12128 to 12131). No `zoneinfo`, no `tzdata`, no `ZoneInfo` anywhere in the engine, panel or tests.
- Where a per-site rule plugs in: `observing_night` is the single pivot both parsers call. A site-aware version takes `(dt, tz_from, site_tz)` (or the Starfront code calls its own `starfront_night(dt_naive_in_utc_or_camera_clock)` that converts to `America/Chicago` with `zoneinfo.ZoneInfo` before the 12 h subtraction) and is used in: the Starfront scan's hours-per-night, the pull's Day grouping (the `by_night` dict, 8914 to 8916, and `_seestar_day_number`'s continuation, 8840 to 8847), the ledger row's `night`, and the inventory's `night` (6543) if Starfront frames are to show the Texas night on the PC. On the PC's python.org Python there is no system tz database: `ZoneInfo("America/Chicago")` raises `ZoneInfoNotFoundError` unless the `tzdata` package is installed (`py -3 -m pip install --user tzdata`), so "fail closed when the zone can't load" is the right rule and `selftest.py` should check it.

---

## 3. Rule 2 and how the SAFE clear enforces it

CLAUDE.md, "Rules that are never broken", item 2, quoted:

> A camera file is deleted only when the ledger proves a verified copy of those bytes, from that camera. Brett must also have confirmed, with default No. The SAFE gate (`_seestar_unproven_files`) re-checks at the moment of deletion and deletes only the files it checked.

`seestar_safe_cleanup(state, scan_s, cleanup_candidates)` (9510 to 9629), step by step:

1. `_confine(vol)` and `_confine(realpath(vol/MyWorks))` (9525 to 9528): in test mode the deletes must land inside the root.
2. First gate, per candidate `(label, dirs, exempt_superseded)`: `_seestar_unproven_files` (9530 to 9539). Proven means (9470 to 9475) a row for THIS camera (`state.file_entry(_rel(p, vol), camera)`), `verifiedAtImport`, the same `size`, and `cameraMtime` within `_mtime_close`. Exempt: `_thn`, `._*`, `.DS_Store` (9442 to 9445); a stack that a verified later stack continues (9454 to 9460); a JPG twin of a proven FIT in a `_sub` folder (9461 to 9469). One unproven file blocks the whole folder and is named (9540 to 9543).
3. The SAFE folders are listed with sizes (9546 to 9553), then the question `"Delete these SAFE source folders from the Seestar? [y/N] "` (9556) through `safe_input(q, default="n")` (9562); on the panel the card text names the scope and lists the folders (9557 to 9561). Anything but `"y"` keeps everything (9563 to 9565). Headless with no `ASTRO_STDIN_PROMPTS`, `safe_input` answers the default (1035 to 1039).
4. Second check at the moment of deletion: the camera identity is read again and must equal the one checked (9566 to 9574); each folder is re-gated with `collect=todo` (9578 to 9585); every collected path must `realpath` to inside `MyWorks` and not be a symlink (9586 to 9591).
5. `os.remove(p)` for exactly the collected paths (9593 to 9598); a failure only warns and the file is left.
6. Folders now empty (or holding only litter) are removed, deepest first, each confined to `MyWorks` (9601 to 9611). This INCLUDES the top-level `<target>` and `<target>_sub` folders: the tests assert it (`test_v2.py:1050` to `1051`: `not os.path.isdir(MyWorks/M 101)`; `test_app.py:783`: `_sub` gone after the clear).
7. The rows whose files were removed are flagged `clearedFromCamera` (9613 to 9619), one history event per label (9626), `save_ledger` (9627).

Entry points: the end of `run_seestar_import` (9378, only when the camera didn't vanish mid-import), `run_clear(state, group_id)` (7347 to 7377, the panel's clear button; groups from `seestar_groups`, 7320 to 7344, keyed by the camera folder name such as `M 42_sub`), and the hand-over inside `run_discard` (7555).

"Format": the importer never formats anything. There is no `diskutil erase`, `Format-Volume`, `mkfs` or anything like it in the engine; the only deletes are `os.remove` on checked files and `shutil.rmtree` on emptied folders inside `MyWorks`, and `run_discard`'s typed-DISCARD path. "Format" in the Starfront docs means the Seestar app's own wipe, which clears `darklibrary` too; this tool has nothing to do with it.

---

## 4. How the tests simulate a Seestar, and how a panel button is tested

- `test_env_helper.make_env(root)` (40 to 86) builds the whole environment: `ASTRO_TEST_ROOT` (53), a fake home (54 to 56), `ASIAIR_STATE = <root>/state` (the ledger, `ledger.json`, 60), `SEESTAR_VOLUME = <root>/Seestar` (66), the four Seestar destinations under `<root>/dest` (67 to 70), `ASTRO_ARCHIVE_MOUNT = <root>/archive-mount` (71, with `_verify/<side>` made by the ship), `ASTRO_DRIVE_ROOTS` pointing at a missing folder so no real drive is ever searched (73), `ASTRO_PANEL_PORT` a free port (75). `extra` overrides or removes keys (81 to 85). `isolate_runner()` (88 to 95) puts the test process itself in test mode.
- `teh.Env(name, asiair, seestar)` (416 to 461): `self.svol = <root>/Seestar`, `self.myworks = <root>/Seestar/MyWorks` (421 to 422), `self.state`, `self.archive`; `Env.run(*args, stdin, extra_env)` (463 to 467) runs the engine as a subprocess; `Env.ledger()` (469) reads `ledger.json`.
- Fixtures: `make_seestar_fits` (381 to 400) writes a 2880-byte header with `EXPTIME`, `DATE-OBS` and `CREATOR`; `add_seestar_sub(project, stamp, creator, exptime)` makes `MyWorks/<project>_sub/<stamp>.fit` (482 to 489); `add_seestar_stack` (491 to 500) `MyWorks/<project>/Stacked_<n>_<base>_<exp>_<filt>_<stamp>.fit`; `add_seestar_panel` (502 to 510) `MyWorks/<mosaic>_pt/<stamp>.fit`; `add_seestar_nondso` (512). A Starfront `_sub` with the new filename form (`Light_M 17_30.0s_LP_20261027-195802_1032.fit`) is just a different name passed to `make_seestar_fits`.
- The Yes path: `ASTRO_STDIN_PROMPTS=1` with piped answers (`test_v2.py:899`, `STDIN_Y`; chain S15 at 1032 to 1060 answers `"n\ny\n"` and then checks the folder is gone). Side effects: `teh.os_calls(root, "notify")` (323 to 335) reads `os-calls.jsonl`. The Windows drive-letter layer on any OS: chain W1 (1738 to 1775) with `ASTRO_DRIVE_ROOTS` pointing at folders inside the root. Share rights: `teh.no_delete_env` (225) and `teh.denied` (304).
- For Starfront: sandbox a folder inside the root as the share root (the same way `SEESTAR_VOLUME` is), with `MyWorks/<Target>`, `MyWorks/<Target>_sub`, `MyWorks/darklibrary`; the ledger and archive come from `make_env` as they are. Anything that would touch the network (WireGuard `sc`, the roof share, the ntfy POST) must be routed through `_test_record` (193 to 203) in test mode and asserted with `os_calls`, as `notify` and `_powershell` already are.
- The panel in `test_app.py`: `env = teh.Env("APP", asiair=True, seestar=True)` (218), `PORT` from `env.env["ASTRO_PANEL_PORT"]` (219), `start_panel(env, PORT)` (142 to 150: `astro-app.py --no-browser --port`, stdin `DEVNULL`, output to `<root>/panel.log`), `own_panel` (160 to 180) confirms `/api/ping` names this root's state folder, `load_token` (107) reads the per-launch token from the page, `api(path, body)` (90) POSTs JSON with it, `wait_for(pred)` (113 to 120) polls `/api/state`. A button test is chain T13 (770 to 785): `api("/api/clear", {"name": "M 42_sub"})`, `wait_for` a `question`, check `kind == "confirm"`, `default == "n"` and the prompt names the folder, `api("/api/answer", {"id": q["id"], "value": "y"})`, `wait_for` idle, then check the folder is gone and `lastDone.op == "clear"`. A Starfront Pull button test follows that shape exactly; the "confirm n deletes nothing" test sends `"n"`.

---

## 5. Brief assumptions the code contradicts, with the fix

1. Version. The brief says "v1.7.6" and "release 1.8.0". The branch is 1.9.0 (`astro-import.py:54`); 1.8.0 and 1.9.0 are both shipped. Starfront is 1.10.0 at least. The check counts in CLAUDE.md's Testing section are also behind the latest commit's counts; take them from a green run, not from the brief.
2. Observatory. `run_observatory` is the standalone HTML export; the live record is `observatory.json` from `run_projects` through `observatory_from` (12441 to 12494), and `E:\Astro Config Data\Observatory\dataset.json` is the August scan's file (`OBSERVATORY_DATASET`, 853 to 857), read only by the Archive tab. Fix: write the `starfront` section inside `observatory_from`'s return dict (12140 to 12185), keep every existing key, and let `--starfront-scan` end with `run_projects(state)` the way `--pc-nightly` does, or write the section into a small `starfront.json` in the state folder that `observatory_from` merges in (the scan then never has to rebuild the whole project layer over a VPN-slow run).
3. The clear removes top-level folders today (9601 to 9611; tests `test_v2.py:1050`, `test_app.py:783`). The brief's "never remove the top-level target or `_sub` folders" needs a parameter on the delete phase (keep the two top folders, remove only emptied subfolders) that the home path leaves off.
4. `copy_file_verified` is not resumable: the `.partial` is deleted on failure (2146 to 2151) and a file restarts from zero. The brief's drop handling ("stop cleanly, delete the .partial, let the ledger resume next run") is consistent with that, but "restartable" means per file, not per byte. Over a 1280-MTU tunnel at 120 to 230 ms a 2160 x 3840 sub of some 16 MB restarts whole.
5. The mtime rule. The home gate uses `_mtime_close`'s tolerance (8794 to 8806) through `_camera_changed`. An exact rule for Starfront must be a separate check, and the new rows should record `st_mtime_ns` (as the inventory does at 6545), because `cameraMtime` is stored as a float (8732 to 8739). Rollout step 1 must confirm the share's mtime resolution and that it is stable across listings (Samba with an emmc backing store may report whole seconds).
6. The listing calls are at 9423 and 9438 (`os.walk`, silent skip), 9604 and 9609 (delete phase, the bare `os.listdir` can raise after deletes and before the ledger is flagged); not 9404 and 9424. The Starfront gate needs `os.walk(..., onerror=...)` that aborts, and flags rows per removed file.
7. `resolve_scope` does skip `unit` entries (10717), but switching `S50P-STARFRONT` on means four edits in `scopes.json`, not one: remove `unit`, set `match.camera` to the new name, set `archive_root` to the new root, fix the `note`/`about_sites` text; then add the hash to `contract/shipped.sha256` (test_v2 checks it) and bump nothing else. `_obs_units` (11816) and `scopes_for_root` (10729) follow the same `unit` rule, so they switch on together.
8. `notify()` is not "Windows toast plus panel": it is toast (Windows), Notification Centre (Mac), `NOTIFY_FN` (desktop app only), and a record in test mode; the web panel never sees it. The ntfy POST is new, cross-platform code with no HTTP client to reuse; it must be recorded in test mode and must not be in the platform layer (it is the same on both platforms; PARITY.md gets a row all the same).
9. `SEESTAR_VOLUME` can take a UNC path today (318 to 326), which is a trap, not a feature (home camera name, header reads over the VPN, eject). Starfront gets its own key and its own scan; never reuse `seestar_volume()` for it, and in the panel pass `need_camera=False` to `_run` (`astro-app.py:241`), because `_camera_ok` (208) doesn't know the share.
10. Scheduled tasks: the installer registers everything with `-RunLevel Limited` (229) and refuses an admin window (43 to 55). "Highest privileges" for the scan/silent/digest tasks contradicts that and isn't needed if the WireGuard service auto-starts (Brett's one-off admin command). If `sc start` is kept, it runs only when the service is stopped and must degrade to the "not installed / not running" alert, never to a failed task.
11. Tests cannot sandbox a UNC root: `_within` (165 to 173) says a UNC path is never inside the test root. Tests use a local folder as the share root; the Starfront code must accept any folder and must never assume `\\` prefixes, mapped drives or `net use`.
12. Exposure from the filename: `_sub_meta`'s docstring (8851) says names carry no metadata, which was true of the bare-stamp names. `_STACK_SESSION_RE` (8751, `_(\d+(?:\.\d+)?)s_([A-Za-z0-9]+)_(\d{8}-\d{6})`) already parses `_30.0s_LP_20261027-195802` but is only applied to `Stacked_` names through `_stack_info` (8753). Reuse the regex for subs; the header fallback stays `_sub_meta` (astropy reads the header blocks; the brief's "first 2880 bytes" is an optimisation it can add).
13. "Shipped with read-back" as a clear condition: the row field is `archiveVerifiedAt` (3769, 4076, 4384), set by the PC sweep's unbuffered re-read, not by the ship itself. On the PC the Starfront pull lands on C: first (the Seestar destinations are under `~/Documents/Astro`, 322 to 331) and `ship_after_import` files it to E: (5617); so "shipped with read-back" on the PC means `archiveVerifiedAt` present, which arrives only after the next sweep (logon or 03:30). The gate should say "waiting for the archive sweep" rather than block silently.
14. `sourceRehashed` / `sourceSha256` do not exist (grep: none). They are new ledger fields; `LEDGER_VERSION` (936) stays 1 if they are additive. The `read` word already lives in hash and inventory rows (6552).
15. No darkness, roof or sun code exists in the engine (grep for sunset / twilight / darkness: none), and the sky-calendar roof parser the brief wants to reuse is in another repo. Both are new modules; keep them pure (inputs in, verdict out) so the guard tests need no clock or network.
16. Parallel copies: `_UnplugWatch` (2239) calls the camera gone after three consecutive OS errors, which eight workers would reach in one bad second; the Starfront pull needs its own stall/drop accounting (the brief's "no bytes for 120 s" rule) and a single-threaded ledger writer.
17. The receipt has no `site` and AstroLog keys on `telescope`: adding `site`, `hours` and `nights` is additive, but the new telescope name and the new field are links between projects; update the project map's receipt row.

---

## 6. Quick index

Engine (`astro-import.py`): `VERSION` 54; `_within` 165; `TEST_ROOT` 175; `_test_record` 193; `_confine` 205; `_test_root_guard` 211; `_CONFIG` 248 to 260; `_env_path` 262; `SEESTAR_VOLUMES` 318; `_win_long` 342; `_rel` 355; `_drive_roots` 362; `refresh_camera_volumes` 413; `pid_alive` 434; `_powershell` 470; `_WIN_TOAST` 484; `hash_file_unbuffered` 565; `_win_hash_unbuffered` 587; `_env_flag` 812; `panel_port` 821; `SEESTAR_IMPORT_SUB_JPEGS` 833; `STAMP_RE` 844; `RECEIPT_BASE` 846; `OBSERVATORY_DATASET` 853; `CONTRACT_DIR` 862; `_env_rule` 878; `NIGHT_PIVOT_HOURS` 934; `LEDGER_VERSION` 936; `PROMPT_FN` 996; `EVENT_FN` 997; `NOTIFY_FN` 998; `emit` 1000; `show_progress` 1017; `safe_input` 1027; `notify` 1058; `observing_night` 1181; `_unique_receipt_path` 1274; `_atomic_write_json` 1290; `CAMERA_KEY_SEP` 1320; `_row_camera` 1326; `State` 1343; `history_event` 1521; `key_for` 1548; `file_entry` 1560; `is_imported` 1565; `max_day_number` 1576; `add_file` 1596; `mark_cleared` 1614; `seestar_seen` 1659; `LOCK_PATH` 1779; `acquire_lock` 1792; `_hash_dest_uncached` 2090; `copy_file_verified` 2115; `_cam_listdir` 2228; `_UnplugWatch` 2239; ASIAir receipt 3280; `other_record` 4104; `status_summary` 4392; `_ShipLock` 5132; `_archive_ship_lock` 5175; `run_ship` 5588; `ship_after_import` 5617; `_run_ship` 5651; `publish_receipts` 5813; inventory row 6543; `seestar_groups` 7320; `run_clear` 7347; `run_discard` 7380; `_volumes_named_seestar` 8291; `seestar_volume` 8315; `_seestar_creator_model` 8339; `seestar_model_ex` 8359; `_fits_files` 8459; `scan_seestar` 8474; `_seestar_ledger_add` 8722; `_STACK_SESSION_RE` 8751; `_mtime_close` 8794; `_camera_changed` 8808; `_SEESTAR_STAMP_RE` 8815; `_seestar_file_night` 8817; `_seestar_day_number` 8829; `_sub_meta` 8850; `run_seestar_import` 8863 (receipt 9360, clear 9378); `_seestar_unproven_files` 9385; `_jpeg_twin_proven` 9479; `seestar_safe_cleanup` 9510; `seestar_baseline` 9631; `SCOPE_SLOT` 9683; `save_scan_summary` 10059; `load_contract` 10534; `resolve_scope` 10705; `scopes_for_root` 10729; `_row_night` 10747; `build_projects` 11158; `_obs_dataset_summary` 11748; `_obs_unit` 11761; `_obs_units` 11806; `observatory_from` 11840 (return 12140 to 12185); `build_observatory` 12187; `run_observatory` 12235; `load_observatory` 12334; `run_projects` 12441; `main` 12507.

Panel (`astro-app.py`): `App` 51; `write` 70; `on_prompt` 97; `answer` 115; `_camera_ok` 208; `_run` 241; `do_import` 582; `do_clear` 749; `STATUS_CMD` 855; `_started` 1234; `GET /api/state` 1360; `GET /observatory` 1408; `POST /api/clear` 1528; `POST /api/projects/rebuild` 1566; `POST /api/answer` 1600; `renderQuestion` 2292; `make_server` 2938; `serve` 2962.

Tests: `test_env_helper.py` `make_env` 40, `isolate_runner` 88, `no_delete_env` 225, `os_calls` 323, `make_seestar_fits` 381, `Env` 416, `add_seestar_sub` 482; `test_v2.py` `STDIN_Y` 899, chain S15 1032, chain W1 1738, chain P2 6575; `test_app.py` `api` 90, `wait_for` 113, `start_panel` 142, `own_panel` 160, env 218, T13 clear 770 to 785.

Installer (`install-windows.ps1`): admin refusal 43 to 55; principal 229; `Register-AstroTask` 230; ship task 244 to 251; sweep 270 to 273; tick 283 to 291; watcher shortcut 183 to 190.
