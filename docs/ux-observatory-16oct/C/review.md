# Observatory review C: meaning and hierarchy

For Brett. Plain words, ranked. The mockup is `mock-C.html` (rendered with your sample data as `mock-C.rendered.html`), screenshots `C-desk.png` and `C-phone.png` (plus `-2`/`-3` for the lower parts of the page).

## 1. What is wrong with the page today, in order of harm

1. **Bare numbers.** "292.8 h · 16,414 lights" in the corner, "20.4 9,494 32" on the equipment cards, "101.7 / 35 / 4,956" in the Targets table. You have to remember what each column was. Every number should carry its word.
2. **Zero and unknown look the same.** Milky Way Core shows 0.0 h beside 2,150 frames. The frames are real; the exposure was never recorded. Showing 0.0 tells you that project is empty. It is not.
3. **One badge hides four states.** Andromeda is on four scopes in four different states (capturing, to process, in progress twice). The Targets row says "Still capturing", the Pipeline splits it into four cards in four columns, and nothing joins them up. The column is honestly labelled "state (the scope furthest behind)", but that is a rule you have to read, not a picture you can see.
4. **Three facts squeezed into one word.** "In progress" mixes *is it still being shot*, *has a master been made* and *are the darks and flats there*. The warning that matters most ("the master in the shared Askar folder may belong to the other Askar") is grey small print on a card.
5. **History before decisions.** Eighteen session cards come first; the processing queue is below them; the totals are below that. The page tells you what happened before it tells you what to do.
6. **Warnings you cannot act on.** "2 things to know: 2 target names the contract doesn't know (run --targets-draft...)" is a sentence, not a job. It also under-sells: 491 rows are not counted (184 unknown names, 2 no scope, 305 duplicates), and the 305 duplicates are *correct*, which the banner does not say.
7. **Tiny test snaps sit in the queue** next to real projects (Fireworks Galaxy 0.8 h on one night, and on your real data the 1-, 4- and 55-frame targets). The queue looks bigger and less finished than it is.
8. **Scopes in a different order on every panel**, colour the only thread. And the smallest two slices of "Integration by scope" have no label at all.
9. **Charts without numbers**: the Nights heatmap legend is "quiet ... big night", the Sky map's four purples are hard to tell apart, Coverage cannot say "not captured" vs "unknown".
10. **The page looks like a spreadsheet** because everything is the same weight, the same grey, the same size. There is no headline and nothing to look at.

## 2. ChatGPT's eight points: where I agree and where I do not

| # | Point | Verdict |
|---|---|---|
| 1 | Label every number | **Agree.** Done everywhere in the mock: hero, tiles, lists, legends, tooltips. |
| 2 | Unknown is not zero | **Agree, and go further.** "Integration unknown" is a *state* with its own note and hollow timeline dots, and it is also an item in Needs attention (2,150 frames, exposure unknown) so it is a job, not a footnote. |
| 3 | Mixed states shown honestly, 87 targets vs 147 datasets | **Agree.** The project header carries counted badges ("1 still capturing · 1 to process · 2 in progress") and opens to one lane per scope. "41 targets" and "50 datasets (one target on one scope)" sit side by side in the totals so the two numbers stop fighting. |
| 4 | Three indicators, uncertainty beside the badge | **Agree; this is the heart of it.** Capture, Processing and Calibration are three separate marks on every scope row, each with a glyph, a word and a small reason. Uncertainty is a `?` ring beside the word, and the shared-Askar note is a red callout at the top of the Andromeda card, not small print. |
| 5 | Decisions before history | **Agree, with one change.** Order is totals → needs attention → process next / finish → latest capture per scope → projects → charts. But the *very* first thing is "Last night", one line in the header, because "what did I capture lately" is the question you asked first. One session per scope, expandable to three. |
| 6 | More room: one scrollbar, compact nav, view selector on the phone, list alternative to the board | **Agree.** The mock has one page scroll and no inner scroll panes, a one-row nav, a labelled "View" selector under 700 px, and the queue is a list with "show all 23". The Pipeline board stays as a view; the list is the default. |
| 7 | Warnings into actions, separate from the correct duplicates | **Agree.** Each item is: a count, what it touches, why, and a button with a verb. The 305 duplicates are listed last, grey, "Nothing to do". |
| 8 | Chart meaning visible | **Agree; partly in the mock.** Every chart here has a numeric legend (hours, %, frames, nights per scope) and a table toggle. The Nights / Sky / Coverage fixes are specified in section 5, not drawn. |

