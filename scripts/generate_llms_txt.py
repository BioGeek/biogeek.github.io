#!/usr/bin/env python3
"""Regenerate llms.txt from the site's own Quarto source files.

llms.txt (see https://llmstxt.org/) is a plaintext/Markdown index that gives
LLMs a curated map of the site: a short summary plus grouped links, without
having to crawl and parse the full rendered HTML.

This script rebuilds it from the qmd front matter already on disk (title,
description/subtitle, date, draft) rather than hand-maintaining a duplicate
list, so it can't drift from the real site structure. Draft posts (the
`draft: true` used to keep in-progress posts unpublished) are skipped, same
as the Writing page listing. Run it directly (`python scripts/generate_llms_txt.py`)
or via the update-llms-txt GitHub Action, which re-runs it whenever a .qmd
file or _quarto.yml changes and commits the result if it differs.
"""
import html
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

# Experience entries: "::: {.experience-entry ...}\n### <img .../> [Company](url)\n**Position**\\\n<i ...calendar3...></i> _Date range_\\"
EXPERIENCE_RE = re.compile(
    r"::: \{\.experience-entry[^}]*\}\n"
    r"### .*?\[([^\]]+)\]\([^)]+\)\n"
    r"\*\*([^*]+)\*\*\\\n"
    r'<i class="bi bi-calendar3"></i> _([^_]+)_\\'
)

# Publication cards: "<div class=\"pub-title\"><a href=\"URL\">Title</a></div>" followed
# later by "<div class=\"pub-venue\">Venue text</div>" for the same card, both in order.
PUB_TITLE_RE = re.compile(r'<div class="pub-title"><a href="([^"]+)">(.*?)</a></div>', re.DOTALL)
PUB_VENUE_RE = re.compile(r'<div class="pub-venue">(.*?)</div>', re.DOTALL)


def front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}


def site_url() -> str:
    config = yaml.safe_load((ROOT / "_quarto.yml").read_text(encoding="utf-8"))
    return config["website"]["site-url"].rstrip("/")


def blurb(meta: dict) -> str:
    return (meta.get("description") or meta.get("subtitle") or "").strip()


def strip_tags(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def pandoc_slug(text: str) -> str:
    """Approximate Quarto/Pandoc's auto-generated heading id for anchor links."""
    text = text.lower()
    text = re.sub(r"[^\w\s.-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"^[^a-zà-\U0010ffff]+", "", text)
    return text or "section"


def section_body(text: str, heading: str, next_heading: str) -> str:
    return text.split(f"\n## {heading}\n", 1)[1].split(f"\n## {next_heading}\n", 1)[0]


def collect_experience(base_url: str, index_text: str) -> list[str]:
    body = section_body(index_text, "Experience", "Education")
    return [
        bullet(company, f"{base_url}/#{pandoc_slug(company)}", f"{position.strip()} — {dates.strip()}")
        for company, position, dates in EXPERIENCE_RE.findall(body)
    ]


def collect_publications(base_url: str, index_text: str) -> list[str]:
    body = section_body(index_text, "Publications", "Experience")
    titles = PUB_TITLE_RE.findall(body)
    venues = PUB_VENUE_RE.findall(body)
    entries = []
    for (url, title), venue in zip(titles, venues):
        if not url.startswith("http"):
            url = f"{base_url}/{url}"
        entries.append(bullet(strip_tags(title), url, strip_tags(venue)))
    return entries


def bullet(title: str, url: str, description: str) -> str:
    title = title.strip()
    if description:
        # llms.txt entries are one line each; collapse any wrapped YAML text.
        description = " ".join(description.split())
        return f"- [{title}]({url}): {description}"
    return f"- [{title}]({url})"


def collect_posts(base_url: str) -> list[tuple[str, dict]]:
    posts = []
    for post_dir in sorted((ROOT / "posts").iterdir()):
        qmd = post_dir / "index.qmd"
        if not qmd.exists():
            continue
        meta = front_matter(qmd)
        if meta.get("draft"):
            continue
        url = f"{base_url}/posts/{post_dir.name}/"
        posts.append((url, meta))
    posts.sort(key=lambda item: item[1].get("date", ""), reverse=True)
    return posts


def collect_qmds(base_url: str, dirname: str) -> list[tuple[str, dict]]:
    entries = []
    for qmd in sorted((ROOT / dirname).glob("*.qmd")):
        meta = front_matter(qmd)
        if meta.get("draft"):
            continue
        url = f"{base_url}/{dirname}/{qmd.stem}.html"
        entries.append((url, meta))
    return entries


def build() -> str:
    base_url = site_url()
    index_text = (ROOT / "index.qmd").read_text(encoding="utf-8")
    index_meta = front_matter(ROOT / "index.qmd")
    writing_meta = front_matter(ROOT / "writing.qmd")
    photography_meta = front_matter(ROOT / "photography" / "index.qmd")

    lines = [
        f"# {index_meta['title']}",
        "",
        f"> {index_meta['description-meta']}",
        "",
        "## Pages",
        "",
        bullet("Home", f"{base_url}/", blurb(index_meta)),
        bullet("Writing", f"{base_url}/writing.html", blurb(writing_meta)),
        bullet("Photography", f"{base_url}/photography/", blurb(photography_meta)),
    ]

    publications = collect_publications(base_url, index_text)
    if publications:
        lines += ["", "## Publications", ""]
        lines += publications

    experience = collect_experience(base_url, index_text)
    if experience:
        lines += ["", "## Experience", ""]
        lines += experience

    posts = collect_posts(base_url)
    if posts:
        lines += ["", "## Writing", ""]
        lines += [bullet(meta["title"], url, blurb(meta)) for url, meta in posts]

    projects = collect_qmds(base_url, "projects")
    if projects:
        lines += ["", "## Projects", ""]
        lines += [bullet(meta["title"], url, blurb(meta)) for url, meta in projects]

    work = collect_qmds(base_url, "work")
    if work:
        lines += ["", "## Work", ""]
        lines += [bullet(meta["title"], url, blurb(meta)) for url, meta in work]

    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    (ROOT / "llms.txt").write_text(build(), encoding="utf-8")
