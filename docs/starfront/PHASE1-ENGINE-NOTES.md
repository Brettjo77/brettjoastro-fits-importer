# Starfront Phase 1 (read only): the engine as built

Built 6 Nov 2026 on branch `claude/starfront` against `docs/starfront/DESIGN.md`. This note is what landed in `astro-import.py`, `test_v2.py`, the contract, the Windows installer and `selftest.py`, and where it differs from the design note and why. Plain words, no em dashes or double dashes.

## What it does

The PC lists the hosted Seestar's share over the WireGuard tunnel every 2 hours and counts integration hours per project from the file names alone. Nothing is downloaded, nothing on the Seestar is written or deleted, and the ledger is never touched. At night, every 20 minutes, it reads the roof file and says when the Seestar has gone silent. The Observatory record gains a `starfront` section and a unit card for the Texas Seestar.

Everything lives in one marked section of the engine, `STARFRONT SOURCE (1.10.0, Phase 1: read only)`, just before `run_projects`; every function is prefixed `sf_` or `starfront_` (plus `ensure_tunnel`, `read_roof`, `notify_push` and `StarfrontStall`). The listing is `os.scandir` only, one call per folder, never `os.walk`; a test reads the source to make sure.

## Config keys (`config.json` in `%LOCALAPPDATA%\Astro Import`, or an environment variable)

