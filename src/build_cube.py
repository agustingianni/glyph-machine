#!/usr/bin/env python3
"""A variable font of spinning 3D wireframes on one SPIN axis (0..360 degrees).
Letters and digits are extruded stroke letters that turn about their vertical
axis; every other character is a tumbling cube. Each master is the scene
projected with perspective at one angle, and edges are drawn thicker when they
are closer to the camera. Animate the axis in CSS and the shapes rotate in 3D.
"""
import math
from fontTools.pens.ttGlyphPen import TTGlyphPen
from common import make_font, make_variable, save, VISIBLE_ASCII

CX, CY = 280, 380          # glyph-space center
CAM = 1000                 # perspective camera distance
STEP = 15                  # degrees between masters
ANGLES = list(range(0, 361, STEP))   # 360 == 0, so the loop is seamless

# The cube: 8 vertices, 12 edges (vertex pairs that differ in one coordinate).
S = 140
CUBE_V = [(x, y, z) for x in (-S, S) for y in (-S, S) for z in (-S, S)]
CUBE_E = [(i, j) for i in range(8) for j in range(i + 1, 8)
          if sum(a != b for a, b in zip(CUBE_V[i], CUBE_V[j])) == 1]

# Stroke letters on a 4 x 6 grid (y up). Each entry is a list of polylines.
O_RING = [(1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)]
P_BOWL = [(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)]
STROKES = {
    "A": [[(0, 0), (0, 4), (2, 6), (4, 4), (4, 0)], [(0, 3), (4, 3)]],
    "B": [P_BOWL, [(3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    "C": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1)]],
    "D": [[(0, 0), (0, 6), (2, 6), (4, 4), (4, 2), (2, 0), (0, 0)]],
    "E": [[(4, 6), (0, 6), (0, 0), (4, 0)], [(0, 3), (3, 3)]],
    "F": [[(4, 6), (0, 6), (0, 0)], [(0, 3), (3, 3)]],
    "G": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (2, 3)]],
    "H": [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    "I": [[(1, 6), (3, 6)], [(2, 6), (2, 0)], [(1, 0), (3, 0)]],
    "J": [[(4, 6), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "K": [[(0, 0), (0, 6)], [(4, 6), (0, 2)], [(1.4, 3.4), (4, 0)]],
    "L": [[(0, 6), (0, 0), (4, 0)]],
    "M": [[(0, 0), (0, 6), (2, 3), (4, 6), (4, 0)]],
    "N": [[(0, 0), (0, 6), (4, 0), (4, 6)]],
    "O": [O_RING],
    "P": [P_BOWL],
    "Q": [O_RING, [(2.5, 1.5), (4, 0)]],
    "R": [P_BOWL, [(2, 3), (4, 0)]],
    "S": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3), (3, 3), (4, 2), (4, 1),
           (3, 0), (1, 0), (0, 1)]],
    "T": [[(0, 6), (4, 6)], [(2, 6), (2, 0)]],
    "U": [[(0, 6), (0, 1), (1, 0), (3, 0), (4, 1), (4, 6)]],
    "V": [[(0, 6), (2, 0), (4, 6)]],
    "W": [[(0, 6), (1, 0), (2, 3), (3, 0), (4, 6)]],
    "X": [[(0, 6), (4, 0)], [(4, 6), (0, 0)]],
    "Y": [[(0, 6), (2, 3), (4, 6)], [(2, 3), (2, 0)]],
    "Z": [[(0, 6), (4, 6), (0, 0), (4, 0)]],
    "0": [O_RING, [(0, 1), (4, 5)]],
    "1": [[(1, 5), (2, 6), (2, 0)], [(1, 0), (3, 0)]],
    "2": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (0, 0), (4, 0)]],
    "3": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (1, 3)],
          [(3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "4": [[(3, 0), (3, 6), (0, 2), (4, 2)]],
    "5": [[(4, 6), (0, 6), (0, 3), (3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    "6": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2),
           (3, 3), (0, 3)]],
    "7": [[(0, 6), (4, 6), (1, 0)]],
    "8": [[(1, 3), (0, 4), (0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (1, 3),
           (0, 2), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (3, 3)]],
    "9": [[(4, 3), (1, 3), (0, 4), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)]],
}
UNIT = 66                  # grid unit in font units: letters are 264 x 396
DEPTH = 80                 # half the extrusion depth
LETTER_ADV = 440
CUBE_ADV = 560

def extrude(strokes):
    """Turn 2D polylines into a 3D wireframe: a front copy, a back copy, and
    one edge through the depth at every vertex."""
    verts, edges = [], set()
    def vid(p):
        if p not in verts:
            verts.append(p)
        return verts.index(p)
    for z in (DEPTH, -DEPTH):
        for line in strokes:
            ids = [vid(((x - 2) * UNIT, (y - 3) * UNIT, z)) for x, y in line]
            edges.update(tuple(sorted(e)) for e in zip(ids, ids[1:]))
    front = [v for v in verts if v[2] == DEPTH]
    for x, y, _ in front:
        edges.add(tuple(sorted((verts.index((x, y, DEPTH)), verts.index((x, y, -DEPTH))))))
    return verts, sorted(edges)

def rotate(v, yaw, pitch):
    x, y, z = v
    x1 = x * math.cos(yaw) + z * math.sin(yaw)
    z1 = -x * math.sin(yaw) + z * math.cos(yaw)
    y2 = y * math.cos(pitch) - z1 * math.sin(pitch)
    z2 = y * math.sin(pitch) + z1 * math.cos(pitch)
    return x1, y2, z2

def wire_glyph(verts, edges, yaw, pitch, cx, thick):
    """Project the wireframe and draw every edge as a quad whose width follows
    the perspective scale at each end: near edges thick, far edges thin.
    `thick` is the half-thickness at depth 0."""
    pts = []
    for v in verts:
        x, y, z = rotate(v, yaw, pitch)
        sc = CAM / (CAM - z)
        pts.append((cx + x * sc, CY + y * sc, thick * sc))
    pen = TTGlyphPen(None)
    for i, j in edges:                        # one 4-point quad per edge, fixed order
        (x0, y0, t0), (x1, y1, t1) = pts[i], pts[j]
        ln = math.hypot(x1 - x0, y1 - y0) or 1.0
        dx, dy = (x1 - x0) / ln, (y1 - y0) / ln
        x0, y0 = x0 - dx * t0, y0 - dy * t0   # square caps close the corners
        x1, y1 = x1 + dx * t1, y1 + dy * t1
        pen.moveTo((x0 - dy * t0, y0 + dx * t0)); pen.lineTo((x1 - dy * t1, y1 + dx * t1))
        pen.lineTo((x1 + dy * t1, y1 - dx * t1)); pen.lineTo((x0 + dy * t0, y0 - dx * t0))
        pen.closePath()
    return pen.glyph()

def master(angle):
    a = math.radians(angle)
    glyphs = {".notdef": TTGlyphPen(None).glyph(), "space": TTGlyphPen(None).glyph(),
              # the cube tumbles: it turns twice about X for each turn about Y
              "cube": wire_glyph(CUBE_V, CUBE_E, a, 2 * a + math.radians(20), CUBE_ADV / 2, 13)}
    for ch, strokes in STROKES.items():       # letters turn about their own axis
        verts, edges = extrude(strokes)
        glyphs[f"w{ch}"] = wire_glyph(verts, edges, a, math.radians(-18), LETTER_ADV / 2, 11)
    cmap = {c: "cube" for c in VISIBLE_ASCII}
    cmap[0x20] = "space"
    for ch in STROKES:
        cmap[ord(ch)] = f"w{ch}"
        cmap[ord(ch.lower())] = f"w{ch}"
    advances = {"*": LETTER_ADV, "cube": CUBE_ADV}
    return make_font("CubeSpin", glyphs, cmap, advances, ascent=720, descent=120)

def build():
    vf = make_variable("SPIN", "Spin", [(a, master(a)) for a in ANGLES])
    return save(vf, "CubeSpin.woff2", f"; {len(ANGLES)} masters")

if __name__ == "__main__":
    build()
