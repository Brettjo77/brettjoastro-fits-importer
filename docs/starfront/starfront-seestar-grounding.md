# Starfront Seestar: Grounding Knowledge

Consolidated reference for Brett's **owned, hosted Seestar S50 Pro at Starfront Observatories** (Rockwood, Texas; Building 15, pier SB-B17, pier code B15-SB-B17). Built on 30 Oct 2026 from the pinned messages in the Starfront Discord, Starfront's help centre and status tools, and ZWO's official material. Use this as the source of truth for how Starfront and the Seestar work; use **claude/starfront-kit-list-and-checklist.md** for what still needs doing.

---

## 1. How to weigh the sources

When sources disagree, the higher rank wins.

| Rank | Source type | Examples |
|---|---|---|
| 1 | **Starfront staff, current** | Help centre Seestar articles (updated 25 Oct 2026), staff announcements in Discord pins, sfro-bot roof notices, status and time tools |
| 2 | **ZWO official** | Seestar app, Auto Plan guide, Batch Export tutorial, ZWO Alpaca release notes |
| 3 | **Mark (ws7m) guide** | "Deploy Seestar at Starfront", rev 21 Dec 2025 (pinned as a Dropbox PDF; local copy in iCloud > Starfront) |
| 4 | **Community pins and forums** | Individual experience; useful, but may be dated |

Two filters on top of the ranking:
- **Rental-only advice is ignored** unless it tells us how the scope or the site behaves. Brett owns the scope.
- **Dated advice loses to newer advice** from the same rank.

---

## 2. Sources captured

| Source | Rank | What it covers | Status |
|---|---|---|---|
| Discord #all-roofs (sfro-bot) | 1 | Roof open and close notices with instructions | Read |
| Pin: "Seestar rentals: 10 quick fixes" | 1 (tips 1 to 8 from staff), 4 (tips 9 and 10 community) | Exposure, Close Arm, downloads, firmware, status checks, tickets | Read; rental framing, mostly transferable |
| Pin: SMB security announcement | 1 | Firewall on Seestar file shares, ticket process | Read |
| Pin: SMB guide (Google Doc "For Customers - Accessing your Seestar") | 1 | Finding the Seestar IP and connecting to its share | **Summary only** (full doc needs a Google sign-in) |
| Pin: #smart-telescopes "simple list of everything needed" | 1 or 4 (poster unclear) | Hardware and software list | Read |
| Pin: community explainer (Mac mini, iPad app) | 4 | How the Mac mini setup works in practice | Read; partly dated |
| Pin: community batch export report | 4 | Download then export; large batch stall | Read |
| Pin: Mark's guide (Dropbox) | 3 | Full deployment guide | **Not readable here** (Dropbox blocks automated access) |
| Pin: help centre Seestar section | 1 | 8 articles; 2 are for owners | Owner articles read: Remote Operation Requirements, Rental vs Hosting. Also read: Getting Your Data |
| Pin: status.starfront.space/tx/building/15 | 1 | B15 roof state | Read, plus its data feed |
| Pin: time.starfront.tools | 1 | Twilight times for the site | Read |
| Starfront post-install guide (website) | 1 | Roof status files, coordinates, flats | Read |
| Starfront App (beta) page | 1 | Windows control program and NINA plugin | Read |
| ZWO Auto Plan guide (Jul 2026) | 2 | Auto-generated imaging plans | Read |
| ZWO Alpaca notes (via SharpCap forum) and ZWO forum bug report (Jan 2026) | 2 and 4 | Alpaca Park/Unpark, dither, dew heater; clock bug | Read |
| Discord thread, 30 Oct 2026 (AndyT, apsphoto, MarkH, IntegratedCorn) | 4, confirmed by Brett's own test | SwitchBot hold time to power on the Seestar; start-up wait | Read; 6 s hold tested and working on B15-SB-B17 |
| Customer-general pins (customers only) | 1 (staff) and 4 | Roof status share, WireGuard config, ticket rules, parking direction, no-slew during tickets, shipping, site links | Read in full, 30 Oct |
| #customer-announcements, 23 to 30 Oct 2026 | 1 | Live sessions, full moon caps and Seestar lens cleaning, USPS address, no Friday UPS/FedEx, B15 WiFi reboot, ticket replies | Read |
| #smart-telescopes, 29 to 30 Oct 2026, plus new pin | 1 and 4 | Mac download folder path, NINA caveats, B15 WiFi issues | Read |
| Discord searches (Mac mini, RustDesk, dummy plug, Mac update, power outage) | 1 and 4 | Mac-specific setup and failure modes | Read; individual reports, treat as experience not policy |

