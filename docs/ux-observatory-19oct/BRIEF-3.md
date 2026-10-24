# Observatory review round 3 (19 Oct 2026) — brief for every reviewer

Brett (astrophotographer, not a developer) has been using the rebuilt Observatory
(importer 1.7.2–1.7.4, page `astro-observatory.html`) on his Mac and PC for a day.
His words this morning, verbatim:

> I have been reviewing the observatory... these are the most important for me.
> Having the history is super important as to what was recently captured and onto
> what scope / camera. I still think there is scope to make this look super awesome.
> The header takes up too much space. Spin up a load of UX agents and make this look
> top class by reviewing what's important to me, there appears to be some features
> from the earlier design review that were not implemented: donut graphs, etc...

So, in priority order:
1. **History**: what was captured recently, on which scope/camera, is the thing he
   opens the page for. The "What each scope captured" strip and the "Projects that
   moved lately" cards (and the per-project "one lane per scope" panel) are the parts
   he screenshotted as "most important".
2. **Look**: "super awesome", "top class". Professional, dynamic, colourful, but every
   mark must mean something (the 16 Oct spec's rules still hold).
3. **The header takes up too much space.** Note the page sits inside the panel's
   Observatory tab, so above it there is also the panel's own header (FITS Importer,
   status pills, tabs, "Worked out ... Refresh now"). Count everything the eye passes
   before the first useful content.
4. **Promised but not built**: the 16 Oct design round (directions A / B / C, the five
   R reviews, SPEC.md) promised things the built page does not show, e.g. donut
   graphs. Find every such gap, say which are worth building now.

## What to look at

Screenshots Brett sent this morning (Safari on the Mac, light theme, ~2000 px wide):
- `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/images/7.webp`  — "What each scope captured", 90 nights
- `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/images/8.webp`  — the same, 30 nights
- `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/images/9.webp`  — "Projects that moved lately" cards
- `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/images/10.webp` — a project card opened: "one lane per scope", plus more cards
- `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/images/11.webp` — the top of the tab: the panel's header + the Observatory hero + share bar + legend + nav

Repo (read-only for you; never edit anything under it): `/home/user/brettjoastro-fits-importer/`
- `astro-observatory.html` — the built page (230 KB, one file: CSS, JS, a `__DATASET__` slot). Grep it; don't read it whole.
- `docs/ux-observatory-16oct/SPEC.md` — the specification the page was built to (read it).
- `docs/ux-observatory-16oct/BRIEF.md`, `BRIEF-R.md` — the earlier briefs (dataset schema in BRIEF.md).
- `docs/ux-observatory-16oct/A/ B/ C/` — the three design directions (mockup HTML + PNGs + notes). Brett liked A and C.
- `docs/ux-observatory-16oct/R/{type,colour,motion,truth,layout}/` — the five detail reviews (findings.md + demos).
- `docs/ux-observatory-16oct/built/` — screenshots of the page as built (1440 and 390 px).
- `docs/ux-observatory-16oct/sample-dataset.json` — a realistic sample dataset; `R/truth/stress-dataset.json` is a real-size one (87 targets / 147 datasets).
- `CHANGELOG.md` top entries (1.7.2–1.7.4) say what shipped.

Tooling in the scratchpad (copy it into your own folder if you change it):
- `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux2/render.py` builds `observatory-current.html` from `dataset.json` through the engine's `observatory_html()`; `python3 render.py`.
- `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux2/shoot_file.sh PAGE OUT.png W H [js]` screenshots a page with headless Chromium (desktop only; a phone shot needs the trick in `docs/ux-observatory-16oct/A/shoot_phone.sh`). Read your PNGs back with the Read tool.
- The `dataviz` skill (Skill tool) has the colour, chart and interaction rules this page follows. Load it.

Facts about the data: six scopes in a fixed order (Seestar S30 Pro amber, S30 blue, S50 near-black, S50 Pro slate, Askar FRA400 red, Askar 107PHQ green; colours come from the dataset, never a palette in the page); states Still capturing / Ready to process / Finish it / Done / Quick look; the quiet period is 14 nights; a night is noon-to-noon; the record is built by the PC nightly and by the Mac on demand; the page refreshes in place every 30 s. The ZWO scopes (FRA400, 107PHQ) have calibration frames; the Seestars calibrate in camera.

Things already known (don't spend time rediscovering them): the "1 Seestar S50 Pro" / "1" label on the share bar in 11.webp is a bug (the scope's name carries a stray "1"); the "Open cluster in the Tadpoles (IC 410, NGC 1893)" card exists because Brett's PC has not yet got the contract change that folds NGC 1893 into IC 410; the Observatory as its own route (one scrollbar) is on the backlog and would remove the double header.

## What to deliver

Write `/tmp/claude-0/-home-user/c23ee14e-85ed-5f5b-94f9-0fb713d6fb24/scratchpad/ux3/<your-name>/findings.md`:
- Ranked findings, most valuable to Brett first. For each: what is on screen now (cite the screenshot or the file:line), what to change, why it serves one of his four points above, effort (S / M / L), and whether it is a page-only change or needs an engine field (name the field).
- A short "keep as it is" list: what already works and must not be lost.
- Mockups are welcome (PNG via the shoot script, from a copy of the page or a standalone HTML in your folder) when words would not do. Name them in findings.md.
- Plain words, no jargon Brett would not know. Be concrete: pixel heights, type sizes, exact labels.
- Write ONLY inside your own folder. Never touch the repo.
