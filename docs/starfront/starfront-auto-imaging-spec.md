# Starfront Auto Imaging: Spec

**Status:** Parked (30 Oct 2026). Not started. Pick up once the Mac mini login is sorted.
**Owner:** Brett
**Scope:** Brett's owned Seestar S50 Pro, Starfront Observatories, Building 15, pier B15-SB-B17

Related docs: claude/starfront-seestar-grounding.md (how Starfront and the Seestar work), claude/starfront-kit-list-and-checklist.md (what is still to do).

---

## 1. Problem

Roofs at Starfront open and close automatically, often overnight UK time, and sometimes close part way through the night. Today a session only happens if Brett is awake to start a Plan in the Seestar app, and nothing reacts if the roof closes mid-plan.

Nobody at Starfront has a ready answer for Mac plus Seestar. PFRAstro asked on 29 and 30 Oct and got no answer beyond a pointer that @wokka is or was working on a Mac version of NINA for Seestars over Alpaca. Roof-driven automation on Discord is all NINA on Windows.

## 2. Goal

A small program on the Mac mini that, every night without Brett:

1. Starts imaging when the B15 roof is open and it is astronomically dark
2. Picks the best target from Brett's own list
3. Stops and closes the arm when the roof closes or dawn comes
4. Tells Brett what happened
5. Optionally gets the subs ready for the BrettjoAstro FITS Importer in Texas daytime

## 3. Non goals (version 1)

- No mosaics, meridian flip logic or multi-target sequencing within one night beyond simple target switching
- No processing or stacking on the Mac (the Seestar stacks; Brett processes at home)
- No control from the UK over the VPN (a UK member found NINA from home too slow)
- No firmware updates driven by the program

## 4. Environment and constraints

| Item | Value |
|---|---|
| Computer | Mac mini M6, 16GB, at the pier, Ethernet to Starfront, WiFi to the Seestar (to confirm) |
| Scope | Seestar S50 Pro on ZWO TH10 in EQ mode, CAVIX leveler |
| Power | Kasa KP303 (outlets: Mac, Seestar charger, backup charger). SwitchBot Bot via Hub Mini, 6 s hold to power on |
| Site | Rockwood, Texas. Lat 31.54733, lon -99.38273. US Central Time |
| Roof input (supported) | SMB share \\172.16.5.21\sfro-customer, guest login, one file per building |
| Roof input (fallback) | alpaca-api.tx.starfront.space/api/v1/roof/state, B15 is device_number 15, fields is_open and state_update (undocumented) |
| Time zone | Mac must run on US Central Time; the Seestar takes time and location from the app when it connects |

Starfront rules the program must respect:
- **Close Arm, never Shut Down**
- **Never park pointing west or east**; Close Arm stows the scope safely
- **Do nothing while a support ticket is active** (technicians may be at the pier)
- Keep all outlets on; the program never switches Kasa outlets off

## 5. Design

One Python service, run as a launchd agent so it starts at login and restarts if it crashes. Six parts:

### 5.1 Roof monitor
- Poll the roof status file every 60 s; fall back to the JSON feed if the share is unreachable
- **Open** only counts after it has been open for 3 minutes (stops a flicker starting a session)
- **Closed** acts at once
- If both sources fail for 5 minutes, treat the roof as closed

### 5.2 Darkness and target selection
- Compute astronomical dusk and dawn from the site coordinates (Skyfield or Astropy); no dependence on time.starfront.tools
- Targets live in a YAML file Brett edits:
  ```yaml
  - name: M42
    ra: "05h35m17s"     # or resolve by name
    dec: "-05d23m28s"
    priority: 1
    min_alt: 30
    max_hours: 4        # per night
    exposure_s: 30      # Starfront advise 30 s; test longer in EQ mode
  ```
- At each start, and every 30 minutes, pick the highest priority target that is above min_alt for at least the next hour and has hours left
- Avoid targets within a set distance of the Moon (configurable, off by default)

### 5.3 Scope driver
Behind one interface (`connect`, `open_arm`, `goto`, `start_stack`, `stop_stack`, `close_arm`, `status`) so the route can be swapped:

| Route | Pros | Cons |
|---|---|---|
| **A. Seestar command channel (seestarpy)**, preferred | Closest to the app: open arm, goto, stack on the scope with Save each frame, close arm | Unofficial. Needs authentication on firmware 7.18+. Docs do not name the S50 Pro. A ZWO firmware update could break it |
| **B. ZWO official Alpaca**, fallback | Official. Park and Unpark, slew, PulseGuide for dither, dew heater | Behaves as a mount plus camera, so every frame comes back to the Mac. Community reports of the Alpaca API stopping mid-session and a wrong Bayer pattern |

