# Phase 2 ("scope first"): the record fields the page, the panel and the phone agree on

Brett, 29 Oct 2026: "I need the new design in there now." Phase 2 of `Observatory_UX_Plan.md` (§7: three layers, scope cards first) plus the two decisions taken with phase 1 (Dashboard → Ledger with Space in Data checks; the own-tab `/observatory`). Pictures, goals, park and the "This month" list behind the line are phase 3.

Three agents build it at once, on branch `claude/observatory-ux-v2`, so the field names below are fixed up front. All additive to `observatory/1`; nothing existing is removed or renamed (the iOS app reads this record).

## Engine (astro-import.py) adds to observatory.json

- `rules.activeWindowNights` already exists (30). A scope is **active** when it has a session within the last `activeWindowNights` nights of `asOfNight`.
- `scopes[]` gain `active` (bool), `lastOut` (ISO night or null).
- `units[]`: the cards' units, in the fixed card order. One unit per Seestar scope; ONE unit for the ZWO camera covering both Askars.
  ```
  {"id": "ZWO", "label": "ZWO", "name": "ZWO ASI585MC Air", "kind": "askar",
   "scopeIds": ["FRA400", "107PHQ"], "scopes": ["Askar FRA400", "Askar 107PHQ"],
   "colour": "<the colour of onScope, else the first scope's>", "short": "ZWO",
   "onScope": "Askar FRA400" | null, "onScopeId": "FRA400" | null,   # the Askar of the newest ASIAir session; for a Seestar unit: its own scope
   "onScopeCurrent": true | false,                                   # true when that session is inside the active window ("on the FRA400"), else "last on the FRA400"
   "active": true | false, "lastOut": "2026-10-23" | null,
   "current": [ <dataset summary>, ... ],      # datasets of this unit with frames inside the active window, newest first, at most 2
   "moreReady": 3, "moreReadyHours": 12.4,     # other ready_to_process datasets on this unit (not in current)
   "strip": [{"night": "2026-10-23", "hours": 4.1}, ...],   # one entry per night with frames, inside the active window, oldest first
   "latestDone": {"tid": ..., "target": ..., "camera": ..., "finalDate": ...} | null   # the most recent done dataset whose finalDate is after this unit's previous night out, else null
  }
  ```
  Card order: `scopeOrder` with the two Askars collapsed into the ZWO unit at the position of the first of them. (Today's contract order gives: ZWO, then the Seestars in contract order.) Units with `active: false` are the Resting row; the page keeps them in `units[]` and folds them.
- `<dataset summary>` (also used in `thisMonth.items` and already mostly on `programmes[]`): `{tid, target, codes[], camera, scopeId, state, stateWord, hours, frames, nights, firstNight, lastNight, readySince, reason, nextAction, calMissing, mosaic}`.
- `programmes[]` gain `nextAction` (plain words, the first unfinished step) and `calMissing` (bool):
  - calibration missing (ASIAir, `calibration.missing` non-empty) → "Darks or flats missing: {what}" first;
  - capturing → "Still capturing · ready from Sat 31 Oct";
  - ready_to_process → "Next step: collect the lights ({n} nights, {frames} frames)";
  - in_progress → "Finish it · master in the folder";
  - done → "Done · final of Thu 9 Oct" (or "Done");
  - sample → "Sample · {hours}".
- `thisMonth`: `{"month": "2026-10", "movedForward": n, "finished": n, "items": [{...dataset summary, "what": "ready" | "final", "date": "2026-10-16"}]}` — `ready` = `readySince` inside this calendar month; `final` = `finalDate` inside it. (Masters have no date yet; phase 3.)
- `recordsUpTo`: the newest night with frames (ISO), for the status line's "records up to Fri 16 Oct".
- `pendingImport.scope`: `save_scan_summary(..., scope=)` gains a scope name (the ASIAir dest plan's scope for the first target, from the panel); `read_scan_summary` returns it (missing → null).

## Panel (astro-app.py) adds when it serves the record (`/observatory`, `/observatory?json=1`)

- `status`: the serving computer's live safety facts, injected like `pendingImport`:
  ```
  {"checked": true | false, "reason": "<why not, when false>",
   "onlyHere": <frames only on this computer, from status_summary>, "machine": "Mac" | "PC",
   "pendingFiles": n, "pendingCamera": "ASIAir" | ..., "pendingSeenAt": iso | null,
   "servedAgeHours": <age of the record being served>, "publishedFrom": "PC" | null}
  ```
  The page derives the level: amber when `onlyHere > 0`, or `pendingFiles > 0`, or `servedAgeHours > 24`, or `checked` is false; else quiet.
- `space`: this computer's Space figures (what `--space` works out, as the Dashboard tab showed), so the page's Data checks can show them. Null when it can't be worked out.
- The Dashboard tab becomes **Ledger** (the SAFE verdicts, discards, events, Recent activity stay there; Space moves to the page's Data checks; camera storage goes, the header has it).
- `GET /observatory` opened in its own tab (not in the panel's frame) serves the full page; the cross-site refusal stays for `?json=1` only. The page shows its "← Importer" link when it is top-level.
- `pendingImport.scope` passed from the dest plan into `save_scan_summary`.

## Page (astro-observatory.html)

Three layers, as §7.1–7.4; everything reachable today stays behind **Explore**; §7.5 breakpoints with container queries; §7.6 states; the footer carries the build time (UK time) and the server dot. Cards read `units[]`; the status line reads `status` + `recordsUpTo`; the "This month" line reads `thisMonth`; Layer 2 reads `targets[].programmes[]` for the unit's scopes; Layer 3 reads the programme, its `sessions[]` and the other programmes of the target ("Also on disk"). "Open files" posts `archive-show` for the target and scope as today's cards do.
