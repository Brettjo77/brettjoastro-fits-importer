# Observatory round 3 · lens: is every word and number true, clear and useful?

Reviewed: `A/mock-A.html` and `C/mock-C.html` rendered with `dataset.json` (the sample, 41 targets / 50 datasets), their
desktop PNGs, and both mocks re-rendered with `stress-dataset.json` (87 targets / 147 datasets, built to the engine's real
`observatory/1` shape from `astro-import.py observatory_from()`, not the sample generator's). Every number below was
checked by script against the dataset and, where the rule lives in the engine, against the engine.

Severity: **Critical** = a wrong or misleading statement Brett would act on · **High** = true in the sample, wrong on real
data · **Medium** = unclear or inconsistent · **Low** = polish.

## The five things that matter most

1. **The "Sample" cutoff files real projects as test snaps, in both mocks.** A's rule (under 1.5 h, any status but
   capturing/done) removes 6 of the sample's 24 waiting datasets, five of them two-night Seestar projects (Sadr Region
   504 frames, Iris 396, Heart on the S50 432). On the stress data it removes 17 of 61, including Thor's Helmet on the
   S30 Pro, which has a **master saved** (A badges an in-progress dataset "Sample"), and the Double Cluster (84 × 30 s
   on the FRA400: a bright cluster, finished at that length by most people). C's rule (under 1.0 h **and** one night) is
   safer but still drops the Double Cluster. Two finished pictures in Brett's own sample, M 13 at 0.4 h and M 57 at
   0.6 h, prove that short is not the same as sample. Hours cannot decide this: a Seestar gives 0.9 h from 324 frames.
   **Fix:** no page-side cutoff. "Sample" is a word Brett gives a dataset (capture-state.json already carries open /
   complete; add `sample`). Until the engine stores it, the only honest automatic rule is "≤ 10 frames on one night, more
   than 90 nights ago, no master, no final", and the list must say the rule beside it ("kept out because: 1 frame").

2. **The freshness line says things the record cannot know.** A prints a green tick "nothing known to be waiting on a
   camera" whenever `D.pending` is absent, which it always is: on Brett's real archive 3,559 files on 29 targets are
   waiting and the eject failed. C is honest ("not reported by this record") but buries it. C's header "worked out …
   from 11,206 ledger rows" reads `D.snapshotRows`, which in the engine is **the Mac's snapshot only**; its own footer says
   79,972 (see C-stress.png, top right vs bottom). Both mocks regex the prose `sourceNote` for the Mac's date when
   `D.inputs.snapshot.at / ageHours` already exist as fields. **Fix:** "Record built 16 Oct 2026, 09:12 · the Mac's copy is
   3 days old · frames still on a camera: not known to this page" until the engine adds `pendingImport`; never a tick.

