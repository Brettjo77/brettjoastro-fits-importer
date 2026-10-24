# Observatory design round, 16 Oct 2026

Three reviewers, three directions, one brief (`BRIEF.md`: Brett's words, the ChatGPT
critique and a second review checked against his real data). Nothing here is live:
these are mockups rendered from `sample-dataset.json` (6 scopes, 41 targets, 50 datasets).

- `0-current-*.png`: the page as it is today, with the same sample data.
- `A/`: "glanceable". Scope colour everywhere, a 30-night strip per scope, three to-do
  columns with a stage badge per scope, project cards with a ring and a dotted timeline.
- `B/`: "the story of the season". The timeline is the spine: a lane per scope, a dot per
  night sized by hours, the quiet band at the right; then where each scope is, what is
  growing now, what went quiet.
- `C/`: "meaning first". Every number wears its word, a legend explains every colour once,
  warnings become jobs with counts, and each project opens into a lane per scope with
  capture / processing / calibration marks.

Each folder has `review.md` (the critique and proposal), `mock-X.html` (the source, with
`__DATASET__`), and screenshots. To look at one in a browser:

    python3 render_mock.py B/mock-B.html /tmp/mock-B.html

then open `/tmp/mock-B.html`. The earlier panel-and-page colour mockups of the same day are
parked in `../ux-mockups-16oct/`.

`built/` holds screenshots of the page as built for 1.7.2 from `SPEC.md` (light and dark, the
project and night panels, the phone, the stress dataset of 87 targets).
