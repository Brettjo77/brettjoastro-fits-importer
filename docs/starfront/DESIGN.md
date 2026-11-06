# Starfront source: design note (Phase 0, 6 Nov 2026)

The brief is `BUILD-PROMPT.md`; the facts are `FACTS.md`; the code survey is `CODE-MAP.md`. This note settles what the builders code, where the brief and the code disagreed, and the record the page and the phone read. Plain words, no em dashes or double dashes.

## Decisions taken in Phase 0 (Brett, 6 Nov)

1. Version 1.10.0, built on branch `claude/starfront` from 1.9.0. The brief's "1.8.0" is taken.
2. The live Observatory is `observatory.json` from `--projects` (`observatory_from`), not `run_observatory` / `dataset.json`. The Starfront data is an additive top-level `starfront` section plus a unit card in `units[]` and an Explore view on the page. Never remove or rename an existing field: the iOS app reads this record.
3. **PC only, by design.** The proof that a file was really re-read from the Seestar needs an unbuffered read, which `hash_file_unbuffered` reports only on Windows (`FILE_FLAG_NO_BUFFERING`). The Mac sees Starfront's projects through the PC's published record, as it sees everything else of the PC's. PARITY lists it under Differences by design.
4. Rule 2 is amended for this camera only, in Phase 3 (the clear), with Brett's yes at rollout step 4. Phase 1 writes nothing on the Seestar and deletes nothing anywhere.
5. Pushes to GitHub still wait for Brett's word (rule 9). The rollout stops are the brief's five.

## Phase 1: read only (this build)

### Config keys (all through the usual loader; `config.json` in `%LOCALAPPDATA%\Astro Import`)

