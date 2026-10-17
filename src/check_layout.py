#!/usr/bin/env python3
"""Check that no text or box sticks out of its container, on every page.

    pip install playwright && python3 -m playwright install
    python3 src/check_layout.py [--engines chromium,firefox,webkit] [--widths 320,390,768,1280,1920]

The script serves the site itself on a free port, loads the gallery and every
demo page at each window width, and also checks each gallery preview inside its
card. It prints each problem and exits with status 1 if it found any. For
example, a long line that does not wrap prints:

    firefox 390 /life/
      SPILL code#holds: content 1715px wide, box 324px "[......|..OO..."
"""
import argparse, functools, http.server, os, sys, threading
from playwright.sync_api import sync_playwright
from build_site import DEMOS, ROOT

# Runs in the page (or in a preview frame) and returns a list of problems.
FIND = r"""() => {
  const out = [];
  const vw = document.documentElement.clientWidth;
  const text = el => (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40);
  const name = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
    + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/).join('.') : '');
  if (document.documentElement.scrollWidth > vw + 1)
    out.push(`PAGE: content ${document.documentElement.scrollWidth}px wide, window ${vw}px`);
  for (const el of document.querySelectorAll('body *')) {
    if (['SCRIPT', 'STYLE', 'IFRAME'].includes(el.tagName)) continue;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (cs.display === 'none' || r.width === 0) continue;
    if (r.right > vw + 1 || r.left < -1)
      out.push(`OFFSCREEN ${name(el)}: spans ${r.left.toFixed(0)}px to ${r.right.toFixed(0)}px, window ${vw}px "${text(el)}"`);
    if (el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1 && !['auto', 'scroll', 'hidden', 'clip'].includes(cs.overflowX))
      out.push(`SPILL ${name(el)}: content ${el.scrollWidth}px wide, box ${el.clientWidth}px "${text(el)}"`);
  }
  // A line of text that runs past the right edge of its own element.
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = walk.nextNode());) {
    const el = n.parentElement;
    if (!n.textContent.trim() || ['SCRIPT', 'STYLE'].includes(el.tagName)) continue;
    const range = document.createRange();
    range.selectNodeContents(n);
    const box = el.getBoundingClientRect();
    if ([...range.getClientRects()].some(r => r.right > box.right + 1))
      out.push(`TEXT-OUT ${name(el)}: text passes the right edge "${n.textContent.trim().slice(0, 40)}"`);
  }
  return [...new Set(out)];
}"""

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

def serve():
    handler = functools.partial(Quiet, directory=ROOT)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/"

def check(page, base, path):
    """Problems on one page, plus those inside its preview frames."""
    page.goto(base + path)
    page.wait_for_timeout(500)
    found = {"": page.evaluate(FIND)}
    # The gallery previews load lazily, so scroll each card into view first.
    for frame in page.locator("iframe").all():
        frame.scroll_into_view_if_needed()
        handle = frame.element_handle().content_frame()
        handle.wait_for_load_state()
        found[" preview " + handle.url.removeprefix(base)] = handle.evaluate(FIND)
    return found

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--engines", default="chromium,firefox,webkit")
    ap.add_argument("--widths", default="320,390,768,1280,1920")
    args = ap.parse_args()
    base = serve()
    paths = [""] + [d["slug"] + "/" for d in DEMOS]
    bad = previews = 0
    with sync_playwright() as p:
        for engine in args.engines.split(","):
            browser = getattr(p, engine).launch()
            for width in map(int, args.widths.split(",")):
                page = browser.new_page(viewport={"width": width, "height": 900})
                for path in paths:
                    found = check(page, base, path)
                    previews += len(found) - 1
                    for where, problems in found.items():
                        if problems:
                            print(f"{engine} {width} /{path}{where}")
                            for line in problems:
                                print("  " + line)
                            bad += len(problems)
                page.close()
            browser.close()
            print(f"{engine}: checked {len(paths)} pages and {previews} previews"
                  f" at widths {args.widths}")
            previews = 0
    print(f"{bad} problem(s)" if bad else "no layout problems")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
