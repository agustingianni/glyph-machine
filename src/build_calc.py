#!/usr/bin/env python3
"""A seven-segment 'calculator' font. Its GSUB table evaluates sums like
12+34-5 while the text is shaped, so the rendered line shows the answer and the
text underneath never changes.

The font works on whole numbers from 0 to 99, left to right like a pocket
calculator. Anything outside that range shows E. GSUB runs in two stages:

1. JOIN passes glue typed digits into one number glyph: [one two] -> v12.
   Each pass adds one digit, and a number above 99 becomes E.
2. OP passes each replace the leftmost [number op number] with its result,
   so 1+2+3 becomes 3+3, then 6. One pass is needed per operator.
"""
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from common import make_font, save

ADV = 480          # one digit cell
MAX = 99           # the largest number the display shows
JOIN_PASSES = 7    # numbers of up to 8 digits, like a pocket calculator
OP_PASSES = 8      # operators per line

# Seven segments as rectangles (x0, y0, x1, y1).
SEG = {
    "A": (70, 720, 410, 800),   # top
    "G": (70, 360, 410, 440),   # middle
    "D": (70,   0, 410,  80),   # bottom
    "F": (70, 440, 150, 720),   # top-left
    "B": (330, 440, 410, 720),  # top-right
    "E": (70,  80, 150, 360),   # bottom-left
    "C": (330, 80, 410, 360),   # bottom-right
}
DIGIT_SEGS = ["ABCDEF", "BC", "ABGED", "ABGCD", "FGBC",
              "AFGCD", "AFGECD", "ABC", "ABCDEFG", "ABCFGD"]
OPS = {"plus": lambda a, b: a + b, "minus": lambda a, b: a - b,
       "times": lambda a, b: a * b}

def rect(pen, x0, y0, x1, y1):
    pen.moveTo((x0, y0)); pen.lineTo((x1, y0))
    pen.lineTo((x1, y1)); pen.lineTo((x0, y1)); pen.closePath()

def quad(pen, pts):
    pen.moveTo(pts[0])
    for p in pts[1:]:
        pen.lineTo(p)
    pen.closePath()

def segs_glyph(segs):
    pen = TTGlyphPen(None)
    for s in segs:
        rect(pen, *SEG[s])
    return pen.glyph()

def op_glyph(name):
    pen = TTGlyphPen(None)
    if name in ("plus", "minus"):
        rect(pen, 120, 360, 360, 440)
    if name == "plus":
        rect(pen, 200, 240, 280, 560)
    if name == "times":                       # two crossed bars
        quad(pen, [(135, 220), (380, 520), (345, 560), (100, 260)])
        quad(pen, [(345, 220), (380, 260), (135, 560), (100, 520)])
    if name == "equal":
        rect(pen, 120, 250, 360, 330)
        rect(pen, 120, 470, 360, 550)
    return pen.glyph()

def number_glyph(n, glyphs):
    # Two-digit numbers reuse the digit outlines as components.
    pen = TTGlyphPen(glyphs)
    pen.addComponent(f"v{n // 10}", (1, 0, 0, 1, 0, 0))
    pen.addComponent(f"v{n % 10}", (1, 0, 0, 1, ADV, 0))
    return pen.glyph()

def value_name(n):
    return f"v{n}" if 0 <= n <= MAX else "err"

def features():
    nums = [f"v{n}" for n in range(MAX + 1)]
    lines = ["languagesystem DFLT dflt;", "languagesystem latn dflt;",
             f"@DIG = [{' '.join(nums[:10])}];",
             f"@NUM = [{' '.join(nums)} err];",
             f"@OP = [{' '.join(OPS)}];"]

    # JOIN: a number followed by one more typed digit.
    lines.append("lookup JOIN {")
    for x in range(MAX + 1):
        for d in range(10):
            lines.append(f"  sub v{x} v{d} by {value_name(10 * x + d)};")
    lines += [f"  sub err v{d} by err;" for d in range(10)]
    lines.append("} JOIN;")

    # CALC: number op number -> result.
    lines.append("lookup CALC {")
    for op, f in OPS.items():
        for a in range(MAX + 1):
            for b in range(MAX + 1):
                lines.append(f"  sub v{a} {op} v{b} by {value_name(f(a, b))};")
            lines.append(f"  sub v{a} {op} err by err;")
        lines.append(f"  sub err {op} @NUM by err;")
    lines.append("} CALC;")

    # Each pass fires only at the leftmost match: the 'ignore' rule skips any
    # match that already has a number to its left.
    for i in range(JOIN_PASSES):
        lines += [f"lookup JOIN{i} {{",
                  "  ignore sub @NUM @NUM' @DIG';",
                  "  sub @NUM' lookup JOIN @DIG';",
                  f"}} JOIN{i};"]
    for i in range(OP_PASSES):
        lines += [f"lookup CALC{i} {{",
                  "  ignore sub @NUM @OP @NUM' @OP' @NUM';",
                  "  sub @NUM' lookup CALC @OP' @NUM';",
                  f"}} CALC{i};"]
    # A trailing '=' disappears, so 3+4= shows 7.
    lines.append("lookup EQUAL {")
    lines += [f"  sub {n} equal by {n};" for n in nums + ["err"]]
    lines.append("} EQUAL;")

    passes = [f"JOIN{i}" for i in range(JOIN_PASSES)] + \
             [f"CALC{i}" for i in range(OP_PASSES)] + ["EQUAL"]
    lines.append("feature calt {")
    lines += [f"  lookup {p};" for p in passes]
    lines.append("} calt;")
    return "\n".join(lines)

def build():
    glyphs = {".notdef": TTGlyphPen(None).glyph(), "space": TTGlyphPen(None).glyph()}
    for name in list(OPS) + ["equal"]:
        glyphs[name] = op_glyph(name)
    glyphs["err"] = segs_glyph("AFGED")       # a seven-segment E
    for n in range(10):
        glyphs[f"v{n}"] = segs_glyph(DIGIT_SEGS[n])
    for n in range(10, MAX + 1):
        glyphs[f"v{n}"] = number_glyph(n, glyphs)

    cmap = {0x20: "space", ord("+"): "plus", ord("-"): "minus", 0x2212: "minus",
            ord("*"): "times", ord("x"): "times", ord("X"): "times", 0xD7: "times",
            ord("="): "equal"}
    cmap.update({0x30 + n: f"v{n}" for n in range(10)})
    advances = {"*": ADV}
    advances.update({f"v{n}": 2 * ADV for n in range(10, MAX + 1)})
    font = make_font("SevenSegCalc", glyphs, cmap, advances, ascent=820, descent=180)
    addOpenTypeFeaturesFromString(font, features())
    return save(font, "SevenSegCalc.woff2")

if __name__ == "__main__":
    build()
