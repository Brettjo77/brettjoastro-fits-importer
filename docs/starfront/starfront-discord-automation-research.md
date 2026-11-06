# Starfront Discord: Automation Research (Seestar sub tracking and pulls)

Researched 6 Nov 2026 in the Starfront Observatories Discord (read only), plus Starfront's help article "Transfer Files from Your Seestar (Windows)". Purpose: find out whether anyone has already built a tool that counts integration per project on the Seestar, graphs progress, notifies at a target, pulls FITS home with SHA-256 verification, clears the project, and survives VPN drops.

Related docs: claude/starfront-seestar-grounding.md, claude/starfront-vpn-access.md, claude/starfront-auto-imaging-spec.md.

**How to read the labels.** "Staff" means a Starfront Staff account (Jiro, Nate, Josh) or Starfront's help centre, and counts as policy. "Moderator" means a Community Moderator (ip, Mike1959, DynamoHum, Reg, Joshua). Moderators speak for Starfront on process but are not staff, so their posts sit between policy and community. Note that the [SFRO] tag next to a name is a server tag that many ordinary members wear; it does not mean staff.

**Coverage.** All 37 listed searches were run, plus extras (format, delete, CSV, filename, FITS header, guest, SMB seestar, two devices, handshake, bandwidth). Pins read in #smart-telescopes, #seestar-nina, #customer-general and #alpaca; #automation-chat has no pins. #automation-chat was read back to 12 Oct (last post 29 Oct). #smart-telescopes was read from 2 Nov to today; Discord would not load further back by scrolling, so 23 Oct to 2 Nov there is covered by the keyword searches and the 30 Oct grounding work, not read line by line.

---

## Answers

### 1. Has anyone built this?

No. Nobody has published a Seestar tool that tracks hours per project, pulls on a threshold, hash-verifies, or deletes automatically. The nearest pieces:

- **GaryP (Sep 2025, community):** a Python script on his Mac mini that copied new Seestar FITS (plus one stacked JPG per target) every 3 minutes until sunrise into a Syncthing folder. It never deleted; he formatted the Seestar weekly by hand. He also mentioned a script that writes one CSV row per directory with an option to process only "_sub" folders (its exact columns were not described). He said he would share it; no repo turned up.
- **wokka (Aug 2026, community):** a script on his Mac that pulls from the Seestar SMB share, then syncs to a NAS. He also tied roof status into his fork of seestar_alp. No repo for either.
- **Zachary (11 Aug 2026, community):** a Go program that tunnels through ZWO's Telescope Network with his own resumable SMB downloader. No repo given. zmerlynn's seestar-wormhole later did the same job publicly.
- **Brian, github.com/dasshark/starfront (2 Oct 2026, community, working):** PowerShell 7 scheduled task that checks the NINA sequencer has finished, transfers images by FTP to a home NAS, moves transferred files to a "transferred" folder, and reports to Discord by webhook. NINA rig, not Seestar, but the closest pattern to yours (state check, transfer, mark as done, notify).
- **Av, github.com/avleen/astro-tools (28 to 29 Oct 2026, community, working):** Python sub selection (eccentricity, star count, FWHM), copies the best to "_selected". Windows support added 28 Oct. Useful as a later stage, not for pulls.
- **KP7 (Jan 2026, community):** rclone from a Seestar skipping JPGs: about 18 MiB/s with 8 transfers on the local LAN, and a re-check for new files took under a second. Shows rclone's incremental listing works on the Seestar share.
- **Mike1959 (28 Oct 2026, moderator):** posted a Stacking Wizard grading CSV for Seestar subs. Not a tool of his, but it shows the filename format (question 5).
- **StellarVision (RNA, 2 Nov 2026, community):** now publishes a status.json feed (for Home Assistant) and a nightly recap channel. Site conditions only, nothing per scope.

Status: everything above is either a private script or a neighbouring tool. Your hours tracker, threshold notification, hash verification and automated clear would be new.

### 2. Is deleting from the Seestar over SMB safe?

Starfront's own guide says yes. "Transfer Files from Your Seestar (Windows)" (Jiro, updated 21 Aug 2026, owners only) ends with: once the transfer completes you can delete the data from your Seestar if you wish.