Where I disagree with the way point 4 is usually read: the four-word pipeline status (Still capturing / To process / In progress / Done) should **not** be thrown away. It is the *next step*, and it is what the queue sorts by. Keep it, but call it what it is ("Keep capturing", "Process it", "Finish it", "Done") and show the three facts it was derived from beside it.

The second review's additions, and whether this direction answers them:
- Test snaps inflate the queue → **yes**: a *Sample* state (under 1.0 h on one night) kept out of the queue, counted in Needs attention with "mark as sample, or process anyway". The cutoff is a page setting; the engine should eventually store the flag.
- "Still capturing" is partly your own capture-state.json → **yes**: the Capture indicator says *Active* (inferred from dates: "quiet from 29 Oct if nothing new") or *Kept open by you* (from capture-state.json). The dataset does not yet say which, see section 7.
- Missing type / constellation → **yes**: "type not set · constellation not set" in italics, never a blank or "undefined".
- Thin bars unlabelled → **yes**: wide slices carry their label inside; thin ones get a number tick that the list below repeats (S50 Pro, Starfront, S50 are 4, 5, 6).
- One scope order everywhere → **yes**: one list (most hours first) drives the legend, the bar, the season strip, the latest-capture list, the project lanes and the chart stacks. The legend says so.
- Freshness line → **yes**: header says when it was worked out, how old the Mac's record is, and has a slot for "N files on the camera not yet imported (M targets)". The sample dataset cannot fill that slot, so it says "not reported by this record".

## 3. The proposal in one paragraph

Three colour systems, each meaning one thing, each explained once in the legend strip under the header. **Scope colours** (yours, from the contract) only ever mean the scope and only appear as a dot, a stripe or a fill. **Next-step colours** (cyan keep capturing, amber process it, violet finish it, green done, grey sample) only appear as a pill with a glyph and a word. **Marks** (a hollow ring for "nothing yet / not needed", a `?` ring for "uncertain") carry doubt. On top of that: a night-sky header with the last night as a headline, a warm paper page, totals with words, a Needs-attention list of jobs with counts, a queue, one latest session per scope, and project cards that open into a timeline lane per scope with the quiet-period band (the picture you liked) and the three indicators beside each lane.

## 4. The colours, and why they pass

Status set `#0891b2 #d97706 #6d28d9 #15803d` validated with the dataviz checker (light surface): all checks pass on adjacent pairs; on all-pairs the green/amber pair sits in the 6–8 band, which is allowed because every pill also carries a glyph and a word. Your scope set passes separation (worst pair S50 Pro ↔ S50, ΔE 9.8) but S50 grey fails the chroma floor and S30 Pro yellow / S50 Pro green are under 3:1 on a light surface, so scope colour never appears without a name beside it. There is no way to keep six fixed scope hues and have four status hues that never come near them (cyan is near 107PHQ blue, amber near S30 Pro yellow), so the rule is **shape and place, not hue alone**: a scope is always a round dot beside a scope name; a status is always a filled pill with a glyph and a verb.

## 5. What changes, view by view

**Header (every view)**: one-line nav; "View" selector under 700 px; freshness line with the "not yet imported" slot; "Last night" headline with one chip per scope; the Data-health count on its tab. The warning banner goes; the jobs move to Needs attention.

**Overview**: order totals → needs attention → process next + finish → latest capture per scope → projects → "where the hours went". Integration-by-scope bar with every slice labelled and a numeric legend. Season strip (nights per month by scope) replaces the bare KPI "130 nights".

**Targets → Projects**: same tappable list, but the state column becomes the counted badges ("1 still capturing · 2 in progress") and each row opens in place to the lane-per-scope card. Columns keep their words ("101.7 h", "35 nights"). "Integration unknown" where hours are 0 with frames. Sort and filter chips stay. Type and constellation fall back to "not set".

**Pipeline → Process queue**: list first (target, scope, integration, quiet-for, calibration, Next), board as the alternative. Samples kept out and counted. "Finish" and "Keep capturing" are separate lists, not columns of the same board.

