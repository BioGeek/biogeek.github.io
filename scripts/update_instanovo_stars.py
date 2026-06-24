#!/usr/bin/env python3
"""Sync the InstaNovo GitHub star count into index.qmd.

Fetches stargazers_count from the GitHub API and rewrites the count in the
InstaNovo "Code (N stars)" badge. Run via the update-instanovo-stars GitHub
Action (or manually), then `quarto render`.
"""
import json
import os
import re
import urllib.request

REPO = "instadeepai/InstaNovo"
QMD = "index.qmd"
API = f"https://api.github.com/repos/{REPO}"
# Matches the count inside: ...InstaNovo"><i class="bi bi-github"></i> Code (N <star icon>)
BADGE = re.compile(r'(instadeepai/InstaNovo"><i class="bi bi-github"></i> Code \()\d+( <i class="bi bi-star-fill"></i>\))')


def fetch_stars():
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "biogeek-site"}
    token = os.environ.get("GITHUB_TOKEN")  # higher rate limit inside Actions
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return int(json.load(resp)["stargazers_count"])


def main():
    stars = fetch_stars()
    text = open(QMD, encoding="utf-8").read()
    if not BADGE.search(text):
        raise SystemExit("InstaNovo 'Code (N stars)' badge not found in index.qmd")
    new = BADGE.sub(rf"\g<1>{stars}\g<2>", text)
    if new != text:
        open(QMD, "w", encoding="utf-8").write(new)
        print(f"Updated InstaNovo stars to {stars}")
    else:
        print(f"InstaNovo stars unchanged ({stars})")


if __name__ == "__main__":
    main()
