# Smart Road — static marketing site

Plain HTML, CSS and JavaScript. No build step, no framework runtime, no
third-party request at page load. Drop this folder on Vercel and it works.

## Fonts

The IBM Plex binaries are **in this folder** — `fonts/*.woff2`, 405 kB for seven
weights. Nothing to fetch, nothing to install, no request to Google or any other
third party at page load. Open `index.html` from disk and it renders correctly.

They are the **complete** faces rather than unicode-range subsets, and that is
deliberate. IBM ships pre-split subsets and an earlier draft of this build used
them; they cannot be used here, because **U+02BB and U+02BC — the Uzbek
apostrophes in oʻ and gʻ — are in none of IBM's subsets.** Latin1 covers U+02C6,
U+02DA and U+02DC and stops. Splitting would drop the one character that appears
in nearly every Uzbek word on this site. The cost is that a Russian reader
downloads no less than an Uzbek one; correctness of the primary language is
worth more than that saving.

Licence: SIL Open Font License 1.1 (`fonts/LICENSE.txt`). Self-hosting and
redistribution are permitted.

### If a font ever fails to load

The `.sr-oz` apostrophe inset is scoped to `[data-plex="on"]`, and `index.html`
sets that attribute only after `document.fonts.check` confirms Plex is loaded.
So a font failure degrades to *unfitted but readable* — never to the apostrophe
being pulled into the letters on either side, which is what an unconditional
inset on a fallback face produces. A red band and a console error say what
happened.

## Deploying

```
vercel deploy --prod
```

No configuration needed: it is a static folder with `index.html` at the root.
Any static host works the same way — Netlify, GitHub Pages, S3, nginx.

## What is in here

```
index.html      the page, plus the font guard
styles.css      design tokens, generated from the design system's tokens/*.css
site.css        layout grids, interactive states, breakpoints (1080 / 720)
fonts/          the seven .woff2 binaries, @font-face rules and the OFL licence
copy.js         all three languages, verbatim from SAYT_MATNI.md
data.js         survey figures and detection fixtures, with provenance comments
app.js          DOM helpers and the components the sections compose
sections.js     the eight sections and the boot sequence
uz-apostrophe.js  the U+02BB / U+02BC fit pass
assets/         logo lockups and three photographs
```

## Languages

All three ship in the page. Switching re-renders from `copy.js` and never
fetches. The choice is written to the URL — `?lang=ru`, `?lang=en`, Uzbek is the
default and carries no parameter — so a juror can be sent straight to one
language and a reload keeps it. `<html lang>` follows the switch, which is what
a screen reader and the browser's own hyphenation read.

`?theme=light` works the same way if you need to link someone to the light view.

## Images

Re-encoded at the size they are displayed, not at source resolution:

| file | source | shipped | on screen |
|---|---|---|---|
| `hero-yangizamon.jpg` | 1920×1080 | 1600×900, 256 kB | full-bleed right column |
| `frame-tehran.jpg` | 1024×576 | 1024×576, 126 kB | S3 and S4 figures |
| `demo-poster.jpg` | 1200×754 | 1000×628, 43 kB | S4 recording poster |

Total first load is roughly 830 kB including all seven font weights; the fonts
are cached from then on, so a language switch or a second page view costs
nothing further.

## Two things still to replace

1. **The demo recording.** `assets/demo-poster.jpg` is a still of the current
   Streamlit app and the play control has no video wired to it. Record the demo,
   drop the file in `assets/`, and pass its path as the second argument to
   `S.videoBlock(...)` in `sections.js`.
2. **The deduct-chain quantities.** The three rows in `data.js` (`3.4 m²`,
   `0.93 %`, `2.6 m` and their deduct values) are illustrative — they are
   internally consistent with the score shown, 100 − 64.8 = 35.2, but they did
   not come from a detector run. Every other figure on the page is traceable to
   `SAYT_MATNI.md` or the repository. Replace them with a real run on
   `attain_tehran_000795.jpg` before the jury sees this.
3. **Two Cyrillic names.** Placed — Баходир Низамов and Фахриддин Жумаев in the
   Russian view, Latin forms retained in Uzbek and English.

## Changing anything

Copy lives in `copy.js` and nowhere else — no string is written in `sections.js`.
Colours, type and spacing are all custom properties in `styles.css`, regenerated
from the design system; edit them there rather than here so the app and the
report pages stay in step.
