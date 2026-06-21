#!/usr/bin/env python3
"""Sync the Advent of Code badge table in index.qmd from the adventofcode repo README.

The repo README (https://github.com/BioGeek/adventofcode) holds one shields.io badge
per year for days-completed and stars. This script fetches that README, parses every
year it finds, and regenerates the table between the AOC:ROWS markers in index.qmd plus
the star total between the AOC:SUMMARY markers.

Because it rebuilds the table from *all* year badges present, new years (2025, 2026, ...)
appear automatically with no code change. Run it directly (`python scripts/update_aoc.py`)
or via the update-aoc GitHub Action; then `quarto render` to rebuild the site.
"""
import re
import sys
import urllib.request

README_URL = "https://raw.githubusercontent.com/BioGeek/adventofcode/{branch}/README.md"
QMD = "index.qmd"
COLOR = "0b5e54"  # site teal, matches the rest of the page

# Badge URLs look like:
#   https://img.shields.io/badge/days%20completed-5-red&year=2024
#   https://img.shields.io/badge/stars%20⭐-10-yellow&year=2024
BADGE_RE = re.compile(r"badge/([^-\s)]+)-(\d+)-\w+&year=(\d+)")


def fetch_readme():
    for branch in ("master", "main"):
        try:
            req = urllib.request.Request(
                README_URL.format(branch=branch),
                headers={"User-Agent": "biogeek-site-sync"},
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8")
        except Exception as e:  # noqa: BLE001
            print(f"fetch {branch} failed: {e}", file=sys.stderr)
    return None


def parse(readme):
    days, stars = {}, {}
    for label, value, year in BADGE_RE.findall(readme):
        year, value = int(year), int(value)
        if label.startswith("days"):
            days[year] = value
        elif label.startswith("stars"):
            stars[year] = value
    return days, stars


def build_rows(days, stars):
    years = sorted(set(days) | set(stars), reverse=True)
    rows = []
    for y in years:
        d, s = days.get(y, 0), stars.get(y, 0)
        db = f"https://img.shields.io/badge/days_completed-{d}-{COLOR}"
        sb = f"https://img.shields.io/badge/stars_%E2%AD%90-{s}-{COLOR}"
        rows.append(
            f'      <tr><td>{y}</td>'
            f'<td><img src="{db}" alt="{d} days completed"></td>'
            f'<td><img src="{sb}" alt="{s} stars"></td></tr>'
        )
    return "\n".join(rows), years, sum(stars.values())


def replace_region(text, start, end, new):
    try:
        s = text.index(start) + len(start)
        e = text.index(end)
    except ValueError:
        raise SystemExit(f"markers {start!r}/{end!r} not found in {QMD}")
    return text[:s] + new + text[e:]


def main():
    readme = fetch_readme()
    if not readme:
        print("could not fetch README; leaving index.qmd unchanged")
        return 0
    days, stars = parse(readme)
    if not days and not stars:
        print("no year badges parsed; leaving index.qmd unchanged")
        return 0

    rows, years, total = build_rows(days, stars)
    qmd = open(QMD, encoding="utf-8").read()
    qmd = replace_region(
        qmd, "<!-- AOC:ROWS:START -->", "<!-- AOC:ROWS:END -->", "\n" + rows + "\n      "
    )
    summary = f"{total} stars across {years[-1]}–{years[0]}"
    qmd = replace_region(
        qmd, "<!-- AOC:SUMMARY:START -->", "<!-- AOC:SUMMARY:END -->", summary
    )
    open(QMD, "w", encoding="utf-8").write(qmd)
    print(f"updated AoC: {len(years)} years ({years[-1]}–{years[0]}), {total} stars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
