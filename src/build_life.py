#!/usr/bin/env python3
"""Build Life.woff2: Conway's Game of Life computed by the font's GSUB table.

The page holds generation 0 as one line of text, written column by column,
top to bottom. For example this 3x2 board:

    . O .        is the text   [.O|O.|..]
    O . .

'.' is a dead cell, 'O' a live one, '|' ends a column, and the brackets mark
the two ends of the board. The TIME axis picks the generation: through
FeatureVariations, TIME=g turns on the lookups for generations 1 to g.

A cell has 8 neighbors, but text is one line. The cells above and below sit
next to it in the text, and the cells to the left and right are a whole
column away (W = ROWS + 1 glyphs, counting the '|'). The board is stored by
column because that walk is the slow part, and a board has fewer rows than
columns. One generation is 3 passes:

  V      v = the cell plus its live neighbors above and below (0 to 3).
  LEFT   x = v + the v of the cell to its left.
  RIGHT  The neighbor count is x + the v of the cell to its right - the cell
         itself, and that decides if the cell lives.

Every cell glyph stores four fields: its previous state p, its current state
c, v, and x. Each pass writes one field, and only when the value changes.
CoreText is slow at substituting glyphs, and most of a board is empty space
whose fields never change. Since no pass reads the field it writes, each rule
sees the same answer from a neighbor, whether that neighbor was already
visited in this pass or not.

At the end one pass gives every cell its row, and a row glyph draws its square
that far down. Only the bottom row has an advance width, so the pen moves one
cell to the right per column.
"""
import copy
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables._f_v_a_r import Axis
from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.varLib import featureVars
from common import make_font, save

COLS, ROWS = 48, 20
GENS = 120          # TIME axis runs 0..GENS, one generation per unit
CELL = 100          # cell size in font units
W = ROWS + 1        # glyphs from a cell to the one on its right

# One glyph per combination of the four fields.
STATES = [(p, c, v, x) for p in (0, 1) for c in (0, 1) for v in range(4) for x in range(7)]
def cell(p, c, v, x): return f"c{p}{c}{v}{x}"
CELLS = [cell(*k) for k in STATES]
def cells(test):
    return [cell(*k) for k in STATES if test(*k)]

# What a finished cell shows, from (previous state, current state).
KINDS = {(0, 0): "empty", (0, 1): "born", (1, 1): "live", (1, 0): "died"}
PALETTE = {"live": "#39ff8a", "born": "#f4ffb8", "died": "#1f6b4a", "empty": "#262d4d"}
SHAPE = {"live": "sq", "born": "sq", "died": "ghost", "empty": "dot"}
SHAPES = {"sq": (7, 16), "ghost": (30, 10), "dot": (44, 6)}   # inset, corner radius

# --------------------------------------------------------------------- glyphs
def square(inset, radius, row):
    """Rounded square inside the cell of `row`, `inset` units from each side."""
    pen = TTGlyphPen(None)
    x0, x1 = inset, CELL - inset
    y0, y1 = -row * CELL + inset, -row * CELL + CELL - inset
    r = radius
    pen.moveTo((x0 + r, y0))
    pen.lineTo((x1 - r, y0)); pen.qCurveTo((x1, y0), (x1, y0 + r))
    pen.lineTo((x1, y1 - r)); pen.qCurveTo((x1, y1), (x1 - r, y1))
    pen.lineTo((x0 + r, y1)); pen.qCurveTo((x0, y1), (x0, y1 - r))
    pen.lineTo((x0, y0 + r)); pen.qCurveTo((x0, y0), (x0 + r, y0))
    pen.closePath()
    return pen.glyph()

def blank():
    return TTGlyphPen(None).glyph()

def build_glyphs():
    # pad, sep, and the cell glyphs come first and in one run, so the class
    # "any glyph" is one range of glyph IDs and cheap to test.
    g = {".notdef": blank(), "pad": blank(), "sep": blank()}
    g.update({n: blank() for n in CELLS})
    g.update({"open": blank(), "close": blank()})
    for r in range(ROWS):
        for shape, (inset, radius) in SHAPES.items():
            g[f"{shape}{r}"] = square(inset, radius, r)
        for kind in PALETTE:
            g[f"{kind}{r}"] = square(*SHAPES[SHAPE[kind]], r)
    return g

# ------------------------------------------------------------------- features
def cls(names):
    return "[" + " ".join(names) + "]"

def lookup(name, rules):
    return f"lookup {name} {{\n  " + "\n  ".join(rules) + f"\n}} {name};"

def setter(name, new):
    """A lookup that rewrites each cell to new(p, c, v, x), skipping cells
    that already hold that value."""
    rules = [f"sub {cell(*k)} by {cell(*new(*k))};" for k in STATES if new(*k) != k]
    return lookup(name, rules)

