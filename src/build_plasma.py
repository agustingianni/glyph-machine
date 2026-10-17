#!/usr/bin/env python3
"""A variable font whose single glyph is a demoscene 'plasma' dot-field.
A 16 x 16 grid of round dots pulses in size and swirls in position, driven by
summed sine waves. Each master is one time step of the loop, and a single CSS
keyframe animates the TIME axis. A COLRv1 sweep gradient colors the dots, and its angle
also varies with TIME, so the color wheel turns while the dots move through it.
Browsers without COLRv1 draw the dots in the CSS text color.
"""
import math
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.ttLib.tables import otTables as ot
from common import make_font, make_variable, save, VISIBLE_ASCII

UPM = 1000
G = 16                      # grid is G x G dots
M = 24                      # time steps per loop (25 masters: the last repeats the first)
MARGIN = 60
SPAN = UPM - 2 * MARGIN
TAU = 2 * math.pi
RMIN, RMAX = 6, 32          # dot radius range
SWIRL = 22                  # positional swirl amplitude
WHEEL = [                   # sweep gradient colors, first == last for a seamless wheel
    (1.00, 0.30, 0.49), (1.00, 0.54, 0.24), (1.00, 0.86, 0.35),
    (0.22, 0.91, 0.75), (0.36, 0.55, 1.00), (0.61, 0.42, 1.00), (1.00, 0.30, 0.49),
]

def wave(gx, gy, p):
    # summed sines -> [0,1]; this is the "plasma".
    w = (math.sin(TAU * 1.5 * gx + p)
         + math.sin(TAU * 1.7 * gy + 1.2 * p)
         + math.sin(TAU * 1.2 * (gx + gy) + 0.8 * p)
         + math.sin(TAU * 2.3 * math.hypot(gx - 0.5, gy - 0.5) - p))
    return (w + 4) / 8

def dot(pen, cx, cy, r):
    # Four off-curve points and no on-curve points: TrueType draws a round
    # quadratic curve through the midpoints, close to a circle.
    k = r * 1.08
    pen.qCurveTo((cx + k, cy + k), (cx - k, cy + k), (cx - k, cy - k), (cx + k, cy - k), None)
    pen.closePath()

def plasma_glyph(phase):
    pen = TTGlyphPen(None)
    for iy in range(G):
        for ix in range(G):
            gx, gy = ix / (G - 1), iy / (G - 1)
            n = wave(gx, gy, phase)
            cx = MARGIN + gx * SPAN + SWIRL * math.sin(TAU * 2 * gy + phase)
            cy = MARGIN + gy * SPAN + SWIRL * math.cos(TAU * 2 * gx + phase)
            dot(pen, cx, cy, RMIN + (RMAX - RMIN) * n)
    return pen.glyph()

def color(font, m):
    # The same paint tree in every master; only the rotation angle differs, so
    # varLib turns it into a PaintVarRotateAroundCenter. The wheel repeats every
    # 180 degrees, so a half turn per loop is seamless. (A full turn would not
    # fit: COLR stores angle deltas as F2Dot14 multiples of 180 degrees.)
    font["CPAL"] = buildCPAL([[c + (1.0,) for c in WHEEL]])
    stops = [{"StopOffset": i / (len(WHEEL) - 1), "PaletteIndex": i, "Alpha": 1.0}
             for i in range(len(WHEEL))]
    font["COLR"] = buildCOLR({"demo": {
        "Format": ot.PaintFormat.PaintGlyph,
        "Glyph": "demo",              # the glyph paints its own outline
        "Paint": {
            "Format": ot.PaintFormat.PaintRotateAroundCenter,
            "angle": -90 + 180 * m / M,
            "centerX": UPM // 2, "centerY": UPM // 2,
            "Paint": {
                "Format": ot.PaintFormat.PaintSweepGradient,
                "ColorLine": {"Extend": "repeat", "ColorStop": stops},
                "centerX": UPM // 2, "centerY": UPM // 2,
                "startAngle": 0, "endAngle": 180,
            },
        },
    }})

def master(m):
    empty = TTGlyphPen(None).glyph()
    glyphs = {".notdef": empty, "space": empty, "demo": plasma_glyph(TAU * m / M)}
    cmap = {c: "demo" for c in VISIBLE_ASCII}
    cmap[0x20] = "space"
    font = make_font("Plasma", glyphs, cmap, {"*": UPM}, ascent=1000, descent=0)
    color(font, m)
    return font

def build():
    # m == M repeats phase 0, so the loop is seamless.
    vf = make_variable("TIME", "Time", [(round(1000 * m / M), master(m)) for m in range(M + 1)])
    return save(vf, "Plasma.woff2", f"; {M + 1} masters, {G * G} dots")

if __name__ == "__main__":
    build()
