#!/usr/bin/env python3
"""The two MD5 fonts. Each one computes the MD5 hash of the text it shapes and
draws it as 32 hex digits, for a different text engine:

- MD5Safari.woff2 runs in Safari. It is an AAT `morx` font: 2,690 state
  machines grow the text into a tape of one glyph per bit, then add, rotate,
  and copy bits along it.
- MD5Graphite.woff2 runs in Firefox. It is a Graphite font: its rules keep the
  MD5 words as integers on one glyph and revisit that glyph 128 times.

The builders are in src/md5/. They write TrueType files next to themselves,
and this script saves them as WOFF2 in docs/fonts/.

The Safari font needs only fontTools. The Firefox font also needs SIL's
Graphite compiler with a small patch, which src/md5/prepare_compiler.py
downloads and builds (it needs git, CMake, a C++ compiler, and ICU). Without
the compiler, this script keeps the MD5Graphite.woff2 already in docs/fonts/.
"""
import os
import sys
from fontTools.ttLib import TTFont
from common import save

MD5 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "md5")
sys.path.insert(0, MD5)      # the builders import each other by module name
import build_md5, build_safari_md5

COMPILER = os.environ.get("GRCOMPILER", "/tmp/md5-grcompiler/build/compiler/grcompiler")

def build():
    build_safari_md5.build()
    save(TTFont(os.path.join(MD5, "MD5Safari.ttf")), "MD5Safari.woff2")
    if os.path.exists(COMPILER):
        build_md5.build()
        save(TTFont(os.path.join(MD5, "MD5Graphite.ttf")), "MD5Graphite.woff2")
    else:
        print(f"kept docs/fonts/MD5Graphite.woff2: no Graphite compiler at {COMPILER}"
              " (run src/md5/prepare_compiler.py, or set GRCOMPILER)")

if __name__ == "__main__":
    build()
