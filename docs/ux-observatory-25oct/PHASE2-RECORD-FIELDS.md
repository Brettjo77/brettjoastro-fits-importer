# Phase 2 (scope first): what the engine now writes

Engine: `astro-import.py` on branch `claude/observatory-ux-v2`, after 1.8.0. The field names are the
agreement in `PHASE2-CONTRACT.md`; this file is the reference for what landed. Everything here is
**additive** to `observatory/1`: no existing field was removed or renamed, and no existing field carries
a new kind of value. Chain P2 in `test_v2.py` proves each group, and proves that every 1.7.x and 1.8.0
field is still present (the iOS app reads this record).

Formats are phase 1's (`PHASE1-RECORD-FIELDS.md` §2): dates `Sat 31 Oct` (the year only when it isn't
the as-of night's), hours `29.4 h`, under an hour `45 min`, no exposure recorded `hours unknown`.
ISO dates are `YYYY-MM-DD`. A night is named by its evening (noon to noon).

## 1. The active window

`rules.activeWindowNights` (default 30, `ASTRO_ACTIVE_WINDOW_NIGHTS`) now does something: the window is
the **as-of night and the `activeWindowNights − 1` nights before it** ("the last 30 nights"). A night is
inside it when `asOfNight − night < activeWindowNights` in days. A scope, a unit or a dataset with frames
inside the window is active.

New top-level `activeWindow` (not in the contract; added so the page can draw the strip's empty cells
without working the rule out again):

```json
"activeWindow": {"nights": 30, "from": "2026-09-11", "to": "2026-10-10"}
```

## 2. `scopes[]` gain `active` and `lastOut`

| Field | Type | Meaning |
| --- | --- | --- |
| `active` | bool | the scope has a session inside the window |
| `lastOut` | ISO night | the scope's newest night with frames (never null in practice: a scope is listed only when it has frames) |

## 3. `units[]`: the cards

One card per **unit**, in the fixed card order: `scopeOrder` (the contract's order, scopes with frames
only) with the two Askars collapsed into ONE unit, `"ZWO"`, at the position of the first Askar. Each
Seestar scope is its own unit. Units with `active: false` are the Resting row; they stay in `units[]`.

