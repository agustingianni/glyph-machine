# Glyph Machine

Five small experiments where a line of text does something a font is not
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

## Browser support

Chrome and Firefox shape text with HarfBuzz; Safari uses CoreText. All five
demos run in all three. Safari does not draw COLRv1, so there the landscape
uses its COLRv0 flat colors and the plasma uses the CSS text color.

The demos were tested in the Chromium, Firefox, and WebKit builds that come
with Playwright.

## Run locally

Serve the `docs/` folder with any static web server, for example:

    python3 -m http.server 8000 --directory docs

Then open <http://localhost:8000/>.

## Rebuild

    pip install fonttools brotli
    python3 src/build_all.py

This builds the five fonts into `docs/fonts/` (as WOFF2) and then the pages in
`docs/`. `src/build_site.py` rebuilds only the pages. Tested with fontTools
4.67. The calculator takes up to a minute, because its `GSUB` table holds a rule
for every pair of numbers.

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

Run it again after you change how a demo looks. The tags need the site's full
URL, which is `SITE_URL` at the top of `src/build_site.py`. Change it if the
site lives somewhere else, then run `src/build_site.py` again.

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
