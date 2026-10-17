#!/usr/bin/env python3
"""Take the 1200 x 630 images that social sites show for a shared link.

    pip install playwright && python3 -m playwright install chromium
    python3 src/build_previews.py

Each image is a screenshot of a card: the page title and a one-line
description at the top, and below them the demo's preview page, frozen at a
good moment. The gallery's card shows all five demos. The images go to
docs/preview.png and docs/<slug>/preview.png, and every page links its image
through its og:image tag. The images are only for link sharing: the demos
themselves draw everything with fonts.

Run it again after changing a demo. Chromium is used because it draws COLRv1.
"""
import os
from playwright.sync_api import sync_playwright
from build_site import DEMOS, GALLERY_DESC, SITE_NAME
from check_layout import serve
from common import SITE

CARD = """<!doctype html>
<meta charset="utf-8" />
<style>
  body {{
    margin: 0;
    width: 1200px;
    height: 630px;
    overflow: hidden;
    background: radial-gradient(1100px 760px at 50% -8%, #1c1236, #05060c 62%) #05060c;
    font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
  }}
  h1 {{
    margin: 40px 0 0;
    text-align: center;
    font-size: 54px;
    font-weight: 750;
    background: linear-gradient(90deg, #ff8a3d, #ff4d7d, #9b6bff, #38e8c0);
    -webkit-background-clip: text;
    color: transparent;
  }}
  p {{ margin: 6px 0 0; text-align: center; font-size: 25px; color: #9aa3c7; }}
  .scenes {{
    position: absolute;
    inset: 172px 24px 24px;
    display: grid;
    gap: 12px;
    grid-template-columns: {columns};
  }}
  iframe {{ width: 100%; height: 100%; border: 0; border-radius: 14px; }}
  .wide {{ grid-column: span 2; }}
</style>
<h1>{title}</h1>
<p>{desc}</p>
<div class="scenes">{frames}</div>
"""

def card(title, desc, demos):
    """The card's HTML: one frame per demo. On the gallery's card, the wide
    demo spans two of the three columns, as in the gallery."""
    frames = "".join(f'<iframe class="{"wide" if len(demos) > 1 and d.get("wide") else ""}" '
                     f'src="{d["slug"]}/hero.html"></iframe>' for d in demos)
    return CARD.format(title=title, desc=desc, frames=frames,
                       columns="1fr 1fr 1fr" if len(demos) > 1 else "1fr")

def main():
    base = serve()
    cards = [("preview.png", SITE_NAME, GALLERY_DESC, DEMOS)]
    cards += [(f"{d['slug']}/preview.png", d["title"], d["card_desc"], [d]) for d in DEMOS]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 630})
        for out, title, desc, demos in cards:
            # Serve the card from the site's own origin, so its frames load and
            # this script can reach into them.
            html = card(title, desc, demos)
            page.route(base + "card.html", lambda route: route.fulfill(
                body=html, content_type="text/html"))
            page.goto(base + "card.html")
            page.wait_for_timeout(1000)
            for frame, demo in zip(page.frames[1:], demos):
                frame.evaluate("""ms => document.getAnimations().forEach(a => {
                    a.pause(); a.currentTime = ms; })""", demo["preview_ms"])
            page.wait_for_timeout(300)
            page.screenshot(path=os.path.join(SITE, out))
            page.unroute(base + "card.html")
            print(f"wrote docs/{out} ({os.path.getsize(os.path.join(SITE, out)):,} bytes)")
        browser.close()

if __name__ == "__main__":
    main()
