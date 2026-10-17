#!/usr/bin/env python3
"""Build every font into docs/fonts/, then the site pages.  python3 src/build_all.py"""
import build_calc, build_cube, build_life, build_plasma, build_site, build_terrain

for module in (build_terrain, build_plasma, build_cube, build_calc, build_life):
    module.build()
build_site.build()
