# Phase 1 (honest numbers): what the engine now writes

Engine: `astro-import.py` on branch `claude/observatory-ux-v2`. Everything here is **additive**:
no existing field was removed or renamed. Two existing fields can now carry a **new value**:
`status` (projects.json dataset / observatory programme) can be `"sample"`, and a card's
`state` can be `"sample"`. `capture_state_source` / `captureStateSource` can be `"sample-rule"`.

`projects.json` keeps its snake_case; `observatory/1` its camelCase. The same fact has both
spellings; both files come from one `build_projects` pass, so they never disagree.

## 1. States (per dataset / programme)

Precedence, in `build_projects`:

1. a matching finished picture → `done`
2. one of Brett's masters in the folder → `in_progress`
3. hand mark `open` → `capturing`; hand mark `complete` → `ready_to_process`
4. **kept state** (§6.1): if Final Astro Images could not be read this time and the previous
   projects.json had this dataset `done`, it stays `done` (its `finals` and `final_date` are
   carried over); if the inventory is missing and it was `in_progress`, it stays so. Only
   from a previous file; a fresh build keeps nothing.
5. **sample rule** (§6.2): status still `capturing`/`ready_to_process`, hand mark `auto`, no
   master, no final, and `integration_seconds < ASTRO_SAMPLE_MINUTES * 60` → `sample`.
   Not applied when integration is 0 because the frames carry no exposure (hours unknown).
   A hand `sample` mark is also `status: "sample"` now (was: derived status + `sample: true`).
6. else the date rule: `days_since_last_night <= quietDays` → `capturing`, else `ready_to_process`.

`sample: true` stays on every sample (rule or hand), so old readers still work.

## 2. New per-dataset fields

projects.json `projects[].datasets[]` → observatory `targets[].programmes[]` (and where noted the `statusCards[]`):

| projects.json | observatory/1 programme | card | Type | Meaning |
| --- | --- | --- | --- | --- |
| `ready_since` | `readySince` | `readySince` | ISO date or null | `ready_to_process` only. Rule-ready: `last_session + quietDays + 1`. Hand `complete`: `last_session`. Null for every other state. |
| `reason` | `reason` | `reason` | string | The state in words, one line (formats below). |
| `final_date` | `finalDate` | — | ISO date or null | Day the newest matching finished picture was last saved (file mtime, local date). Null unless `done`. |
| `new_frames_since_final` | `newFramesSinceFinal` | — | bool | `done` and `last_session > final_date`. State stays done; the page should show "new frames since". |
| `state_kept_from` (only when kept) | `stateKeptFrom` | — | ISO timestamp or null | The `generated_at` of the projects.json the state was kept from. |
| `capture_state_source` | `captureStateSource` | — | `"rule"` / `"capture-state.json"` / **`"sample-rule"`** | New value for rule samples. |
| `status` | `status` | `state` | adds **`"sample"`** | Card `state` is `"sample"` too (`OBS_STATE["sample"] = "sample"`). |
| — | `target`, `tid` | (cards had `target`) | string | The programme's target display name and contract id, so a flat list of programmes can be sorted and labelled without its parent. |

`reason` formats (plan §9.1; dates `Fri 16 Oct`, with the year only when it isn't the as-of
night's year; hours `29.4 h`, under an hour `45 min`, no exposure recorded `hours unknown`;
scope is the name without its maker: `FRA400`, `S30 Pro`, `S50`):

- ready: `ready since Wed 16 Sep · 31 min on the S30 Pro`
- capturing: `still capturing · ready from Fri 23 Oct` (or `still capturing · kept open by hand`)
- in_progress: `master in the folder · 29.4 h on the FRA400`
- done: `finished · final of Thu 20 Aug` (or just `finished` when no date)
- sample: `sample · 29 min on the S30 Pro`

Observatory `evidence` for a sample: `a quick look: 29 min of light (under 30 min); kept out of the queue`
(or `(your flag)` for a hand mark). A done programme with new frames appends
`; new frames since (last session 20 Sep 2026)` to its evidence.

