#!/usr/bin/env python3
"""A CFF2 color font whose one glyph is a whole animated landscape: three
mountain ranges scrolling at different speeds (parallax), a striped sun that
sets and rises again, and stars that come out at dusk. Each master is the scene
at one time-step. varLib merges the masters into CFF2 'blend' operators, which
the browser runs for every frame as the TIME axis sweeps.

The font has two sets of colors. COLRv1 (Chrome, Firefox) paints gradients,
and its alphas vary with TIME too, so the sky darkens as the sun goes down.
Safari only draws COLRv0, so it gets the same moving shapes in flat colors.
"""
import math, random
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.colorLib.builder import buildCOLR, buildCPAL, populateCOLRv0
from fontTools.ttLib.tables import otTables as ot
from common import make_font, make_variable, save, VISIBLE_ASCII

W = 1000                     # the scene is one 1000 x 1000 em
M = 48                       # time steps per loop (49 masters: the last repeats the first)
TAU = 2 * math.pi

# Mountain ranges, back to front. A range is a sum of sines that repeats every
# W, so scrolling it by `speed` widths per loop ends where it began. The far
# range is jagged and slow; the near one is smooth and fast. Linear interpolation
# between masters only looks like scrolling while each step moves a fraction of
# the smallest wave, hence 48 steps.
RANGES = [  # name, samples, speed, base height, amplitude, harmonics
    ("far",  72, 1, 330, 170, 12),
    ("mid",  48, 2, 230, 120, 5),
    ("near", 36, 3, 120,  70, 3),
]
_rng = random.Random(7)
WAVES = {name: [(k, _rng.uniform(0, TAU), _rng.uniform(0.6, 1.0) / k ** 0.9)
                for k in range(1, h + 1)]
         for name, _, _, _, _, h in RANGES}

SUN_X, SUN_R = 620, 150
SUN_HIGH, SUN_LOW = 560, 40           # center height at noon and at midnight
STRIPES = [(-0.15, 0.06), (-0.38, 0.09), (-0.62, 0.12)]   # (offset, height) in radii
_srng = random.Random(1234)
STARS = [(_srng.uniform(20, 980), _srng.uniform(420, 980), _srng.uniform(3, 8))
         for _ in range(60)]

def darkness(m):
    """0 at the start of the loop (sun high), 1 halfway (sun down)."""
    return (1 - math.cos(TAU * m / M)) / 2

def sun_y(m):
    return SUN_HIGH - (SUN_HIGH - SUN_LOW) * darkness(m)

# ------------------------------------------------------------------ outlines
def box(pen, x0, y0, x1, y1):
    pen.moveTo((x0, y0)); pen.lineTo((x1, y0)); pen.lineTo((x1, y1)); pen.lineTo((x0, y1))
    pen.closePath()

def sun_glyph(m):
    """The sun as horizontal bands of a circle, with gaps for the stripes.
    Each band is a polygon: up the right edge of the circle, down the left."""
    cy, r = sun_y(m), SUN_R
    cuts = sorted([-1.0, 1.0] + [off - h for off, h in STRIPES] + [off for off, _ in STRIPES])
    pen = T2CharStringPen(W, None)
    for lo, hi in zip(cuts[0::2], cuts[1::2]):        # (band, gap, band, gap, ...)
        n = max(2, round(24 * (hi - lo)))
        ys = [lo + (hi - lo) * i / n for i in range(n + 1)]
        right = [(SUN_X + r * math.sqrt(max(0.0, 1 - y * y)), cy + r * y) for y in ys]
        left = [(2 * SUN_X - x, y) for x, y in reversed(right)]
        pen.moveTo(right[0])
        for p in right[1:] + left:
            pen.lineTo(p)
        pen.closePath()
    return pen.getCharString()

def ridge_glyph(name, m):
    _, samples, speed, base, amp, _ = next(r for r in RANGES if r[0] == name)
    shift = speed * m / M                              # in widths
    pen = T2CharStringPen(W, None)
    pen.moveTo((0, 0))
    for i in range(samples):
        u = i / (samples - 1)
        h = sum(a * math.sin(TAU * k * (u + shift) + ph) for k, ph, a in WAVES[name])
        pen.lineTo((u * W, base + amp * h))
    pen.lineTo((W, 0))
    pen.closePath()
    return pen.getCharString()

def stars_glyph():
    pen = T2CharStringPen(W, None)
    for x, y, s in STARS:
        box(pen, x, y, x + s, y + s)
    return pen.getCharString()