| Key | Default | Meaning |
|---|---|---|
| `STARFRONT_SHARE` | `\\10.15.10.212\EMMC Images` | the Seestar's share root (UNC only; a mapped drive is refused) |
| `STARFRONT_CAMERA` | `ZWO Seestar S50 Pro (Starfront)` | the camera name on every Starfront row, taken from the share, never from a header |
| `STARFRONT_TZ` | `America/Chicago` | the site's zone; if it cannot be loaded, every Starfront command stops ("fail closed") and says to install `tzdata` |
| `STARFRONT_LAT`, `STARFRONT_LON` | 31.54733, -99.38273 | the site, for sun altitude and the header sanity check |
| `STARFRONT_DEFAULT_HOURS` | 20 | the target a project is measured against unless `starfront-targets.json` overrides it |
| `STARFRONT_VPN_MODE` | `on-demand` | `always`, `on-demand` or `never` |
| `STARFRONT_VPN_TUNNEL` | `BrettJohnson-B15` | the WireGuard tunnel name; the service is `WireGuardTunnel$<name>` |
| `STARFRONT_SEESTAR_IP` | `10.15.10.212` | the host the tunnel probe tries on port 445 |
| `STARFRONT_STALL_SECONDS` | 120 | no bytes for this long counts as a dropped link |
| `STARFRONT_VPN_ALERT_HOURS` | 12 | one alert after this long down, one on recovery |
| `STARFRONT_ROOF_SHARE` | `\\172.16.5.21\sfro-customer` | the customer share; the roof file sits under `roof\` |
| `STARFRONT_ROOF_FILE` | empty | the roof file's path once rollout step 1 names it; empty means "look in `roof\` for the newest file" |
| `STARFRONT_ROOF_CLOSED_HOURS` | 2 | a pull guard (Phase 2) |
| `STARFRONT_SILENT_MINUTES` | 90 | the "Seestar silent" alert threshold |
| `NOTIFY_PUSH_URL` | empty | an ntfy topic URL; one HTTP POST per push; empty means no push |
| `STARFRONT_AUTO_CLEAR` | false | Phase 3 only |
| `STARFRONT_WORKERS` | 8 (max 32) | Phase 2 only |

State files, all in the state folder, all confined in test mode: `starfront-inventory.json` (the listing cache, keyed by path + size + mtime), `starfront-headers.json` (the cached first header block per sub, keyed the same way), `starfront-targets.json` (per-project hour targets, keyed by the contract's canonical target name), `starfront-status.json` (per project: status, `notifiedReadyAt`, last hours; plus `tunnel.lastOk`, `tunnel.alertedAt`, `silentAlertedNight`), `starfront-roof.jsonl` (one row per roof reading: when, state, raw), `starfront-last-scan.json` (the last scan's summary for the Observatory and the panel). Flags: `starfront-pause` and `starfront-vpn-hold` (empty files in the state folder; Brett creates and removes them; the panel shows them).

### `--starfront-scan`

1. Zone check first (fail closed). Then `ensure_tunnel()` (below). If the tunnel is down, the scan says so, records `tunnel.lastOk` unchanged, and exits 1 without touching the cache.
2. List `MyWorks` top level only, then only the `*_sub` and `*_mosaic_pt` folders (one `os.scandir` per folder, no `os.walk`), plus a top-level `darklibrary` listing (count and size only). Every entry: path, size, mtime. Entries unchanged against `starfront-inventory.json` keep their cached facts; new or changed entries are parsed. A listing error anywhere ends the scan with "incomplete" and nothing is written to the cache.
3. Hours: the exposure parsed from the sub's filename (`Light_<target>_<exposure>s_<filter>_<yyyymmdd-hhmmss>_<n>.fit`, the filter token optional). A name without an exposure is read for its first 2880-byte FITS header block (one read, over SMB, cached in `starfront-headers.json`); `EXPTIME` from it. The header read also records `GAIN`, `DATE-OBS`, `SITELAT`, `SITELONG`, `RA`/`DEC` or `OBJCTRA`/`OBJCTDEC` when present, for the sanity checks; the first sub of every project per night is read once for that purpose even when the name has the exposure.
4. Projects: `<Target>` = `<Target>` (stacks) + `<Target>_sub` (subs) and, for mosaics, `<Target>_mosaic`, `<Target>_mosaic_sub` and `<Target>_mosaic_pt`. The target name resolves through the contract (`resolve_target`) for the display name and the target key; an unknown name is kept as it is and flagged.
5. Nights: the filename stamp is taken as the Seestar's own clock; the night key is the stamp shifted by 12 hours in `America/Chicago`, as a date. The scan prints, for one sub per project, the filename stamp and `DATE-OBS` side by side, so rollout step 1 can say which clock the stamp uses; until Brett confirms, the record carries `clock: "filename, unconfirmed"`.
6. Per project: hours, subs, hours per night, nights, GB on the scope, target hours, per cent of target, ETA (nights with data in the last 14 calendar nights give hours per clear night; remaining hours divided by that; null when no data in the window), the split by filter and gain, status (`collecting`, `ready`; `pulling`, `pulled-awaiting-clear`, `cleared` come later), flags from the sanity checks: `site-mismatch` (SITELAT/SITELONG over 0.1 degrees from the site), `clock-mismatch` (DATE-OBS and the stamp disagree by over 5 minutes), `mixed-settings` (exposure, gain or filter mixed within the project), `pointing-moved` (RA/Dec moves over about 10 arcmin between nights), `unknown-name`.
7. Storage: `shutil.disk_usage` on the share root; GB per night from the last 14 nights; "full in N nights"; a `pullNow` flag when N is under `STARFRONT_FULL_WARN_NIGHTS` (default 5).
8. Written: `starfront-last-scan.json` and the cache files. Then `run_projects` is NOT called by the scan; `--projects` (and the PC's nightly build) reads `starfront-last-scan.json` and adds the `starfront` section and the unit card. The scan ends with one line per project and the storage line.
9. In test mode the share root is a folder in the test root (`STARFRONT_SHARE` set by the test), so every path rule, the UNC-only rule included, has a test switch: `_starfront_share_ok(path)` accepts a UNC path, or any path under the test root in test mode.

### Targets

`starfront-targets.json`: `{"<canonical name>": hours}`. `--starfront-target "M 45" 12` sets one (the panel gets a field in Phase 2). The default is `STARFRONT_DEFAULT_HOURS`.

### Notify

`notify_push(title, text)`: one `urllib` POST to `NOTIFY_PUSH_URL` with a 10 s timeout; failures are logged, never raised. In test mode nothing is sent and the call is recorded in `os-calls.jsonl` (kind `push`). `notify()` itself is unchanged. The scan pushes "M 42 ready: 20.3 of 20 h on the Starfront Seestar" once, when a project first crosses its target (`notifiedReadyAt` in the status file); raising the target above the hours clears the mark, so a later crossing notifies again.

### The tunnel: `ensure_tunnel(timeout=60)`

- A TCP connect to `STARFRONT_SEESTAR_IP:445` answering within 3 s means up. In test mode the probe is a file: `<test root>/starfront-tunnel-up` present means up.
- Else: if `starfront-vpn-hold` exists or the mode is `never`, return False with the reason.
- Else query the service with `sc query WireGuardTunnel$<name>`; a missing service means the reason "WireGuard tunnel service not installed" and an alert once. If stopped, `sc start` it and remember that this run started it (the tool never stops a tunnel it did not start; Phase 1 never stops a tunnel at all). Poll the probe every 5 s until the timeout. In test mode `sc` is never run: the call is recorded in `os-calls.jsonl` and the test decides the outcome.
- `sc start` needs rights the installer's tasks do not have (`-RunLevel Limited`, and the installer refuses an Administrator window). So the install steps tell Brett to set the service to start automatically once, as administrator (`sc config "WireGuardTunnel$BrettJohnson-B15" start= auto`), and `ensure_tunnel` treats "access denied" from `sc start` as "start the tunnel yourself", with one alert.
- `tunnel.lastOk` is kept in the status file. One alert after `STARFRONT_VPN_ALERT_HOURS` down, one on recovery.
- Dead link by progress, for Phase 2's copies and for the scan's listings: no bytes (or no listing progress) for `STARFRONT_STALL_SECONDS`, or `OSError` with winerror 53, 59, 64, 67, 121 or 1231, counts as a drop.

### The roof reader

`read_roof()` opens the roof file read only, reads it, closes it at once (a `with` block, nothing else), and returns `{state: "open" | "closed" | "unknown", since, raw, readAt}`. The file's name and format are not in any document: Phase 1 takes `STARFRONT_ROOF_FILE` when set, else the newest file under `roof\`, and parses JSON, `key=value` or `key: value` lines and plain words, looking for `open` or `closed`. The raw text is kept in `starfront-roof.jsonl` so rollout step 1 can fix the parser. Each reading is appended with the time, so a night shows roof-open hours. The alpaca endpoint is a documented fallback, not built in Phase 1.

### Sun and night at the site

A small NOAA-style solar altitude function (no new dependency) gives, for the site and a UTC time: `daytime` (sun above 0 degrees), `dark` (sun below minus 18). `--starfront-watch` (the 20-minute task) exits at once in daytime; at night, with the roof open and the Seestar's newest sub older than `STARFRONT_SILENT_MINUTES`, it pushes "B15 open but no new subs since 02:10" once per night. It also appends the roof reading. The night's row (`dark hours`, `roof-open hours`, `captured hours`) is derived from the roof log and the subs' stamps when the record is built.

### The record (additive)

Top level `starfront`:

```
{"camera": "ZWO Seestar S50 Pro (Starfront)", "site": "Starfront", "timezone": "America/Chicago",
 "scannedAt": iso, "scanAge": hours, "tunnel": {"up": bool, "lastOk": iso, "mode": "on-demand", "hold": false},
 "paused": false, "clock": "filename, unconfirmed",
 "storage": {"usedGb", "freeGb", "totalGb", "gbPerNight", "fullInNights", "pullNow"},
 "roof": {"state", "since", "readAt"},
 "projects": [{"name", "tid", "target" (display), "codes", "mosaic": bool, "hours", "subs", "stacks", "gb",
               "targetHours", "percent", "eta": {"nights": n, "date": iso} | null, "status", "flags": [],
               "nights": [{"night", "hours", "subs"}], "byFilter": {...}, "byGain": {...},
               "firstNight", "lastNight", "notifiedReadyAt"}],
 "nightsLog": [{"night", "darkHours", "roofOpenHours", "capturedHours"}],
 "darklibrary": {"files", "gb", "newestMtime"}}
