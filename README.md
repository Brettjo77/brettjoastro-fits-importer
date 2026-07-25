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

**ZWO ASIAir**

- Per-scope recognition from FITS focal length; filename-parsed metadata with FITS fallback (including no-filter and mosaic-panel filename forms)
- A calibration library that ingests **all** darks/flats/biases from `Autorun/`, then hard-links the *matching* set (gain, filter, focal length, rotator angle, exposure) into each session's folder — and asks first when flats look like they belong to a different optical configuration
- The ASIAir is treated as a **backup of record**: this tool never deletes from it, ever

**Seestar (S30 Pro / S50)**

- Model detected from the FITS `CREATOR` header (with an S50-only-mode-folder fallback)
- Full MyWorks semantics: `_sub` light frames into Day folders, only the highest `Stacked_N` kept, `_mosaic_pt` panels into `panels/`, `(mosaic)` display suffixes
- Simultaneous **Milky Way captures auto-pair** to the DSO session shot at the same moment, renamed and filed under the DSO's display name
- S50 Lunar / Solar / Planetary / Scenery photo and video import
- SAFE-aware cleanup: after an import it offers to clear source folders **only** when every single file in them is ledger-verified — with No as the default

## Install

Requires macOS with the Xcode Command Line Tools Python 3 and `astropy`
(`/usr/bin/python3 -m pip install --user astropy`).

```bash
git clone https://github.com/Brettjo77/brettjoastro-fits-importer.git
cd brettjoastro-fits-importer
bash install-scripts.sh
```

The installer copies the engine, panel, and watcher to `~/bin`, installs a single LaunchAgent (with your `$HOME` substituted), and prints the first-run steps. Then just plug a camera in.

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
| `--skip-target` / `--unskip-target` | Never-import list management |
| `--unbaseline <target>` | Remove *unverified* baseline entries so files count as new again |
| `--dry-run` | Everything printed, nothing written |
| `--targets A B` | Restrict an import to specific targets |

## Testing

136 end-to-end checks run the real engine and the real panel against simulated cameras (hand-built minimal FITS files, both device layouts, crash/rename/mosaic/Milky-Way/cleanup scenarios):

```bash
python3 test_v2.py     # 114 engine checks
python3 test_app.py    # 22 panel checks (boots the real HTTP server)
```

## Project layout

```
astro-import.py                      the engine (both cameras, ledger, report, dashboard)
astro-app.py                         the control panel (localhost:8765)
astro-watch.sh                       drive watcher (one for both cameras)
com.brettjohnson.astro-import.plist  LaunchAgent template ($HOME substituted on install)
install-scripts.sh                   installer / updater
config.example.json                  optional path overrides
test_v2.py · test_app.py · test_env_helper.py
docs/                                the website (GitHub Pages: Settings → Pages → /docs)
```

## License

[MIT](LICENSE) © 2026 Brett Johnson. Built with [Claude](https://claude.com/claude-code).

*FITS = Flexible Image Transport System — the astronomy standard since 1981. This tool treats every one of yours as irreplaceable.*