## 3. New top-level fields

| projects.json | observatory/1 | Shape |
| --- | --- | --- |
| `rules` | `rules` | `{"quietDays": 14, "sampleMinutes": 30, "activeWindowNights": 30}` |
| `state_counts` | `stateCounts` | `{"capturing": n, "ready_to_process": n, "in_progress": n, "done": n, "sample": n}` — datasets; samples are outside the four |
| `state_hours` | `stateHours` | same keys, hours to 1 dp |
| `finals_unmatched` | `finalsUnmatched` | `[{"file": "holiday_snap.png", "folder": "", "why": "..."}]`, capped at 200 |
| `finals_unmatched_count` | `finalsUnmatchedCount` | int (the true count, even past the cap) |
| `finals_ambiguous` | `finalsAmbiguous` | `[{"file": "ZWO Askar Scopes/M81_Bodes_Galaxy.jpg", "target": "M81", "scopes": ["FRA400", "107PHQ"]}]`, capped at 200 |
| `finals_ambiguous_count` | `finalsAmbiguousCount` | int |
| `states_kept_from` | `statesKeptFrom` | ISO timestamp or null |
| — | `targets[].readySince` | newest `readySince` among the target's programmes, or null |

`finalsUnmatched[].why` is one of exactly three strings:
- `no catalogue code or known name in the file name`
- `name not in the contract` (the name carries a catalogue code the contract lacks)
- `no dataset for that object on that scope`

`finalsUnmatched[].file` is the bare file name and `folder` its path inside Final Astro
Images (`""` at the root). `finalsAmbiguous[].file` is the path inside Final Astro Images.

New `notices[]` kinds (same `{kind, count, frames, text}` shape, also in `warnings[]`):
- `finals_unmatched` (count = pictures), `finals-ambiguous` (count = pictures; hyphen as the brief asked),
- `states_kept` (count = datasets kept; text: `states kept from 2026-10-25T16:47:30+00:00: Final Astro Images could not be read, so 2 dataset(s) keep the done / in progress state they had`),
- `config` (a rule set to a bad value: `ASTRO_SAMPLE_MINUTES is set to 'abc', which isn't a whole number from 0 to 100000; using the default of 30`).
The existing `finals_unchecked` and `inventory_missing` notices stay.

`provenance` gained a sentence on samples. Existing `totals`, `pendingProgrammes` and the
target's `state` already excluded samples; `stateCounts`/`stateHours` are the per-state figures
to show. `totals.hours`/`lights` still include samples (they are archive totals, not a queue).

## 4. One order: `dataset_sort_key(d)`

The engine sorts every list it emits with one function (its docstring is the spec the page
mirrors): projects.json `projects[]` and each project's `datasets[]`, observatory
`targets[]` (no longer alphabetical) and each target's `programmes[]` and `statusCards[]`.

1. most recent capture first (`lastNight` / `last_session` / `last_captured`, newest first);
2. then the newest `readySince` / `ready_since` first (items without one sort after);
3. then the most hours (`hours`, or `integration_seconds / 3600`);
4. then the name, A to Z.

In JS terms, for programmes:
```js
const ord = iso => iso ? Date.parse(iso.slice(0,10) + "T12:00:00Z") : 0;
list.sort((a, b) => ord(b.lastNight) - ord(a.lastNight)
                 || ord(b.readySince) - ord(a.readySince)
                 || (b.hours - a.hours)
                 || String(a.target || a.name || "").toLowerCase().localeCompare(String(b.target || b.name || "").toLowerCase()));
```
Samples are not treated differently by the key: keep them out of the queue by `status`.

## 5. Config (§6.5)

