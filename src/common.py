"""Helpers shared by the font build scripts."""
import os
from fontTools.fontBuilder import FontBuilder
from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor
from fontTools.varLib import build as varbuild

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "docs")      # the published site
FONTS = os.path.join(SITE, "fonts")
VISIBLE_ASCII = range(0x21, 0x7F)

def make_font(family, glyphs, cmap, advances, ascent, descent, cff=False):
    """Build one static font in memory. `glyphs` maps glyph name to a TrueType
    glyph (or a CFF charstring when cff=True), in glyph order. `advances` maps
    glyph name to advance width; glyphs not listed get advances["*"]."""
    order = list(glyphs)
    fb = FontBuilder(1000, isTTF=not cff)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    if cff:
        fb.setupCFF(family, {"FullName": family}, glyphs, {})
        charstrings = fb.font["CFF "].cff.topDictIndex[0].CharStrings
        bounds = {g: charstrings[g].calcBounds(charstrings) for g in order}
        lsb = {g: round(b[0]) if b else 0 for g, b in bounds.items()}
    else:
        fb.setupGlyf(glyphs)
        glyf = fb.font["glyf"]
        for g in order:
            glyf[g].recalcBounds(glyf)
        lsb = {g: getattr(glyf[g], "xMin", 0) for g in order}
    # The left side bearing must equal xMin. FreeType places a TrueType glyph
    # at xMin - lsb, so a wrong lsb shifts the drawing away from its bounds.
    fb.setupHorizontalMetrics({g: (advances.get(g, advances["*"]), lsb[g]) for g in order})
    fb.setupHorizontalHeader(ascent=ascent, descent=-descent)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=ascent, sTypoDescender=-descent,
                usWinAscent=ascent, usWinDescent=descent)
    fb.setupPost()
    return fb.font

def make_variable(tag, name, masters):
    """Merge in-memory masters into one variable font with a single axis.
    `masters` is a list of (axis value, font); the first value is the default."""
    doc = DesignSpaceDocument()
    axis = AxisDescriptor()
    axis.tag, axis.name = tag, name
    axis.minimum = axis.default = masters[0][0]
    axis.maximum = masters[-1][0]
    doc.addAxis(axis)
    for value, font in masters:
        src = SourceDescriptor()
        src.font, src.location = font, {name: value}
        doc.addSource(src)
    vf, _, _ = varbuild(doc)
    return vf

def save(font, filename, note=""):
    """Save into docs/fonts/. A .woff2 name compresses the font (needs `brotli`)."""
    os.makedirs(FONTS, exist_ok=True)
    path = os.path.join(FONTS, filename)
    font.flavor = "woff2" if filename.endswith(".woff2") else None
    font.save(path)
    print(f"wrote docs/fonts/{filename} ({os.path.getsize(path):,} bytes){note}")
    return path
