# Glyph Machine

Six small experiments where a line of text does something a font is not
supposed to do. Each scene lives entirely inside a font file and is drawn by the
browser's own text engine. No image, no canvas, no SVG.

## The demos

- **Landscape** (`docs/landscape/`) - three mountain ranges scroll at different
  speeds while a striped sun sets and rises again. CFF2 `blend` moves every
  outline across 49 masters. COLRv1 paints the gradients, and its variable
  paints darken the sky and bring out the stars as the sun goes down. A COLRv0
  layer set gives the same scene in flat colors where COLRv1 is missing.
- **Plasma** (`docs/plasma/`) - a 256-dot demoscene plasma. A variable font with
  one `TIME` axis and 25 masters. The dots are sized by summed sine waves. A
  COLRv1 sweep gradient colors them and turns with the same axis.
- **Spinning 3D type** (`docs/cube/`) - every letter and digit is an extruded 3D
  wireframe, and every other ASCII symbol is a tumbling cube. One `SPIN` axis
  turns them all, with perspective baked into each glyph. Type a word and it
  spins.
- **Calculator** (`docs/calc/`) - a seven-segment font whose `GSUB` table
  evaluates sums like `12+34-5`. Whole numbers from 0 to 99 with `+`, `-`, and
  `*`, worked left to right like a pocket calculator. A result outside 0 to 99
  shows `E`. A line can hold up to 8 operators, and a number up to 8 digits.
  Copy the output and your text comes back.
- **Game of Life** (`docs/life/`) - Conway's Life on a 48x20 board, computed by
  `GSUB`. The page stores only generation 0, as one line of text written column
  by column, like `[.O|O.|..]`. A `TIME` axis picks the generation: through
  `FeatureVariations`, `TIME=g` turns on 3 lookups per generation, up to 120.
  COLRv0 colors cells that are newborn, alive, or just died. Click or drag on
  the board to draw.
- **MD5 hash** (`docs/md5/`) - type up to 55 printable ASCII characters, and
  the font draws the MD5 hash as 32 hex digits. The font does the padding, the
  length, and all 64 rounds. Each browser gets its own font. Firefox runs
  `MD5Graphite.woff2`, a Graphite font: its rules keep MD5's words as integers
  on one glyph and revisit that glyph 128 times. Safari runs `MD5Safari.woff2`,
  an AAT `morx` font: 2,690 state machines grow the text into a tape of one
  glyph per bit, then add, rotate, and copy bits along it. The page wraps the
  message in invisible private-use characters (U+E000 at the start, U+E001 at
  the end, and four U+E002 after the start for Safari). Its JavaScript picks
  the font and checks the input, and never computes the hash.

## Browser support

Chrome and Firefox shape text with HarfBuzz; Safari uses CoreText. The first
five demos run in all three. Safari does not draw COLRv1, so there the
landscape uses its COLRv0 flat colors and the plasma uses the CSS text color.

The MD5 demo runs only in Firefox (through its Graphite engine) and Safari
(through AAT `morx`). Chrome runs neither font, and the page says so instead
of drawing a hash.

The demos were tested in the Chromium, Firefox, and WebKit builds that come
with Playwright. The MD5 fonts were also checked against Python's `hashlib`
on 1,334 messages, in Graphite2, CoreText, and by reading the pixels each
browser drew.

## Run locally

Serve the `docs/` folder with any static web server, for example:

    python3 -m http.server 8000 --directory docs

Then open <http://localhost:8000/>.

## Rebuild

    pip install fonttools brotli
    python3 src/build_all.py

This builds the fonts into `docs/fonts/` (as WOFF2) and then the pages in
`docs/`. `src/build_site.py` rebuilds only the pages. Tested with fontTools
4.67. The calculator takes up to a minute, because its `GSUB` table holds a rule
for every pair of numbers.

The Firefox MD5 font also needs SIL's Graphite compiler, `grcompiler`, at a
pinned commit with a small patch: the compiler only names 16 of the 64 glyph
variables that Graphite allows. This script clones it into
`/tmp/md5-grcompiler` and builds it (it needs git, CMake, a C++ compiler, and
ICU from Homebrew):

    python3 src/md5/prepare_compiler.py

Without the compiler, `src/build_hash.py` builds only the Safari MD5 font and
keeps the Firefox one that is already in `docs/fonts/`. Set `GRCOMPILER` and
`GDLPP` if the compiler lives somewhere else. The builder also fixes two
problems in that compiler's output: it swaps the AND and OR opcodes back, and
it keeps the compiler's own `Silf` table layout, because fontTools writes one
that Firefox's font checker rejects.