def sky_glyph():
    pen = T2CharStringPen(W, None)
    box(pen, 0, 0, W, W)
    return pen.getCharString()

# --------------------------------------------------------------------- color
PALETTE = [
    (1.00, 0.55, 0.30),   # 0 sky horizon: orange
    (0.80, 0.22, 0.48),   # 1 sky middle: rose
    (0.16, 0.06, 0.35),   # 2 sky top: violet night
    (0.03, 0.02, 0.10),   # 3 night shade
    (0.95, 0.95, 1.00),   # 4 stars
    (1.00, 0.88, 0.35),   # 5 sun top: gold
    (1.00, 0.25, 0.55),   # 6 sun bottom: hot pink
    (0.62, 0.42, 0.80),   # 7 far range, top: lavender haze
    (0.40, 0.20, 0.60),   # 8 far range, base
    (0.55, 0.16, 0.52),   # 9 mid range, top
    (0.25, 0.07, 0.38),   # 10 mid range, base
    (0.18, 0.06, 0.30),   # 11 near range, top
    (0.05, 0.02, 0.12),   # 12 near range, base
    (0.98, 0.50, 0.42),   # 13 flat sun (COLRv0)
    (0.45, 0.17, 0.48),   # 14 flat sky (COLRv0)
]

def gradient(glyph, stops, y0, y1):
    return {
        "Format": ot.PaintFormat.PaintGlyph, "Glyph": glyph,
        "Paint": {
            "Format": ot.PaintFormat.PaintLinearGradient,
            "ColorLine": {"Extend": "pad", "ColorStop": [
                {"StopOffset": o, "PaletteIndex": i, "Alpha": 1.0} for o, i in stops]},
            "x0": 0, "y0": y0, "x1": 0, "y1": y1, "x2": 100, "y2": y0,
        },
    }

def solid(glyph, index, alpha):
    return {"Format": ot.PaintFormat.PaintGlyph, "Glyph": glyph,
            "Paint": {"Format": ot.PaintFormat.PaintSolid, "PaletteIndex": index,
                      "Alpha": alpha}}

def colr_v1(m):
    """The COLRv1 scene for master m. Every master has the same paint tree, so
    varLib can merge them; values that differ become variable paints."""
    sy, d = sun_y(m), darkness(m)
    layers = [
        gradient("scene", [(0, 0), (0.45, 1), (1, 2)], 0, W),         # sky
        solid("scene", 3, round(0.8 * d, 3)),                         # night falls
        solid("stars", 4, round(0.1 + 0.9 * d, 3)),                   # stars come out
        gradient("sun", [(0, 6), (1, 5)], sy - SUN_R, sy + SUN_R),    # gradient rides the sun
        gradient("far", [(0, 8), (1, 7)], 0, 520),
        gradient("mid", [(0, 10), (1, 9)], 0, 380),
        gradient("near", [(0, 12), (1, 11)], 0, 220),
    ]
    return {"Format": ot.PaintFormat.PaintColrLayers, "Layers": layers}

def add_colr_v0(font):
    """Add flat COLRv0 layers next to the v1 paints. Renderers that support
    COLRv1 use the v1 record; older ones (Safari) fall back to these."""
    populateCOLRv0(font["COLR"].table, {"scene": [
        ("scene", 14), ("stars", 4), ("sun", 13), ("far", 8), ("mid", 10), ("near", 12)]})

# ---------------------------------------------------------------------- build
def master(m):
    def empty():
        p = T2CharStringPen(W, None); p.moveTo((0, 0)); p.closePath()
        return p.getCharString()
    glyphs = {".notdef": empty(), "space": empty(), "scene": sky_glyph(),
              "stars": stars_glyph(), "sun": sun_glyph(m)}
    for name, *_ in RANGES:
        glyphs[name] = ridge_glyph(name, m)
    cmap = {c: "scene" for c in VISIBLE_ASCII}
    cmap[0x20] = "space"
    font = make_font("Terrain", glyphs, cmap, {"*": W}, ascent=1000, descent=0, cff=True)
    font["CPAL"] = buildCPAL([[c + (1.0,) for c in PALETTE]])
    font["COLR"] = buildCOLR({"scene": colr_v1(m)}, clipBoxes={"scene": (0, 0, W, W)})
    return font

def build():
    # m == M repeats m == 0, so the loop is seamless.
    vf = make_variable("TIME", "Time", [(round(1000 * m / M), master(m)) for m in range(M + 1)])
    add_colr_v0(vf)
    return save(vf, "Terrain.woff2", f"; {M + 1} masters")

if __name__ == "__main__":
    build()
