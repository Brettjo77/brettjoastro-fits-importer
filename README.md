# BrettjoAstro FITS Importer

**Backup-first imports for ZWO ASIAir and Seestar smart telescopes — every frame verified to the byte, every session remembered forever.**

![The control panel with both cameras connected](docs/img/panel-dark.png)

Plug in either camera (or both). A notification fires, a local control panel opens, and every new frame is copied with cryptographic proof it arrived intact. A lifetime ledger remembers everything you have ever imported — so archiving finished targets never causes re-imports, and the tool can tell you, honestly, what is safe to delete from a camera and what is not.

Built by [Brett Johnson](https://github.com/Brettjo77) for a ZWO ASI585MC Air (Askar FRA400 + Askar 107PHQ) and a Seestar S30 Pro, and generalised so it works on any Mac. First light: 686 frames imported, SHA-256-verified, and safely cleared from the camera in a single run.

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

**Seestar (S30 Pro / S50)**

- Model detected from the FITS `CREATOR` header (with an S50-only-mode-folder fallback)
- Full MyWorks semantics: `_sub` light frames into Day folders, only the highest `Stacked_N` kept, `_mosaic_pt` panels into `panels/`, `(mosaic)` display suffixes
- Simultaneous **Milky Way captures auto-pair** to the DSO session shot at the same moment, renamed and filed under the DSO's display name
- S50 Lunar / Solar / Planetary / Scenery photo and video import
- SAFE-aware cleanup: after an import it offers to clear source folders **only** when every single file in them is ledger-verified — with No as the default

## Install

Requires macOS, Python 3, and `astropy`. **Install Python from
[python.org](https://www.python.org/downloads/)** (then
`/usr/local/bin/python3 -m pip install astropy`) — see the permissions
section for why Apple's bundled Python is not enough.

```bash
git clone https://github.com/Brettjo77/brettjoastro-fits-importer.git
cd brettjoastro-fits-importer
bash install-scripts.sh
```

The installer copies the engine, panel, and watcher to `~/bin`, installs and ad-hoc-signs the app wrapper into `~/Applications`, puts a one-double-click **Restart FITS Importer** button on your Desktop, installs a single LaunchAgent (with your `$HOME` substituted), and prints the first-run steps. Then just plug a camera in.

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
- A concurrency lock (with stale-PID detection) stops two imports colliding
- The ledger is plain JSON, history is an append-only JSONL log, and a published mirror folder keeps browsable copies of both plus the dashboard and last report

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

166 end-to-end checks run the real engine and the real panel against simulated cameras (hand-built minimal FITS files, both device layouts, crash/rename/mosaic/Milky-Way/cleanup/consent scenarios — including that the destination preview must equal the folders the import then actually creates):

```bash
python3 test_v2.py     # 120 engine checks
python3 test_app.py    # 46 panel checks (boots the real HTTP server)
```

## Project layout

```
astro-import.py                      the engine (both cameras, ledger, report, dashboard)
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
