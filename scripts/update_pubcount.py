#!/usr/bin/env python3
"""Keep the "N publications" count in index.qmd in sync with the cards listed.

Counts the publication cards in the "## Publications" section of index.qmd and
rewrites the number between these markers:

    <!-- PUBCOUNT:START -->N<!-- PUBCOUNT:END -->

Wired as a Quarto pre-render step in _quarto.yml, so the number is recomputed on
every build (local and CI) and can never drift when a publication is added or
removed. The Projects/Photography/Hackathons sections reuse the `.pub-card`
style but live under other level-2 headings, so only cards between the
"## Publications" heading and the next "## " heading are counted.

The write is skipped when the number is already correct, so `quarto preview`
(which re-renders on file changes) does not loop.
"""
import re

QMD = "index.qmd"
MARKERS = re.compile(r"(<!-- PUBCOUNT:START -->).*?(<!-- PUBCOUNT:END -->)", re.S)


def publications_section(text):
    """The slice of index.qmd from '## Publications' to the next '## ' heading."""
    m = re.search(r"^## Publications\b", text, re.M)
    if not m:
        raise SystemExit("update_pubcount: '## Publications' heading not found.")
    start = m.end()
    nxt = re.search(r"^## ", text[start:], re.M)
    end = start + nxt.start() if nxt else len(text)
    return text[start:end]


def main():
    text = open(QMD, encoding="utf-8").read()
    if not MARKERS.search(text):
        raise SystemExit("update_pubcount: PUBCOUNT markers not found in index.qmd.")
    count = len(re.findall(r'<div class="pub-card', publications_section(text)))
    new = MARKERS.sub(lambda m: f"{m.group(1)}{count}{m.group(2)}", text)
    if new != text:
        open(QMD, "w", encoding="utf-8").write(new)
        print(f"update_pubcount: set publications count to {count}.")
    else:
        print(f"update_pubcount: count unchanged ({count}).")


if __name__ == "__main__":
    main()
