# Observatory UX round 2 (16 Oct 2026): the brief every reviewer gets

Brett (astrophotographer, not a developer) on the Astro Archive Observatory page:

> "The UX issue, specific to the Observatory at the moment, is how the data is presented
> to me... at the moment, it's just a lot of text and numbers - it's like looking at Excel.
> I need more thoughtful visuals that are going to make it easier for me (or anyone) to
> understand what's what, the latest project captures, on what scopes... etc."

Earlier today he also said, about the panel and this page: "there is a lot of info, but
hard to read, I need more colour, and simpler, more dynamic design."

ChatGPT reviewed the same page for him and said (keep this; Brett pasted it "for the record"):

1. Make every number self-explanatory (101.7 h integration · 37 nights · 11,294 lights, not bare numbers).
2. Distinguish unknown from zero (Milky Way Core: 0.0 h beside 2,150 frames; the exposure is missing, say "Integration unknown").
3. Show mixed processing states honestly (Andromeda has To process and In progress datasets across scopes; "2 awaiting · 2 in progress" with expandable scope rows; 87 targets vs 147 target/scope datasets).
4. Separate capture activity, processing stage and calibration readiness into three indicators, with uncertainty visible beside the badge; the "master may belong to the other Askar" warning deserves prominence.
5. Decisions before session history: archive totals → needs attention → suggested processing queue → recent captures → charts. One latest session per scope at first, expandable.
6. Give the Observatory more room: one main scrollbar, compact navigation, a labelled view selector on narrow screens, a list alternative for the Pipeline board.
7. Turn data warnings into actions ("184 rows excluded across 2 unrecognised target names — review names"), separate from the 305 duplicate copies correctly excluded.
8. Make chart meaning visible: numerical legends on Nights, stronger state distinctions on Sky, "Approximate footprints" up front, Coverage distinguishing not captured / unknown / not planned.
Keep: searchable catalogue, scope filters, chart/table alternatives, source timestamps, the Why / Next explanations.

## What the page is

`observatory-template.html` is the live page (1956 lines, one HTML file, no libraries, no network:
it is served by the importer's local panel and must work offline). The importer substitutes
`__DATASET__` with a JSON document (schema observatory/1). `dataset.json` here is a realistic
sample: 6 scopes, 41 targets, 50 datasets (one object on one scope), 160 sessions, 292.8 h.
`observatory-current.html` is that page rendered with the sample, and `shots/` has every view at
1440 wide (desk-*.png) and 390 wide (phone-*.png).

Dataset facts you will need (read the template's JS for the rest):
- `D.scopes[]`: camera, id, colour (the scope's identity colour, fixed by the contract: keep these
  as each scope's colour), frames, hours, nights, first, last.
- `D.targets[]`: name, codes, type, constellation, ra/dec, state (the least advanced dataset:
  captured / stacked / processing / complete), hours, nights, lights, lastNight, cameras[],
  programmes[] (one per scope: status capturing / ready_to_process / in_progress / done, hours,
  nights, lights, lastNight, readyOn, evidence, action, where[], calibration {applies, missing[]},
  filters, exposures, masters, processedFinals), statusCards[] (the same, flattened).
- `D.sessions[]`: target, camera, night (ISO), frames, hours, filters, exps, cal.
- `D.totals`, `D.health[]` (severity info/warn), `D.reconciliation[]`, `D.warnings[]`,
  `D.sourceNote`, `D.provenance`, `D.quietPeriodDays`, `D.asOfNight`.
- Milky Way Core has hours 0 with 2,150 frames and filters {unrecorded}: integration unknown.
- Andromeda is on four scopes with four different statuses, and one Askar note about the shared folder.

Status meanings (the project layer's): Still capturing = a session within the 14-night quiet
period; To process = quiet period passed, nothing started; In progress = a master of Brett's is
saved; Done = a finished picture names the object and scope.

## Tools here

- `python3 render_mock.py IN.html OUT.html` fills `__DATASET__` in your mockup with dataset.json.
- `./shoot_file.sh PAGE.html OUT.png 1440 2400` and `... 390 3000` screenshot a page with headless
  Chromium (optional 5th arg: JS to run on load, e.g. "go('targets')").
- Read your PNGs back with the Read tool to check your own work. Do that.
- The `dataviz` skill (Skill tool) has colour and chart rules worth loading before drawing charts.

## Rules

- Nothing live changes. Do not edit anything under /home/user. Work only in your folder.
- Mockups use the real sample data through `__DATASET__`, never typed-in numbers.
- Plain HTML/CSS/SVG, no libraries, no web fonts, no network. Both 1440 and 390 wide.
- Keep the scope colours from `D.scopes[].colour` as each scope's identity.
- Brett wants to look at something and know: what did I capture lately, on which scope, what
  should I process next, how is each project doing. Pictures over numbers; numbers labelled.
- Write for Brett: plain words, no jargon, short.

## Addendum (a second review Brett received, checked full-width against his real data)

Agrees with ChatGPT on: the 184 excluded rows undersold by "2 things to know" (in truth 491 rows not
counted: 184 unknown names, 2 no scope, 305 duplicate copies); Milky Way Core shown as 0.0 h; one badge
hiding mixed states (the column is honestly labelled "state (the scope furthest behind)", but Andromeda
says To process while one scope is in progress); decisions before history (eighteen session cards come
before the processing queue); calibration as its own signal (FRA400 Pleiades "none linked").
Qualifies: full width, the Targets table does have Hours / Nights / Frames / Latest headings; and
"still capturing" partly reflects Brett's own capture-state.json (open / complete), so it is intent, not
only a guess. Show that difference.
Adds, for the display:
- Test snaps inflate "To process 83": targets with 1, 4 or 55 frames from long ago sit in the queue.
  A minimum-integration cutoff or a "sample" state would make the queue honest. Design for it.
- Type labels are inconsistent ("Nebula" vs "Emission nebula"); some targets have no type or
  constellation at all. Design for missing type/constellation gracefully.
- The S50 and S50 Pro bars in "Integration by scope" have no labels (too thin). Small values need labels too.
- Scopes appear in a different, unexplained order in each panel. Fix one scope order and use it everywhere.
- Freshness: the page is built from a record that may be a day old while frames still sit on the camera
  (29 targets, 3,559 files not yet imported, and a failed eject). A "not yet imported" line in the
  header would stop the queues looking more settled than they are. The dataset has D.generatedAt and
  D.sourceNote; design a freshness line that could also carry "N files on the camera not yet imported".
Its suggested order: names first (an engine fix, not yours), then labelled metrics, unknown vs zero,
mixed statuses, then the layout reorder and more room.
