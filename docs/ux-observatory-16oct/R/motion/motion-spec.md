# Observatory motion spec

Everything here is implemented in `demo-motion.html` (CSS transitions and animations, ~60 lines of vanilla JS for the parts CSS cannot do: keyed dots, the expand panel, the tooltip, the poll). No libraries, no network, no web fonts; it runs from a `file://` URL.

## 1. Principles

- **Motion only where it carries meaning.** Four cases: something **arrives** (load-in, a new session, a panel), something **moves** (a dot to its new place when the range changes), something **leaves** (a job marked done, dots out of range), something **changes value** (a refreshed number). Nothing else animates. No decoration, no looping effects on an idle page.
- **Arriving decelerates, leaving accelerates, moving does both.** `--ease-out` for arrivals, `--ease-in` for departures, `--ease-move` for A→B. The only overshoot on the page is a dot popping in (`--ease-spring`), because a dot is small and a 35% overshoot on a 10 px circle reads as "landed", not "bouncy".
- **Transform and opacity only**, except the one height transition on the expand panel (it is the thing that has to push the rows below). No animated layout anywhere else.
- **Nothing waits on motion.** Data is in the DOM before any animation starts; a screen reader, a search, or a screenshot at 0 ms sees the finished page. Load-in is fill-mode `both` on elements that are already laid out.
- **Reduced motion is a first-class state**, not a kill switch: see §9.

## 2. Tokens (`:root`)

| Token | Value | Used for |
|---|---|---|
| `--dur-micro` | 120 ms | hover colour, lift, press, chevron colour |
| `--dur-short` | 200 ms | tooltip fade, chip/segmented state, count tick |
| `--dur-base` | 320 ms | dots moving, band sliding, view crossfade rise, job collapse |
| `--dur-long` | 480 ms | panel expand/collapse height, ring segment draw |
| `--dur-reveal` | 600 ms | a block rising on load; the hero count-up on refresh |
| `--dur-pop` | 360 ms | a dot arriving |
| `--dur-fade` | 200 ms (120 ms reduced) | opacity-only swaps: text, axis labels, empty-night dots, view fade |
| `--dur-stars` | 900 ms (120 ms reduced) | the star field fading up behind the header |
| `--sweep` | 420 ms (300 ms inside a panel) | how long a strip takes to draw its dots left to right |
| `--stagger` | 70 ms | between blocks on load |
| `--ease-out` | `cubic-bezier(.2,.7,.2,1)` | arriving |
| `--ease-in` | `cubic-bezier(.4,0,1,1)` | leaving |
| `--ease-move` | `cubic-bezier(.65,0,.35,1)` | moving A→B |
| `--ease-spring` | `cubic-bezier(.34,1.35,.5,1)` | a dot popping in |
| `--lift` | −1 px (0 reduced) | hover lift on cards and buttons |
| `--rscale` | 1 (0 reduced) | multiplies every delay, so reduced motion has no staggers |
| `--loop` | 1 (0 reduced) | whether anything may loop (only the rebuilding LED) |

Colours for the freshness LED: `--led #22b573` (live), `--led-amber #e09a1a` (stale), `--led-red #d04040` (offline), `#ffd48a` (rebuilding, pulsing).

## 3. Load-in (once per page load)

| Step | What | Starts | Duration · easing |
|---|---|---|---|
| 1 | Header left half (eyebrow, title, freshness) rises 10 px → 0, opacity 0 → 1 | 0 ms | 600 ms `--ease-out` |
| 2 | Header right half (hero number, share bar, key) rises | 120 ms | 600 ms `--ease-out` |
| 3 | Stars fade up | 200 ms | 900 ms |
| 4 | Share bar segments `scaleX(0 → 1)` from the left, in scope order | 260 ms + 60 ms × i | 600 ms `--ease-out` |
| 5 | Body blocks rise, in order: last night, needs attention, strips, projects | 150 ms + 70 ms × i (`--block-delay`) | 600 ms `--ease-out` |
| 6 | Ring segments draw (`stroke-dasharray 0 100 → len rest`), one after another | block + 240 ms + 140 ms × j | 480 ms `--ease-out` |
| 7 | Strip dots pop (`scale 0 → 1`), left to right | block + 200 ms + k × `--sweep`, k = position 0…1 | 360 ms `--ease-spring` |

