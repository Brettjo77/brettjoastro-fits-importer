# Observatory round 3 ("history first"): build notes (19 Oct 2026)

Built to `scratchpad/ux3/SPEC-2.md` on a copy of `astro-observatory.html` (1.7.4), then copied over
`/home/user/brettjoastro-fits-importer/astro-observatory.html` (the only repo file changed; 290 KB, was 230 KB).
Rendered through the engine's `observatory_html()` with `build/dataset.json`: the real-size stress set
(87 targets / 505 sessions) recoloured to Brett's six scopes as `history/dataset-history.json` does, plus the
1.7.2 fields the page reads (`scopeOrder`, `generatedAtLocal`, `inputs.snapshot.at`, `notCounted`, `notices`,
per-session `calDetail` / `importedOn` / `archived`) and a `pendingImport` like Brett's 19 Oct one, with the new
`targetNames: ["Tadpoles Nebula"]` and `elsewhereMachine: "PC"`. Tooling beside it: `render.py`, `shot.sh`
(desktop, motion off via `data-motion="reduce"`), `shoot_phone.sh` (a 390 px iframe inside a 500 px window —
headless Chrome refuses a window under 500 px, which is why the brief's missing `A/shoot_phone.sh` needed a
"trick"), `errs.sh` (JS errors on load) and `probe.sh` (evaluate an expression in the loaded page).

## What was built (SPEC-2 section by section)

**§1 Overview order.** Recent nights → What each scope captured (+ What each scope shot in the same card) →
Projects that moved lately → Needs your attention → What to do next → Where the hours went. The old phone-only
"sofa order" special case is gone: one order everywhere.

**§2 Recent nights** (`renderRecent`, replaces `renderLastNight`; `OV.rn`). Rows = nights newest first
("Fri 16 → Sat 17 Oct", under it "11.5 h · 7 objects on 5 scopes"); columns = `SC` in the fixed order, head "dot ·
name · ›" (opens `openScope`) with "5 nights · 9.5 h · 3,455 frames"; an idle scope shrinks to a 108 px column
("nothing in 7 nights · last out 30 Aug"). A cell lists the scope's objects that night (biggest first) as buttons
(`objButton`): `nameEl` + a MOSAIC tag, "**576 frames** · 1.6 h", "10 s LP" / "300 s L-eXtreme · ✓ 30 darks · 25
flats" / "⚠ no darks or flats filed" (warm ink), "not all on the archive yet" when `archived < frames`, and a 3 px
hours bar in the scope colour (dashed when hours unknown). Empty cell in the newest frames row: "not out"; else a
faint dash. Top row eyebrow "Last night" / "Latest frames · 2 nights ago". Blank runs collapse: "The last 2 nights ·
Sat 17 → Mon 19 Oct · no frames on any scope" at the top, "Tue 6 → Thu 8 Oct · 2 nights · no frames on any scope"
inside. Only nights ≤ `asOfNight` are ever called empty; when the record is older than last night (by the
calendar, `lastNightIso()`), a thin row says "record built 19 Oct 2026, 03:38 · nights after it are not in this
list". Range: a week / 14 nights / 30 nights (`mem.ledgerRange`). The pending line (`#pendLine`) sits above the
rows when `pendingImport.files > 0`: "87 files still on the ASIAir, not yet imported · 1 target · Tadpoles Nebula ·
85 already backed up by the PC · seen 3 h ago · not in the rows below" with "Open the Panel to import" (posts
`{kind:"open-panel"}` through `ask()`; shown only inside the panel's frame). When the scan found nothing, a muted
line "nothing left to import on the ASIAir at the last scan · seen …"; when `pendingImport` is null, nothing (the
fact stays on Data checks). Phone: one column, a block per night, one 44 px line per object with the scope dot and
short name first; tablet (< 900): idle scopes become the footer line "Not out in these 7 nights: S50 (last out 30
Aug)".