Read like `ASTRO_QUIET_PERIOD_DAYS` (env var, else `config.json`, else default; Notepad's BOM fine):

| Key | Default | Range | Effect |
| --- | --- | --- | --- |
| `ASTRO_QUIET_PERIOD_DAYS` | 14 | 0–3650 | calendar days since the last night before a dataset is ready (unchanged) |
| `ASTRO_SAMPLE_MINUTES` | 30 | 0–100000 | under this much light → sample; **0 switches the rule off** |
| `ASTRO_ACTIVE_WINDOW_NIGHTS` | 30 | 1–3650 | reported in `rules.activeWindowNights` only; the page decides which scopes are active |

A value outside the range or not a whole number → the default, plus a `config` notice.
`--projects` now also prints one line: `States: 1 still capturing · 2 ready to process · 0 finish it · 1 done · 3 samples`.

## 6. Example (observatory/1, trimmed)

```json
{
  "schema": "observatory/1",
  "rules": {"quietDays": 14, "sampleMinutes": 30, "activeWindowNights": 30},
  "stateCounts": {"capturing": 1, "ready_to_process": 2, "in_progress": 0, "done": 1, "sample": 3},
  "stateHours": {"capturing": 1.0, "ready_to_process": 1.5, "in_progress": 0.0, "done": 0.2, "sample": 0.8},
  "finalsUnmatched": [
    {"file": "NGC9999_unknown.jpg", "folder": "", "why": "name not in the contract"},
    {"file": "holiday_snap.png", "folder": "", "why": "no catalogue code or known name in the file name"},
    {"file": "M31_FRA400.jpg", "folder": "", "why": "no dataset for that object on that scope"}
  ],
  "finalsUnmatchedCount": 3,
  "finalsAmbiguous": [{"file": "ZWO Askar Scopes/Iris_Nebula_HOO.jpg", "target": "NGC7023", "scopes": ["FRA400", "107PHQ"]}],
  "finalsAmbiguousCount": 1,
  "statesKeptFrom": null,
  "notices": [
    {"kind": "finals_unmatched", "count": 3, "frames": null, "text": "3 finished picture(s) match no dataset: ..."},
    {"kind": "finals-ambiguous", "count": 1, "frames": null, "text": "1 finished picture(s) could be of either Askar ..."}
  ],
  "targets": [
    {"id": "M64", "name": "Black Eye Galaxy (M 64)", "lastNight": "2026-09-20", "readySince": null, "state": "complete",
     "programmes": [{
       "camera": "Seestar S50", "status": "done", "sample": false,
       "captureState": "auto", "captureStateSource": "rule",
       "readySince": null, "reason": "finished · final of Thu 20 Aug",
       "finalDate": "2026-08-20", "newFramesSinceFinal": true, "stateKeptFrom": null,
       "finalsNamed": ["Black_Eye_S50.jpg"], "evidence": "finished picture Black_Eye_S50.jpg; new frames since (last session 20 Sep 2026)"
     }],
     "statusCards": [{"camera": "Seestar S50", "state": "complete", "readySince": null, "reason": "finished · final of Thu 20 Aug"}]
    },
    {"id": "M31", "name": "Andromeda Galaxy (M 31)", "state": "sample",
     "programmes": [{"camera": "Seestar S30 Pro", "status": "sample", "sample": true,
                     "captureStateSource": "sample-rule", "reason": "sample · 29 min on the S30 Pro",
                     "evidence": "a quick look: 29 min of light (under 30 min); kept out of the queue"}]}
  ]
}
```

## 7. Finals matching (how `done` is decided now)

- Object: the file stem through `resolve_target` (codes, `Name (CODE)`, `CODE - Name`, aliases), then
  the longest run of words in the stem that is a known name or alias, then the nearest parent folder
  that resolves. `_lookup_name` also knows a name without its kind word (`Black Eye` for
  `Black Eye Galaxy`) when no second target shares it — this applies to ledger names too.
- Scope: a rig tag in the file name (`_rigs_in`), else the nearest per-scope parent folder, else a
  folder that spells an archive root (`ZWO Askar Scopes`, `S30P`).
- A picture naming no scope: marks the dataset when the target has exactly one candidate
  (in that root, or at all); with two or more it marks **none** and is listed in `finalsAmbiguous`
  (each candidate dataset carries `attribution: ["shared-final"]` or `["unscoped-final"]`, as before).