Everything has landed by ~1.2 s. The hero number does **not** count up (see findings, 7). Replay by reloading; the demo's "Replay load-in" button does exactly that.

Implementation: `.reveal { animation: rise var(--dur-reveal) var(--ease-out) both; animation-delay: calc(var(--block-delay) * var(--rscale)) }`; the dot's delay is `calc((var(--block-delay) + 200ms + var(--k) * var(--sweep)) * var(--rscale))` with `--k` set per dot. Three nested SVG groups per dot so the three motions never fight: `g.dot` (position, transitions), `g.pop` (arrival, animation), `circle.c` (hover/focus scale).

## 4. Hover, press, focus

| Target | Hover | Press | Focus (keyboard) |
|---|---|---|---|
| Project card | border darkens, shadow `0 4px 14px`, `translateY(var(--lift))`, 120 ms | — | 2 px `--focus` outline inset 3 px on the header button |
| Buttons (`.btn`, `.more`, tabs, segmented) | background wash / lift, 120 ms | `scale(.97)` for 60 ms | 2 px outline, offset 2 px; segmented buttons get a white outline inset |
| Strip dot | `scale(1.25)` + ink stroke 2.5 px, 120 ms | — | same as hover, via `.cur` on the walked dot; the strip itself shows the outline |
| Scope name / last-night row | wash, 120 ms | — | outline |
| Share bar segment | `brightness(1.15)` | — | — (the key row carries the numbers) |
| Tab | text to white, wash | — | outline; the underline (`.ink`) slides to the tab: `left`/`width` 320 ms `--ease-move` |

One focus style for everything: `:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px }`. SVG marks use stroke instead of outline (outline on SVG is inconsistent across browsers).

## 5. Tooltip

- One element, `#tt`, `role="tooltip"`, `position: fixed`, `pointer-events: none`.
- **Anchor:** centred above the mark's bounding box, 9 px gap, a 10 px caret under it; flips below when there is no room above; clamped 8 px inside the viewport with the caret following the mark (`--ax`). It never follows the cursor.
- **Timing:** opens 90 ms after `pointerover` (a flyby shows nothing); while "warm" (within 400 ms of the last close, or when moving straight from one mark to another) it opens at once, so walking along a strip is continuous. Closes on `pointerout` immediately with a 200 ms fade; closes on scroll, resize and Escape.
- **Appearance:** fade + 4 px rise, 200 ms `--ease-out`. Dark ink surface, 12.5 px text, max 300 px.
- **Content:** title line (date · weekday / object name), then rows: label left, **value right in bold tabular digits**, keyed by a 12×3 px stroke of the scope colour; a muted hint line last ("Enter or click opens the project" / "tap again to open the project"). Names are inserted with `textContent`.
- **Keyboard:** `focusin` on a `[data-tip]` opens the same tooltip; `focusout` closes it. On a strip, ← → move a `.cur` dot and re-anchor the tooltip to it.
- **Touch:** `pointerdown` with `pointerType === "touch"` pins the tooltip to the mark and swallows the following `click`; a second tap on the same mark acts (opens the project); a tap anywhere else closes it. Hover-only behaviours never run for touch.
- **Hit target:** every dot has a transparent 24 px (r = 12) circle behind it; a bar's whole height is its target.
- **Where:** marks only (dots, ring segments, share bar segments, scope names, last-night rows, the "‹N" earlier marker, the freshness pill, the indicator glyphs). Never on a card, a job or a button: those say what they are.

## 6. Range change (strips on the Overview; lanes in a project panel)

- Control: a segmented radio group (30 nights / 90 nights / a year; in a panel: 90 nights / a year / all time). Click or ← → changes it; the chosen segment fills ink in 200 ms.
- Dots are **keyed** by `scope|night` and kept in a map. On change:
  - a dot in both ranges gets a new `transform: translate(x, y)` → slides 320 ms `--ease-move`; its radius transitions too (`r`, 320 ms);
  - a dot leaving gets `.out` → opacity 0 and `scale(.3)` over 320 ms `--ease-in`, then is removed;
  - a dot arriving is inserted at its final x with `.in` (`scale(0)`) and released next frame → 120 ms `--ease-out` to full size;
  - the quiet band (last 14 nights) is one rect that `translateX` + `scaleX` to its new width, 320 ms `--ease-move`;
  - the 30-night empty-night dots crossfade out/in (`--dur-fade`);
  - the axis labels and the right-hand text ("7.1 h over 4 nights · latest …") swap through a 200 ms fade; the "‹N" earlier-nights marker updates in place.
