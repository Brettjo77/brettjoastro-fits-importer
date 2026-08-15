# Changelog

## 1.1.0 — 2026-08-14

Two weeks of nightly real-world use (a Mac rebuild included) fed straight back
into the tool.

**Panel**
- Calibration **pairing preview with consent checkboxes**: the scan runs the real
  matching gates and shows which bias/dark/flat sets pair with which target;
  everything pre-ticked, unticking skips the link (frames still back up), and
  ticked pairings import with no interruptions. Only questionable pairings still
  ask — and the question now names the set, its date and rotation versus the
  lights' ("self-describing cards").
- **"Where files will land"**: live destination tree computed by the same
  Day-numbering code the import uses; updates as you tick. Tests pin that the
  preview equals the folders the import then creates.
- One-page app layout (page never scrolls; panes do), camera storage as a live
  header meter, wider Activity log with hanging indents and `~`-shortened paths,
  date-ordered target and inventory lists (newest first, last-shot dates shown),
  calibration summary card with new-set breakdown, collapsible backed-up
  inventory.
- **Completion banner** (frames, targets, duration — survives rescans until
  dismissed), tab-title flip, and a macOS notification with chime.
- Scope badges read the *incoming* frames' focal length, so multi-rig targets
  are labelled by tonight's setup, not their history.

**Engine**
- `--set-filter "<target>" "<filter>" [--night YYYY-MM-DD]` records the true
  glass when the ASIAir filename carries no filter token.
- Panel pre-consent map (`CAL_DECISIONS`) honoured at link time; CLI behaviour
  unchanged when empty. Probation-mark hygiene between match runs.

**macOS permissions, solved properly**
- All launchers prefer **python.org Python** when installed (Apple's Python is a
  platform binary: silently denied removable-volume access from background
  launches and never allowed to ask; python.org Python asks once).
- New **app wrapper** (`BrettjoAstro FITS Importer.app`) — ad-hoc signed by the
  installer — gives the panel a stable, grantable identity; the watcher launches
  the panel through it.
- Desktop **Restart FITS Importer.command**: one double-click, Terminal context,
  always works.
- The panel's permission hint now names the exact binary macOS is blocking.

**Watcher**
- Camera *swaps* always announce (flap guard now applies per camera set, not
  globally); honest notification wording when the pre-scan is blocked; panel
  launches route through the app wrapper when present.

**Installer v5**
- Installs and signs the app wrapper, installs the Desktop restart button,
  checks astropy against the preferred Python, documents the permission model.

166 end-to-end checks (120 engine + 46 panel), all green.

## 1.0.0 — 2026-07-25

First public release as **BrettjoAstro FITS Importer**.

- One engine, one ledger, one panel, one watcher for ZWO ASIAir **and** Seestar (S30 Pro / S50)
- SHA-256-verified, crash-safe copies; lifetime ledger; honest backup report; HTML dashboard
- ASIAir: per-scope recognition, calibration library with configuration-matched hard-links,
  ask-before-linking gate for questionable flats, mosaic support, backup-of-record stance
- Seestar: CREATOR-based model detection, full MyWorks semantics, Milky Way ↔ DSO session
  pairing, keep-highest stacks, S50 non-DSO modes, SAFE-aware cleanup (default No)
- Generalised for any Mac: $HOME-derived paths + optional config.json overrides
- 136 end-to-end checks against simulated cameras
- Proven on real hardware the day of release: 686-frame Seestar import, verified and
  safely cleared from the camera
