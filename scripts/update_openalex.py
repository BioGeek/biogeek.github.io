#!/usr/bin/env python3
"""Sync citation metrics from OpenAlex into index.qmd and data/openalex.json.

Fetches author metrics (total citations, h-index, i10-index, citations per year)
by ORCID from the free OpenAlex API (no key; an email puts us in the polite
pool), builds a tiny inline-SVG citations-per-year sparkline, and rewrites the
content between these markers in index.qmd:

    <!-- OPENALEX:START --> ... <!-- OPENALEX:END -->

Add that once, inside a raw-HTML block in the Publications section, e.g.:

    ```{=html}
    <p class="pub-metrics"><!-- OPENALEX:START --><!-- OPENALEX:END --></p>
    ```

Run via the update-openalex GitHub Action (or `make openalex`), then quarto render.
"""
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ORCID = "0000-0003-4480-5567"
QMD = "index.qmd"
DATA = "data/openalex.json"
MAILTO = "jeroen.vangoey@gmail.com"          # OpenAlex "polite pool"
TEAL = "#0b5e54"
MARKERS = re.compile(r"(<!-- OPENALEX:START -->).*?(<!-- OPENALEX:END -->)", re.S)


def get(url, retries=4):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"biogeek-site ({MAILTO})"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (429, 503) and attempt < retries - 1:
                import time
                time.sleep(2 ** attempt * 3)   # 3s, 6s, 12s backoff
                continue
            raise
    raise last


def sparkline(counts_by_year, n=8):
    """Inline SVG bar sparkline of citations received per year."""
    years = sorted(counts_by_year, key=lambda c: c["year"])[-n:]
    if not years:
        return ""
    vals = [c["cited_by_count"] for c in years]
    mx = max(vals) or 1
    bw, gap, h = 9, 3, 26
    bars = "".join(
        f'<rect x="{i*(bw+gap)}" y="{h-round(h*v/mx)}" width="{bw}" '
        f'height="{round(h*v/mx)}" rx="1" fill="{TEAL}">'
        f'<title>{c["year"]}: {v} citations</title></rect>'
        for i, (c, v) in enumerate(zip(years, vals)))
    w = len(vals) * (bw + gap)
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'style="vertical-align:-0.4em;margin:0 .4rem" role="img" '
            f'aria-label="Citations per year">{bars}</svg>')


def main():
    author = get(f"https://api.openalex.org/authors/https://orcid.org/{ORCID}?mailto={MAILTO}")
    stats = author.get("summary_stats", {})
    cited = author.get("cited_by_count", 0)
    h_index = stats.get("h_index", 0)
    i10 = stats.get("i10_index", 0)
    counts = author.get("counts_by_year", [])

    # Per-work citation counts (handy for future per-paper badges).
    works_url = ("https://api.openalex.org/works?"
                 + urllib.parse.urlencode({
                     "filter": f"author.orcid:{ORCID}",
                     "per_page": 200, "sort": "cited_by_count:desc",
                     "select": "title,publication_year,cited_by_count,doi",
                     "mailto": MAILTO}))
    works = [{"title": w["title"], "year": w.get("publication_year"),
              "doi": w.get("doi"), "cited_by_count": w.get("cited_by_count", 0)}
             for w in get(works_url).get("results", [])]

    now = datetime.now(timezone.utc)
    h_tip = (f'If you have an h-index of {h_index}, it means you have published '
             f'at least {h_index} papers that have each received {h_index} or '
             f'more citations')
    i10_tip = (f'If you have an i10-index of {i10}, it means you have published '
               f'{i10} papers that have each received 10 or more citations')
    strip = (f'<strong>{cited}</strong> citations &middot; '
             f'<span class="h-index-term" tabindex="0" role="note" '
             f'aria-label="{h_tip}" data-tip="{h_tip}">h-index</span> '
             f'<strong>{h_index}</strong> &middot; '
             f'<span class="h-index-term" tabindex="0" role="note" '
             f'aria-label="{i10_tip}" data-tip="{i10_tip}">i10</span> '
             f'<strong>{i10}</strong>{sparkline(counts)}'
             f'<span style="color:#888;font-size:.8rem">via OpenAlex, {now:%b %Y}</span>')

    # 1) Inject the metrics strip into index.qmd between the markers.
    text = open(QMD, encoding="utf-8").read()
    if not MARKERS.search(text):
        raise SystemExit("OPENALEX markers not found in index.qmd (see this script's docstring).")
    new = MARKERS.sub(lambda m: m.group(1) + strip + m.group(2), text)
    if new != text:
        open(QMD, "w", encoding="utf-8").write(new)
        print(f"Updated index.qmd: {cited} citations, h-index {h_index}, i10 {i10}.")
    else:
        print(f"index.qmd unchanged ({cited} citations).")

    # 2) Write the full data file for future use (per-paper badges, etc.).
    import os
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    with open(DATA, "w", encoding="utf-8") as fh:
        json.dump({
            "generated_at": now.isoformat(timespec="seconds"),
            "orcid": ORCID,
            "cited_by_count": cited,
            "works_count": author.get("works_count"),
            "h_index": h_index,
            "i10_index": i10,
            "counts_by_year": counts,
            "works": works,
        }, fh, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