- The SVG's `viewBox` width is set to its rendered width (`fitStrip`) and re-set on resize, so x is in real pixels and circles are circles on a 1440 px desk and a 390 px phone alike. A resize re-lays the dots with `.still` (no pop) and the band without transition.

## 7. Expanding a project card

- The header of a card is a `<button aria-expanded aria-controls>`; click, Enter or Space toggles; Escape anywhere closes every open panel; the panel's Close button returns focus to the header.
- On open: the card takes `.open` (darker border, stronger shadow, header wash), the chevron rotates 180° (320 ms `--ease-move`); a **panel** (`grid-column: 1 / -1`) is inserted after the last card of the same row, so the cards in that row stay exactly where they are and only the rows below move down.
- Height: panel `height: 0 → scrollHeight` over 480 ms `--ease-out`, then `auto` (so it can reflow). Its contents (`.panelin`) fade in and rise 6 px → 0 over 320 ms starting 60 ms in. The lanes' dots sweep in (200 ms + k × 300 ms). The band draws without transition on first paint.
- Scroll: if the panel's bottom would be off screen, `scrollBy` the smaller of "what is needed" and "the card's top to 80 px", `behavior: smooth`, started with the expand so both finish together.
- Close: height `scrollHeight → 0` over 480 ms, then the panel is removed. Opening another card closes the open one first. One panel per grid.
- Inside the panel: C's lanes (scope · integration · sessions · capture / processing / calibration · next), a range control that **moves** the dots (§6), the Askar note, the Why line.

## 8. Views (tabs)

- `role="tablist"`, roving `tabindex`, ← → Home End; `aria-selected`; the health tab carries its count in a badge.
- Switch: old view `opacity 1 → 0` (200 ms `--ease-in`), then it is hidden; the new view is shown at `opacity 0, translateY(6px)` and released next frame → 200 ms fade / 320 ms rise, `--ease-out`. The underline slides (320 ms). Each tab remembers its own scroll position and restores it instantly. Lanes that were hidden (`display: none` has no width) are drawn when the view appears.

## 9. Needs attention: a job done

- Click the job's button → the row gets an explicit height, then `.gone`: height → 0, padding → 0, opacity → 0, `translateX(12px)`, border → 0, all 320 ms `--ease-in`; then `display: none`.
- The count badge in the heading (and the health tab badge) updates and bumps `scale(1.25)` for 200 ms `--ease-spring`; at zero it turns green and the list shows "✓ Nothing needs you right now" (rise, 320 ms).
- A toast (bottom centre, 320 ms rise+fade in) says "Marked as done · …" with **Undo** for 7 s; Undo reverses the collapse. The "Nothing to do" row (duplicates, correctly counted once) only explains itself in a toast.
- Writing "done" back is an engine question (an endpoint, or `localStorage` until there is one).

## 10. Live refresh

**States of the freshness pill** (header, next to "Built 16 Oct 2026, 09:12 …"):

| state | LED | text | page |
|---|---|---|---|
| `fresh` | green | live · 3 min ago (re-worded every 30 s) | normal |
| `stale` | amber | a day old · 26 h ago | normal (record older than 24 h) |
| `rebuilding` | amber, pulsing 1.2 s loop (static halo under reduced motion) | rebuilding from your records… | `main` at 72% opacity, `aria-busy="true"`, still interactive; the old numbers stay (no skeleton, no flash) |
| `updated` | green, pill tinted green | updated just now | changed things highlighted; back to `fresh` after 8 s |
| `offline` | red | importer not answering · last seen 3 min ago | normal; keeps trying |

**Polling:** `GET /api/status` every 30 s (the panel already serves it and already polls it every second, so this is cheap). Two failures in a row → `offline`. When the status reports a newer `observatory.generatedAtIso` than the page's, the page fetches the dataset and calls `applyDataset()`.