Community experience supports it, with caveats:
- michaelcoelho (Aug 2026) deletes JPGs and then whole imaging folders over SMB after every copy, with no reported problems.
- JimS (Aug 2025) deleted the MyWorks folder over SMB and Finder's "empty folder" glitch went away.
- Deleting a stack inside the app also deletes its FITS but leaves an empty folder in MyWorks (DocWaton, Nov 2025).
- The common habit is to **format the Seestar from the app** after downloading rather than delete (Coneman, Manoj, Peper, Ettaswell-Jon). ip (moderator, Apr 2026) says formatting is effectively the same as deleting everything, only much faster.
- **Formatting also wipes the "darklibrary" folder** that sits beside MyWorks (MarkH, 17 Oct 2026). Copy it off first, or delete per project instead of formatting.

No reports were found of SMB deletion breaking the app album, thumbnails or firmware. Not reported is not the same as safe, so test on one small target first.

### 3. How full does the S50 Pro get, and what happens?

- Ettaswell-Jon's S50 Pro: over 60 GB in 3 days (23 Oct), and about 100 GB sitting on it by 26 Oct, with no reported problem.
- Space (15 Oct, #seestar-nina): Alpaca service crash logs filled the Seestar's storage and caused his problem. So something other than your subs can eat the space.
- Nobody on Discord stated the S50 Pro's capacity or described the full-storage behaviour. Check free space in the app (or from the SMB share) rather than assume.

### 4. Starfront rules on polling, bandwidth and deletion

No written rule was found on how often you may poll the roof share or the Seestar, on VPN bandwidth caps, or on automated deletion. What does exist:

- **Staff:** owners may delete from the Seestar after transfer (help article above).
- **Staff, Jiro (26 Sep 2026):** a client system had locked a file on the customer share; roof status files and daily.txt are now covered by their lock cleaner. Implication: open roof files read only and close them immediately.
- **Staff, Nate (pin, 9 Jan 2026):** if you expect night work, leave the Seestar homed and not running a plan.
- **Moderator pin (25 Oct 2026, "from the team"):** download the next day, in Texas daytime, to keep the network clear for everyone imaging overnight.
- **Moderator, Mike1959 (25 Oct):** says the staff recommendation for traditional rigs is to push frames home overnight as they are taken. This conflicts with the Seestar daytime advice; for a Seestar the daytime rule wins, because pulling during imaging slows the scope (see zmerlynn below).
- **Community, zmerlynn (31 Oct):** pulling hard from a Seestar makes control latency suffer.
- **Moderator, ip (30 Oct):** WireGuard configs are for traditional rigs and owned Seestars, by ticket; not rentals.

Worth asking Starfront in a ticket: polling interval for the roof share and the Seestar, and whether automated per-project deletion is fine.

### 5. Filename format and FITS headers

- Example from Mike1959's grading CSV (28 Oct, a rental Seestar): **Light_M 17_30.0s_LP_20261027-195802_1032.fit**. Pattern: Light, target, exposure in seconds, filter (LP when the light pollution filter is in, IRCUT otherwise is likely but not confirmed here), local date and time, then a frame number. So exposure **is** in the filename, and hours can be counted from directory listings alone.
- Ettaswell-Jon (5 Nov): subs from the S50 Pro app show **GAIN 200** in the header, while Alpaca defaults to 80.
- astrodreamer99 (19 Oct): S50 Pro frames are 2160 x 3840 and the header still shows 1x1 binning even with the new binning option on.
- The header includes XBAYROFF (Space, Aug 2026), which affects how NINA reports the Bayer pattern.
- Nothing found on SITELAT, SITELONG or a frame count keyword. Check one of your own subs.

### 6. WireGuard on Windows: staying connected

- **Staff, Jiro (pin, Jul 2025):** PersistentKeepalive 25 keeps the tunnel alive through NAT; MTU 1280 avoids fragmentation (remove it if you cannot connect). Your config already has both.
- **Community, michaelgehrisch (B19, Sweden, Jul to Sep 2026):** Windows copy hangs on glitches; robocopy recovers and carries on. /MT:32 to /MT:64 is 2.5 to 3 times faster to Europe than the default 8 threads, because of latency. His command uses /J /Z /R:3 /W:5 /XC. He waits a couple of hours after roofs close before copying.
- **Community, Uno7418 (B17, 18 Oct):** offload over WireGuard dropped to almost nothing one morning while pings still worked. So "ping OK" does not prove the transfer path is healthy.
- No tip was found for automatic reconnection on Windows.

### 7. The one-device rule

- **Community, michaelgehrisch (Jul 2026):** having the WireGuard client with the same keys active on two devices at once always makes the copy fail.
- **Community, SchlapperAstro (Dec 2025):** could not have his phone and PC on the VPN at the same time.
- No staff post on Discord states the rule; it comes from Starfront's note with your config (6 Nov).

---

## Finds

| Date | Author | Channel | Type | Summary | Link |
|---|---|---|---|---|---|
| 21 Aug 2026 | Jiro (Staff) | Help centre | Staff rule | Owner guide: WireGuard, map \\IP\EMMC Images as guest, copy from _sub folders, may delete after transfer. Guest logon fixes per Windows edition | starfront.zendesk.com/hc/en-us/articles/51349163984532 |
| 26 Sep 2026 | Jiro (Staff) | customer-general | Staff rule | Client lock on the share; roof files now in lock cleaner | |
| 9 Jan 2026 | Nate (Staff) | smart-telescopes pin | Staff rule | Leave Seestar homed and no plan running if night work expected; ask for manual PA "Bray's Way" | |
| 4 Sep 2025 | Jiro (Staff) | smart-telescopes pin | Staff rule | Firewall on Seestar SMB except your own system; never 10.0.0.1 | |
| Jul 2025 | Jiro (Staff) | customer-general pin | Staff rule | WireGuard config tips (keepalive 25, MTU 1280, DNS) | |
| 25 Oct 2026 | DynamoHum (Mod) | smart-telescopes pin | Staff rule (relayed) | Download next day in Texas daytime; Close Arm; 30 s subs | |
| 26 Apr 2026 | ip (Mod) | sfro-suggestion-box | Moderator | Formatting = deleting all images, much faster | |
| 30 Oct 2026 | ip (Mod) | customer-general | Moderator | WireGuard by ticket for owned systems | |
| 3 Nov 2026 | ip (Mod) | smart-telescopes | Moderator | Pointed you to the Windows and Mac transfer guides | |
| 25 Oct 2026 | Mike1959 (Mod) | automation-chat | Moderator | Says staff advise pushing frames home overnight for rigs | |
| 28 Oct 2026 | Mike1959 (Mod) | seestar-rental-lounge | Working (other tool) | Grading CSV shows Seestar filename format with exposure | |
| 17 Oct 2026 | MarkH | customer-general | Warning | darklibrary folder beside MyWorks; app format deletes it | |
| 8 Oct 2026 | Ettaswell-Jon | general | Idea | VPN map MyWorks, copy FITS, then format via app | |
| 23 and 26 Oct 2026 | Ettaswell-Jon | smart-telescopes, PowerShell search | Data point | S50 Pro: 60 GB in 3 days, about 100 GB stored | |
| 5 Nov 2026 | Ettaswell-Jon | smart-telescopes | Data point | S50 Pro app subs show GAIN 200 in header | |
| 15 Oct 2026 | Space | seestar-nina | Warning | Alpaca crash logs filled Seestar storage | |
| Aug 2026 | michaelcoelho | guest search | Working (manual) | Deletes JPGs and imaging folders over SMB after copying | |
| Nov 2025 | DocWaton | smart-telescopes | Data point | Deleting in app removes FITS, leaves empty folder | |
| 12 and 22 Sep 2025 | GaryP | customer-general, smart-telescopes | Working (private) | Python copier every 3 min until sunrise; never deletes; CSV of _sub dirs | none |
| Aug 2026 | wokka | seestar-nina, alpaca | Working (private) | Mac script SMB to Mac to NAS; roof check in seestar_alp fork | github.com/smart-underworld/seestar_alp |
| 11 Aug 2026 | Zachary | smart-telescopes | Working (private) | Go tunnel through Telescope Network with resumable downloader | none |
| 2 Oct 2026 | Brian | automation-chat | Working tool | PowerShell transfer, move to "transferred", Discord webhook | github.com/dasshark/starfront |
| 28 Oct 2026 | Av | automation-chat | Working tool | Python sub selection, Windows support | github.com/avleen/astro-tools |
| Jan 2026 | KP7 | smart-telescopes | Data point | rclone from Seestar, 18 MiB/s LAN, re-check under 1 s | rclone.org |
| 1 Nov 2026 | zmerlynn | smart-telescopes | Idea | Considering a copy feature in wormhole; SMB is guest and unencrypted at your end | github.com/zmerlynn/seestar-wormhole |
| 31 Oct 2026 | zmerlynn | smart-telescopes | Warning | Heavy pulls hurt control latency; delivers plans via JSON-RPC | |
| 1 Nov 2026 | Hydris | smart-telescopes | Idea | Wants roof-aware plans that resume night after night via wormhole | |
| Jul to Sep 2026 | michaelgehrisch | asiair, general | Working (manual) | robocopy /MT:32 to 64 much faster to Europe; Windows copy hangs; two devices on one key breaks copies | |
| 18 Oct 2026 | Uno7418 | customer-general | Warning | WireGuard offload near zero while ping fine | |
| 6 Sep 2026 | Uno7418 | customer-general | Idea | Same setup as yours (S30 Pro, WireGuard direct); asked about trickle download to free storage | |
| Dec 2025 | SchlapperAstro | asiair | Warning | Phone and PC on VPN at once failed | |
| 24 Feb 2026 | Coneman | seestar-nina pin | Guide | NINA with Seestar over WireGuard from home ("SFRO Seestar Alpaca + NINA Setup") | Google Doc in pin |
| 24 Feb 2026 | Coneman | seestar-nina pin | Idea | Ground Station plugin for Discord or Pushover notifications | |
| 2 Nov 2026 | RNA | customer-tools | Working tool | StellarVision status.json feed and nightly recap channel | stellarvision.space |
| 19 Oct 2026 | astrodreamer99 | smart-telescopes | Data point | S50 Pro frames 2160 x 3840 | |
| 4 to 5 Nov 2026 | AndyT, Ettaswell-Jon | smart-telescopes | Warning | B15 WiFi still slow (autofocus 5 to 7 minutes) | |

---

## What this changes in my plan

1. **Hash "at both ends" needs a rethink.** The Seestar has no shell, so nothing can hash a file on the scope. The Seestar-side hash has to be a second read of the source over SMB after the copy. That doubles the traffic for every verified file. A middle way: hash the local copy, compare size and modified time with the source, and only do the full read-back hash for the final check before deleting a project.
2. **Hours can be counted from listings alone.** Exposure is in the filename (Light_target_30.0s_...). Count .fit files per _sub folder and multiply. If a name ever lacks it, read only the first FITS header block (a few KB) for EXPTIME rather than the whole file. This is my suggestion, not something anyone posted.
3. **Listing the Seestar is slow, so cache it.** Several people report slow SMB listings on the Seestar. List only MyWorks/*_sub, keep a local index, and refresh incrementally.
4. **Deleting is sanctioned, but delete per project, not by format.** Starfront's guide allows deleting after transfer. Formatting would also wipe the darklibrary. Delete only the verified project's _sub folder (and its stacked folder if you want), never darklibrary, and test on one small target first.
5. **Never pull while imaging.** Gate pulls on Texas daytime and roof closed for a couple of hours. Heavy pulls slow the scope's control.
6. **Use robocopy-style behaviour.** Restartable copies, retries with waits, and 16 to 32 parallel streams. Single-stream copies to the UK will be slow at 120 to 230 ms latency.
7. **Detect a dead tunnel by transfer progress, not ping.** Uno7418 saw ping fine and copies stalled. Treat "no bytes for N minutes" as a drop, back off, and resume.
8. **One device only.** The tool must run on one machine and you must not have the same config active elsewhere (phone, laptop), or copies fail.
9. **Watch free space as well as hours.** Alpaca logs can fill the storage. Track free space on the share and alert on a threshold.
10. **Roof share hygiene.** Open roof files read only, read, close. Do not keep a handle open (Starfront had to add a lock cleaner).
11. **Pause flag for tickets and night work.** Matches Nate's staff pin. The tool should do nothing while a ticket is open.
12. **Notifications.** ntfy (already used by the sky calendar) is fine; Discord webhooks are the community norm (Brian, PierCam, PFR Sentinel, Ground Station).
13. **Gain and exposure metadata.** S50 Pro app subs record GAIN 200. Read it from the header if you want the dashboard to split hours by settings.
14. **Ask Starfront** (one ticket): acceptable polling intervals for the roof share and the Seestar, and confirm that automated per-project deletion over SMB is fine.

## Open checks

- Look at one of your own S50 Pro subs for SITELAT, SITELONG, DATE-OBS and any frame count keyword.
- Confirm the S50 Pro filename includes the filter and exposure in the same way as the rental example.
- Find the free space on your Seestar share (Windows: dir on the share prints bytes free).