| Key | Default | Notes |
|---|---|---|
| `STARFRONT_SHARE` | `\\10.15.10.212\EMMC Images` | UNC only. A drive letter is refused with the UNC path named. In test mode a folder inside the test root. |
| `STARFRONT_CAMERA` | `ZWO Seestar S50 Pro (Starfront)` | The camera name on every Starfront row; from the share, never a header. Must equal the contract's `match.camera`. |
| `STARFRONT_TZ` | `America/Chicago` | If it can't load, every Starfront command stops (exit 1) and says to install tzdata. |
| `STARFRONT_LAT`, `STARFRONT_LON` | 31.54733, -99.38273 | The site. |
| `STARFRONT_DEFAULT_HOURS` | 20 | Unless `starfront-targets.json` overrides. |
| `STARFRONT_VPN_MODE` | `on-demand` | `always`, `on-demand` or `never` (a new `_env_choice` helper; a typo falls back with a CONFIG_WARNINGS note). `always` behaves as `on-demand` in Phase 1. |
| `STARFRONT_VPN_TUNNEL` | `BrettJohnson-B15` | Service `WireGuardTunnel$<name>`. |
| `STARFRONT_SEESTAR_IP` | `10.15.10.212` | The probe host, port 445. |
| `STARFRONT_STALL_SECONDS` | 120 | A drop by progress (used by `sf_is_link_drop`; Phase 2's copies). |
| `STARFRONT_VPN_ALERT_HOURS` | 12 | One alert after this long down, one on recovery. |
| `STARFRONT_ROOF_SHARE` | `\\172.16.5.21\sfro-customer` | The roof file sits under `roof\`. |
| `STARFRONT_ROOF_FILE` | empty | Empty means the newest file under `roof\`. |
| `STARFRONT_ROOF_CLOSED_HOURS` | 2 | Phase 2's pull guard (read, not used yet). |
| `STARFRONT_SILENT_MINUTES` | 90 | The silent alert. |
| `STARFRONT_FULL_WARN_NIGHTS` | 5 | `pullNow` when "full in N nights" is under this (DESIGN step 7 named it; it was not in the table). |
| `NOTIFY_PUSH_URL` | empty | An ntfy topic URL. One POST per push. Empty means no push. |
| `STARFRONT_AUTO_CLEAR` | false | Phase 3 only (read, unused). |
| `STARFRONT_WORKERS` | 8 (1 to 32) | Phase 2 only (read, unused). |

State files, all in the state folder and confined in test mode: `starfront-inventory.json` (the listing cache keyed by relpath, reused when size and mtime match), `starfront-headers.json` (the cached header facts per sub, keyed the same way), `starfront-targets.json` (`{"Orion Nebula (M 42)": 12}`, keyed by the contract's display name), `starfront-status.json` (per project `status`, `notifiedReadyAt`, `hours`; `tunnel.lastOk`, `downAlertedAt`, `serviceAlert`, `lastReason`; `silentAlertedNight`; `lastWatch`), `starfront-roof.jsonl` (one row per reading: `at`, `state`, `since`, `file`, `raw`), `starfront-last-scan.json` (the scan's summary). Flags: `starfront-pause` and `starfront-vpn-hold` (empty files Brett creates and removes).

## Commands

- `--starfront-scan`: the zone check, `ensure_tunnel()`, the listing, the caches, projects, storage, the ready push, `starfront-last-scan.json`. Prints one line per project, the storage line, then for one sub per project the stamp beside DATE-OBS. Exit 1 when the tunnel is down or a listing fails ("incomplete": the caches are left exactly as they were). It does not rebuild `projects.json`; `--projects` and `--pc-nightly` read the scan file.
- `--starfront-target NAME HOURS`: sets one project's target (`--starfront-target "M 45" 12`); `0` removes the override. A mosaic shares its object's target.
- `--starfront-watch`: in daytime at the site exits at once, before the tunnel is touched. At night: `ensure_tunnel()`, the roof reading appended, and with the roof open, the sky dark (sun under minus 18 degrees) and no new sub for `STARFRONT_SILENT_MINUTES`, one push per night: "B15 open but no new subs since 21:00".

All three run on the PC (Windows) or in test mode; on a Mac they say the Starfront source runs on the PC (DESIGN decision 3).

For the panel: `starfront_panel_status()` returns `{configured, share, lastScan, scanAge, projects, tunnelLastOk, tunnelReason, vpnMode, hold, paused, roof, roofReadAt, storage}`; `run_starfront_scan()` returns `{"ok": bool, ...}` and prints the same lines as the command, so the panel can run it under the oplock with `need_camera=False`.

## The record (observatory.json)

Only when `starfront-last-scan.json` exists. Without it nothing is added and an old record is byte for byte as before (a test proves it). With it, three additions, all additive:

1. a top-level `starfront` section;
2. a unit card in `units[]`, right after the home S50 Pro's (id `S50P-STARFRONT`, label `S50 Pro · Starfront`, kind `seestar`, `site: "Starfront"`, built with the same `_obs_unit` as every other card, so `current` is dataset summaries with exactly the phase 2 keys, newest first, at most two, `strip` from hours per night, `moreReady` the ready ones left over);
3. a scope in `scopes[]` with `site`. `scopeOrder` is left as it was (the ledger's scopes with frames).

Once Phase 2's pulls write ledger rows with the Starfront camera, `_obs_units` makes the card the ordinary way and the two additions above are skipped (the section stays).

The section, from the SF fixture (900 subs of 30 s of M 42 over three nights, a 60-sub M 45 mosaic with its target set to 0.1 h, the roof read twice in the night of 6 Nov; `nights` cut short here):

```json
"starfront": {
  "camera": "ZWO Seestar S50 Pro (Starfront)", "site": "Starfront", "timezone": "America/Chicago",
  "scannedAt": "2026-11-07T09:00:00+00:00", "scanAge": 0.3,
  "tunnel": {"up": true, "lastOk": "2026-11-07T09:00:00+00:00", "mode": "on-demand", "hold": false},
  "paused": false, "clock": "filename, unconfirmed",
  "storage": {"usedGb": 61.2, "freeGb": 194.8, "totalGb": 256.0, "gbPerNight": 0.0, "fullInNights": null, "pullNow": false},
  "roof": {"state": "open", "since": "2026-11-07T01:10:00Z", "readAt": "2026-11-07T06:20:00+00:00"},
  "projects": [
    {"name": "M 42", "tid": "M42", "target": "Orion Nebula (M 42)", "codes": ["M 42", "NGC 1976"], "mosaic": false,
     "hours": 7.5, "subs": 900, "stacks": 1, "panels": 0, "gb": 0.0, "targetHours": 20.0, "percent": 37.5,
     "eta": {"nights": 6, "date": "2026-11-12", "hoursPerClearNight": 2.5}, "status": "collecting", "flags": [],
     "nights": [{"night": "2026-11-04", "hours": 2.5, "subs": 300}, {"night": "2026-11-05", "hours": 2.5, "subs": 300}, "..."],
     "byFilter": {"LP": 7.5}, "byGain": {"200": 7.5}, "firstNight": "2026-11-04", "lastNight": "2026-11-06",
     "notifiedReadyAt": null,
     "clock": {"night": "2026-11-06", "stamp": "20261106-200000", "dateObs": "2026-11-07T02:00:00",
               "stampAsUtc": "2026-11-07T02:00:00+00:00", "differenceMinutes": 0.0, "agree": true}},
    {"name": "M 45_mosaic", "tid": "M45", "target": "Pleiades (M 45) (mosaic)", "codes": ["M 45", "Mel 22"], "mosaic": true,
     "hours": 0.17, "subs": 60, "stacks": 0, "panels": 1, "gb": 0.0, "targetHours": 0.1, "percent": 166.7,
     "eta": null, "status": "ready", "flags": [], "nights": [{"night": "2026-11-06", "hours": 0.167, "subs": 60}],
     "byFilter": {"IRCUT": 0.17}, "byGain": {"200": 0.17}, "firstNight": "2026-11-06", "lastNight": "2026-11-06",
     "notifiedReadyAt": "2026-11-07T09:00:00+00:00", "clock": {"...": "as above"}}
  ],
  "nightsLog": [
    {"night": "2026-11-04", "darkHours": 10.5, "roofOpenHours": 0.0, "capturedHours": 2.5},
    {"night": "2026-11-05", "darkHours": 10.5, "roofOpenHours": 0.0, "capturedHours": 2.5},
    {"night": "2026-11-06", "darkHours": 10.5, "roofOpenHours": 1.0, "capturedHours": 2.67}
  ],
  "darklibrary": {"files": 1, "bytes": 5000, "newestMtime": "2026-11-06T16:21:00+00:00"},
  "share": "\\\\10.15.10.212\\EMMC Images", "incomplete": false
}
```

The unit card and the scope from the same fixture:

```json
{"id": "S50P-STARFRONT", "label": "S50 Pro · Starfront", "name": "Seestar S50 Pro (Starfront)", "kind": "seestar",
 "scopeIds": ["S50P-STARFRONT"], "scopes": ["Seestar S50 Pro (Starfront)"], "colour": "#ec835a", "short": "S50P-STARFRONT",
 "onScope": "Seestar S50 Pro (Starfront)", "onScopeId": "S50P-STARFRONT", "onScopeCurrent": true,
 "active": true, "lastOut": "2026-11-06",
 "current": [
   {"tid": "M45", "target": "Pleiades (M 45) (mosaic)", "codes": ["M 45", "Mel 22"], "camera": "Seestar S50 Pro (Starfront)",
    "scopeId": "S50P-STARFRONT", "state": "ready_to_process", "stateWord": "Ready to process", "hours": 0.17, "frames": 60,
    "nights": 1, "firstNight": "2026-11-06", "lastNight": "2026-11-06", "readySince": "2026-11-07",
    "reason": "ready · 0.2 of 0.1 h on the Starfront Seestar", "nextAction": "Ready to pull · 0.2 of 0.1 h",
    "calMissing": false, "mosaic": true},
   {"tid": "M42", "target": "Orion Nebula (M 42)", "codes": ["M 42", "NGC 1976"], "camera": "Seestar S50 Pro (Starfront)",
    "scopeId": "S50P-STARFRONT", "state": "capturing", "stateWord": "Still capturing", "hours": 7.5, "frames": 900,
    "nights": 3, "firstNight": "2026-11-04", "lastNight": "2026-11-06", "readySince": null,
    "reason": "collecting · 7.5 of 20 h on the Starfront Seestar", "nextAction": "Collecting · 7.5 of 20 h · ready in about 6 nights",
    "calMissing": false, "mosaic": false}
 ],
 "moreReady": 0, "moreReadyHours": 0.0,
 "strip": [{"night": "2026-11-04", "hours": 2.5}, {"night": "2026-11-05", "hours": 2.5}, {"night": "2026-11-06", "hours": 2.67}],
 "latestDone": null, "site": "Starfront", "starfront": true}

{"camera": "Seestar S50 Pro (Starfront)", "id": "S50P-STARFRONT", "frames": 960, "hours": 7.7, "nights": 3, "bytes": 0,
 "first": "2026-11-04", "last": "2026-11-06", "colour": "#ec835a", "order": 7, "kind": "seestar",
 "active": true, "lastOut": "2026-11-06", "site": "Starfront", "starfront": true}
```

Statuses: `collecting` and `ready` (the card's `capturing` and `ready_to_process`). `pulling`, `pulled-awaiting-clear` and `cleared` come with Phase 2 and 3. Flags: `site-mismatch`, `clock-mismatch`, `mixed-settings`, `pointing-moved`, `unknown-name`. `eta` is null when the project is ready or no night in the last 14 has data. Night dates are the site's.

The scan's own lines, for rollout step 1:

```
▸ M 42: 7.5 of 20 h (38%), 900 subs, 3 nights, 0.0 GB; ready in about 6 nights [collecting]
▸ M 45_mosaic: 0.2 of 0.1 h (167%), 60 subs, 1 night, 0.0 GB; ready [ready]
▸ Storage: 61.2 GB used, 194.8 GB free of 256.0 GB; 0.0 GB per night; no nightly rate yet
▸ M 42: stamp 20261106-200000 (as site time = 2026-11-07T02:00:00+00:00) vs DATE-OBS 2026-11-07T02:00:00 UTC: agree by 0 min
  962 files listed (0 unchanged, 962 parsed), 4 header reads, 0.0 s; pushed: M 45_mosaic
```

The stamp is taken as the Seestar's own clock on site time. If the real stamps turn out to be UTC, every project will show "differ by 360 min" and the flag `clock-mismatch`: that is the signal, and the fix is one line in `sf_stamp_dt`.

## Install steps on the PC (PowerShell, as Brett, not as administrator)

1. The zone database, once (python.org's Python has none):

       py -3 -m pip install --user tzdata

2. The tunnel service, once, as administrator, so a limited task never has to start it (the installer's tasks run with limited rights and may not start a service). In an administrator PowerShell:

       wireguard.exe /installtunnelservice "C:\Program Files\WireGuard\Data\Configurations\BrettJohnson-B15.conf.dpapi"
       sc config "WireGuardTunnel$BrettJohnson-B15" start= auto
       sc query "WireGuardTunnel$BrettJohnson-B15"

   Then close that window. (The guest SMB settings from FACTS section 2 are also admin, once: `Set-SmbClientConfiguration -EnableInsecureGuestLogons $true -RequireSecuritySignature $false`.)

3. `config.json` (`$env:LOCALAPPDATA\Astro Import\config.json`): add the push topic and anything that differs from the defaults. Backslashes written twice:

       "NOTIFY_PUSH_URL": "https://ntfy.sh/<your topic>",
       "STARFRONT_SHARE": "\\\\10.15.10.212\\EMMC Images"

4. Run the installer as usual (`Install on Windows.cmd` from a normal window). It registers "Astro Starfront scan" (every 2 hours) and "Astro Starfront watch" (every 20 minutes), both "run as soon as possible after a missed start", both with limited rights. Then check:

       py -3 -X utf8 "$env:LOCALAPPDATA\BrettjoAstro\bin\selftest.py"

   It lists both tasks and says whether America/Chicago loads.

5. The first scan, by hand, in Terminal, and read its lines against rollout step 1's checks (the filename format and filter codes, the stamp against DATE-OBS, the SITELAT/SITELONG/GAIN headers, hours against the app, free space):

       py -3 -X utf8 "$env:LOCALAPPDATA\BrettjoAstro\bin\astro-import.py" --starfront-scan
       py -3 -X utf8 "$env:LOCALAPPDATA\BrettjoAstro\bin\astro-import.py" --projects

   The roof file's name and format: look in `\\172.16.5.21\sfro-customer\roof`, then either set `STARFRONT_ROOF_FILE` to it or leave it empty (the newest file under `roof\` is read). After the first night, `starfront-roof.jsonl` in the state folder holds the raw text of every reading, so the parser can be fixed against the real file.

6. A target for one project: `py -3 -X utf8 "...\astro-import.py" --starfront-target "M 45" 12`.

## Where it differs from DESIGN.md, and why

- The header read takes the first four 2880-byte blocks in one read (11.5 KB, one round trip), not one block. A Seestar header has more than 36 cards, so one block would stop before SITELAT, SITELONG and the pointing. Parsing stops at END.
- The stack folders (`<Target>`, `<Target>_mosaic`) are listed too, one `os.scandir` each (a handful of files), so `stacks` and the GB on the scope are real. DESIGN step 2 listed only the `_sub` and `_mosaic_pt` folders but step 6 wants `stacks`. The dark library is counted at its top level only. The record also carries `panels` (the `_mosaic_pt` count) and `share`.
- The ETA and the storage forecast both use the hours (or GB) per night WITH data in the last 14 calendar nights, not divided by 14: "hours per clear night", as DESIGN step 6 says; a near-zero rate forecasts nothing (`fullInNights` null, "no nightly rate yet").
- `byGain` is known only for the subs whose header was read (one per project per night), so a night's hours go to that night's first sub's gain. `byFilter` is from every name.
- The pointing check is skipped for mosaics (each sub points at a different panel).
- The watch's "newest sub" is the newest `*_sub` folder's own modification time from the one `os.scandir` of MyWorks (a folder's mtime moves when a file lands in it), not a listing of every sub folder: at 20-minute intervals that keeps the night's traffic to one round trip.
- The pause flag does not stop the scan or the watch (both are read only and light); it is reported in the scan file, the record and the panel status, and Phase 2's pull will refuse on it.
- `ensure_tunnel` returns `{"up", "reason", "started"}` rather than a bare False, so the callers can say why and whether this run started the service. Alerts for a missing service and for "access denied" are said once each (`tunnel.serviceAlert`), cleared when the tunnel comes up.
- `--starfront-target` keys the override by the contract's display name (`Orion Nebula (M 42)`); a lookup also tries the id and the folder name, and a mosaic shares its object's target.
- The contract entry's `name` is `Seestar S50 Pro (Starfront)` (was `(Starfront, Texas)`), the same shape as the other Seestars' (name = camera without `ZWO`), and its `colour` is `orange` so the card has one (the home S50 Pro has none). Brett can change both; the hash in `shipped.sha256` is the file as it is now.
- The installer's Starfront tasks are registered for every install (no gate on a config key), between sections 6 and 7 (so the W1 check that reads section 7 is untouched); the IN check that counted three `Register-AstroTask` calls now counts five.
- The tests set `ASTRO_TEST_SC` (missing, stopped, running, denied) to script what `sc` would answer, `ASTRO_TEST_SF_FAIL_LIST` to make one folder's listing fail, and the probe file `<root>/starfront-tunnel-up` for the tunnel. `sf_disk_usage` is a function of its own so a test can stand in a disk of a known size.

Not in Phase 1, by design: `config.example.json`, PARITY.md, CHANGELOG, README and the VERSION bump (Brett's), the panel line and the page (the other agent's), the pull and the clear.