**What `applyDataset()` animates**, in this order (all at once, ~1.4 s):
1. Hero hours: count from old to new over 600 ms with ease-out, tabular digits, plus a `washsky` glow that fades over 1.4 s. The frames / nights numbers and the per-scope key swap, and any key value that changed gets the wash.
2. Last-night card: 200 ms fade out, redraw, fade in, wash.
3. Strips: keyed update (§6), so the new night **pops in** at the right and everything else shifts one night left.
4. Right-hand strip text that changed: fade swap + wash.
5. Projects grid: re-rendered; any open panel is re-opened; the card of a target that gained a session gets the wash.
6. Needs attention: re-rendered.
7. Toast: "Updated · 1 new session: Horsehead Nebula on FRA400 · +1.6 h" with **Show** (scrolls to the strips).

**Two small things the importer needs to add** (in `astro-app.py` / `astro-import.py`, upstream, with tests):
- `/api/status` carries `observatory: { generatedAtIso, rebuilding }` (the generatedAt of the current `observatory.json`, and whether `--projects` is running).
- `GET /observatory?json=1` returns the dataset alone (what the panel substitutes for `__DATASET__`), so the page can redraw in place instead of the panel reloading the iframe. Until then, the panel's existing `observatory-ready` postMessage can at least tell the page to show `updated`; the demo's `demo.rebuild()` simulates the whole thing with a fake new session.

## 11. Keyboard map

| Keys | Where | Does |
|---|---|---|
| Tab | page | tabs → freshness pill → last-night rows → job buttons → range control → each strip (one stop) → scope names → cards → "+N more" |
| ← → Home End | tablist | switch view |
| ← → ↑ ↓ | range control | change range (radio group) |
| ← → Home End | a strip | walk its nights; the tooltip follows; `.cur` ring on the dot |
| Enter | a strip with a walked dot; a last-night row | open the project (scroll to its card, expand, focus its header) |
| Enter / Space | card header | expand / collapse |
| Escape | anywhere | close tooltip, close panels |
| Enter / Space | toast buttons | Undo / Show / dismiss |

## 12. Reduced motion

Under `@media (prefers-reduced-motion: reduce)` (and `html[data-motion="reduce"]`, which the demo's checkbox sets):
- every `--dur-*` except `--dur-fade` → 0 ms; `--sweep`, `--stagger` → 0; `--rscale` → 0 (so no delays either); `--lift` → 0; `--loop` → 0;
- so: blocks and panels appear at once, dots jump to their places, nothing lifts or pops, the hero never counts, the chevron snaps, the LED does not pulse (static halo), `scrollBy`/`scrollIntoView` use `behavior: "instant"`;
- kept: 120 ms opacity fades (crossfades are not motion and avoid "did it change?"), the wash on changed numbers (colour only), the toast (fade only).
Verified in headless Chromium with the media query emulated: 0 running animations with a non-zero duration after load; after a range change, only 120 ms opacity fades.

## 13. Performance notes

- Only `transform`, `opacity`, `stroke`, `stroke-dasharray`, `r` and the one `height` are animated. Dots are `<g>` with CSS transforms (composited); no attribute animation except `r`.
- Brett's real archive: 6 scopes × up to ~730 nights ≈ at most 4,400 dots at "a year" on the Overview if every scope went out every night; in practice a few hundred. The keyed map avoids rebuilding them. Panels only build their lanes when opened.
- Pop animations are CSS; the JS never schedules per-dot timers. The only `requestAnimationFrame` loop is the 600 ms count-up on a refresh.
- The tooltip is one element rebuilt on open; it never reflows the page.

## 14. Browser notes

- Chrome, Edge, Safari ≥ 16: everything. Safari may transition `r` as a jump rather than an ease (harmless). `transform-box: fill-box` is needed for the per-dot scale and is supported in all three.
- `scrollBy({behavior:"smooth"})` and a concurrent height transition are both GPU-cheap; if Safari stutters, drop the scroll to `instant`.
- Nothing depends on `document.getAnimations()` except the demo's frame shooter (`shoot.js`), which freezes animations at a given time to capture the strips.
