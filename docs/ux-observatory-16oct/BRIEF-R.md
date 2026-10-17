# Observatory round 3 (17 Oct 2026): the details

Brett has seen the three directions in this folder (A/, B/, C/: each has review.md, mock-X.html,
mock-X.rendered.html and PNGs; BRIEF.md is what their designers were told). He said:

> "really liking the visuals of the A and C... the devil is in the detail and it's the details
> that matter. 5 UX agents to critically review, consider with dynamic impact that looks
> professional."

So this round is not new directions. It is a critical, detailed review of A and C (B is
reference: Brett liked its spine too), with one lens per reviewer, and "dynamic impact":
the page should feel alive and professional (motion, hover, transitions, loading, live
refresh) without being gimmicky. The end product will be ONE page that blends A and C.

Facts to keep in mind:
- The page is one offline HTML file served by the importer's local panel: no libraries, no web
  fonts, no network, must render on macOS and Windows 11 browsers (Safari, Edge, Chrome) and on
  a phone over the home network. Everything inline.
- Data comes as `__DATASET__` (see BRIEF.md for the schema); `sample-dataset.json` is realistic
  but Brett's real archive is larger: 87 targets, 147 datasets, names up to ~45 characters
  (e.g. "Open cluster in the Tadpoles (IC 410) (NGC 1893)"), six scopes, two years of nights.
- Scope colours come from `D.scopes[].colour` (contract-fixed): FRA400 red, 107PHQ blue, S30 Pro
  amber, S50 grey, S50 Pro green, Starfront S50 Pro purple.
- Status meanings: Still capturing (a session within the 14-night quiet period, or kept open by
  hand), To process (quiet, nothing started), In progress (a master saved), Done (a final found),
  plus the new Sample (tiny test captures kept out of the queue).
- Brett is an astrophotographer, not a developer; words on the page must be plain.

Tools: `python3 render_mock.py IN.html OUT.html` fills `__DATASET__`; `./shoot_file.sh PAGE OUT.png W H [js]`
for desktop shots; `A/shoot_phone.sh` (read it) for a TRUE 390 px phone layout (desktop Chromium won't
lay out under ~500 px, so a plain 390 shot is a crop). Read your PNGs back with the Read tool.
The `dataviz` skill (Skill tool) has colour, chart and interaction rules: load it.

Rules: never edit anything under /home/user and never edit A/, B/, C/. Work only in R/<your lens>/.
Deliver: `findings.md` (ranked, each finding = where (A or C, which block), what is wrong, why it
matters, the fix, and a severity), a `demo-<lens>.html` that shows your fixes applied to the
relevant blocks (built from `__DATASET__`, real data), PNGs of it, and at the top of findings.md
the five things that matter most. Be harsh and specific; Brett wants the detail.
