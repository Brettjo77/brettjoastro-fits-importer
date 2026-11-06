# Starfront source: the facts the builders code from

Digest written 6 Nov 2026 from the six documents in this folder plus CLAUDE.md and PARITY.md. Nothing here is new research: every line points at where it came from. Where the source documents rank their sources, the rank is given too.

How to read the tags:

- [BRIEF] = BUILD-PROMPT.md, Brett's brief for release 1.8.0 (sections A to M, the facts list, the rollout). Brett's own statement, so it wins over everything else unless it is a question of fact that a higher-ranked source settles.
- [VPN] = starfront-vpn-access.md, Brett's own tested results on his Windows PC, 6 Nov 2026.
- [DISCORD] = starfront-discord-automation-research.md, the Discord read-through of 6 Nov 2026. It labels posts staff, moderator or community. Staff counts as policy. Moderators speak for Starfront on process but are not staff. Community is one person's experience.
- [GROUND] = starfront-seestar-grounding.md, the 30 Oct 2026 source-of-truth sheet. It ranks sources 1 (Starfront staff, current), 2 (ZWO official), 3 (Mark's guide), 4 (community). Higher rank wins; newer wins at the same rank; rental-only advice is ignored unless it tells us how the scope or the site behaves.
- [SPEC] = starfront-auto-imaging-spec.md, the parked (30 Oct 2026) plan for a Mac mini imaging service. Not being built now; quoted only for facts it carries.
- [TICKET] = 02-starfront-ticket.txt, the ticket Brett has drafted to Starfront. Its three questions are open until Starfront answers.
- [CLAUDE] = CLAUDE.md rules 1 to 9. [PARITY] = PARITY.md "Differences by design". [SCOPES] = contract/scopes.json as it is on the branch today.

Where a fact appears only in the brief and nowhere else, it says "[BRIEF only]". Those are Brett's statements or working assumptions and the rollout's step 1 is where several of them get checked.

Command-line flags are quoted exactly as the code spells them.

* * *

## 1. The Seestar share

### Address, share and login

- UNC root: `\\10.15.10.212\EMMC Images`. The share name has a space, so quote the path. [VPN, tested 6 Nov] [BRIEF]
- The Seestar runs Samba 4.19.5 with ONE share, EMMC Images. [VPN, tested]
- Login: guest with a BLANK password. Windows tries the logged-in Windows account first and gets error 5 (Access Denied) unless a guest session to IPC$ is opened first: [VPN, tested] [BRIEF]
  - `net use \\10.15.10.212\IPC$ /user:guest ""`
  - `net use "\\10.15.10.212\EMMC Images" /user:guest ""`
  - `dir "\\10.15.10.212\EMMC Images\MyWorks"`
- No Starfront ticket was needed for share access over the VPN. [VPN, tested 6 Nov]. The older staff rule (Jiro, 4 Sep 2025, rank 1) that Seestar SMB is firewalled except from the owner's own system, arranged by ticket, concerns access from the Starfront network itself (the Mac mini). [GROUND section 6] [DISCORD finds]. Newer and tested wins for the VPN route; the firewall rule still stands for on-site access.
- Never connect to `smb://guest@10.0.0.1/EMMC Images`: that is the first Seestar on the network, possibly someone else's. Always use your own scope's IP. [GROUND section 6, staff, rank 1]
- Is 10.15.10.212 reserved so it will not change? Open, asked in the ticket. [TICKET question 3] [VPN "still open"]
- Starfront's owner guide "Transfer Files from Your Seestar (Windows)" (Jiro, staff, updated 21 Aug 2026, starfront.zendesk.com/hc/en-us/articles/51349163984532) says: WireGuard, map `\\IP\EMMC Images` as guest, copy from the `_sub` folders, and you may delete after transfer. It also has guest-logon fixes per Windows edition. [DISCORD finds, staff]
- The share is guest and unencrypted at your end (zmerlynn, community, 1 Nov 2026). [DISCORD finds]

### Folder layout

- Top level: `darklibrary` and `MyWorks`. [VPN, tested] [BRIEF]
- `darklibrary`: the Seestar's own darks. An app format wipes it (MarkH, community, 17 Oct 2026). [BRIEF] [DISCORD answer 2]. The brief wants it copied to the archive whenever it changes, read only, never cleared. [BRIEF section D]
- `MyWorks\<Target>`: stacks, `.fit` and `.jpg`. [BRIEF]
- `MyWorks\<Target>_sub`: the subs, `.fit` and `.jpg`. Subs only exist if "Save each frame" is on (Open Arm, Stargazing mode, three dots, Save each frame). [BRIEF] [GROUND section 6] [VPN]
- Mosaics: `<Target>_mosaic` and `<Target>_mosaic_sub` are confirmed on Brett's own unit ("M 42_mosaic", "M 42_mosaic_sub"). [VPN, tested]. The brief adds a `_mosaic_pt` folder. [BRIEF only]
- Deleting a stack inside the app deletes its FITS but leaves an empty folder in MyWorks (DocWaton, community, Nov 2025). [DISCORD answer 2]
- The Mac app's download folder, for reference only (the brief does not use it): `~/Library/Containers/<app id>/Data/Documents/LocalCache/Download/<scope id>/MyWorks/<target>_sub/`. [GROUND section 7, pinned 29 Oct]

### Filenames seen

- Sub, rental example (Mike1959's grading CSV, moderator, 28 Oct 2026, a rental Seestar, not Brett's): `Light_M 17_30.0s_LP_20261027-195802_1032.fit`. Read as: `Light`, target (with its space), exposure in seconds, filter code, date and time stamp, frame number. So exposure IS in the filename and hours can be counted from listings alone. [DISCORD answer 5] [BRIEF]
- Filter codes: `LP` when the light-pollution filter is in. `IRCUT` otherwise is "likely but not confirmed". [DISCORD answer 5]. The brief states "LP or IRCUT". [BRIEF]. Confirm on Brett's unit (rollout step 1).
- Nothing in the documents shows a stack filename, a JPG filename, or a thumbnail filename. The brief says to delete "JPG and _thn files first, then FITS", so `_thn` thumbnails are expected. [BRIEF section G only]. The stack `.fit` sits in `MyWorks\<Target>` and the brief wants it pulled with the subs. [BRIEF goal 4]
- Nothing on Brett's own unit's filenames is confirmed yet beyond the folder names above. [VPN] Rollout step 1 checks "my real filename format and filter codes". [BRIEF rollout 1]

### FITS headers, what is known

- `GAIN 200` in app subs from an S50 Pro (Ettaswell-Jon, community, 5 Nov 2026); Alpaca defaults to 80. [DISCORD answer 5] [BRIEF]
- Frame size 2160 x 3840; the header still says 1x1 binning even with the new binning option on (astrodreamer99, community, 19 Oct 2026). [DISCORD answer 5] [BRIEF]
- `XBAYROFF` is present (Space, community, Aug 2026); it affects how NINA reports the Bayer pattern. [DISCORD answer 5] [BRIEF]
- `SITELAT`, `SITELONG` and any frame-count keyword: nothing found. Unconfirmed. [DISCORD answer 5 and open checks] [BRIEF]
- `DATE-OBS` clock: unknown. The Seestar takes its time and location from the app when it connects (staff, rank 1) [GROUND section 3], and the on-site Mac is meant to run on US Central Time [SPEC section 4] [GROUND section 10, Mike1959]. So the filename stamp is probably Texas local, but which clock the stamp uses, and whether it agrees with DATE-OBS, is rollout step 1's check. [BRIEF section E and rollout 1]. Known related bug: NINA could not set the Seestar's clock unless the app had connected first (ZWO forum, Jan 2026). [GROUND section 4]
- `EXPTIME` fallback: if a filename lacks the exposure, read only the first 2880-byte header block, once ever, cached. [BRIEF section A]. The Discord doc proposed the same ("my suggestion, not something anyone posted"). [DISCORD "what this changes" 2]

### Exposure and advice

- Starfront advise 30 s subs for rentals (alt-az; longer subs get rejected or trailed). Rental advice; in EQ mode longer is worth testing. [GROUND section 5, staff via moderator pin 25 Oct 2026]

### mtime and listing behaviour over SMB

- No document describes how mtimes behave on this share. Rollout step 1 checks "SMB mtime behaviour". [BRIEF rollout 1]. The clear gate wants an EXACT mtime match, not the home card's tolerance. [BRIEF section G]
- Seestar SMB listings are slow, so cache them (`starfront-inventory.json`, keyed by path + size + mtime, refreshed incrementally). [BRIEF section A] [DISCORD "what this changes" 3]
- rclone's incremental re-check for new files on a Seestar share took under a second, 18 MiB/s with 8 transfers on a LAN (KP7, community, Jan 2026). [DISCORD answer 1]
- Samba leases mean a normal re-read can come from the client cache, so a re-hash counts as proof only when the read mode was "unbuffered". [BRIEF section D]

### Storage

- An S50 Pro filled over 60 GB in 3 days and held about 100 GB by 26 Oct with no reported problem (Ettaswell-Jon, community). [DISCORD answer 3] [BRIEF]
- Alpaca service crash logs filled a Seestar's storage (Space, community, 15 Oct 2026). Something other than subs can eat the space. [DISCORD answer 3] [BRIEF]
- Nobody stated the S50 Pro's capacity or the full-storage behaviour. Check free space rather than assume. [DISCORD answer 3]. The brief reads free space with `shutil.disk_usage` on the UNC root. [BRIEF section A]. `dir` on the share also prints bytes free. [DISCORD open checks]

* * *

## 2. The tunnel

### WireGuard config (from Starfront, 6 Nov 2026)

- Tunnel name: `BrettJohnson-B15`; config file `BrettJohnson-B15.conf` (holds the private key; password manager only, never shared, never in the repo). [VPN] [CLAUDE rule 8]
- Brett's VPN address: 10.15.250.16. [VPN] [BRIEF]
- AllowedIPs (split tunnel, only these go over the VPN): 10.15.10.212 (the Seestar) and 172.16.5.21 (the customer share). The Mac mini is NOT in AllowedIPs; reach it with RustDesk. [VPN] [BRIEF]
- Endpoint 74.84.11.76:51820, MTU 1280, PersistentKeepalive 25. [VPN] [BRIEF]. Staff reasoning (Jiro, pin, Jul 2025): keepalive 25 keeps the tunnel alive through NAT; MTU 1280 avoids fragmentation (remove it only if you cannot connect). [DISCORD answer 6, staff]
- Measured latency: Seestar 125 to 236 ms, share about 116 ms; port 445 open on both. [VPN, tested]

### The one-device rule

- ONE device on the tunnel at a time. Starfront's own instruction with the config. Do not install it on the Mac mini (already on site). [VPN]
- Two devices on the same keys always make the copy fail (michaelgehrisch, community, Jul 2026); phone and PC could not both be on (SchlapperAstro, community, Dec 2025). No staff post states the rule on Discord; it comes from Starfront's note with the config. [DISCORD answer 7]
- The brief's answer: a hold flag `starfront-vpn-hold` in the state folder means never start the tunnel (Brett is using it on his phone). [BRIEF section H]

### Windows guest SMB settings

- Windows 11 blocks guest logins by default (error 1272). One-off, in an admin PowerShell: `Set-SmbClientConfiguration -EnableInsecureGuestLogons $true -RequireSecuritySignature $false`. This lowers protection for all network shares on the PC. Undo with `$false` / `$true`. [VPN, tested] [BRIEF]
- A Windows update can reset it. [BRIEF only]
- SMBClient event 31017 means "guest rejected", not "tunnel down". [BRIEF only]
- Error 5 (Access Denied) on the Seestar share means the IPC$ guest session was not opened first. [VPN]

### Service, commands and paths

- Install the tunnel as a service (admin): `wireguard.exe /installtunnelservice "C:\Program Files\WireGuard\Data\Configurations\BrettJohnson-B15.conf.dpapi"`. [BRIEF section H only]
- Service name: `WireGuardTunnel$BrettJohnson-B15`. Query with `sc` (a missing service = alert "not installed"); check auto-start with `sc qc`; start with `sc start` if stopped and remember that the tool started it. Never stop a tunnel the tool did not start. [BRIEF section H only]
- Scheduled tasks that may start the service run with highest privileges. [BRIEF section H]
- `STARFRONT_VPN_MODE` = always | on-demand | never, default on-demand. [BRIEF section H]
- `ensure_tunnel(timeout=60)`: TCP 445 on 10.15.10.212 answering within 3 s = up; else hold flag or mode never = return False; else query the service, start if stopped, poll every 5 s until the timeout. [BRIEF section H]
- UNC paths only, no mapped drives. [BRIEF section H]. (Starfront's own Windows guide maps a drive; the brief overrides that for the tool.) [DISCORD finds]
- No community tip exists for automatic reconnection on Windows. [DISCORD answer 6]

### Dead link by progress, not ping

- Offload over WireGuard dropped to almost nothing one morning while pings still worked (Uno7418, B17, community, 18 Oct 2026). "Ping OK" does not prove the transfer path. [DISCORD answer 6] [BRIEF section H]
- Windows copy hangs on glitches; robocopy recovers and carries on (michaelgehrisch, community, Jul to Sep 2026). [DISCORD answer 6]. Brett's own note: use robocopy, not drag and drop, because it resumes after a dropped tunnel. [VPN]
- The brief treats either of these as a drop: no bytes for `STARFRONT_STALL_SECONDS` (120), or Windows errors 53, 59, 64, 67, 121 or 1231. On a drop: `ensure_tunnel`, retry after 5, 15 and 45 s, then stop cleanly, delete the `.partial`, let the ledger resume next run. Keep `last_ok`; one alert after `STARFRONT_VPN_ALERT_HOURS` (12) down and one on recovery. [BRIEF section H]
- The error numbers come from the brief without their names. Their standard Windows meanings, for the builders' comments (not from the docs): 53 network path not found; 59 unexpected network error; 64 the specified network name is no longer available; 67 the network name cannot be found; 121 the semaphore timeout period has expired; 1231 the network location cannot be reached.

### Throughput

- /MT:32 to /MT:64 robocopy threads are 2.5 to 3 times faster to Europe than the default 8, because of latency; his command used `/J /Z /R:3 /W:5 /XC`; he waits a couple of hours after roofs close before copying (michaelgehrisch, community). [DISCORD answer 6]
- The brief: 8 parallel workers by default, configurable up to 32, daytime only. Restartable with `copy_file_verified` and `.partial` files. [BRIEF section D]

* * *

## 3. The roof and the site

### The customer share

- `\\172.16.5.21\sfro-customer`, login guest / guest (`net use \\172.16.5.21\sfro-customer /user:guest guest`). Folders: `images`, `roof`, `weather`. One share for all buildings. [VPN, tested] [GROUND section 7, staff pin] [BRIEF]
- The roof status file is Starfront's supported automation input, one file per building. [GROUND section 7] [SPEC section 4]
- The roof file's exact name, path under `roof`, and format are NOT in any document. Rollout step 1 checks "the roof file format". [BRIEF rollout 1] [SPEC open questions]. Jiro's lock-cleaner post mentions "roof status files and daily.txt" on the share. [DISCORD answer 4, staff]
- The "open read only and close at once" rule and why: a client system locked a file on the customer share; Starfront (Jiro, staff, 26 Sep 2026) added a lock cleaner covering the roof status files and daily.txt. So open roof files read only, read, close immediately, never hold a handle. [DISCORD answer 4 and "what this changes" 10] [BRIEF]. The brief's test list includes "the roof file handle is closed after each read". [BRIEF section M]
- The ticket tells Starfront the file is "opened read only and closed straight away" and asks whether reading it every 20 minutes at night is acceptable. [TICKET]

### The Alpaca fallback feed

- `alpaca-api.tx.starfront.space/api/v1/roof/state`: public JSON, one entry per building; B15 is `device_number` 15, with `is_open` and a UTC `state_update`, refreshed about every minute. It is what status.starfront.space/tx/building/15 reads. Undocumented, so confirm with Starfront before relying on it. [GROUND section 7] [SPEC section 4] [BRIEF]
- The parked spec's rule of thumb: poll the share, fall back to the feed if the share is unreachable, and if both fail for 5 minutes treat the roof as closed. [SPEC section 5.1]. The brief's guards simply require the roof CLOSED for at least `STARFRONT_ROOF_CLOSED_HOURS` (2) and treat an unreadable roof as a refusal. [BRIEF sections D and M]

### Brett's existing roof parser

- "My starfront-sky-calendar repo already parses B15 roof state; reuse that parser." [BRIEF only]. No document names the file inside that repo. The builders must look in the starfront-sky-calendar repo to find it; the sky calendar also already uses ntfy, which is why `NOTIFY_PUSH_URL` is ntfy. [BRIEF section C] [DISCORD "what this changes" 12]

### Site and time

- Starfront Observatories, Rockwood, Texas. Lat 31.54733, lon -99.38273. Time zone America/Chicago (US Central). Building 15, pier B15-SB-B17. [BRIEF] [GROUND] [SPEC section 4]
- Texas is 6 hours behind the UK for most of the year, 5 hours in the short spells when only one country has changed clocks (for example 25 Oct to 1 Nov 2026). [GROUND section 5]
- Twilight: time.starfront.tools gives sunset, civil, nautical and astronomical dusk and dawn for the site, computed in the browser (not machine readable); compute the same from the coordinates. Example 30 Oct 2026: astronomical dusk 20:12, dawn 06:30 Texas time. [GROUND sections 5 and 7]
- Roofs are automated, move by building, can open before sunset and close part way through the night (28 Oct 2026: open 19:30, closed 22:41 Texas time). sfro-bot posts each move in #all-roofs. [GROUND section 5, staff]

### What "Texas daytime" and "night" mean for the guards

- Pulls and clears happen only in Texas daytime, because at night Starfront's connection is prioritised for keeping everyone's scopes running and big transfers are slower [GROUND section 6, staff], and because heavy pulls hurt the Seestar's control latency [DISCORD answer 4, zmerlynn, community]. The team's relayed rule: "download the next day, in Texas daytime" (DynamoHum, moderator, pin 25 Oct 2026). [DISCORD answer 4]
- The brief's night-time work uses "astronomically dark" for the silent alert, "after Texas dawn" for the digest, and nights split in America/Chicago (not a noon pivot on the filename clock). [BRIEF sections E, I, J]
- No document gives an exact boundary for "Texas daytime" as a guard. The builders must pick one and say so; the safe reading from the docs is: between astronomical dawn and astronomical dusk at the site, computed from the coordinates in America/Chicago, with the roof also closed for 2 hours. On Windows add tzdata; if the zone cannot be loaded, fail closed. [BRIEF section E]
- Home your mount when roofs open and when they close; if you expect remote support leave equipment powered on. [GROUND section 5, sfro-bot, staff]

* * *

## 4. Starfront policy and etiquette

- Deletion after transfer is allowed: "once the transfer completes you can delete the data from your Seestar if you wish." Help article "Transfer Files from Your Seestar (Windows)", Jiro, staff, updated 21 Aug 2026, owners only. [DISCORD answer 2, staff] [BRIEF]
- Community practice: michaelcoelho (Aug 2026) deletes JPGs then whole imaging folders over SMB after every copy with no problem; JimS (Aug 2025) deleted MyWorks over SMB. The common habit is to format from the app instead (several members); ip (moderator, Apr 2026) says formatting equals deleting everything, faster. Formatting also wipes darklibrary (MarkH, 17 Oct 2026). No reports of SMB deletion breaking the album, thumbnails or firmware; "not reported is not the same as safe", test on one small target first. [DISCORD answer 2]
- Download the next day in Texas daytime (moderator pin, "from the team", 25 Oct 2026). [DISCORD answer 4] [GROUND section 6]
- Leave the Seestar homed and not running a plan if you expect night work (Nate, staff, pin 9 Jan 2026). The brief's `starfront-pause` flag in the state folder is for this and for open tickets. [DISCORD answer 4, staff] [BRIEF section D]
- Do not slew while a ticket is active; technicians may be at the pier. [GROUND section 8] [SPEC section 4]
- Heavy pulls hurt the Seestar's control latency (zmerlynn, community, 31 Oct 2026). [DISCORD answer 4] [BRIEF]
- Alpaca crash logs have filled Seestar storage (Space, community, 15 Oct 2026). [DISCORD answer 3] [BRIEF]
- 60 GB in 3 days on an S50 Pro (Ettaswell-Jon, community, 23 Oct 2026). [DISCORD answer 3] [BRIEF]
- No written rule exists on polling intervals, VPN bandwidth caps or automated deletion. [DISCORD answer 4]. The ticket asks: (1) is listing the Seestar share every 2 hours and reading the roof file every 20 minutes at night acceptable, and if not, what intervals; (2) is automated per-target deletion over SMB fine; (3) is the Seestar's IP reserved. [TICKET]
- Batch export in the app: 1,100 x 10 s frames still exporting after 6 hours and the scope sluggish until restarted; keep batches modest (community). Relevant as a warning that big transfers slow the scope. [GROUND section 6]
- Etiquette: one ticket per issue through starfront.zendesk.com, pier code B15-SB-B17 on every ticket, reply in the ticket not by email, same-night work raised before 4 pm Central, moderators cannot see tickets, do not DM staff. [GROUND section 8]
- WireGuard configs go to traditional rigs and owned Seestars by ticket, not rentals (ip, moderator, 30 Oct 2026). [DISCORD answer 4]
- End of session: Close Arm, never Shut Down (a shut-down scope stays offline until powered on by hand or SwitchBot). Power on: one SwitchBot press, 6 s hold, then wait about 20 s before pressing again. [GROUND sections 5 and 9]

* * *

## 5. Prior art

Nobody on the Starfront Discord has built hours tracking, threshold pulls, hash verification or automated per-project clears. [DISCORD answer 1] [BRIEF]

- github.com/dasshark/starfront (Brian, community, 2 Oct 2026, working): a PowerShell 7 scheduled task for a NINA rig. Checks the sequencer has finished, transfers images by FTP to a home NAS, moves transferred files to a "transferred" folder, reports to Discord by webhook. Closest pattern: state check, transfer, mark as done, notify. The brief wants it for PATTERNS, not to copy. [DISCORD answer 1] [BRIEF prior art]
- github.com/avleen/astro-tools (Av, community, 28 to 29 Oct 2026, working): Python sub selection by eccentricity, star count and FWHM, copies the best to `_selected`; Windows support added 28 Oct. The brief sees it as a possible LATER STAGE after a pull, not for pulls. [DISCORD answer 1] [BRIEF prior art]
- github.com/zmerlynn/seestar-wormhole (zmerlynn, community, 1 Nov 2026): a ZWO Telescope Network proxy giving SMB with no VPN, handling reconnects; considering a copy feature. The brief wants it ASSESSED as a fallback route when the VPN is down (UNC root on a local forwarded port), with a report back before anything is built. [DISCORD finds] [BRIEF prior art]
- Private scripts, no repos: GaryP (Sep 2025) copied new FITS every 3 minutes until sunrise into Syncthing, never deleted, formatted weekly, plus a CSV of `_sub` folders; wokka (Aug 2026) SMB to Mac to NAS with roof status in a seestar_alp fork (github.com/smart-underworld/seestar_alp); Zachary (Aug 2026) a Go tunnel through Telescope Network with a resumable downloader; KP7 (Jan 2026) rclone with JPGs skipped. [DISCORD answer 1]
- Neighbouring: StellarVision status.json and nightly recap (site conditions only); Coneman's NINA over WireGuard guide and Ground Station plugin for Discord or Pushover alerts. [DISCORD finds]

* * *

## 6. Open questions and contradictions

### Rollout step 1 must answer (read-only `--starfront-scan`) [BRIEF rollout 1]

1. The real filename format and filter codes on Brett's own S50 Pro (is `IRCUT` really the other code; do stacks and JPGs follow the same pattern; what the `_thn` thumbnails are called).
2. Which clock the filename stamp uses, checked against `DATE-OBS` (section E: nights split in America/Chicago; section F: flag when `DATE-OBS` and the stamp disagree).
3. The `SITELAT`, `SITELONG` and `GAIN` headers, and any frame-count keyword (section F: flag when SITELAT/SITELONG are more than 0.1 degrees from 31.54733, -99.38273; flag mixed exposure, gain or filter; flag pointing moving more than about 10 arcmin between nights).
4. Hours counted from filenames against what the Seestar app reports.
5. Free space on the share (and the S50 Pro's capacity, which no document states).
6. The roof file's name, path and format on `\\172.16.5.21\sfro-customer\roof`.
7. SMB mtime behaviour (does mtime survive a listing unchanged; does it ever read in the future; is an exact match safe for section G's gate).
8. Whether guest can delete: create and delete a throwaway file in MyWorks.

### Open with Starfront (the ticket) [TICKET]

- Polling intervals (2 hours for the scope listing, 20 minutes at night for the roof file).
- Automated per-target deletion over SMB.
- Whether 10.15.10.212 is reserved.
- Also still open from the grounding sheet: whether the Alpaca roof feed may be polled and how often; what owners can control over the VPN (file access now works; app control untested and expected not to). [GROUND section 10] [VPN "still open"]

### Contradictions, and which wins

- Push frames home overnight (Mike1959, moderator, 25 Oct 2026, for traditional rigs) versus download in Texas daytime (team rule via moderator pin, 25 Oct 2026). Daytime wins for a Seestar: it is the team's rule for Seestars, and heavy pulls slow the scope's control (zmerlynn). [DISCORD answer 4] [BRIEF guards]
- "Hash at both ends" in the brief's goal versus the fact that the Seestar has no shell, so nothing can hash a file on the scope. The brief's section D already resolves this: the scope-side hash is an unbuffered re-read of every source `.fit` over SMB before any clear, doubling the traffic, daytime only, and a buffered re-read does not count. [DISCORD "what this changes" 1] [BRIEF section D]
- Starfront's Windows guide maps a drive letter; the brief says UNC paths only, no mapped drives. The brief wins for the tool. [DISCORD finds] [BRIEF section H]
- Seestar SMB "blocked except from your own system, by ticket" (staff, Sep 2025) versus "no ticket needed" (Brett's test, 6 Nov 2026). Both true: the VPN route works today without a ticket; the on-site firewall rule is about the Starfront network. Newer, tested fact wins for the VPN. [GROUND section 6] [VPN]
- The parked spec polls the roof every 60 s and treats "both sources down for 5 minutes" as closed; the brief checks every 20 minutes at night and requires closed for 2 hours before a pull. The brief wins: the spec is parked, and the 20-minute interval is what the ticket asks Starfront to approve. [SPEC 5.1] [BRIEF section I] [TICKET]
- `contract/scopes.json` today: the `S50P-STARFRONT` entry has `archive_root: "S50P"`, `match.camera: "ZWO Seestar S50 Pro"`, `"unit": null`, and a note that it stays switched off. The brief wants a NEW archive root `S50P-Starfront`, the camera name `ZWO Seestar S50 Pro (Starfront)` taken from the share path (never the headers), the entry turned on by REMOVING the `unit` key, and `timezone America/Chicago`. The brief wins; the builders must change `archive_root` on that entry as well, or the home S50P root would be shared, which the brief forbids (Day numbering counts the Day folders on disk, and `os.replace` could overwrite). A changed contract needs a new hash in `contract/shipped.sha256`. [SCOPES] [BRIEF section D] [CLAUDE 1.7.0 contract note]
- CLAUDE.md rule 2 (a camera file is deleted only when the ledger proves a verified copy of those bytes, Brett confirms with default No, the SAFE gate re-checks at deletion) versus the brief's `STARFRONT_AUTO_CLEAR=true`. The brief amends rule 2 for this camera ONLY, and only after rollout step 5 (weeks of confirmed clears). Until then confirm-first with default No stands, and the brief's section G tightens the gate rather than loosening it (sourceRehashed, exact mtime, settled across two listings 30 minutes apart, shipped with read-back, JPG twin rule kept, unknown types block, any listing error stops, darklibrary never deleted, top-level folders never removed). Rule 9 (ask before anything irreversible) is why the default stays confirm-first. [CLAUDE rules 2, 9] [BRIEF sections G and rollout 5]
- CLAUDE.md rule 6 (each computer keeps its own ledger; no file written by two machines) is why the Starfront source lives on the PC alone (SKYLARKPC, archive `E:\Astro Image Data`) with its own ledger rows, and why the tests require "Starfront and home rows don't collide". [CLAUDE rule 6] [BRIEF section M]
- CLAUDE.md rule 7 (Brett deletes files on his own disks himself) does not cover the Seestar: it is a camera, so rule 2 governs its clear. Rule 1 (nothing deleted from the ASIAir) is untouched. [CLAUDE rules 1, 2, 7]
- PARITY "Differences by design": unbuffered reads are Windows-only; elsewhere a read is recorded as "buffered". The brief says `_hash_dest_uncached` only bypasses the cache on the Mac, and that a re-hash is proof only when the read mode was "unbuffered". Taken together, the Starfront clear can only ever be proven on the PC. The Starfront source is therefore a PC-only capability and must be listed in PARITY's "Differences by design" with that reason (the Mac has no unbuffered read, and the tunnel is one device at a time, on the PC). [PARITY] [BRIEF sections D and H] [VPN one-device rule]
- `_mosaic_pt` is in the brief alone; Brett's unit shows `_mosaic` and `_mosaic_sub`. The brief wins (count and pull it, test it) but step 1 should confirm the folder exists and what it holds. [BRIEF section A and M] [VPN]
- The SwitchBot hold time (3 s Mark, 4 s Starfront, 6 s tested) is settled at 6 s; not the tool's business but it is what the "Seestar silent" alert leads Brett to do. [GROUND section 9] [BRIEF section I]

* * *

## 7. Glossary

- **Pier code**: Starfront's identifier for a customer's spot, written on every ticket. Brett's is B15-SB-B17. [GROUND section 8]
- **B15**: Building 15 at Starfront's Texas site, which has its own automated roof and its own entry (device_number 15) in the roof feed. [GROUND sections 5 and 7]
- **SB-B17**: pier B17 on the Seestar Bar (SB) in Building 15; "B15-SB-B17" puts the two together. [GROUND top and section 3]
- **Seestar Bar**: the shelf in a building where hosted and rental Seestars sit; power only from Kasa smart plugs there. [GROUND section 3]
- **EMMC Images**: the one Samba share the Seestar exposes, named after its internal eMMC storage; it holds `darklibrary` and `MyWorks`. [VPN]
- **darklibrary**: the Seestar's own dark frames, beside MyWorks; an app format deletes it; the brief copies it and never clears it. [DISCORD answer 2] [BRIEF section D]
- **Autostack**: the stacked `.fit` (and `.jpg`) the Seestar itself writes into `MyWorks\<Target>` while imaging; the brief pulls these FITS along with the subs and shows the newest stack JPG as a thumbnail. [BRIEF goal 4 and section J]
- **Sub**: one light frame, saved into `MyWorks\<Target>_sub` only when "Save each frame" is on. Its filename carries exposure and filter. [GROUND section 6] [DISCORD answer 5]
- **mosaic, mosaic_sub, mosaic_pt**: the Seestar's folders for a mosaic project: `<Target>_mosaic` (the stacked mosaic), `<Target>_mosaic_sub` (its subs), and `_mosaic_pt` (named in the brief only; the documents do not say what it holds, so step 1 looks). A project groups target + `_sub` + `_mosaic_pt`. [VPN] [BRIEF section A]
- **_thn**: thumbnail files the Seestar writes beside its images; deleted first in a clear. [BRIEF section G only]
- **LP / IRCUT**: the filter code in a sub's name: LP with the light-pollution filter in, IRCUT (unconfirmed) otherwise. [DISCORD answer 5]
- **Plan / Auto Plan**: the Seestar's own scheduled imaging, which keeps running if the app connection drops. "Leave the Seestar homed with no plan" is the staff rule before night work. [GROUND sections 4 and 5]
- **Close Arm**: the Seestar's end-of-session stow; never Shut Down. [GROUND section 5]
- **Telescope Network**: ZWO's cloud control route; what seestar-wormhole tunnels through. [GROUND section 4] [DISCORD finds]
- **Lock cleaner**: Starfront's process that clears client locks on the customer share's roof files and daily.txt; the reason roof files are opened read only and closed at once. [DISCORD answer 4]
- **Texas daytime**: the window in which pulls and clears are allowed; see section 3 for how the docs define it and what the builders must decide. [GROUND section 6] [BRIEF]
- **sfro-bot**: Starfront's Discord bot that posts roof moves in #all-roofs. [GROUND section 5]
- **ntfy**: the push service Brett's sky calendar already uses; `NOTIFY_PUSH_URL` in the brief is one HTTP POST to it. [BRIEF section C]
- **SAFE gate**: `_seestar_unproven_files`, the engine's re-check at the moment of deletion; stays own-ledger only; the brief re-runs every pull guard right before its second check. [CLAUDE rule 2 and 1.7.1 note] [BRIEF section G]
- **.partial**: the engine's restartable copy file (`copy_file_verified`); on a tunnel drop it is deleted and the ledger resumes next run. [BRIEF sections D and H]
- **starfront-pause / starfront-vpn-hold**: two flag files in the state folder: pause stops all Starfront work (ticket open or night work expected); vpn-hold means never start the tunnel (Brett has it on his phone). [BRIEF sections D and H]