**§3 What each scope captured** (`renderStrips` rewritten; `CHART`; `STRIPCARD` still points at the card so
`openScope` keeps its home). Eyebrow "Nights out · 19 Sep to 18 Oct 2026"; facts line "Out 20 of the last 30
nights, 13 of them with the moon under half lit · the FRA400 took 42% of the hours" (+ " · a column is a week /
month" at the longer ranges). Four tiles (24 px numbers): Nights out "20 of 30" with a strip of squares (one per
night, filled when any scope was out, the selected night ringed; a share bar instead at the bin ranges);
Integration captured "184.0 h" with the share bar by scope (+ "+ N frames, hours unknown"); Nights with the moon
under half lit "13 of 20 out" with a bar; Biggest night "24.7 h · Thu 8 → Fri 9 Oct · 4 scopes out". Moon row
(30 nights only): a disc per night from the illumination (synodic 29.530588853 d from 2000-01-06 18:14 UTC,
f = (1 − cos(2π·age/29.5306))/2 at local midnight of the night), "New" and "Full" labelled, each column's glow
`--moon-glow` at opacity = f. All-scopes row: a stacked column per night in the fixed order bottom-up, a nice
guide line ("20 h" from `niceTicks`), the selected column's total above it. One row per scope in `D.scopeOrder`
(never sorted): label "dot · name" (opens `openScope`) and "59.7 h · 15 nights · 44%"; pills (rounded both ends,
never shorter than their width, so a short night is a dot), hatched (`hatchFor`) for frames with no exposure, a
2 px speck for a night not out, a ring on the selected night. Resting scopes leave the rows: "Resting this period ·
● Seestar S50 · quiet for 414 nights · last out 30 Aug 2025". Longer ranges: 90 nights = weeks (asOf-anchored, as
`marksOf` bins), a year and everything = calendar months (quarters past 36 months); the bin's nights count sits on
each all-scopes column; the moon row is hidden; tiles still count nights. Selected-night panel on the right:
"Selected night · Fri 16 Oct · 11.5 h · across 5 scopes", the moon disc with "Waxing crescent · 32% lit", a row per
scope with hours, a bar and its objects ("Running Man Nebula (NGC 1977) 576 frames · 1.6 h", each opens
`openNight`), "‹ Previous night out" / "Next night out ›"; ← → Home End walk the nights out, Enter opens the night;
clicking a column selects it (a scope's pill also opens the night); the newest night out is selected on load.
Legend, three items: "length is hours imaged · column glow is moonlight · a speck is no frames that night".
Axis: day numbers, nights out bold, month names at the 1st, "last night" under the last column, the last-14-nights
band labelled under the axis. Phone: labels drawn inside the SVG, tiles 2 × 2, the panel under the chart.

**§4 What each scope shot** (`renderShotBars`, in the same card, sharing the range). One 20 px bar per scope in
the fixed order, length = hours against the biggest scope, pieces = objects biggest first (≤ 6 + "N more
objects"), 2 px gaps, name + hours inside a piece when the measured text fits (`textW`, canvas), else its number;
text on a scope colour is `--on-scope` (#15141f); the tip "77.9 h · 15 nights · 11 objects"; a 14 px hatched stub
"+ N frames, hours unknown"; under the bar the numbered line "**1** Swan Nebula **18.2 h** · **2** …"; a resting
scope is one muted line "nothing in 30 nights · last out 30 Aug 2025 · 414 nights ago". Hover/focus/tap: value-
first tooltip (hours · nights · frames · last night); click opens `openProject`; "view as table" twin (Scope ·
Object · Hours · Nights · Frames · Last night).

**§5 Project cards** (`projCard`). Ring 56 px, 7 px stroke, 2 px gaps. Meta "29.4 h · 1,476 frames · 12 nights ·
latest 16 Oct: 44 frames on the 107PHQ" (`latestTxt`; two scopes: "503 on the S30 Pro + 60 on the FRA400").
`describe()` says "mosaic on the S30 Pro" when only some datasets are mosaics (`programmes[].mosaic`). The
pills are replaced by one row per scope: "● S30 Pro · 3.0 h ······ ▶ Ready to process" (glyph + word in the
state's ink; only Ready to process is bold ink). Mini timeline: one 18 px lane per scope, 52 px muted labels,
dots in the scope's own colour, the band and the "last night" line across all lanes (`buildStrip` gained
`today`, `lblCls` options), "‹N" per lane, 120 nights, month ticks under it ("21 Jun · 20 Aug · 18 Oct · last
night"). The section is a region (heading on the page, cards white on the page, radius 12, grid gap 20, lanes
pinned to the bottom). The opened panel keeps its lanes table and three marks; the nights table opens by default
when ≤ 8 nights; "everything" is offered only when the project is older than 90 nights (truth 12).

**§6 Header.** Row 1: "Astro Archive Observatory" 16/700 with the eyebrow "PC · E:\Astro Image Data" (mono 11,
hover = "every number on this page comes from the importer's record"); under it ONE freshness line "Built on the
PC at 03:38 this morning · 20 h old · from the Mac's record of 18 Oct 20:04" (`builtText`, `oldText`,
`snapText`; the full source note is its hover), the live pill reduced to the connection ("live" / "rebuilding…" /
"updated just now" / "importer not answering" / "saved record" from a file), and, only when a camera holds
files, the 22 px amber chip "⚠ 87 files still on the ASIAir" (hover = the whole sentence; click scrolls to
`#pendLine`). Right: "1,000.7" 28/700 + "hours of integration" 13 px, then "78,668 frames · 87 targets · 320
nights · 6 scopes" 12 px ("nights" hover: nights with at least one scope out). Row 2: a 10 px share strip with
2 px gaps and no labels; ONE key line of buttons "● S30 Pro 64.9 h · 6% · 61 nights …" (this is the scope
legend; the numbered-tick fallback and the "1" prefix are gone; a click opens `openScope`). The sticky bar is
44 px: tabs, **Key** (opens `#keyfold` under the bar: scopes, next-step pills, marks: hollow dot, hatched, the
band, the speck, the moon glow and "‹N = N earlier nights"), **Refresh now** (`#refreshBtn`, shown only inside
the panel's frame; posts `{kind:"observatory-refresh"}`, shows "rebuilding…" and polls at 4 s and 12 s; on a
computer that shows the other's copy its hover says "Rebuild this computer's record now. The PC's newer copy is
shown while it is under 2 days old, so the page may not change."), the theme toggle. The mono "record built"
stamp (`#asof`) is gone; the footer keeps the one provenance line. Measured: 121 px of dark band at 1440 (the key
line wraps to a second 16 px line with the headless DejaVu font; with SF / Segoe it fits one line → 105 px) +
44 px bar. Hero rounding (truth 5): in `derive()` a scope's hours are the sum of its sessions' displayed
hours and the hero is the sum of the scope figures, so strip, key and hero agree to the tenth.

**§7 Polish.** The craft tokens for both themes (`--page #eeeae0`, `--card #fffefb`, `--line #d9d3c5`, `--ink2
#403e52`, `--muted #625f74`; dark `--card #181d36`, `--line #303860`, `--muted #9aa0bd`), `--on-scope #15141f`,
`--shadow-hover`, lead numbers 15/600, sentences 13/400 ink2, section sub-lines ≤ 72 characters, keyboard hints
only on `:focus-within` (`.keys`), legends ≤ 3 items (the Where-the-hours scope legend stays: it is the chart's
series legend), one border per level, no dust dots.

**§8 Truth fixes.** 1 week bins numbered and the subtitle says "a column is a week"; 2 one freshness line; 3 the
pending line with `targetNames` / `elsewhereMachine` (both optional: `[]` / null / absent all work); 5 one
rounding; 6 share key without ticks; 7 scope rows instead of pills; 8 no truncation (resting scopes on their own
line, `.marks3 small` wraps, Where-the-hours names wrap to two lines with the codes in the hover); 9 "‹N"
explained in the Key, the card's hover and the panel's foot line; 10 legend entries true for the range (the glow
item hides at bin ranges; the unknown swatches are neutral, not a scope colour); 11 "mosaic on the S30 Pro";
12 no "everything" for a project ≤ 90 nights; 13 the page never says "Data health"; 14 "ready to process from
31 Oct unless you add frames"; 15 the Refresh hover above; 17 newest-first-then-biggest sort, the panel title
without " · one lane per scope" (it leads the subtitle), the "240 nights" hover, "scopes in their usual order".
Also from the reviews: "Needs your attention" folds the nothing-to-do rows into "Also, nothing to do: 305 frames
imported on both computers · 14,379 files that are not lights · show"; the Equipment rhythm chart drops a year
label within 40 px of the previous one.

## Judgement calls (where SPEC-2 and the reviews were silent or pulled apart)

- The spec says both "use the page's `binFor` logic" and "a year = months". `binFor` would give weeks at a year
  on a desktop plot, so the chart uses its own `chartBins`: nights ≤ 30, weeks ≤ 90 (anchored on `asOfNight`
  like `marksOf`), calendar months after that, quarters past 36 months. `buildStrip` / `updateStrip` / `binFor`
  are untouched and still drive the scope panel, the project panel and the card lanes.
- Bars are pills (rounded both ends, never shorter than their width): that is what Brett's mockup draws and
  what the legend "length is hours imaged" describes. Height is linear in hours against the biggest scope-bin
  of the range, so rows are comparable with each other.
- The "N more objects" piece is in the scope colour like the rest (colour means scope); clicking it switches to
  the table.
- The chart's scope rows show "+ frames, hours unknown" only in the tile and the hover (the label line would
  truncate at 200 px).
- Card rows use the short scope name (S30 Pro) with the full name in the row's hover: the full name plus hours
  plus "▶ Ready to process" does not fit a 3-up card with the wider Windows fonts.
- The Key fold serves desktop and phone alike (the old phone-only `details.keyfold` is gone).
- The live pill's "stale" state keeps a live LED (the age is now in the sentence); "saved record" (opened from a
  file) keeps the grey LED.
- Phone shots are taken through a 390 px iframe (`built/phone-*.png`); the brief's `A/shoot_phone.sh` does not
  exist in the repo.

## Left out, and why

- Brett's 12-month "last twelve months by scope" Overview chart (charts proposal 3): not in SPEC-2 §1; the
  chart's "a year" range now shows months, which covers the question.
- Split dots for shared nights on the mini lane (craft 10): moot, each scope has its own lane now.
- The Observatory as its own route, the panel's rows (§9): the lead's, not the page's. The panel handlers for
  `observatory-refresh` and `open-panel` were already in `astro-app.py` (1.7.5 lines), so the buttons work.
- `pendingImport.files === 0` shows a muted "nothing left to import … at the last scan" line in the ledger rather
  than a green chip in the header (never a tick the engine did not give; §6 says the chip appears only when a
  camera holds files).

## Strings a test could assert (all in the served page or its JS)

- Header / freshness: `Built on the `, ` h old`, `from the `, `'s record of `, `hours of integration`,
  `id="keyBtn"`, `id="refreshBtn"`, `id="keyfold"`, `kind:"observatory-refresh"`, `kind:"open-panel"`,
  `class="camchip"`/`id="camChip"` (only when `pendingImport.files > 0`), ` files still on the `,
  `not in the rows below`, `already backed up by `; gone: `id="asof"`, `record built ` in the bar, the share
  key's `class="no"` tick, `from the importer's record`.
- Recent nights: `Recent nights`, `function renderRecent(card,changed)`, `id="pendLine"`, `Open the Panel to
  import`, `"a week"`, `"14 nights"`, `"30 nights"`, `no frames on any scope`, `The last `, `Latest frames · `,
  `Last night`, `not out`, `nights after it are not in this list`, `not all on the archive yet`, `no darks or
  flats filed`, `Not out in these `.
- The chart: `What each scope captured` (kept), `function renderStrips(card,first)` (kept name, new body),
  `function chartData(N)`, `function chartBins(N)`, `function moonAt(night)`, `29.530588853`, `Nights out`,
  `Integration captured`, `Nights with the moon under half lit`, `Biggest night`, `moon under half lit`,
  `Resting this period`, `Selected `, `Previous `, ` out ›`, `length is hours imaged`, `column glow is
  moonlight`, `a speck is no frames that `, `a column is a `, `last night`, `class="cchart"` (via
  `svgEl`: `class:"cchart"`), `const RANGES=[["30","30 nights",30],["90","90 nights",90],["365","a year",365],
  ["all","everything",0]]`.
- What each scope shot: `What each scope shot`, `function renderShotBars(box,d)`, ` more objects`, `view as
  table`, `frames, hours unknown`, `split by object`.
- Cards: `function latestTxt(t)`, `latest `, `mosaic on the `, `class="rows"` (built as `el("div","rows")`),
  `"srow"`, `"step p-st-`, `lblCls:"mini"`, `today:true`, `newest first, then biggest`, `one lane per scope ·`;
  gone from the card: `pill(stKey(p),{cam:p.camera})` inside `projCard`, `a grey dot is a night on more than one
  scope`.
- Truth wording: `ready to process from `, `scopes in their usual order` (ledger sub: `a column per scope in
  their usual order`), `Also, nothing to do: `, `‹N = N nights before this range`; absent: `Data health`,
  `the lists below don't include them`, `waits until `.
- Unchanged for the suites: `function openScope(cam)`, `function scopePanelFor(cam`, 9 × `openScope(`,
  `function openNight(cam,night,target,host`, `function nightPanelFor(cam,night,target)`, the project-panel
  range literal `["90","90 nights",90],["365","a year",365],["all","everything",` (3 ×), `what it has been
  doing`, `Timeline of its projects`, `function normalise(d)`, `reconciliation:[],warnings:[]`, `Needs your
  attention`, `Astro Archive Observatory`, the dataset slot once, `kind:"observatory-ready"`, `v===null?null:`,
  `stageOf(`, `function showDrawer(`, the tooltip div, `const col=cam=>(BY[cam]&&BY[cam].colour)||"var(--muted)"`,
  no `const CAMORDER`, no `--cam-s30p`, no external URL (the only `http://` is the SVG namespace in `svgEl`).
  Five `<script>` blocks, all parse in node.

## test_app.py

Run once from the repo root with the page in place; output in `scratchpad/ux3/build/test_app.out`.
Result line: see the end of this file (appended after the run).

**First run: `189 passed, 2 failed` (exit 1)**, with Chrome screenshots running on the same container at the
time. Every OB and PR check passed, including the five-script-block parse and "OB5 (1.7.5) … the page's Refresh
and 'Open the Panel' arrive as observatory-refresh and open-panel". The two failures were both `AP` checks
(`test_app.py:1349`, the sys.exit job, and the sys.frozen astropy banner): the job runner answered "The importer
is busy (idle); try again when it has finished." instead of starting the job. Those checks do not read the page
(the earlier 1.7.4 run in `scratchpad/app_174.out` was 189 passed, 0 failed), so the suite was run a second
time, sequentially, on a quiet machine; that result is appended below.

**Second run (quiet machine, `scratchpad/ux3/build/test_app-run2.out`): `191 passed, 0 failed` (exit 0).**
All 26 OB / PR checks pass; the two AP flakes of the first run pass too, so they were the container's load,
not the page.