With today's `contract/scopes.json` the order is **S30P, S50, S50P, ZWO** (the Askars are 5th and 6th in
the contract). The contract document says "ZWO, then the Seestars": that needs the Askars moved to the
top of `scopes.json`, which is a contract change, not an engine one.

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | the scope id for a Seestar (`"S30P"`); `"ZWO"` for the camera |
| `label` | string | the card's short title: the scope without its maker (`"S30 Pro"`, `"S50"`); `"ZWO"` |
| `name` | string | the full name: `"Seestar S30 Pro"`; the camera's name `"ZWO ASI585MC Air"` (from the Askars' `match.camera`) |
| `kind` | `"seestar"` / `"askar"` | |
| `short` | string | the tag: same as `id` |
| `scopeIds` | [string] | the Seestar's own id; for ZWO **both** contract Askars in contract order, whether or not each has frames |
| `scopes` | [string] | their names |
| `onScope`, `onScopeId` | string / null | the scope of the unit's newest session (the Askar of the newest ASIAir night); a Seestar unit: itself. The same night on both Askars (a data slip) goes to the one with more frames that night, then the first in contract order |
| `onScopeCurrent` | bool | that newest session is inside the window ("on the FRA400"); false means "last on the FRA400" |
| `colour` | hex or null | `onScope`'s colour (the `scopes[].colour` hex); the first scope's when there is no session |
| `active` | bool | any night inside the window across the unit's scopes |
| `lastOut` | ISO night / null | the unit's newest night with frames |
| `current` | [dataset summary] | the unit's datasets with frames inside the window, newest first (`dataset_sort_key`), **at most 2**. A **sample is never current** (phase 1 keeps a quick look out of every queue); a Done dataset with new frames is |
| `moreReady` | int | the unit's other `ready_to_process` datasets, not in `current` |
| `moreReadyHours` | float (1 dp) | their hours |
| `strip` | [{night, hours}] | one entry per night with frames inside the window, across the unit's scopes, oldest first; hours to 2 dp |
| `latestDone` | object / null | the unit's most recent Done dataset whose `finalDate` is **after** `lastOut` (the final is newer than the unit's newest night out, compared as ISO strings, so a final saved the day after the last night still shows). Null once the unit has been out again. Shape `{tid, target, codes, camera, scopeId, finalDate}` (the contract's four plus `codes` and `scopeId`) |

## 4. The dataset summary

One helper, `_obs_dataset_summary(programme)`, builds the short form used by `units[].current` and
`thisMonth.items`, so a card never disagrees with the programme it stands for. Exactly these keys:

```
tid, target, codes[], camera, scopeId, state, stateWord, hours, frames, nights,
firstNight, lastNight, readySince, reason, nextAction, calMissing, mosaic
```

`state` is the programme's `status` (`capturing` / `ready_to_process` / `in_progress` / `done` / `sample`);
`frames` is the programme's `lights`; `hours` the programme's (2 dp).

## 5. `programmes[]` gain five fields

| Field | Type | Meaning |
| --- | --- | --- |
| `scopeId` | string | the contract scope id (`camera` already carried the name) |
| `codes` | [string] | the target's catalogue codes (as `targets[].codes`) |
| `stateWord` | string | the four state words exactly, plus Sample: `Still capturing`, `Ready to process`, `Finish it`, `Done`, `Sample` |
| `nextAction` | string | the first unfinished step, in plain words (below) |
| `calMissing` | bool | the ASIAir's darks or flats are missing **and** the dataset is still capturing or ready (see below) |

`nextAction`, in order of precedence:

| When | Words |
| --- | --- |
| `calMissing` | `Darks or flats missing: darks` / `…: flats` / `…: darks and flats` |
| capturing, by the rule | `Still capturing · ready from Sat 17 Oct` |
| capturing, kept open by hand (no `readyOn`) | `Still capturing · kept open by hand` |
| ready_to_process | `Next step: collect the lights (3 nights, 650 frames)` (`1 night`, `1 frame` in the singular; thousands with a comma) |
| in_progress | `Finish it · master in the folder` |
| done | `Done · final of Thu 9 Oct`, or `Done` when the picture has no date |
| sample | `Sample · 29 min` (phase 1's hours format) |

**`calMissing` is true only while the dataset is capturing or ready.** The contract says "calibration
missing (ASIAir, `calibration.missing` non-empty)"; the engine adds the state condition because for a
dataset with a master (Finish it) or a final (Done) the missing frames are no longer the next step, and
"Darks or flats missing" would be the wrong first line on a finished picture. This matches the rule the
1.7.2 `evidence` note already used. A Seestar dataset (`calibration.applies: false`) is never `calMissing`.

## 6. `thisMonth`

```json
"thisMonth": {"month": "2026-10", "movedForward": 1, "finished": 1,
              "items": [{...dataset summary, "what": "final", "date": "2026-10-06"},
                        {...dataset summary, "what": "ready", "date": "2026-10-05"}]}
```

- `month` is the **build's own local date** (`now` in `observatory_from`; tests pass a fixed one), not
  the as-of night.
- `ready` items: `readySince` inside the month; `final` items: `finalDate` inside the month. A dataset
  can't be both (readySince is set only when ready, finalDate only when done). Masters carry no date yet
  (phase 3).
- `movedForward` counts the `ready` items, `finished` the `final` items (the line reads
  "{n} projects moved forward · {n} finished" as two separate counts).
- `items` are newest `date` first, ties by `dataset_sort_key`.

## 7. `recordsUpTo`

The newest night with frames across every scope (ISO), or null with no frames at all. A sample's frames
count: frames are frames. For the status line's "records up to Fri 16 Oct".

## 8. `pendingImport.scope`

`save_scan_summary(..., scope=None)` gained a keyword argument (every earlier argument and default is
unchanged): the scope name the panel worked out for the waiting frames (the ASIAir dest plan's scope for
the first target). It is written to `last-scan.json` as `scope`, null when not given, blank or not a
string. `read_scan_summary()` returns `scope` (a 1.8.0 file without it, or a wrong type, reads as null),
so `pendingImport.scope` is a string or null.

## 9. Example (observatory/1, trimmed to the new fields; the P2 fixture, as-of night 10 Oct 2026)

```json
{
  "schema": "observatory/1",
  "rules": {"quietDays": 14, "sampleMinutes": 30, "activeWindowNights": 30},
  "activeWindow": {"nights": 30, "from": "2026-09-11", "to": "2026-10-10"},
  "recordsUpTo": "2026-10-05",
  "scopeOrder": ["S30P", "S50", "S50P", "FRA400", "107PHQ"],
  "scopes": [
    {"id": "S30P", "camera": "Seestar S30 Pro", "kind": "seestar", "order": 1, "colour": "#eda100",
     "active": true, "lastOut": "2026-10-05", "...": "1.7.x fields unchanged"},
    {"id": "S50", "camera": "Seestar S50", "kind": "seestar", "order": 3, "colour": "#0a0a0a",
     "active": false, "lastOut": "2026-08-20"},
    {"id": "FRA400", "camera": "Askar FRA400", "kind": "askar", "order": 5, "colour": "#e05a5a",
     "active": true, "lastOut": "2026-10-02"},
    {"id": "107PHQ", "camera": "Askar 107PHQ", "kind": "askar", "order": 6, "colour": "#3cb554",
     "active": true, "lastOut": "2026-09-20"}
  ],
  "units": [
    {"id": "S30P", "label": "S30 Pro", "name": "Seestar S30 Pro", "kind": "seestar", "short": "S30P",
     "scopeIds": ["S30P"], "scopes": ["Seestar S30 Pro"], "colour": "#eda100",
     "onScope": "Seestar S30 Pro", "onScopeId": "S30P", "onScopeCurrent": true,
     "active": true, "lastOut": "2026-10-05",
     "current": [
       {"tid": "M31", "target": "Andromeda Galaxy (M 31)", "codes": ["M 31", "NGC 224"],
        "camera": "Seestar S30 Pro", "scopeId": "S30P", "state": "capturing", "stateWord": "Still capturing",
        "hours": 0.52, "frames": 31, "nights": 2, "firstNight": "2026-10-01", "lastNight": "2026-10-03",
        "readySince": null, "reason": "still capturing · kept open by hand",
        "nextAction": "Still capturing · kept open by hand", "calMissing": false, "mosaic": false},
       {"tid": "M42", "target": "Orion Nebula (M 42)", "codes": ["M 42", "NGC 1976"],
        "camera": "Seestar S30 Pro", "scopeId": "S30P", "state": "ready_to_process", "stateWord": "Ready to process",
        "hours": 0.67, "frames": 40, "nights": 1, "firstNight": "2026-09-15", "lastNight": "2026-09-15",
        "readySince": "2026-09-30", "reason": "ready since Wed 30 Sep · 40 min on the S30 Pro",
        "nextAction": "Next step: collect the lights (1 night, 40 frames)", "calMissing": false, "mosaic": false}
     ],
     "moreReady": 1, "moreReadyHours": 1.7,
     "strip": [{"night": "2026-09-12", "hours": 1.67}, {"night": "2026-09-15", "hours": 0.67},
               {"night": "2026-10-01", "hours": 0.27}, {"night": "2026-10-03", "hours": 0.25},
               {"night": "2026-10-05", "hours": 0.08}],
     "latestDone": null},
    {"id": "S50", "label": "S50", "name": "Seestar S50", "kind": "seestar", "short": "S50",
     "scopeIds": ["S50"], "scopes": ["Seestar S50"], "colour": "#0a0a0a",
     "onScope": "Seestar S50", "onScopeId": "S50", "onScopeCurrent": false,
     "active": false, "lastOut": "2026-08-20", "current": [], "moreReady": 1, "moreReadyHours": 0.7,
     "strip": [], "latestDone": null},
    {"id": "S50P", "label": "S50 Pro", "name": "Seestar S50 Pro", "kind": "seestar", "short": "S50P",
     "scopeIds": ["S50P"], "scopes": ["Seestar S50 Pro"], "colour": null,
     "onScope": "Seestar S50 Pro", "onScopeId": "S50P", "onScopeCurrent": true,
     "active": true, "lastOut": "2026-10-04",
     "current": [{"tid": "NGC7023", "target": "Iris Nebula (NGC 7023)", "state": "capturing",
                  "nextAction": "Still capturing · ready from Mon 19 Oct", "...": "the summary's other keys"}],
     "moreReady": 0, "moreReadyHours": 0.0, "strip": [{"night": "2026-10-04", "hours": 1.0}],
     "latestDone": {"tid": "M64", "target": "Black Eye Galaxy (M 64)", "codes": ["M 64", "NGC 4826"],
                    "camera": "Seestar S50 Pro", "scopeId": "S50P", "finalDate": "2026-10-06"}},
    {"id": "ZWO", "label": "ZWO", "name": "ZWO ASI585MC Air", "kind": "askar", "short": "ZWO",
     "scopeIds": ["FRA400", "107PHQ"], "scopes": ["Askar FRA400", "Askar 107PHQ"], "colour": "#e05a5a",
     "onScope": "Askar FRA400", "onScopeId": "FRA400", "onScopeCurrent": true,
     "active": true, "lastOut": "2026-10-02",
     "current": [
       {"tid": "NGC7380", "target": "Wizard Nebula (NGC 7380)", "codes": ["NGC 7380", "Sh2-142"],
        "camera": "Askar FRA400", "scopeId": "FRA400", "state": "capturing", "stateWord": "Still capturing",
        "hours": 0.67, "frames": 4, "nights": 2, "firstNight": "2026-09-30", "lastNight": "2026-10-02",
        "readySince": null, "reason": "still capturing · ready from Sat 17 Oct",
        "nextAction": "Still capturing · ready from Sat 17 Oct", "calMissing": false, "mosaic": false},
       {"tid": "M81", "target": "Bode's Galaxy (M 81)", "codes": ["M 81", "NGC 3031"],
        "camera": "Askar 107PHQ", "scopeId": "107PHQ", "state": "ready_to_process", "stateWord": "Ready to process",
        "hours": 0.67, "frames": 4, "nights": 1, "firstNight": "2026-09-20", "lastNight": "2026-09-20",
        "readySince": "2026-10-05", "reason": "ready since Mon 5 Oct · 40 min on the 107PHQ",
        "nextAction": "Darks or flats missing: flats", "calMissing": true, "mosaic": false}
     ],
     "moreReady": 2, "moreReadyHours": 1.3,
     "strip": [{"night": "2026-09-20", "hours": 0.67}, {"night": "2026-09-30", "hours": 0.33},
               {"night": "2026-10-02", "hours": 0.33}],
     "latestDone": null}
  ],
  "thisMonth": {
    "month": "2026-10", "movedForward": 1, "finished": 1,
    "items": [
      {"tid": "M64", "target": "Black Eye Galaxy (M 64)", "camera": "Seestar S50 Pro", "scopeId": "S50P",
       "state": "done", "stateWord": "Done", "nextAction": "Done · final of Tue 6 Oct",
       "what": "final", "date": "2026-10-06", "...": "the summary's other keys"},
      {"tid": "M81", "target": "Bode's Galaxy (M 81)", "camera": "Askar 107PHQ", "scopeId": "107PHQ",
       "state": "ready_to_process", "stateWord": "Ready to process", "nextAction": "Darks or flats missing: flats",
       "what": "ready", "date": "2026-10-05"}
    ]
  },
  "pendingImport": {"files": 5, "targets": 1, "camera": "ASIAir", "targetNames": ["Wizard Nebula (NGC 7380)"],
                    "scope": "Askar FRA400", "...": "the 1.7.5 fields unchanged"},
  "targets": [{"id": "M81", "programmes": [{"camera": "Askar 107PHQ", "status": "ready_to_process",
                "scopeId": "107PHQ", "codes": ["M 81", "NGC 3031"], "stateWord": "Ready to process",
                "nextAction": "Darks or flats missing: flats", "calMissing": true,
                "...": "every 1.7.x and 1.8.0 programme field unchanged"}]}]
}
```

After a quiet spell (the same fixture with the Askar nights in July and the S50 Pro out again on 7 Oct):
the ZWO unit reads `"onScope": "Askar FRA400", "onScopeCurrent": false, "active": false,
"lastOut": "2026-08-02", "current": [], "strip": []` ("last on the FRA400", in the Resting row), and the
S50 Pro's `latestDone` is null because its night out of 7 Oct came after the final of 6 Oct.

## 10. Where it lives

- `astro-import.py`: `OBS_STATE_WORDS`, `_obs_next_action`, `_obs_dataset_summary`, `_obs_unit`,
  `_obs_units` (just before `observatory_from`); the window, `unit_rows`, `scopes[].active/lastOut`,
  `thisMonth`, `recordsUpTo`, `activeWindow` inside `observatory_from`; `save_scan_summary(scope=)` and
  `read_scan_summary`.
- `test_v2.py`: chain P2 (15 checks), between chains HN and AA. All 15 fail against the 1.8.0 engine.
