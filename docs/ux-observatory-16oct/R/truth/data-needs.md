# What the engine must add to `observatory/1` for the page to be honest

Checked against `astro-import.py` (`build_projects` → `observatory_from`). Three kinds of need: fields that exist in
`projects/1` but are dropped before the Observatory; fields the sample dataset shows but the engine does not emit (the
mocks depend on them); and fields nobody has yet.

## A. Already computed by the engine, not passed through (cheap)

| Field | Type | Example | Why / which block |
|---|---|---|---|
| `programmes[].captureState` | `"auto" \| "open" \| "complete"` | `"open"` | Engine has `entry["capture_state"]`; the page only sees it as prose in `evidence`. Needed by the status pill, the "Still capturing" heading, the lane caption, the Targets pills. |
| `programmes[].captureStateSource` | `"capture-state.json" \| "rule"` | `"capture-state.json"` | So the page can say "kept open by you" vs "within 14 nights" without regexing text. |
| `programmes[].calibration.nightsWith`, `.nights`, `.darks`, `.flats`, `.biases` | ints | `{nightsWith: 3, nights: 5, darks: 90, flats: 50}` | Engine emits them in `projects/1`; the sample strips them. Lets the Calibration mark say "flats on 3 of 5 nights" and stops the session-vs-programme contradiction. |
| `programmes[].masters[]`, `programmes[].finals[]` | file names | `["Andromeda Galaxy_master_FRA400.xisf"]` | Already in `evidence` prose. Needed so the shared-Askar warning can be suppressed when the master's name carries a scope id, and so "Finish it" can link the file. |
| `notCounted` | object | `{unknownNames: {names: 2, frames: 184}, noScope: 2, noNight: 0, unreadable: 0, duplicates: 305, notLightFrames: 14379}` | Engine has `sources.dropped`; the page only gets a sentence. Needed by "Needs attention" counts, the buttons, and the reconciliation subtraction (the 31,284 − 16,414 gap must be explained line by line; `notLightFrames` is new arithmetic the engine must do). |
| `warnings[].kind` (make `warnings` objects) | `{kind, count, frames?, text}` | `{kind: "unknown_names", count: 2, frames: 184, text: "…"}` | Both mocks parse warning prose with regexes that already fail on the engine's real strings. Kinds: `unknown_names`, `no_scope`, `no_night`, `unreadable`, `snapshot_age`, `inventory_missing`, `finals_unchecked`, `capture_state_bad`. |
| `scopes[].order` | int | `1` | `D.scopes` is sorted alphabetically by the engine; the contract order (FRA400, 107PHQ, S30 Pro, S50, S50 Pro, Starfront) is what the panel uses. One fixed order everywhere was the brief's ask. |
| `scopes[].kind` | `"askar" \| "seestar"` | `"seestar"` | The page currently guesses "Seestar" from the camera name and from `cal == null`. Calibration wording and the "calibrates in the camera" line depend on it. |
| `unknownNames[]` | strings | `["M31 mosaic panel 3", "ngc7000_test"]` | So "Review the names" can list them on the page instead of sending Brett to `--targets-draft`. |
| `inputs` (keep as the object the engine already builds; the sample has an integer) | object | `{snapshot: {machine: "Mac", at: "2026-10-13T06:40Z", ageHours: 74.5, rows: 11206}, inventoryAt: …, finals: true}` | Freshness line: "the Mac's copy is 3 days old". Both mocks regex `sourceNote` instead. `finals: false` must make the page say "Done cannot be shown: finished pictures weren't checked". |
| `ledgerMeta.rows` vs `snapshotRows` | ints | `31284` / `11206` | Document that `snapshotRows` is the Mac's snapshot only; C's header uses it as the total. |

## B. Shown by the sample but never emitted by the engine (remove the dependency or add the field)

| Field | Type | Example | Why / which block |
|---|---|---|---|
| health item "Duplicate copies excluded" (info) | — | — | Both mocks' "305 duplicates · nothing to do" line comes from this. Either the engine emits it (better: `notCounted.duplicates` above) or the page builds the line from the count. |
| "their 184 frames are not counted" in the unknown-names warning | — | — | The engine's string has no count; C shows "?". Use `notCounted.unknownNames.frames`. |
| `calibration.missing` on Seestar programmes | — | — | Engine emits `{applies: false}` only. Page code must not read `.missing.length` without a guard (A and C both guard today; keep it). |
| `readyOn = lastNight + 14` | — | — | Engine uses `+ QUIET_PERIOD_DAYS + 1` (first night after the quiet period). Page must never recompute it; and the quiet band is "last 14 nights" while the rule is `days_since <= 14` (15 nights inclusive): say "usually" in the caption. |

## C. New fields nobody has yet

| Field | Type | Example | Why / which block |
|---|---|---|---|
| `pendingImport` | `{files, targets, failedEject, camera, seenAt}` | `{files: 3559, targets: 29, failedEject: true, camera: "Seestar S30 Pro", seenAt: "2026-10-16T08:50Z"}` | Freshness line and a note on every "Ready to process" list: these frames are not counted yet. From the watcher's last scan of a mounted camera. `null` = not known, and the page says so. |
| `programmes[].sample` | `true \| false \| null` | `true` | The "Quick look" state. Written by Brett via capture-state.json (`"M45|FRA400|home": "sample"`) and read back as a fact. Replaces both mocks' hour cutoffs. |
| `programmes[].masterOwnerUncertain` | `{uncertain: true, candidates: ["FRA400", "107PHQ"], master: "…xisf"}` | — | Replaces the regex on `evidence` for "other Askar". Suppressed by the engine when the file name carries a scope id. |
| `programmes[].calibration.mode` | `"tracked" \| "inCamera" \| "unknown"` | `"inCamera"` | So "Not tracked · the Seestar calibrates in the camera" is a fact from the engine, not a page assumption from `applies: false`. |
| `programmes[].exposureOverride` | seconds, nullable | `10` | For frames with no exposure in their headers (Milky Way Core: 2,150 frames). Brett types the sub length once; the engine then reports hours and marks them "from your note". The page's "Tell the importer the sub length" button needs somewhere to write. |
| `sessions[].objects` or allow several sessions per (scope, night) with a `sessionIndex` | — | — | Already true in the data (107PHQ on three objects one night); the page needs a stable way to say "3 objects" and to pick "longest", not "first in the array". |
| `night.label` or document the convention | `{night: "2026-10-16", evening: "2026-10-15"}` | — | Noon-to-noon: the night keyed 16 Oct is the evening of the 15th. The page needs `evening` (or the rule in the dataset) to print "Thu 15 → Fri 16 Oct". |
| `targets[].plannedScopes[]` | scope ids | `["FRA400"]` | Coverage view: "not captured" vs "not planned on this scope" (from C's review; not drawn in either mock but the page will need it). |
| `generatedAtLocal` + `timezone` | ISO + IANA | `"2026-10-16T09:12:00+01:00"`, `"Europe/London"` | `generatedAtIso` is UTC with a +00:00 that is not London time in October (BST); "09:12" in `generatedAt` is local. Keep the two from drifting. |

## Page-side rules that need no new data (so the next build gets them right)

- One rounding function (`round half up, 1 dp`) and totals shown as the sum of the displayed parts.
- Count scopes with a Set; count sessions and objects separately.
- Percentages by largest remainder so they sum to 100.
- Minutes below 0.1 h; "hours unknown" when `hours == 0 && lights > 0`; "0" only when `lights == 0`.
- Scope order from `scopes[].order`, never from array order or hours.
- Never regex `evidence`, `sourceNote` or `warnings[]` prose for numbers or state.