Rules for the driver:
- Never run while the Seestar app has an active session; the app is the manual override
- Connect the Seestar app at least once before the first automated night so the scope has Texas time and location
- Every failure path ends in `close_arm`

### 5.4 Session state machine

```
IDLE --(dark AND roof open 3 min AND no ticket flag)--> STARTING
STARTING: connect, open arm, goto target, start stack --> IMAGING
IMAGING --(target done or better target up)--> SWITCHING --> IMAGING
IMAGING --(roof closed OR dawn OR error)--> STOPPING
STOPPING: stop stack, close arm, verify closed --> IDLE
Any state --(pause flag)--> STOPPING then PAUSED
```

- **Pause flag:** a file (e.g. ~/StarfrontAuto/PAUSE) that Brett creates when a ticket is open or he wants manual control. While it exists the program does nothing, apart from closing the arm if it was imaging
- If the roof reopens the same night, the program can start again (max restarts per night configurable)

### 5.5 Notifications
- Push to Brett's phone (ntfy or a Discord webhook to a private channel)
- Events: session started (target), target switched, roof closed, arm closed (with sub count), any error, and an "arm close not confirmed" alarm, which is the only one that is urgent

### 5.6 Morning data step (optional, phase 3)
- In Texas daytime, copy that night's subs to a dated folder on the Mac
- Source: the SMB share once Starfront open it, or the app download folder at ~/Library/Containers/<app id>/Data/Documents/LocalCache/Download/<scope id>/MyWorks/<target>_sub/
- Small batches only (community report of a 1,100 frame export stalling the scope)
- Hand off to the BrettjoAstro FITS Importer conventions

## 6. Logging
- One log file per night, plus a CSV summary: date, roof open and close times, targets, subs captured, errors
- Logs kept on the Mac and copied home with the data

## 7. Phases

| Phase | What | Needs the real scope? |
|---|---|---|
| 0 | Confirm with Starfront it is OK to poll the roof share every minute and drive the Seestar from a script | No |
| 1 | Roof monitor, darkness, target picker, state machine, notifications, all with a **dry-run driver** that only logs what it would do. Run it for a few nights against the real roof feed | No |
| 2 | Real driver (route A), tested in Texas daytime with the roof closed: connect, open arm, goto, close arm. Then one supervised night | Yes |
| 3 | Morning data step and FITS Importer hand-off | Yes |

## 8. Open questions (before phase 2)

- [ ] Starfront OK with automated control and polling the roof share (and how often)?
- [ ] Format of the B15 roof status file on the share
- [ ] Seestar firmware version on the S50 Pro, and whether seestarpy works with it
- [ ] Does the Mac reach the Seestar over the Seestar's own WiFi or Starfront's network? Which IP does the program use?
- [ ] Does Close Arm over the command channel behave exactly like the app's Close Arm?
- [ ] EQ mode: does a goto over the command channel respect EQ mode, and does polar alignment survive Close Arm and Open Arm?
- [ ] Is @wokka's Mac NINA for Seestars still active? If it is, compare before building route B
- [ ] Watch PFRAstro's thread in #smart-telescopes for anything he finds

## 9. Risks

| Risk | Mitigation |
|---|---|
| Firmware update breaks the command channel | Keep ZWO updates manual; Alpaca fallback driver |
| Program and app fight over the scope | Pause flag; never start if the app reports an active session |
| Roof closes and arm close fails | Retry, then urgent alert to Brett; Starfront roofs do not depend on the scope being stowed, but raise a ticket |
| Wrong time or location on the scope | Mac on Central Time; connect the app before the first night |
| B15 WiFi drops mid-session | Stacking continues on the scope (as with Plans); program reconnects and only acts on roof and dawn |

## 10. Sources

- Starfront customer-general pins (roof share, parking direction, no slewing during tickets)
- Starfront roof status page and feed (status.starfront.space/tx/building/15)
- #smart-telescopes, 29 to 30 Oct 2026 (Mike1959 on NINA caveats; Mac download folder pin; PFRAstro's question)
- #customer-general, 29 Oct 2026 (ip on @wokka's Mac NINA work)
- ZWO Seestar Alpaca notes: forums.sharpcap.co.uk/viewtopic.php?p=51262
- seestarpy docs: seestarpy.readthedocs.io
- seestar_alp (alternative community project): github.com/smart-underworld/seestar_alp