3. **"Still capturing" hides two different facts, and the column headings then lie.** The engine has three sources of
   capture state: the 14-night rule, `open` by hand, `complete` by hand (evidence strings "kept open by hand
   (capture-state.json)" / "marked complete by hand; nothing started"; `readyOn` is null for open-by-hand). A does not
   distinguish at all: the kept-open Flaming Star widefield (last frames 44 nights ago) sits in a column headed "frames
   within the last 14 nights", with its last dot outside the shaded band and a cyan "still capturing" disc after it. The
   marked-complete Witch Head (12 nights ago) sits under "no new frames for 14 nights". C's lane caption "a last dot inside
   the band = still capturing, outside = quiet" is contradicted on the same card by both datasets, and C's "Kept open by
   you" works only because it regexes evidence for "capture-state.json", then prints that file name to Brett. Neither mock
   ever says "you marked this complete". **Fix:** four capture words (Active · Open, kept by you · Closed by you · Quiet),
   taken from a field, and headings that describe the list, not the rule ("Ready to process", not "no new frames
   for 14 nights").

4. **The data-quality numbers don't add up and don't survive real data.** 31,284 rows read − 16,414 lights counted =
   14,870 rows unaccounted for; the page explains 491 (184 + 2 + 305), the brief's "191" explains even less. The rest are
   darks, flats, stacks and other non-light rows that nobody says exist. Both mocks' "305 duplicates · fine, nothing to
   do" line comes from a health item **the engine never emits** (it lives only in the sample generator); the "184 frames"
   exists only in the sample's wording (the engine's warning carries no frame count, so C prints a big "?"); the engine's
   real "no scope" warning ("5 frame(s) have no scope recorded (older ASIAir rows)…") misses C's regex and renders as
   "Warning from the project layer … [Look]", four times over; A gives the Mac's-record-age warning a "See the rows"
   button. **Fix:** structured counts from the engine (see data-needs.md) and one subtraction on the page that adds up:
   rows read → not light frames → not counted, by reason → counted once instead of twice → light frames counted.

5. **"Last night" is right in the sample and wrong the moment the night gets busy.** C's headline counts sessions as
   scopes: `plural(ss.length,"scope")` gives "on 7 scopes" for 7 sessions on 5 scopes (C-stress.png). A's rounded parts
   don't sum to its rounded total: 1.8 h + 2.1 h shown under "3.8 h" (1.75 + 2.05); on the stress night the parts sum to
   11.5 against a headline 11.4. A and C also disagree on the same session (A "2.1 h", C "2.0 h" for 2.05 h: `Math.round`
   vs `toFixed`). Neither says what "16 Oct" means: the engine's night is noon-to-noon, so the night labelled 16 Oct is the
   evening of Thursday 15 Oct, and the record was built at 09:12 on the 16th. "Friday" is the morning after. **Fix:**
   "Night of Thu 15 → Fri 16 Oct"; one rounding function for the whole page; show the total as the sum of the rounded
   parts or mark it "≈"; count scopes with a Set.

## All findings, ranked

| # | Where | What is wrong | Why it matters | Fix | Severity |
|---|---|---|---|---|---|
| 1 | A "What to do next" samples line; A Targets pills; C "Needs attention" samples; C queue "kept out" | Hour cutoff mis-files real projects (top five, 1). A also badges an in-progress dataset "Sample" (Thor's Helmet S30 Pro, master saved, 1.47 h) and prints "under 1.5 h · Thor's Helmet · S30 Pro 1.5 h" (1.47 rounds up). | The queue is the page's main decision; a wrong "sample" hides work Brett has started. | Engine flag; no hour rule; never sample a dataset with a master or final; say the reason per item. | Critical |
| 2 | A header freshness | "✓ nothing known to be waiting on a camera" is a claim, not a fact; false on the real archive today. | Brett reads "nothing waiting" and leaves frames on the camera. | "frames still on a camera: not reported" in neutral grey; green only when `pendingImport.files === 0`. | Critical |
| 3 | C header | "from 11,206 ledger rows" uses `D.snapshotRows` (Mac snapshot only). Footer says 79,972. | Two different "how much was read" numbers on one page. | Use `D.ledgerMeta.rows`; or say "this PC's ledger + the Mac's copy (11,206 rows, 3 days old)". | High |
| 4 | A & C capture state | Kept-open / marked-complete datasets contradict the headings, the shaded band and the lane caption (top five, 3). | The only human-set facts in the system are shown as if the machine guessed them. | Field `captureState {value, source}`; four words; captions that match. | Critical |
| 5 | C lanes caption | "a last dot inside it = still capturing, outside = quiet" is stated as a rule but the engine's rule is `days_since <= 14` (15 nights inclusive) plus the hand overrides. | Brett will test the picture against the rule and find it false. | "shaded: the last 14 nights. A dataset is usually still capturing while its last session is in here; you can override that." | Medium |
| 6 | A & C data warnings | Duplicate line depends on a health item the engine never emits; "184 frames" only in sample text; real "no scope" string unparsed → "Warning from the project layer / Look"; Mac-age warning gets "See the rows". | On real data the attention block degrades to raw sentences and wrong buttons. | Structured `notCounted` counts; one button per kind, derived from a `kind` field, never from regex on prose. | High |
| 7 | Both, reconciliation | 31,284 − 16,414 = 14,870, page explains 491. `ok: true` on a check that does not reconcile. | A "health" block that cannot do its own arithmetic is not trusted. | Engine: count non-light rows separately; page: show the subtraction. | High |
| 8 | C "Last night" headline | "on 7 scopes" for 5 scopes. | Plain wrong number in the biggest type on the page. | `new Set(ss.map(s=>s.camera)).size`. | Critical |
| 9 | A "Last night out" | 1.8 + 2.1 ≠ 3.8; A's 2.1 vs C's 2.0 for the same session. | Brett adds it up. | One `fmtH` (round-half-up, 1 dp) everywhere; total = sum of displayed parts. | High |
| 10 | Both "Last night" date | Night "16 Oct" is the evening of the 15th (noon-to-noon); record built 09:12 on the 16th; "Friday" names the morning. | "Last night" + "16 Oct 2026, Friday" reads as the coming Friday night. | "Night of Thu 15 → Fri 16 Oct". Carry `evening` dates or state the rule once in the footer. | High |
| 11 | A 30-night strip "latest:" | When a scope shot three objects in a night A names one, chosen by array order ("latest: Stephan's Quintet" while M 33 and the Tadpoles were also shot). | Says "latest" about a tie it did not break. | "latest night: 3 objects" and list them in the tooltip; or pick the longest and say "longest". | Medium |
| 12 | Scope order, both | The engine sorts `D.scopes` **alphabetically** (107PHQ before FRA400), so A's "contract order" is really alphabetical (see A-stress.png header). C sorts by hours, so S50 Pro (8.5 h) and Starfront (7.9 h) will swap places next month and the legend's "always in this order" becomes untrue. | One fixed order was the brief's explicit ask. | Engine emits `D.scopes[].order` from the contract; page sorts by it. | High |
| 13 | C calibration "Not needed · Seestar handles its own"; C "Latest capture" "Seestar: its own calibration"; A silent | Engine `applies:false` means "not tracked for this scope" (comment: "the Seestar calibrates itself"). A Seestar takes its own darks; it takes no flats. "Not needed" is a claim about Brett's workflow, not the engine's knowledge, and the label is applied by `!cal`, so any future non-Seestar scope without a record would also be "Seestar". | Wrong word becomes wrong confidence. | "Not tracked · the Seestar calibrates in the camera". Field `calibration.mode`. | Medium |
| 14 | C "15 datasets have no calibration linked" | Counts include 2 finished pictures (Wizard FRA400, Whirlpool) and 4 still-capturing datasets whose flats are usually shot at the end of the run. "Link darks and flats" on a done project is a job that does not exist. | Inflates the to-do list by 40 %. | Count only waiting / in-progress datasets; show capturing ones as "no flats yet". | Medium |
| 15 | Sample data vs page, calibration | Session rows carry `cal` counts (Horsehead FRA400: 30 darks that night) while the programme says "missing darks and flats"; C shows both on one page (header chip "30 darks", lane "Missing darks and flats"). The sample generator made them independently; the engine sums one into the other. | A page must never show two calibration facts from two sources without saying which wins. | Derive one from the other on the page; show `nights_with` ("flats on 3 of 5 nights"), which the engine already emits. | Medium |
| 16 | "linked" (both) | "no darks or flats linked to its lights" is importer jargon (hard-linked into the Day folder). | Brett is not a developer. | "no darks or flats filed with these lights". | Low |
| 17 | Shared-Askar note (both) | The page says it "cannot tell which scope made" the master while printing its name: `Andromeda Galaxy_master_FRA400.xisf`. | Reads as the machine not reading its own evidence. | Engine: when the master name carries a scope id, drop the attribution note. Page: "one master, not named for either Askar" only when true. | Medium |
| 18 | "ready from" dates (both) | Engine sets `ready_on = last + 15` (first night after 14 quiet ones); sample used +14, so the sample shows 29 Oct where the engine will say 30 Oct. A's "ready 20 Oct" never says ready for what; a kept-open dataset has no date and A prints nothing. | A date without a verb. | "waits until 30 Oct unless you add frames" / "open until you close it". | Medium |
| 19 | Tiny datasets shown as 0.0 h (both) | Polaris check, 4 × 20 s = 80 s, prints "0.0 h" in A's samples line and C's attention item. The zero/unknown rule has a third case. | The page just promised zero ≠ unknown; now 80 s = 0. | Below 0.1 h show minutes ("1 min", "9 min"). | Medium |
| 20 | C "Integration by scope" legend | Rounded shares sum to 101 % (52 + 35 + 7 + 3 + 3 + 1). | Brett adds it up. | Largest-remainder rounding, or one decimal. | Low |
| 21 | C "Integration by scope" bar | Label "Starfront S50 Pro · 185.7 h" spills over the next segment (C-stress.png); threshold 110 px ignores name length. | Unreadable at exactly the moment it matters. | Measure text; fall back to the numbered tick. | Medium |
| 22 | C "Where the hours went" | Names longer than ~26 chars are cut off the left edge ("oular (M 13) and NGC 6207 widefield"). A truncates with "…" but drops the catalogue code. | Brett's real names run to 45+ chars. | Widen gutter from `max name width`; or two-line labels; keep the code, shorten the prose part. | High |
| 23 | A "Projects that moved lately" | 54 cards on the stress data, each with a timeline: the "wall" the brief complained about, in colour. | History before decisions again. | Cap at 9 with "show all"; or one row per project. | Medium |
| 24 | C "Finish what you started" | Uncapped (23 rows on stress) while "Process next" caps at 6. | Inconsistent, and the finish list is the longer one in practice. | Same cap and "show all N". | Low |
| 25 | A project card badges | "In progress ×2 · To process · Still capturing" in scope-array order; Great Globular shows "Done · Sample · To process · In progress". | "×2" reads as maths; order carries no meaning. | C's form: "1 still capturing · 1 to process · 2 in progress", always in pipeline order. | Medium |
| 26 | A "Samples, kept out of the queue" | One 17-item run-on sentence on real data. | Unreadable. | A list, each with its frame count and the reason. | Medium |
| 27 | Jargon (both) | "contract", "ledger rows", "project layer", "dataset", "programme" (schema), "capture-state.json", "linked", "integration" without a gloss, "row(s)", "name(s)", "frame(s)". | Brett's own words are target, scope, night, frames, hours, master, final. | See wording.md. | Medium |
| 28 | A 12-month chart | Month label "Jan 26" (reads as the 26th); "+ 215 fr, h?" is a code. | Mislabelled axis. | "Jan 2026"; "+215 frames, hours unknown". | Low |
| 29 | A Targets timeline | "‹35", "‹5" earlier-session markers with no key. | Looks like a glitch. | "35 earlier" or a key line. | Low |
| 30 | Eyebrow (both) | "LIVE FROM THE IMPORTER" above "Built 16 Oct 2026, 09:12". | It is a record, not live. | "From the importer's record". | Low |
| 31 | C tiles | "1 as mosaics", "1 samples"; "cameras in the ledgers". | Grammar and jargon. | `plural()`; "scopes". | Low |
| 32 | C "290 GB on the archive" | Bytes/1e9. Explorer on the PC shows the same folder as 270 GB (GiB). | Numbers that don't match the PC. | Use 2^30 and say "GB as Windows shows it", or drop it. | Low |
| 33 | C "LP dual-band" | The page expands the filter name with knowledge the data does not carry. | If a Seestar is ever run with its UV/IR cut, "LP dual-band" is wrong. | Show the recorded name; gloss in a tooltip. | Low |
| 34 | C "1 night ago" vs "the night before last" | Both phrases for the same gap on the same page (table vs lane). | Inconsistent. | One phrase: "1 night ago". | Low |
| 35 | Hero wording | A "hours of light frames"; C "hours of integration". | Two names for one number. | "hours of integration" (Brett's word) with the gloss once: "light-frame exposure, added up". | Low |
| 36 | "Why:" lines (C) | Raw evidence strings joined with " · ", including "(96 nights)" twice and the attribution note twice. | Machine prose. | Keep as a tooltip; the three indicators already say it. | Low |
| 37 | Status set | A verbs "Decide" (sample) and "Finished" (done) vs C "Done"; headings "Process these / Finish these / Still capturing" mix verb and state. | One vocabulary, please. | wording.md, final table. | Medium |

## Stress test: what broke (stress-dataset.json → A-stress.png, C-stress.png, A-targets-stress.png)

Built with `stress_gen.py` (87 targets, 147 datasets, 505 sessions, 998 h, nights since Nov 2023; a target with no type,
constellation or coordinates; the Seestar S50 silent for 412 nights; 7 sessions on 5 scopes last night with the 107PHQ on
three objects; two mosaics; Running Man done on the FRA400 and capturing on the S30 Pro; one kept-open and one
marked-complete dataset; a 1-frame, a 4-frame and a 55-frame snap; the Double Cluster at 0.7 h; unknown exposure on an
Askar; the engine's real warning strings, `inputs` object, Seestar `calibration: {applies:false}` with no `missing` key,
Mac-only `snapshotRows`). Re-render with `python3 render_stress.py ../../A/mock-A.html A-stress.html`; shots with
`node shoot_stress.mjs`. No script errors in either mock.

- **C:** "11.4 h in 1,122 frames on 7 scopes" (5 scopes). Header "from 11,206 ledger rows", footer "79,972". Attention
  block: "? frames not counted" then four "Warning from the project layer … [Look]" cards. "Starfront S50 Pro · 185.7 h"
  label overflows its bar. "Where the hours went" names cut off at the left. "Polaris alignment check (0.0 h)". "Finish"
  list 23 rows uncapped. Scope legend order changed from the sample's (hours-based).
- **A:** scope order is now 107PHQ, FRA400, … (engine sorts alphabetically). Still "✓ nothing known to be waiting".
  Mac-age warning as "To check … [See the rows]". Parts of last night sum to 11.5 under "11.4 h". 17-item samples
  sentence including "under 1.5 h · Thor's Helmet · S30 Pro 1.5 h" and an in-progress dataset. 54 project cards.
  Kept-open Flaming Star widefield under "frames within the last 14 nights". "Polaris alignment check · 0.0 h".
- **Both:** Double Cluster (real, bright, 84 frames) filed as a sample; neither says "marked complete by you" for Witch
  Head; the 48-character names wrap fine in lists but break both bar charts; the no-type target renders "type not recorded"
  (A) / "type not set · constellation not set" (C): both fine.

## Things that are right and should be kept

C's three-indicator row with a reason under each word; C's counted badges; both mocks' hatched / hollow "hours unknown";
C's "Integration unknown, not zero" note; A's labelled thin bars; both mocks' quiet-scope line ("nothing in 30 nights ·
last out 25 Jul 2026, 83 nights ago", every number checked); C's "quiet for N nights" column (all 96 / 70 / 36 / 69 /
70 / 84 verified); C's "15 datasets · 8 flats only · 7 darks and flats · 2,684 frames" (verified to the frame, but see #14);
A's 30-night per-scope hours (7.1 / 13.8 / 1.7 / 2.0 h verified) and "20 projects in the last 60 nights" (verified).
