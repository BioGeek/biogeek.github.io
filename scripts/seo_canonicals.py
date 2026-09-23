#!/usr/bin/env python3
"""Post-render SEO tidy-up for the jeroen.vangoey.be site.

Quarto 1.9.38 does not emit a <link rel="canonical">, and its sitemap lists the
".../index.html" form of pages while GitHub Pages also serves the clean ".../"
form. Google then reports "Duplicate without user-selected canonical" and leaves
the /index.html copy unindexed. Run as a Quarto post-render step, this rewrites
the built docs/ to fix both:

1. Inject a self-referencing <link rel="canonical"> into every page, in the
   clean URL form (index.html -> directory; other pages keep their .html).
2. Rewrite sitemap.xml to those same clean URLs.

The built docs/ is regenerated on every render, so this simply runs each build.
Redirect stubs (i/) and the 404 page are skipped so they carry no self-canonical.
"""
import glob
import os
import re

SITE = "https://jeroen.vangoey.be"
DOCS = "docs"
SKIP_FILES = {"404.html"}
SKIP_DIRS = ("i/",)


def canonical_url(rel_url):
    """docs-relative html path (forward slashes) -> canonical URL (clean form)."""
    if rel_url == "index.html":
        return SITE + "/"
    if rel_url.endswith("/index.html"):
        return f"{SITE}/{rel_url[:-len('index.html')]}"
    return f"{SITE}/{rel_url}"


def inject_canonicals():
    n = 0
    for path in glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True):
        rel_url = os.path.relpath(path, DOCS).replace(os.sep, "/")
        if rel_url in SKIP_FILES or rel_url.startswith(SKIP_DIRS):
            continue
        html = open(path, encoding="utf-8").read()
        if 'rel="canonical"' in html or "<head>" not in html:
            continue
        tag = f'<link rel="canonical" href="{canonical_url(rel_url)}">\n'
        open(path, "w", encoding="utf-8").write(html.replace("<head>", "<head>\n" + tag, 1))
        n += 1
    print(f"seo_canonicals: added canonical to {n} page(s).")


def normalize_sitemap():
    sm = os.path.join(DOCS, "sitemap.xml")
    if not os.path.exists(sm):
        return
    text = open(sm, encoding="utf-8").read()
    new = re.sub(r"/index\.html</loc>", "/</loc>", text)
    if new != text:
        open(sm, "w", encoding="utf-8").write(new)
        print("seo_canonicals: normalized sitemap.xml to clean URLs.")
    else:
        print("seo_canonicals: sitemap.xml already clean.")


if __name__ == "__main__":
    inject_canonicals()
    normalize_sitemap()
