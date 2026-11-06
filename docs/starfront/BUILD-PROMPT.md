You are working on my BrettjoAstro FITS Importer (github.com/Brettjo77/brettjoastro-fits-importer, v1.7.6, astro-import.py plus astro-app.py, custom test harness: py -3 -X utf8 test_v2.py and test_app.py, all existing checks must stay green). Read CLAUDE.md, PARITY.md and README first. Rules 2 (SAFE delete) and 6 (one ledger per machine) matter most here. Also read these docs in the starfront-build-pack/docs folder:
- starfront-discord-automation-research.md
- starfront-vpn-access.md
- starfront-seestar-grounding.md
Writing style: no em dashes or double dashes. Deliver code as a zip plus the individual files, with numbered install steps and exact commands. I've approved the build; don't stop to ask about routine steps. Only stop at the rollout checkpoints below.

GOAL (release 1.8.0): a "Starfront" source for my Seestar S50 Pro hosted at Starfront Observatories, Rockwood, Texas (lat 31.54733, lon -99.38273, America/Chicago), Building 15, pier B15-SB-B17. It runs on my Windows 11 PC (SKYLARKPC, archive at E:\Astro Image Data). It should:
1. Count integration hours per project on the Seestar from file listings alone, with no downloads.
2. Graph progress in my Observatory dashboard (run_observatory; dataset at E:\Astro Config Data\Observatory\dataset.json).
3. Notify me once when a project reaches its target (default 20 h, settable per project). Download nothing until I press Pull in the panel.
4. Pull FITS only (subs plus the Seestar's own stacks, never JPGs), verified by SHA-256 at both ends.
5. Clear the verified project off the Seestar, per project, never by formatting. Confirm-first by default; STARFRONT_AUTO_CLEAR=true makes it automatic later.
6. Survive WireGuard drops.
No daily manual download that depends on the Texas weather.

FACTS ESTABLISHED (6 Nov 2026)
- Tunnel: WireGuard for Windows, tunnel "BrettJohnson-B15". VPN address 10.15.250.16; AllowedIPs 10.15.10.212 (Seestar) and 172.16.5.21 (customer share); endpoint 74.84.11.76:51820; MTU 1280; keepalive 25. ONE device on the tunnel at a time: two devices on the same keys make copies fail (community reports).
- Seestar share: \\10.15.10.212\EMMC Images (Samba 4.19.5). Log in as guest with a BLANK password (net use \\10.15.10.212\IPC$ /user:guest ""). Without that, Windows gets error 5. Layout:
  - darklibrary\, which the Seestar uses for its darks and an app format wipes;
  - MyWorks\<Target> (stacks .fit and .jpg);
  - MyWorks\<Target>_sub (subs .fit and .jpg);
  - mosaics also have <Target>_mosaic, <Target>_mosaic_sub and a _mosaic_pt folder.
- Sub filename format (rental example; confirm on mine): Light_M 17_30.0s_LP_20261027-195802_1032.fit. That's target, exposure in seconds, filter (LP or IRCUT), date-time stamp, frame number. So exposure IS in the name.
- S50 Pro app subs: GAIN 200 in the header, frames 2160 x 3840, XBAYROFF present. SITELAT, SITELONG and a frame-count keyword are unconfirmed.
- Roof share: \\172.16.5.21\sfro-customer (guest/guest), folders roof, weather, images. Starfront staff added a lock cleaner after a client held roof files open, so open roof files READ ONLY, read them, and close immediately. Fallback feed: alpaca-api.tx.starfront.space/api/v1/roof/state (device_number 15; undocumented). My starfront-sky-calendar repo already parses B15 roof state; reuse that parser.
- Windows guest SMB needs (admin) Set-SmbClientConfiguration -EnableInsecureGuestLogons $true -RequireSecuritySignature $false, and an update can reset it. Treat SMBClient event 31017 as "guest rejected", not "tunnel down".
- Starfront policy:
  - owners may delete from the Seestar after transfer (help article "Transfer Files from Your Seestar (Windows)", Jiro, 21 Aug 2026);
  - download the next day in Texas daytime;
  - leave the Seestar homed with no plan running when night work is expected;
  - heavy pulls hurt the Seestar's control latency (zmerlynn);
  - Alpaca crash logs have been seen filling Seestar storage;
  - an S50 Pro filled 60 GB in 3 days.

REUSE (astro-import.py): scan_seestar, seestar_model_ex / _seestar_creator_model, _seestar_file_night, _sub_meta, _seestar_day_number, copy_file_verified, hash_file_unbuffered, _seestar_ledger_add, State.add_file, State.key_for, mark_cleared, history_event, _atomic_write_json, seestar_safe_cleanup and _seestar_unproven_files, _jpeg_twin_proven, run_ship, _ShipLock, notify(), run_observatory, contract/scopes.json (disabled S50P-STARFRONT entry) and contract/targets.json. First confirm or correct these, and the line references below, against the repo.

DESIGN

A. --starfront-scan (read only and cheap)
- List only MyWorks top level, plus *_sub and *_mosaic_pt folders. Seestar SMB listings are slow, so keep starfront-inventory.json (keyed by path + size + mtime) and refresh incrementally.
- Hours = sum of the exposure parsed from each sub .fit filename. If a name lacks it, read only the first 2880-byte FITS header block for EXPTIME, once ever, cached.
- Group into projects: target + _sub + _mosaic_pt for mosaics.
- Per project, record:
  - hours;
  - subs;
  - hours per night;
  - nights;
  - GB on the scope;
  - % of target;
  - ETA from clear nights in the last 14 calendar nights;
  - a split by filter and gain (filter from the filename, gain from the cached header);
  - status: collecting / ready / pulling / pulled-awaiting-clear / cleared.
- Also: Seestar free space (shutil.disk_usage on the UNC root), a "full in N nights" forecast from GB per night, and "pull now" flags when the days left fall below a threshold.
- Write a starfront section into the Observatory dataset.

B. Targets: STARFRONT_DEFAULT_HOURS=20, overrides in starfront-targets.json keyed by the canonical name from targets.json, editable in the panel.

C. Notify: one push when a project first goes ready. notify() today is Windows toast plus panel only, so add NOTIFY_PUSH_URL (ntfy, which my sky calendar already uses) as a single HTTP POST.

D. Pull: --starfront-pull PROJECT, or the panel's Pull button.

Guards:
- tunnel up;
- B15 roof CLOSED for at least STARFRONT_ROOF_CLOSED_HOURS (2);
- Texas daytime;
- no pause flag;
- lock free.
Pause flag: starfront-pause in the state folder, which I set when a Starfront ticket or night work is open.

Copy:
- .fit only, into a NEW archive root, S50P-Starfront. Don't share the home S50P root: Day numbering counts the Day folders on disk, and os.replace could overwrite a file.
- Camera "ZWO Seestar S50 Pro (Starfront)", taken from the SHARE PATH, never from the FITS headers, in both the scan and the delete re-check.
- Turn on S50P-STARFRONT in scopes.json by REMOVING the "unit" key (resolve_scope skips any entry with a unit key), with match.camera set to the new name and timezone America/Chicago.
- Parallel copies: default 8 workers, configurable up to 32. At 120 to 230 ms latency a single stream is slow; Starfront owners in Europe report 2.5 to 3 times faster with 32 to 64 robocopy threads. Keep parallelism daytime only, because of the latency warning.
- Restartable: copy_file_verified with .partial files.

Verification (hash at both ends):
- Hash the stream during the copy, then re-hash the local copy with hash_file_unbuffered. _hash_dest_uncached only bypasses the cache on the Mac.
- Before any clear, re-read every source .fit with hash_file_unbuffered and compare. This doubles the traffic, which I accept, and it happens in daytime only.
- A re-hash counts as proof only if the read mode was "unbuffered", because Samba leases mean a normal re-read can come from the client cache.
- Only then write sourceRehashed: true and sourceSha256 on the ledger row. A mismatch quarantines the copy and blocks the clear.

Afterwards: write the receipt (site "Starfront", hours, nights), ship with read-back if shipping is configured, and push "M 42 pulled and verified".

darklibrary: copy it to the archive (read only, never cleared) whenever it changes, so I have the darks for Siril.

E. Night boundaries: split Starfront nights in America/Chicago, not by a noon pivot on the filename's clock. In rollout step 1, check which clock the filename stamp uses against DATE-OBS. On Windows, add tzdata; if the zone can't be loaded, fail closed.

F. Header sanity checks (headers are cached, so they're cheap). Flag a project when:
- SITELAT/SITELONG (if present) are more than 0.1 degrees from the site;
- DATE-OBS and the filename stamp disagree;
- exposure, gain or filter is mixed;
- the pointing moves by more than about 10 arcmin between nights.

G. CLEAR (amend CLAUDE.md rule 2 for this camera only). A project is SAFE only when ALL of these hold:
- every .fit is verified AND sourceRehashed at its current size, with an EXACT mtime match (not the card tolerance of 15-minute multiples up to 14 h);
- settled: size, mtime and file count are unchanged across two listings at least 30 minutes apart, timed by the PC's clock, with no mtimes in the future;
- shipped with read-back, if shipping is configured;
- each JPG is exempt only when its own same-name .fit is proven (keep the _jpeg_twin_proven rule); unknown file types block.

Rules for the clear itself:
- Re-run every pull guard right before the second check in seestar_safe_cleanup, failing closed.
- Delete per project, never format.
- Delete JPG and _thn files first, then FITS.
- Never remove the top-level target or _sub folders (the scope may write into them).
- Any listing error during the gate means STOP. The listdir walks around lines 9404 and 9424 have no error handling today.
- Mark a project "cleared" only after a later listing confirms the files are gone.
- darklibrary is never deleted; add a test that explicitly refuses it.
- A second pull of a growing project continues Day N, and its clear removes only proven files.

H. WireGuard ensure-tunnel
- STARFRONT_VPN_MODE = always | on-demand | never (default on-demand).
- Hold flag starfront-vpn-hold: never start the tunnel (I'm using it on my phone).
- ensure_tunnel(timeout=60):
  - TCP 445 on 10.15.10.212 answers within 3 s: up;
  - else, if hold flag or mode never: return False;
  - else query service WireGuardTunnel$BrettJohnson-B15 with sc (missing service = alert "not installed");
  - if stopped, sc start it and remember we started it;
  - poll every 5 s until the timeout.
- Never stop a tunnel the tool didn't start.
- DEAD-LINK DETECTION BY PROGRESS, NOT PING: Starfront owners have seen ping stay fine while transfers fall to near zero. Treat either of these as a drop:
  - no bytes for STARFRONT_STALL_SECONDS (120);
  - Windows errors 53, 59, 64, 67, 121 or 1231.
- On a drop: ensure_tunnel, retry after 5, 15 and 45 s, then stop cleanly, delete the .partial, and let the ledger resume next run.
- Keep last_ok. Send one alert after STARFRONT_VPN_ALERT_HOURS (12) down, and one on recovery.
- UNC paths only, no mapped drives.
- Service install (admin): wireguard.exe /installtunnelservice "C:\Program Files\WireGuard\Data\Configurations\BrettJohnson-B15.conf.dpapi". Check auto-start with sc qc. Scheduled tasks that may start the service run with highest privileges.

I. "Seestar silent" alert: roof open, astronomically dark, no new subs for 90 minutes. Push "B15 open but no new subs" so I can power-cycle with my SwitchBot. Use a light newest-file check every 20 minutes during the Texas night. Log roof open/close times so each night shows dark hours, roof-open hours and captured hours.

J. Morning digest (one push after Texas dawn), e.g. "Night 6 Nov: M 42 +2.3 h (14.1 of 20), M 45 +0 h, roof open 5.5 h, Seestar full in about 9 nights". On each Observatory project card, show the newest stack JPG as a thumbnail (a read-only cached copy).

K. Observatory Starfront panel:
1. hours vs target bars, coloured by status;
2. cumulative hours over nights with ETA;
3. a calendar strip of nights with data plus the last scan time;
4. Seestar storage used, free and forecast.

L. Scheduling (Task Scheduler, "run as soon as possible after a missed start"): scan every 2 hours, the silent check every 20 minutes during the Texas night, the digest after dawn. Pulls only on my approval.

M. Tests to add:
- hours from filenames, with the header fallback and the cache;
- one notification per threshold crossing, with overrides winning;
- pull and clear each refuse on roof open, roof unreadable, roof closed for less than 2 h, tunnel down, lock held, pause flag or night time;
- .fit only is copied;
- a source re-hash mismatch, or a buffered re-hash, blocks the clear;
- the JPG twin rule holds for Starfront and is NOT relaxed for the home S50P;
- the settle check needs two listings;
- darklibrary is never deleted, but is copied;
- a stall with no bytes counts as a drop and resumes with no stray .partial;
- a listing error stops the clear;
- Starfront and home rows don't collide;
- confirm "n" deletes nothing;
- top-level folders are never removed;
- a UNC path escaping MyWorks is refused;
- the mosaic _mosaic_pt folder is counted and pulled;
- the roof file handle is closed after each read;
- parallel copy workers respect the configured limit;
- the Observatory dataset includes the starfront section.
Tests sandbox a folder as the UNC root (test_env_helper.make_env). Update CLAUDE.md (rule 2 amendment), PARITY.md, README and CHANGELOG.

ROLLOUT (stop and wait for my output at each step)
1. Read only: --starfront-scan. Check:
   - my real filename format and filter codes;
   - which clock the stamp uses;
   - the SITELAT/SITELONG/GAIN headers;
   - hours against the Seestar app;
   - free space;
   - the roof file format;
   - SMB mtime behaviour;
   - whether guest can delete: create and delete a throwaway file in MyWorks.
2. Look at the Observatory panel.
3. First pull: the M 45 mosaic, with its target set low temporarily. Check the ledger, receipt, Siril, and --verify --deep.
4. First clear: confirm y for M 45 only. Then check the app album on the Mac mini, and that darklibrary is intact.
5. A few weeks of confirmed clears, then STARFRONT_AUTO_CLEAR=true.

PRIOR ART (for patterns, not to copy)
- github.com/dasshark/starfront: PowerShell task. It checks state, transfers, moves files to a "transferred" folder, and reports via a Discord webhook.
- github.com/avleen/astro-tools: sub selection by eccentricity, stars and FWHM. A possible later stage after a pull.
- github.com/zmerlynn/seestar-wormhole: a Telescope Network proxy giving SMB with no VPN, handling reconnects. Assess it as a FALLBACK route when the VPN is down (UNC root on a local forwarded port) and report back before building it.
Nobody on the Starfront Discord has built hours tracking, threshold pulls, hash verification or automated per-project clears. This is new.

Start: read the repo and docs, confirm the references, give me a short phased build plan, then build.