## How Life fits in a font

A cell has 8 neighbors, but text is one line. The board is stored column by
column, so the cells above and below a cell sit right next to it in the text,
and the cells to its left and right are one column (21 glyphs) away. One
generation is 3 `GSUB` passes:

1. Each cell counts itself plus its live neighbors above and below.
2. Each cell adds the count of the cell to its left.
3. Each cell adds the count of the cell to its right, and the total decides
   whether it lives.

A last pass gives every cell its row, and each row's glyph draws its square
that far down. `src/build_life.py` explains the details.

At generation 120, the browser runs 360 lookups over about 1,000 glyphs every
time the generation changes. Measured layout time on an Apple M1 Max:

| Board                    | Chromium | Firefox | WebKit |
|--------------------------|---------:|--------:|-------:|
| Empty                    |    46 ms |   50 ms |  74 ms |
| Glider gun               |    49 ms |   53 ms |  94 ms |
| Random, 28% alive        |    54 ms |   59 ms | 121 ms |

Most of the time goes into walking the board, so even an empty board is not
much faster. CoreText is slow at replacing glyphs. So each cell glyph stores
four fields, and a pass only replaces a glyph when its field really changes.
That cut WebKit's time on busy boards about in half.

## Link previews

When someone shares a link to the site, social sites show a title, a line of
text, and a 1200 x 630 image. Every page sets these through Open Graph tags.
The images are screenshots of each demo, taken by a script:

    pip install playwright && python3 -m playwright install
    python3 src/build_previews.py

Run it again after you change how a demo looks. The images are taken in
Chromium, except any image that shows the MD5 demo, which is taken in Firefox.
The tags need the site's full URL, which is `SITE_URL` at the top of
`src/build_site.py`. Each page also links to its font's source on GitHub,
through `REPO_URL` next to it. Change both if the site or the repo moves, then
run `src/build_site.py` again.

## Check the layout

    python3 src/check_layout.py

This loads the gallery and every demo page in Chromium, Firefox, and WebKit, at
widths from 320 to 1920 pixels. It also checks each gallery preview inside its
card. It prints anything that sticks out of its box, such as a long line that
does not wrap, and exits with status 1 if it found a problem. It serves the
site itself, so no server needs to be running. A full run takes about a minute.

## Deploy (GitHub Pages)

The site is static and already built in `docs/`, so no build runs on GitHub.
Push to a repo, then in Settings > Pages choose "Deploy from a branch", the
`main` branch, and the `/docs` folder. The site then lives at
`https://<user>.github.io/<repo>/`.

## Layout

    docs/                    the published site, all generated by src/
      index.html             gallery landing page
      style.css              shared design for every page
      preview.png            the gallery's link preview image
      fonts/                 the font files the pages load
      <demo>/index.html      a demo page
      <demo>/hero.html       the bare preview shown in the gallery card
      <demo>/preview.png     the demo's link preview image
    src/
      build_all.py           builds every font, then the pages
      build_<font>.py        one script per font
      build_hash.py          the two MD5 fonts, built by the scripts in md5/
      md5/                   the MD5 builders and the Graphite compiler setup
      build_site.py          the pages, their text, and the shared design
      build_previews.py      the link preview images
      check_layout.py        checks that nothing sticks out of its box
      common.py              shared helpers: build a font, merge masters, save

## Prior art

Other people have pushed fonts much further than they were meant to go:

- [Fontemon](https://www.coderelay.io/fontemon.html) by Michael Mulet, a whole
  game in an OpenType font, driven by `GSUB` ligatures.
- [Animated & pixelated variable fonts](https://tosche.net/AnimatedPixelatedVF/)
  by Toshi Omagari, video frames on one axis with pixels sized by brightness.
  The plasma demo uses the same idea.
- [Addition Font](https://litherum.blogspot.com/2019/03/addition-font.html)
  on the Litherum blog, which adds multi-digit numbers with carry using `GSUB`.
- [Numderline](https://thume.ca/2019/11/02/numderline-grouping-digits-using-opentype-shaping/)
  by Tristan Hume, digit grouping through OpenType shaping.
- [llama.ttf](https://fuglede.github.io/llama.ttf/) by Søren Fuglede
  Jørgensen, a language model inside a font through HarfBuzz's WebAssembly
  shaper.
- [Nabla](https://nabla.typearture.com/) by Arthur Reinders Folmer and Just
  van Rossum, an isometric COLRv1 font with variable axes.

## License

MIT. See `LICENSE`. This covers the code and the fonts it builds.
