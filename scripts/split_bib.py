#!/usr/bin/env python3
"""Split publications.bib into one downloadable .bib file per entry.

Writes files/bib/<citekey>.bib for every entry, so each publication card can
offer a "BibTeX" download. Run after editing publications.bib:
    python scripts/split_bib.py
"""
import os
import re

SRC = "publications.bib"
OUT_DIR = "files/bib"

os.makedirs(OUT_DIR, exist_ok=True)
text = open(SRC, encoding="utf-8").read()

# Each entry: @type{key, ... } with the closing brace on its own line.
entries = re.findall(r"@\w+\{([^,]+),.*?\n\}", text, re.S)
matches = re.findall(r"(@\w+\{[^,]+,.*?\n\})", text, re.S)

count = 0
for entry in matches:
    key = re.match(r"@\w+\{([^,]+),", entry).group(1).strip()
    with open(os.path.join(OUT_DIR, f"{key}.bib"), "w", encoding="utf-8") as f:
        f.write(entry.strip() + "\n")
    count += 1
    print("wrote", f"{OUT_DIR}/{key}.bib")

print(f"{count} .bib files written")