**Coverage**: three cell states, each a different mark: a filled chip with hours = captured; a hollow chip with "frames, hours unknown" = unknown; a faint dash = not captured on that scope; and a crossed cell for "not planned on this scope" once the dataset can say so. Keep the gaps-only filter.

**Nights**: legend in numbers (0 / 1–2 h / 2–4 h / 4–6 h / 6 h+), a per-scope toggle that recolours by the selected scope only, and the five summary numbers kept as labelled tiles.

**Sky**: the four purples become the four next-step colours with glyphs in the legend and a numeric dot-size key (1 h / 10 h / 50 h stays); "done" recedes to grey. Labels on the ten biggest dots only.

**Footprints**: "Fields are drawn 2.2× for visibility; the target panel is to scale" moves above the map, not below. Scope colours already right. The target list under it becomes the same searchable list as Projects.

**Equipment**: the three numbers get words ("20.4 h · 9,494 frames · 32 nights"); cards in the fixed scope order; the monthly chart gets the numeric legend; the exposure-length chart keeps its labels.

**Data health**: the reconciliation table stays; the warnings become the same Needs-attention items as on the Overview, with the same buttons, and "305 duplicates counted once" is marked OK, not a warning.

## 6. Indicator vocabulary

One row per dataset (a target on one scope). Each indicator has a glyph in a small disc, the word, and a short reason underneath.

| Indicator | State | Glyph · colour | Words beside it |
|---|---|---|---|
| Capture | Active | ◔ filled cyan | "Active · last session 1 night ago · quiet from 29 Oct if nothing new" |
| Capture | Kept open by you | ◔ filled cyan | "Kept open by you · capture-state.json says open · last session N nights ago" |
| Capture | Quiet | ○ hollow grey | "Quiet · no frames for 96 nights" |
| Capture | Marked complete *(needs data)* | ✓ hollow grey | "Complete · you marked it done on 12 Jul" |
| Processing | Not started | ○ hollow grey | "Not started · no master, no final" |
| Processing | Master saved | ◑ filled violet | "Master saved · 1 master in the folder" |
| Processing | Final found | ● filled green | "Final found · 1 finished picture" |
| Processing | uncertain (any state) | add `?` ring | "… · which Askar?" / "unless the folder's master is this scope's" |
| Calibration | Complete | ✓ filled green | "Complete · darks and flats linked" |
| Calibration | Missing flats / darks and flats | △ filled amber | "Missing flats · none linked to these lights" |
| Calibration | Not needed | – hollow grey | "Not needed · Seestar handles its own" |
| Calibration | Unknown *(needs data)* | `?` ring | "Unknown · no calibration record for this scope" |
| Next step | Keep capturing / Process it / Finish it / Done / Sample | ◔ cyan / ▶ amber / ◑ violet / ✓ green / ○ grey pill | the verb, nothing else |
| Integration | Known / Unknown | bold number / amber "Integration unknown" | "60.0 h" / "2,150 frames, exposure not recorded" |

On a timeline lane: a dot is a session, bigger is more hours, hollow when hours are unknown; the shaded band is the last 14 nights; the disc after the band is the next step.

## 7. Data the page would need that the dataset does not carry

- A per-dataset **capture state source**: `captureState: "open" | "complete" | null` and whether it came from capture-state.json or was inferred from dates. Today the mock has to guess from the evidence text.
- A per-dataset **sample flag** (`sample: true`) written by the engine, so "mark as sample" sticks. The mock uses a page-side cutoff (under 1.0 h on one night).
- A **calibration "not needed" / "unknown"** distinction: today `applies:false` covers both "Seestar, none needed" and "we don't know".
- A **freshness block**: `pendingImport: {files, targets, failedEject}` for "N files on the camera not yet imported".
- **Structured warnings**: `{kind, count, frames, action}` instead of sentences, so counts never have to be parsed out of prose.
- The **shared-folder uncertainty as a field** (`masterOwnerUncertain: true` with the sibling scope), rather than a phrase inside `evidence`.
- For Coverage: a **planned-on-scope** list per target, to tell "not captured" from "not planned".
- Optional: the per-scope display order as a contract field, so the page and the panel agree on it without recomputing.

A note on the phone screenshots: Chromium headless lays out at a 500 px minimum even at `--window-size=390`, so the brief's phone shots (and a naive shot of this mock) show the page cropped. `C-phone.png` here was taken with the document forced to 390 px; the live page itself is fine on a real phone.
