#!/usr/bin/env python3
"""Subset Quarto's bundled Bootstrap Icons to only the glyphs the site uses.

Quarto ships the full Bootstrap Icons set on every page: a ~98 KB CSS file
defining ~2000 icon classes and a ~177 KB `bootstrap-icons.woff` font with all
their glyphs. Both are on the render-blocking critical path, yet the site uses
fewer than 50 icons. On mobile that wasted ~270 KB noticeably delays First
Contentful Paint / Largest Contentful Paint.

This runs as a Quarto post-render step, after `quarto render` has written the
full files into `docs/site_libs/bootstrap/`. It:

  1. scans the built output -- every `docs/**/*.html` AND Quarto's own
     `docs/site_libs/**/*.js` (some icons, e.g. the code-copy clipboard and the
     callout carets, are injected at runtime) -- for `bi-<name>` class tokens;
  2. keeps only those icons' `.bi-<name>::before { content: "\\fXXXX" }` rules;
  3. subsets `bootstrap-icons.woff` to just those codepoints with fontTools;
  4. rewrites `bootstrap-icons.css` with the trimmed rules and a fresh
     cache-busting hash on the font URL.

Because it discovers the used icons from the rendered HTML/JS, it needs no
hand-maintained allow-list: add or remove a `bi bi-*` icon anywhere and the next
build's subset follows automatically. It starts from whatever `quarto render`
wrote, so CI (a clean render) always subsets from the full set.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

DOCS = Path(__file__).resolve().parent.parent / "docs"
CSS = DOCS / "site_libs" / "bootstrap" / "bootstrap-icons.css"
FONT = DOCS / "site_libs" / "bootstrap" / "bootstrap-icons.woff"

# `.bi-github::before { content: "\f3ed"; }`
RULE_RE = re.compile(
    r"\.(bi-[a-z0-9]+(?:-[a-z0-9]+)*)::before\s*\{\s*content:\s*\"\\([0-9a-fA-F]+)\";\s*\}"
)
# A `bi-foo-bar` class token as it appears in HTML class="" or in JS strings.
TOKEN_RE = re.compile(r"bi-[a-z0-9]+(?:-[a-z0-9]+)*")
# The font URL inside the @font-face src, with its cache-busting query.
SRC_RE = re.compile(r'url\("\./bootstrap-icons\.woff(?:\?[0-9a-fA-F]+)?"\)')


def used_icons() -> set[str]:
    """Every `bi-<name>` token in the rendered HTML and in Quarto's own JS."""
    tokens: set[str] = set()
    for html in DOCS.rglob("*.html"):
        tokens |= set(TOKEN_RE.findall(html.read_text(encoding="utf-8", errors="ignore")))
    for js in (DOCS / "site_libs").rglob("*.js"):
        tokens |= set(TOKEN_RE.findall(js.read_text(encoding="utf-8", errors="ignore")))
    return tokens


def main() -> int:
    if not CSS.exists() or not FONT.exists():
        print(f"subset_bootstrap_icons: {CSS} or {FONT} missing; skipping.")
        return 0

    css = CSS.read_text(encoding="utf-8")
    rules = RULE_RE.findall(css)  # [(name, hexcodepoint), ...]
    if not rules:
        # Already subsetted to the point of being unparseable, or format changed.
        print("subset_bootstrap_icons: no icon rules found; leaving file as is.")
        return 0

    available = {name: int(cp, 16) for name, cp in rules}
    wanted = used_icons() & available.keys()
    missing = {t for t in used_icons() if t.startswith("bi-")} - available.keys()
    if missing:
        # A used icon with no glyph in this CSS. In a clean render this cannot
        # happen; in a dirty incremental local build it means the CSS was already
        # subset without this icon -- warn, do not subset further (keep full-ish).
        print(
            "subset_bootstrap_icons: WARNING, used icons absent from the font: "
            f"{sorted(missing)}. Run a clean `quarto render`. Skipping subset.",
            file=sys.stderr,
        )
        return 0

    codepoints = sorted(available[name] for name in wanted)

    # Subset the font to just those codepoints.
    font = TTFont(str(FONT))
    options = subset.Options()
    options.flavor = "woff"
    options.desubroutinize = True
    options.drop_tables += ["GSUB", "GPOS", "GDEF"]  # icon font needs no shaping
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)
    font.flavor = "woff"
    font.save(str(FONT))

    new_hash = hashlib.md5(FONT.read_bytes()).hexdigest()[:16]

    # Preserve the header (comment + @font-face + the generic `.bi::before` base
    # rule): everything before the first per-icon rule. Refresh the font URL hash.
    first_rule = RULE_RE.search(css)
    header = css[: first_rule.start()].rstrip()
    header = SRC_RE.sub(f'url("./bootstrap-icons.woff?{new_hash}")', header)

    kept = "\n".join(
        f'.{name}::before {{ content: "\\{cp:x}"; }}'
        for name, cp in sorted((n, available[n]) for n in wanted)
    )
    CSS.write_text(f"{header}\n{kept}\n", encoding="utf-8")

    print(
        f"subset_bootstrap_icons: kept {len(wanted)} of {len(available)} icons; "
        f"font {FONT.stat().st_size // 1024} KB, css {CSS.stat().st_size // 1024} KB."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
