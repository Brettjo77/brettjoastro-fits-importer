# Changelog

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
