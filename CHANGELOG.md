# Changelog

## 1.3.0 — 2026-09-05

The Seestar S50 Pro joined the family — the fourth camera, and the second
dual-camera model (260mm f/5.2 telephoto + 63° wide-angle, both 4K). Before
release, the whole application went through two adversarial review rounds
(an astrophotographer's eye and an engineer's eye); everything they caught
is fixed below.

**S50 Pro**
- Recognised from its FITS identity with the Pro check deliberately ahead of
  the bare-S50 check (the original-S30 lesson: a Pro variant must never be
  misfiled into its base model's tree). Spacing/case variants all map to the
  same camera, and token matching is bounded so "S50 PRO-anything-else" can
  never sneak in.
- Its **own destination tree** (`Seestar S50 Pro/`), own per-target day
  numbering, own presence tracking — four cameras, four clean stories.
- Four-worlds modes (Lunar / Solar / Planetary / Scenery, photo and video)
  import — and not just for the S50 family: **every** model now backs up
  whatever mode folders it carries (an S30 Pro's Moon shots were silently
  ignored before; review finding).
- Reconcile/verify walk the new tree; Milky Way pairing, night continuation,
  SAFE cleanup, and the panel inherit the new camera automatically.

**Identity honesty (review findings)**
- Model detection now takes **one vote per project folder** instead of
  trusting the first FITS file `os.walk` happens upon — a stale leftover
  from another camera can no longer classify the whole volume.
- **Mixed identities on one volume refuse the import** outright, naming the
  folders; an **unrecognised identity refuses** rather than guessing a tree
  (a ledger that never forgets must never memorise a wrong camera).
- MyWorks folders this tool does not understand are **loudly listed** — on
  the panel, in the report, in the watcher summary — as "on camera, NOT
  backed up", instead of hiding behind "Nothing new. Every frame is backed
  up." A second mounted Seestar is announced too (one camera at a time).
- Volume discovery now matches any `/Volumes/Seestar*` name, so a unit that
  mounts as "Seestar 1" (or a future model's own name) is still found.

**SAFE now means every file (review finding, the big one)**
- The cleanup gate previously ignored JPEGs and unknown file types when
  deciding a folder was SAFE — it could delete a Solar shot's JPEG that had
  never been backed up. Now **every file gates** (only camera thumbnails,
  macOS litter, and superseded stacks are exempt), Solar/Lunar/etc. **JPEG
  siblings are imported, verified, and ledgered** like any frame, and the
  stacked keeper's JPEG rides along verified instead of best-effort.
- Clearing a folder flags **only the scanned camera's** ledger entries —
  relpaths repeat across Seestars, and one unit's cleanup must not falsify
  another's presence record.

**Panel + engine hardening (review findings)**
- The panel server now refuses requests with a non-local Host or foreign
  Origin (drive-by-POST / DNS-rebinding shield), and every answer carries
  the id of the question it answers — a stale click can never resolve a
  later, more dangerous card.
- Panel "Report" takes the same lock as imports (a report save can no longer
  race a running CLI import); the lock itself is created atomically.
- Ledger writes fsync before the atomic rename; a corrupt `ledger.json`
  recovers loudly from its `.bak` instead of falling through to a baseline
  offer.
- Milky Way sessions now use the same ledger-aware, night-continuing Day
  numbering as everything else (an interrupted MW import resumes into the
  same night; archiving MW folders no longer restarts numbering).
- Unparseable calibration filenames in `Autorun/` force a NOT-SAFE verdict
  and are named in the report (they used to vanish from the arithmetic).
- Non-DSO modes appear as ordinary tickable rows on the panel — no more
  invisible riders on an import — and `--targets` governs them too.

**Second review round (fresh adversarial pass on the revision)**
- **Fixed a data-loss bug the first revision introduced**: the SAFE gate's
  superseded-stack exemption was wrong for Milky Way folders, which hold one
  keeper *per session* — an unledgered lower-N keeper could have been
  deleted on a Yes. MW/panel/mode folders now never exempt stacks; only DSO
  project dirs (where import itself enforces keep-highest) do. A test
  reproduces the exact scenario.
- Stack/keeper JPGs are registered in the scan's relpath set, so a report
  right after an import can no longer falsely mark them "cleared from
  camera"; the report's per-target SAFE verdict now runs the same
  every-file walk as the cleanup gate; a blocked folder **names** the
  unproven files instead of going quiet.
- **Stack-only projects import** (sub-frame saving is OFF by default on
  Seestars): a project folder with `Stacked_*.fit` and no `_sub` sibling
  imports through the normal path — naming, keep-highest, JPG rider.
  (MilkyWay stack-only folders stay visibly "NOT handled" — their
  per-session keepers don't fit keep-highest.)
- Identity votes filter AppleDouble litter *before* sampling (a Finder-
  touched card could burn the tries and fall back to a guess); loose root
  FITs vote too; the refusal is a clean message — never a traceback — on
  every path (import, --baseline, --pick), and the panel keeps scanning the
  other camera.
- The watcher notification and the panel's green banner no longer say "all
  backed up" over unhandled folders (new ATTENTION count in the scan tags);
  project-dir matching is exact ("M 8" can no longer adopt "M 81"'s
  folder); non-.fit strays in Autorun weigh on its verdict; reconcile can
  upgrade baselined JPEG/video media; --pick lists mode folders and
  --targets accepts both their names; the destination preview shows mode
  imports; Origin "null" is refused; a corrupt ledger with no usable .bak
  refuses to baseline over itself, and a recovery no longer overwrites the
  good .bak.

**First light (2026-09-05, 724 frames, flawless identity) taught us one thing**
- The S50 Pro writes a **JPEG preview beside every sub** — no earlier Seestar
  did. The every-file SAFE gate caught them on night one (refused cleanup and
  named all 724, exactly as designed). Now they import as **verified,
  ledgered riders** into their sibling FIT's Day folder — including catch-up
  for FITs imported before this existed (a ledger sibling lookup supplies
  the right Day folder, so a later night can never misfile them). Its sub
  names also carry the filter (IRCUT/LP) — first Seestar to tell us.
- JPEG-only and stack-only work now shows as an importable row on the panel
  and in the picker, and counts in the watcher summary.
- The S50 Pro also **re-saves its stack after a session** (an annotation
  pass on shutdown). A camera stack that changed since it was ledgered is
  now re-copied atomically and re-verified — before, it was skipped and the
  SAFE gate (rightly) blocked the folder forever. MW keepers get the same
  treatment.
- The panel's Activity log folds ANY progress bar into one updating line,
  matched by shape rather than a hardcoded label list (the 319-stacked-
  JPEG-bars incident).

222 end-to-end checks (166 engine + 56 panel), all green — including the
fourth-camera chain, the every-file SAFE gate with the MW-keeper repro,
camera-scoped clearing, the identity refusals, MW night continuation,
stack-only imports, JPEG riders fresh + catch-up, the re-saved-stack
refresh, and the panel's Host/Origin and stale-answer shields.

## 1.2.0 — 2026-08-18

A second Seestar joined the family and a yanked USB cable taught the importer
some manners.

- **Original Seestar S30 support**: detected from its own FITS identity, with
  its own destination tree (`Seestar S30/`), its own per-target day numbering,
  and its own camera-presence tracking — two Seestars shooting the same target
  never interleave. Proven live on first contact: five targets, clean scan,
  correct tree.
- **Night continuation for Seestar imports**: an interrupted/resumed import
  now lands in the *same observing night's* Day folder instead of fragmenting
  one night across several (the rule the ASIAir path always had).
- **Repair commands**: `--merge-days "<target>" N M …` folds split Day folders
  back together (files moved, ledger rewritten, empties removed, root-dwelling
  stacks left in place); `--renumber-day "<target>" FROM TO` renames a Day and
  its ledger entries to close numbering gaps.
- **Friendlier install**: a double-clickable
  `Install BrettjoAstro FITS Importer.command` for the download-ZIP route — no
  terminal, no git required.
- **HOW-IT-WORKS.md**: the entire logic in plain English for astronomers —
  the backup-first promise, the ledger, Day folders, calibration consent,
  what SAFE means, and what can never happen.

179 end-to-end checks (133 engine + 46 panel), all green — including a
two-Seestar simulation and the interrupted-night resume.

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