```

A unit card in `units[]` for the Starfront Seestar (id `S50P-STARFRONT`, label `S50 Pro · Starfront`, kind `seestar`, site `Starfront`, `onScope` its own scope) built from the `starfront` section while no ledger rows exist: `current` = projects with subs inside the active window, newest first, as dataset summaries with `state` `capturing` (collecting) or `ready_to_process` (ready), `nextAction` "Collecting · 14.1 of 20 h · ready in about 3 nights" or "Ready to pull · 20.3 of 20 h"; `strip` from hours per night; `moreReady` = ready projects beyond `current`. Once Phase 2 pulls write ledger rows with the Starfront camera, the ordinary unit logic takes over and the two sources are merged by target (the scan's facts win for hours still on the scope). `scopes[]` gains the Starfront scope with its site. Night dates in the section are the site's.

### The contract

`S50P-STARFRONT`: `archive_root` becomes `S50P-Starfront` (a new root on the archive; nothing shares the home S50P folders or their Day numbering), `match.camera` becomes `ZWO Seestar S50 Pro (Starfront)`, `site` stays `Starfront`, `timezone` `America/Chicago` is added, the `unit` key is removed (that is what switches the entry on), the note says the unit is known by the share it came from. New hash in `shipped.sha256`. The card order (1.9.0) puts it after the home S50 Pro.

### The page

An Explore view "Starfront" with: hours vs target bars per project coloured by status; cumulative hours over nights with the ETA; the nights strip (nights with data, dark and roof-open hours when known) and the last scan time; storage used, free and the forecast; the flags and the pause and hold states. The unit card appears on the landing by itself through `units[]`. The project detail (layer 3) for a Starfront project shows the scan's facts until pulled rows exist.

### The panel

A "Starfront" line on the Panel tab: last scan, tunnel state, roof state, paused or not, and a "Scan now" button (`need_camera=False`, under the oplock). Pull comes in Phase 2.

### Scheduling

Phase 1 registers two tasks in `install-windows.ps1` with the installer's existing helper and `-RunLevel Limited`: "Astro Starfront scan" every 2 hours and "Astro Starfront watch" every 20 minutes (the watch exits at once in daytime). Both "run as soon as possible after a missed start". `selftest.py` lists them.

### Tests (chain SF in `test_v2.py`; SF checks in `test_app.py`)

The share is a folder in the test root. Checks: the zone check fails closed; hours from filenames; the header fallback once, cached; a changed file is re-parsed and an unchanged one is not; projects grouped with `_mosaic_pt`; nights in America/Chicago (a sub at 02:00 Chicago on 7 Nov belongs to the night of 6 Nov; a sub at 23:00 UTC does not shift by the UK clock); the sanity flags; free space and the forecast; targets with overrides winning; one push per crossing, again after the target is raised; the tunnel: up by probe, hold flag, `never`, missing service, `sc start` recorded not run, access denied; dead-link classification; the roof reader closes its handle (the test holds the file open for exclusive access after the read on Windows, elsewhere it checks the file object is closed) and parses the three formats; the pause flag reported; the silent alert once per night and never in daytime; a UNC path escaping `MyWorks` refused; a mapped drive refused; a listing error leaves the cache untouched and the scan incomplete; `--projects` adds the `starfront` section and the unit card; the home S50 Pro's rows and camera are untouched; nothing is written on the share (os-calls and a listing diff). Panel: the Starfront line and Scan now; the page: the Explore view and the card.

## Phase 2 (pull) and Phase 3 (clear): settled points carried forward

- `copy_file_verified` deletes its `.partial` on failure and never resumes; "restartable" means the ledger resumes at the next file, and a dropped copy re-copies the whole file. Parallel copies: workers copy, one thread adds ledger rows.
- `archiveVerifiedAt` on the PC is set by the sweep, so "shipped with read-back" waits for the sweep.
- Receipts carry no site today; Phase 2 adds `site`, `hours`, `nights` to the Starfront receipt (AstroLog keys on `telescope`; a project-map link to update).
- The clear gate's `os.walk` and bare `os.listdir` calls (CODE-MAP section 1) get error handling in Phase 3, where every listing error means STOP; the current gate also removes emptied top-level folders, which the Starfront clear must not do (its own gate, same camera check).
- `seestar-wormhole` is assessed in Phase 2 and reported, not built.