---

## 3. The setup, in Starfront's terms

**What Starfront recommend as the most capable setup** (#smart-telescopes pin): an onsite computer that talks to the Seestar, either the Seestar app on an M-series Mac or NINA on a mini PC, which you reach from home with remote desktop. That is Brett's setup.

| Element | What Starfront and the pins say | Brett's position |
|---|---|---|
| Hosting | Owned scope on the Seestar Bar; same monthly fee as a rental (USD 99) | Hosted, B15-SB-B17 |
| Control computer | Optional since Telescope Network, but an onsite Mac mini adds storage, more file transfer options, a pier camera, and no need for a SwitchBot WiFi hub. Minimum Apple Silicon M1 | Mac mini M6, set up by Starfront |
| How the Mac works | Runs the iPad Seestar app natively; talks to the Seestar over WiFi; wired to the Starfront network by a 30 ft Ethernet cable. **The Seestar takes its time and location from the app when it connects** | As described |
| Remote desktop | RustDesk, Chrome Remote Desktop or AnyDesk all recommended. Starfront's requirements name AnyDesk; other tools may need their VPN | RustDesk installed by Starfront; add a second tool |
| Power | Kasa smart plug or strip only (Digital Loggers no longer allowed on the Seestar Bar). **The Seestar and the computer stay plugged in at all times.** Mac mini plus Seestar needs a 2 to 3 port Kasa | Kasa KP303 |
| Charger and cable | US-plug charger; 10 ft USB-C cable (one community pin says 6 ft; 10 ft is the safer length) | 12V USB-C PD charger still to buy; AINOPE 10 ft cables |
| SwitchBot | Optional but recommended. Own account, unique Bot name and PIN, **4 second press** (community: 4 to 6 s), linked to the Hub if you have one. Put the account login, Bot name and PIN in the install ticket. The press length is the Bot's **hold time**, set in the Bot's settings in the SwitchBot app | Have Bot and Hub Mini. **Hold time set to 6 s** (30 Oct); powers the Seestar on |
| Mount (EQ) | Recommended: William Optics WIL-YG-IO-SG01L-RD; **ZWO TH10 with a leveler** (Apertura Easy Leveler suggested); Sky-Watcher Star Adventurer base (accepted, but Starfront have seen quality issues that lose polar alignment) | TH10 plus CAVIX leveler |
| Pier camera | Optional, supplied and installed by Starfront for about USD 235 to 245 | Not yet ordered |
| ZWO account | Seestar must be linked to your ZWO account for Telescope Network | To do |
| Owner extras | Free WireGuard VPN; Starfront can sell an onsite Windows mini PC (runs NINA, or the Seestar app via BlueStacks) | Not used yet |

---

## 4. Ways to control the scope

| Option | What it is | Getting FITS | Automation | Notes |
|---|---|---|---|---|
| **Mac mini + Seestar app** (current) | Remote into the Mac, drive the app as if at home | App download/export, or SMB once Starfront open it | Plan mode and Auto Plan run on the scope and keep going if the app connection drops | Most common, fullest features |
| **Windows mini PC + NINA** | Owner option via Starfront's mini PC | Through NINA | Full sequencing, multi-night targets, safety monitor, Starfront collaboration plugin | Uses ZWO's official Alpaca interface (Park/Unpark, dither, dew heater). Known issue (Jan 2026): NINA could not set the Seestar's clock unless the app had connected first |
| **ZWO Telescope Network** | Control via the ZWO cloud from any app | Starfront's 25 Oct article says FITS subs download through the app this way, slowly | Same Plan mode as the app | What rentals use. Starfront report connection drops on ZWO's side, being fixed. Keep as fallback |
| **VPN direct** | Free WireGuard VPN for owners | n/a | n/a | **Unresolved:** the hosting article offers a VPN to your home computer, but the requirements article says the S30/S50 cannot be controlled directly over VPN |

---

## 5. Nightly operations

**Roofs**
- All roofs are automated and move by building. sfro-bot posts each move in **#all-roofs**
- **Roofs Opening:** home your mount before starting your night
- **Roofs Closing:** home your mount
- **Both:** if you are expecting remote support, leave equipment and PCs powered on
- Roofs can open before sunset and can close part way through the night (28 Oct: open 19:30, closed 22:41 Texas time)

**Darkness**
- time.starfront.tools gives sunset, civil, nautical and astronomical dusk and dawn for the site, with a toggle for UK time. Example, 30 Oct: astronomical dusk 20:12, dawn 06:30 Texas time
- "Too bright" usually just means it is not dark in Texas yet

**The Seestar**
- **Powering on remotely:** one SwitchBot press with a 6 second hold, then wait about **20 seconds** for the Seestar to start up before pressing again. Pressing again too soon turns it straight back off (community, 30 Oct; several members made this mistake early on)
- **End of session: Close Arm. Never Shut Down.** A shut-down scope stays offline until it is powered on again (a tech by hand, or the SwitchBot)
- Prefer running a **Plan** to driving live: it keeps collecting if the app connection drops (community tip)
- Exposure: Starfront advise **30 s** for rentals, as longer subs get rejected or trailed. That advice is for alt-az rentals; in EQ mode longer subs are worth testing
- Firmware updates are optional. If updating, do it before dusk
- Let the app connect before a session even if something else drives the scope, so the scope has the right time and location

**Time zones**
- Starfront lists the site as US Central Time. Discord shows your local (UK) time. Texas is 6 hours behind the UK for most of the year and 5 hours in the short spells when only one country has changed clocks (e.g. 25 Oct to 1 Nov 2026)

---

## 6. Data

**Turn on sub saving first:** Open Arm, Stargazing mode, three dots top right, **Save each frame**. Subs go in a per-target folder ending "_sub".

**Route 1: the app (works for everyone)**
- It is **two steps: download, then export**. My Album > Seestar tab > target "_sub" folder > select all > download; then the Download tab > select all > export, which saves one zip to the Mac. ZWO's walkthrough is the Batch Export tile in the app's Tutorials (h5.seestar.com/course/400261)
- **Batch size matters.** Community report: one export of 1,100 x 10 s frames was still running after 6 hours and left the scope sluggish until restarted. After a restart, 2,000 frames went through in about 30 minutes. Keep batches modest and restart the scope (not Shut Down) if it feels slow

**Route 2: SMB file share (owners, by arrangement)**
- ZWO left a known security weakness in the Seestar's file share, so **Starfront's firewall now blocks Seestar SMB access except from the owner's own system**
- To get access: find the Seestar's IP address in the app, open a ticket with that IP, and Starfront set up your access individually
- Connect to the scope's **"EMMC Images"** share **by your own scope's IP**. **Never use smb://guest@10.0.0.1/EMMC Images**: it connects to the first Seestar it finds, which may be someone else's
- This is the route a script can use, and it avoids the app's download/export queue

**Timing:** download in **Texas daytime**. At night Starfront's connection is prioritised for keeping everyone's scopes running, and big transfers are slower.

---

## 7. Status and automation inputs

| Input | What it gives | Machine-readable? |
|---|---|---|
| **status.starfront.space/tx/building/15** | B15 roof Open or Closed, and last update time | Yes: the page reads a public JSON feed at **alpaca-api.tx.starfront.space/api/v1/roof/state**, one entry per building; B15 is device_number 15 with is_open and a UTC state_update, refreshed about every minute. Undocumented, so confirm with Starfront before relying on it |
| **time.starfront.tools** | Twilight times and Moon | No: calculated in the browser. Compute the same times from the site coordinates (31.54733, -99.38273) |
| Roof status file (network share) | Roof state for automation software | Yes. **\\172.16.5.21\sfro-customer**, guest/guest, one share for all buildings (staff pin, customer-general). Starfront's supported automation input |
| Seestar app download folder on the Mac | Subs after the app's download step | Yes: ~/Library/Containers/<app id>/Data/Documents/LocalCache/Download/<scope id>/MyWorks/<target>_sub/ (pinned in #smart-telescopes, 29 Oct) |
| Customers-only #automation-chat and #alpaca | Community automation work, e.g. a Seestar sub-selection script (github.com/avleen/astro-tools) | Read before building anything |
| #all-roofs | Human-readable roof notices | Discord only |
| ZWO Alpaca on the Seestar | Park/Unpark, slew, camera, dew heater | Yes, local network |
| Starfront App (beta) | Planning, sequencing, Alpaca equipment control, community collaborations | Windows only; also a NINA plugin |

---

## 8. Support and etiquette

- **Is it me or Starfront?** Check the B15 status page (roof, weather, site) before raising anything
- **Tickets** through the help centre (starfront.zendesk.com). Keep one ticket per issue and reply in it with what is happening and what you have tried. **Discord moderators cannot see tickets.** Put pier code B15-SB-B17 on every ticket
- **Reply in the ticket, not to the email** (email replies do not reach the team). Same-night work: raise it before **4pm Central**. The install ticket stays open until the first night is polar aligned, focused, connected and working; after that each issue is a new tech support ticket. Do not slew while a ticket is active
- **Don't DM staff** on Discord; billing and complaints go to a ticket or email, not customer-general
- **Customer role in Discord:** send your Discord username in a ticket; it can take a while
- **Channels that matter:** #smart-telescopes, #seestar-nina, #all-roofs, #weather, #weather-and-roof-operations, #customer-announcements, #community-help-forum, #verify-here
- Long-standing members in #smart-telescopes offer to answer questions, and they answer quickly (the SwitchBot question on 30 Oct was solved within the hour)

---

## 9. Conflicts resolved

| Topic | Older or lower source | Current answer | Why |
|---|---|---|---|
| SwitchBot press | 3 s (Mark, Dec 2025); 4 s (Starfront requirements, Oct 2026) | **6 s hold time** | Community says 4 to 6 s; 6 s tested on Brett's scope 30 Oct and powers it on. Consistent with Starfront's 4 s as a minimum |
| Approved wedges | Only Sky-Watcher and William Optics (community pin) | **TH10 with a leveler is approved**; WO preferred over Sky-Watcher | Starfront requirements, Oct 2026 |
| Telescope Network and FITS | Third-party guide: JPEG only, no FITS | **FITS subs download through the app** over Telescope Network (slowly) | Starfront Getting Your Data, 25 Oct 2026 |
| USB cable length | 6 ft (community pin) | **10 ft** | #smart-telescopes list; more slack on the bar |
| Pier cam price | About USD 235 (community) vs 245 | **About 235 to 245, confirm on ticket** | Prices vary over time |
| Mac mini chips | "M1, M2 or M4" (older pin) | **Any Apple Silicon, M1 or newer** | Starfront requirements; Brett's M6 qualifies |
| Mac mini required? | Community: most people use one | **Optional**, but it unlocks storage, SMB transfer, pier cam | Starfront requirements |
| Getting files via SMB | Open share on the network | **Blocked except for your own system, by ticket**; never 10.0.0.1 | Starfront security announcement |
| VPN control | Hosting article: VPN to your home computer | **Unresolved**; requirements say S30/S50 cannot be controlled directly over VPN | Ask Starfront |

---

## 10. Gaps and open questions

- **Mark's guide (Dropbox pin):** not readable here. If the pinned version is newer than rev 21 Dec 2025, attach the PDF to the project
- **SMB guide:** only the summary was readable. Download it as a PDF and attach it for the exact steps
- ~~B15 roof status file path~~ Found: \\172.16.5.21\sfro-customer (all buildings)
- **Mac networking:** the community connects the Mac's WiFi to the Seestar's own WiFi and uses Ethernet for Starfront. How that fits with Starfront's "SMB by your Seestar's IP" process is unconfirmed
- **NINA caveats (Mike1959, 29 Oct):** NINA uses the computer's time zone, so the PC must run on Texas time; it pulls every frame back to the PC, so remote links cut integration time; the Bayer pattern reported over Alpaca is wrong for Seestars; one owner's Alpaca API stopped responding after 62 subs. A UK member found NINA from home far too slow
- **Roof feed:** OK to poll, how often, and is there an Alpaca SafetyMonitor for NINA?
- **"Home your mount" mid-night:** Close Arm is the end-of-session rule; confirm it is also right when the roof closes mid-plan, and whether Alpaca Park does the same
- **VPN:** what owners can actually control over the WireGuard VPN
- **Rental-only help articles** (Welcome, Getting Started, FAQ, Managing, Troubleshooting) not read; read Troubleshooting if a problem comes up, as some fixes may transfer
