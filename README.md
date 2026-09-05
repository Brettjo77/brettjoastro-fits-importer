# BrettjoAstro FITS Importer

**Backup-first imports for ZWO ASIAir and Seestar smart telescopes — every frame verified to the byte, every session remembered forever.**

![The control panel with both cameras connected](docs/img/panel-dark.png)

Plug in either camera (or both). A notification fires, a local control panel opens, and every new frame is copied with cryptographic proof it arrived intact. A lifetime ledger remembers everything you have ever imported — so archiving finished targets never causes re-imports, and the tool can tell you, honestly, what is safe to delete from a camera and what is not.

Built by [Brett Johnson](https://github.com/Brettjo77) for a ZWO ASI585MC Air (Askar FRA400 + Askar 107PHQ), a Seestar S30 Pro, an original Seestar S30, and a Seestar S50 Pro — and generalised so it works on any Mac. First light: 686 frames imported, SHA-256-verified, and safely cleared from the camera in a single run.

**New here? Read [How it works — in plain English](HOW-IT-WORKS.md)** — the whole logic in astronomer's language, no code anywhere.

---

## Why this exists

Smart telescopes fill up fast, and hand-copying folders leaves you guessing. Most import scripts just copy — they cannot *prove* anything arrived intact, they forget everything once you archive a target, and their "delete the source?" prompts are a leap of faith. This tool inverts that: **nothing is ever marked imported unless the bytes on your Mac provably match the camera, and nothing is ever offered for deletion unless every file in the folder passes that test.**

## What it does

**For both cameras**

- Watches `/Volumes` via a LaunchAgent; when a camera mounts it scans read-only, notifies you, and opens the control panel at `http://127.0.0.1:8765`
- Verified copies: stream-hash from camera → write to `.partial` → fsync → re-read from disk → re-hash → rename. Interrupted copies leave a `.partial`, never a fake backup
- One JSON ledger for every frame ever imported (SHA-256, exposure, night, scope, day number, device) — entries are never deleted, so history survives archiving
- Day-folder numbering per target with night-continuation handling, shared display-name tables (catalogue → common names) plus your own custom names
- A backup report that separates *verified* / *backed up but unverified* / *still on camera only*, and a self-contained HTML status dashboard
- AstroLog-compatible JSON receipts per telescope after each import

**The control panel**

- One-page app layout: the page never scrolls; the target list, activity log, and report panes scroll inside their own cards, with camera storage as a live meter in the header
- **Calibration pairings up front**: the scan runs the real matching gates and shows which bias/dark/flat *sets* pair with which target — each pairing pre-ticked, untickable, so the import runs without interrupting you; only genuinely questionable pairings still ask (and the question names the set, its date and rotation versus your lights')
- **"Where files will land"**: a live destination tree showing the exact Day folders and calibration links the import will create — computed by the same code the import uses, updating as you tick and untick
- Targets and the backed-up inventory in date order, newest first, with last-shot dates
- Scope badges read the *incoming* frames' focal length, so a target shot on two rigs is labelled by tonight's, not its history
- An unmissable finish: green completion banner (frames, targets, duration), tab title flip, and a macOS notification with a chime for imports that end while you're elsewhere

**ZWO ASIAir**

- Per-scope recognition from FITS focal length; filename-parsed metadata with FITS fallback (including no-filter and mosaic-panel filename forms)
- A calibration library that ingests **all** darks/flats/biases from `Autorun/`, then hard-links the *matching* set (gain, filter, focal length, rotator angle, exposure) into each session's folder — and asks first when flats look like they belong to a different optical configuration
- `--set-filter "<target>" "<filter>" [--night YYYY-MM-DD]` records the true glass for sessions where the ASIAir app's filter field was left blank (filenames carry no token)
- The ASIAir is treated as a **backup of record**: this tool never deletes from it, ever

**Seestar (S30 Pro / original S30 / S50 / S50 Pro)**

- Model detected from the FITS `CREATOR` header, one vote per project folder (with an S50-only-mode-folder fallback) — each camera gets its **own** folder tree, its own per-target day numbering, and its own presence tracking, so two Seestars shooting the same nebula keep two clean stories. Pro variants are recognised *before* their base models, whatever the header's spacing or case, so an S50 Pro can never be misfiled as an S50 — and a volume carrying **mixed** or **unrecognised** identities refuses to import at all rather than guess (the ledger never forgets, so it must never memorise a wrong camera)
- Anything in MyWorks the tool does not understand is **loudly reported** — panel, report, and watcher all say "on camera, NOT backed up by this tool" instead of pretending everything is safe; a second mounted Seestar is announced too (one camera at a time)
- Interrupted imports resume into the **same night's** Day folder — a yanked cable costs you a replug, not a fragmented library (and `--merge-days` / `--renumber-day` exist to tidy history if it ever needs it); Milky Way sessions follow the same rule
- **Stack-only projects import too** (sub-frame saving is off by default on Seestars): a project folder holding just `Stacked_*.fit` + JPG goes through the normal path — display naming, keep-highest, verified JPG alongside
- **Per-sub JPEG previews** (the S50 Pro writes one beside every sub) import as verified, ledgered riders into their sibling FIT's Day folder — with catch-up for FITs imported before the camera joined
- A stack the camera **re-saved after a session** (the S50 Pro annotates on shutdown) is detected by the ledger and re-copied atomically, re-verified — the Mac never quietly keeps stale stack bytes
- The S50 Pro's wide-angle camera pairs Milky Way sessions like the S30 Pro's; any *other* wide-camera output the firmware may write will surface as "NOT handled" until it has been seen in the wild — the tool names what it can't read rather than guessing
- Full MyWorks semantics: `_sub` light frames into Day folders, only the highest `Stacked_N` kept, `_mosaic_pt` panels into `panels/`, `(mosaic)` display suffixes
- Simultaneous **Milky Way captures auto-pair** to the DSO session shot at the same moment, renamed and filed under the DSO's display name
- S50-family (S50 / S50 Pro) Lunar / Solar / Planetary / Scenery photo and video import
- SAFE-aware cleanup: after an import it offers to clear source folders **only** when every single file in them is ledger-verified — *every* file, JPEGs and all (photo modes import their JPEG siblings verified + ledgered precisely so this stays true) — with No as the default, and clearing flags only the scanned camera's own ledger entries

## Install

Requires macOS, Python 3, and `astropy`. **Install Python from
[python.org](https://www.python.org/downloads/)** (then
`/usr/local/bin/python3 -m pip install astropy`) — see the permissions
section for why Apple's bundled Python is not enough.

**The easiest route**: click the green **Code** button above →
**Download ZIP** → unzip it (usually lands in Downloads) → paste this one
line into Terminal:

```bash
bash ~/Downloads/brettjoastro-fits-importer-main/install-scripts.sh
```

(Browser downloads strip the "double-clickable" permission from scripts, so
the one paste is more reliable than clicking the installer — though the
`Install … .command` file works too once you right-click → Open it.)

**The git route:**

```bash
git clone https://github.com/Brettjo77/brettjoastro-fits-importer.git
cd brettjoastro-fits-importer
bash install-scripts.sh
```

Either way, the installer copies the engine, panel, and watcher to `~/bin`, installs and ad-hoc-signs the app wrapper into `~/Applications`, puts a one-double-click **Restart FITS Importer** button on your Desktop, installs a single LaunchAgent (with your `$HOME` substituted), and prints the first-run steps. Then just plug a camera in.

## macOS permissions — read this once, save a week

USB camera drives are "removable volumes", and macOS gates background access
to them per-process. Three hard-won facts:

1. **Apple's `/usr/bin/python3` is a "platform binary"** — from a background
   (launchd) launch it is *silently denied* removable-volume access and is
   never allowed to show the permission prompt. No Settings toggle reliably
   fixes this. That's why this project prefers python.org Python: it is
   ordinary signed software, so macOS simply **asks** — click Allow once and
   the hands-free flow (plug in → notification → panel → green scan) is
   permanent, reboots included.
2. **Terminal-launched processes inherit Terminal's grant**, which is why
   `Restart FITS Importer.command` on your Desktop always works, whatever
   else is going on. It is the guaranteed fallback.
3. The **app wrapper** (`BrettjoAstro FITS Importer.app`, ad-hoc signed by
   the installer) gives the panel a stable identity you can also grant Full
   Disk Access to by dragging it into System Settings → Privacy & Security —
   useful belt-and-braces, but unsigned apps' grants can go stale, which is
   why signing matters and the installer does it for you.

If a background-started panel ever logs `Operation not permitted`, the log
line itself names the exact thing to grant — or just use the Desktop button.

### First run on an existing archive

If you already have imported data on disk, don't let everything count as "new":

```bash
python3 ~/bin/astro-import.py --scan-only   # read-only: what does it see?
python3 ~/bin/astro-import.py --report      # read-only: how does it categorise?
python3 ~/bin/astro-import.py --baseline    # existing camera files join the ledger WITHOUT copying
python3 ~/bin/astro-import.py --reconcile   # SHA-verifies camera ↔ disk while both copies exist
```

The baseline prints an audit listing any target with no local copy; `--unbaseline "<target>"` un-marks those (keeping anything reconcile proved) so a real import picks them up.

## Configuration

Defaults put everything under `~/Documents/Astro/`. To relocate anything, copy
[`config.example.json`](config.example.json) to
`~/Library/Application Support/Astro Import/config.json` and edit. Precedence:
environment variable → `config.json` → built-in default. The installer never
overwrites an existing config.

## Safety model

- The camera is read-only apart from optional "done" Finder tags on the ASIAir — and nothing anywhere is deleted without a verified copy plus your explicit Yes
- An empty scan never clears ledger flags (a half-mounted drive can't fake "files vanished"), and each camera's scan can only ever touch its own entries
- A concurrency lock (atomically created, with stale-PID detection) stops two imports colliding — the panel's Report takes the same lock, so a report save can never race an import
- The panel server answers **only** the local page: requests with a non-local Host or a foreign Origin are refused, and prompt answers carry the id of the question they answer, so a stale click can never land on a later card
- The ledger is plain JSON written with fsync-then-atomic-rename (and recovered loudly from its `.bak` if it is ever unreadable), history is an append-only JSONL log, and a published mirror folder keeps browsable copies of both plus the dashboard and last report — **point the mirror at an iCloud folder** (one line in config.json) and the tool's memory survives a full machine rebuild

## CLI reference

The panel covers day-to-day use; everything is also scriptable:

| Command | What it does |
|---|---|
| `--scan-only` | Read-only scan, machine-readable tagged output (used by the watcher) |
| `--report` | The backup report: safe-to-clear / unverified / new, per camera |
| `--baseline` | Mark everything currently on the camera(s) as imported, without copying |
| `--reconcile` | Upgrade baseline entries to *verified* by SHA-comparing camera ↔ disk |
| `--verify [--deep]` | Re-check imported files on disk (size, or full re-hash with `--deep`) |
| `--pick` | Native picker dialog for choosing targets (Terminal fallback flow) |
| `--dashboard` | Regenerate and open the HTML status dashboard |
| `--refresh-metadata` | Back-fill ledger metadata after parser improvements (safe, repeatable) |
| `--set-filter "<target>" "<filter>"` | Record the true filter for a target's ASIAir frames (`--night` to limit; `none` clears) |
| `--skip-target` / `--unskip-target` | Never-import list management |
| `--unbaseline <target>` | Remove *unverified* baseline entries so files count as new again |
| `--dry-run` | Everything printed, nothing written |
| `--targets A B` | Restrict an import to specific targets |

## Testing

222 end-to-end checks run the real engine and the real panel against simulated cameras (hand-built minimal FITS files, every device layout, crash/rename/mosaic/Milky-Way/cleanup/consent/interruption/multi-Seestar scenarios — including that the destination preview must equal the folders the import then actually creates, that a folder holding any unproven file is never offered as SAFE, and that the panel refuses foreign-origin requests):

```bash
python3 test_v2.py     # 166 engine checks
python3 test_app.py    # 56 panel checks (boots the real HTTP server)
```

## Project layout

```
HOW-IT-WORKS.md                      the logic in plain English (start here)
Install … .command                   double-click installer (the no-terminal route)
astro-import.py                      the engine (all cameras, ledger, report, dashboard)
astro-app.py                         the control panel (localhost:8765)
astro-watch.sh                       drive watcher (one for both cameras)
BrettjoAstro FITS Importer.app/      app wrapper — the panel's grantable macOS identity
Restart FITS Importer.command        Desktop one-click restart (Terminal context)
com.brettjohnson.astro-import.plist  LaunchAgent template ($HOME substituted on install)
install-scripts.sh                   installer / updater
config.example.json                  optional path overrides
test_v2.py · test_app.py · test_env_helper.py
docs/                                the website (GitHub Pages: Settings → Pages → /docs)
```

## License

[MIT](LICENSE) © 2026 Brett Johnson. Built with [Claude](https://claude.com/claude-code).

*FITS = Flexible Image Transport System — the astronomy standard since 1981. This tool treats every one of yours as irreplaceable.*