def features():
    fea = ["languagesystem DFLT dflt;"]

    # Helper lookups, called from the contextual rules below.
    for k in range(3):
        fea.append(setter(f"SETV{k}", lambda p, c, v, x: (p, c, c + k, x)))
    for k in range(4):
        fea.append(setter(f"SETX{k}", lambda p, c, v, x: (p, c, v, v + k)))
    for n in (0, 1):
        fea.append(setter(f"BECOME{n}", lambda p, c, v, x: (c, n, v, x)))
    for r in range(ROWS):
        fea.append(lookup(f"ROW{r}", [f"sub {cell(*k)} by {KINDS[k[:2]]}{r};" for k in STATES]))

    # Each bracket becomes W pads: dead cells left of the first column and
    # right of the last, so LEFT and RIGHT always have a glyph to look at.
    pads = " ".join(["pad"] * W)
    fea.append(lookup("EXPAND", [f"sub open by {pads};", f"sub close by {pads};"]))

    allc = cls(CELLS)
    live = cls(cells(lambda p, c, v, x: c == 1))
    fea.append(lookup("V", [
        f"sub {live} {allc}' lookup SETV2 {live};",
        f"sub {live} {allc}' lookup SETV1;",
        f"sub {allc}' lookup SETV1 {live};",
        f"sub {allc}' lookup SETV0;"]))

    # LEFT: the cell to the left is W glyphs back. Most cells have nothing
    # alive there, so that rule comes first.
    gap = " ".join([cls(["pad", "sep"] + CELLS)] * (W - 1))
    def with_v(ks):
        return cls(cells(lambda p, c, v, x: v in ks) + (["pad"] if 0 in ks else []))
    fea.append(lookup("LEFT", [f"sub {with_v([k])} {gap} {allc}' lookup SETX{k};" for k in (0, 1, 2)]
                      + [f"sub {allc}' lookup SETX3;"]))

    # RIGHT: the cell to the right is W glyphs ahead. A cell lives with 3
    # neighbors, or with 2 if it is alive now.
    groups = {}
    for c in (0, 1):
        for x in range(7):
            ok = tuple(k for k in range(4) if (t := x + k - c) == 3 or (c == 1 and t == 2))
            if ok:
                groups.setdefault(ok, []).extend(cells(lambda p, cc, v, xx: (cc, xx) == (c, x)))
    fea.append(lookup("RIGHT", [f"sub {cls(me)}' lookup BECOME1 {gap} {with_v(ok)};"
                                for ok, me in groups.items()]
                      + [f"sub {allc}' lookup BECOME0;"]))

    # Rows: a column starts at row 0 after the pads or a '|'.
    rows = [f"sub [pad sep] {allc}' lookup ROW0;"]
    for r in range(ROWS - 1):
        rows.append(f"sub {cls([f'{k}{r}' for k in PALETTE])} {allc}' lookup ROW{r + 1};")
    fea.append(lookup("ROWS", rows))

    fea.append("feature calt { lookup EXPAND; lookup ROWS; } calt;")
    return "\n".join(fea)

def add_generations(font):
    """Copy the V, LEFT, and RIGHT lookups once per generation and let TIME=g
    turn on generations 1..g through FeatureVariations. A lookup cannot just
    be listed twice: shapers run each lookup index at most once."""
    gsub = font["GSUB"].table
    lookups = gsub.LookupList.Lookup
    # feaLib keeps the written order: helpers, EXPAND, V, LEFT, RIGHT, ROWS.
    expand_i = len(lookups) - 5
    step, rows = lookups[-4:-1], lookups[-1]
    del lookups[-4:]
    gens = []
    for g in range(GENS):
        gens.append(list(range(len(lookups), len(lookups) + 3)))
        lookups.extend(copy.copy(l) for l in step)
    lookups.append(rows)
    rows_i = len(lookups) - 1
    gsub.LookupList.LookupCount = len(lookups)

    calt = [i for i, fr in enumerate(gsub.FeatureList.FeatureRecord) if fr.FeatureTag == "calt"]
    assert len(calt) == 1
    feature = gsub.FeatureList.FeatureRecord[calt[0]].Feature
    feature.LookupListIndex, feature.LookupCount = [expand_i, rows_i], 2
    records = []
    for g in range(1, GENS + 1):
        lo, hi = (g - 0.5) / GENS, min(1.0, (g + 0.5) / GENS)
        idx = [expand_i] + [i for gen in gens[:g] for i in gen] + [rows_i]
        records.append(featureVars.buildFeatureVariationRecord(
            [featureVars.buildConditionTable(0, lo, hi)],
            [featureVars.buildFeatureTableSubstitutionRecord(calt[0], idx)]))
    gsub.FeatureVariations = featureVars.buildFeatureVariations(records)
    gsub.Version = 0x00010001

def add_fvar(font):
    axis = Axis()
    axis.axisTag, axis.minValue, axis.defaultValue, axis.maxValue = "TIME", 0, 0, GENS
    axis.axisNameID = font["name"].addMultilingualName({"en": "Generation"}, font)
    fvar = newTable("fvar")
    fvar.axes, fvar.instances = [axis], []
    font["fvar"] = fvar

def add_colors(font):
    # COLRv0 flat layers, which every browser draws (Safari has no COLRv1).
    kinds = list(PALETTE)
    font["COLR"] = buildCOLR({f"{k}{r}": [(f"{SHAPE[k]}{r}", kinds.index(k))]
                              for r in range(ROWS) for k in kinds}, version=0)
    font["CPAL"] = buildCPAL([[tuple(int(PALETTE[k][i:i + 2], 16) / 255 for i in (1, 3, 5))
                               + (1.0,) for k in kinds]])

def build():
    glyphs = build_glyphs()
    cmap = {ord("."): cell(0, 0, 0, 0), ord("O"): cell(1, 1, 1, 1),
            ord("|"): "sep", ord("["): "open", ord("]"): "close"}
    # Only a bottom-row cell moves the pen, one cell to the right.
    advances = {"*": 0, **{f"{k}{ROWS - 1}": CELL for k in PALETTE}}
    font = make_font("Life", glyphs, cmap, advances, ascent=CELL, descent=(ROWS - 1) * CELL)
    add_fvar(font)
    addOpenTypeFeaturesFromString(font, features())
    add_generations(font)
    add_colors(font)
    save(font, "Life.woff2", f" ({COLS}x{ROWS} board, {GENS} generations)")
    return font

if __name__ == "__main__":
    build()
