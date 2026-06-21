#!/usr/bin/env python3
"""Check external links in index.qmd and keep them alive via the Wayback Machine.

Two modes:
  --check    (default) Probe every external link. For ones that are *definitively*
             gone, replace them in index.qmd with the closest Wayback snapshot.
  --archive  Submit every external link to the Wayback Machine ("Save Page Now")
             so a fresh capture exists for future replacements.

Deliberately conservative — auto-replacing live links is destructive, so:
  * Only HTTP 404/410 and DNS/connection failures (after a retry) count as "dead".
  * Ambiguous responses (401/403/429/5xx/timeouts) are reported, never replaced —
    many healthy sites block bots (LinkedIn -> 999, X -> 403, etc.).
  * Domains in SKIP_DOMAINS (social, badges, archive, doi) are reported only.
  * "HTTP 200 but blank/parked" pages cannot be detected reliably and are NOT
    handled here — fix those by hand.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

QMD = "index.qmd"
UA = "Mozilla/5.0 (compatible; biogeek-linkcheck/1.0; +https://jeroen.vangoey.be)"

# Report-only domains: bot-blockers, badge/archive/doi endpoints.
SKIP_DOMAINS = (
    "linkedin.com", "x.com", "twitter.com", "reddit.com",
    "web.archive.org", "img.shields.io", "doi.org",
)

URL_RE = re.compile(r'https?://[^\s"\'<>)]+')


def extract_urls(text):
    seen, urls = set(), []
    for m in URL_RE.findall(text):
        u = m.rstrip(".,;)")
        if u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def http_status(url, method="HEAD"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None  # DNS / connection / timeout


def is_dead(url):
    """True only for definitive 'gone' signals, after one retry on connection errors.

    Many servers mishandle HEAD (e.g. bsky.app returns 404 to HEAD but 200 to GET),
    so any HEAD failure is confirmed with a GET before a link is declared dead.
    """
    for attempt in range(2):
        st = http_status(url, "HEAD")
        if st in (None, 404, 405, 410, 501) or (st is not None and st >= 500):
            st = http_status(url, "GET")  # confirm HEAD failures with a real GET
        if st is None:
            if attempt == 0:
                time.sleep(3)
                continue
            return True  # repeated connection/DNS failure
        return st in (404, 410)
    return False


def wayback_snapshot(url):
    """Closest available Wayback snapshot, or None. Retries on rate-limiting (429)."""
    api = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe="")
    req = urllib.request.Request(api, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                snap = json.load(r).get("archived_snapshots", {}).get("closest", {})
            if snap.get("available") and snap.get("url"):
                return snap["url"].replace("http://", "https://", 1)
            return None
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate-limited: back off and retry
                time.sleep(5 * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(3)
    return None


def wayback_save(url):
    req = urllib.request.Request("https://web.archive.org/save/" + url,
                                 headers={"User-Agent": UA})
    try:
        urllib.request.urlopen(req, timeout=30).read()
        return True
    except Exception:
        return False


def skip(url):
    return any(d in url for d in SKIP_DOMAINS)


def archive_mode(urls):
    n = 0
    for u in urls:
        if "web.archive.org" in u or "img.shields.io" in u:
            continue
        ok = wayback_save(u)
        print(("saved  " if ok else "failed ") + u)
        n += int(ok)
        time.sleep(2)  # be gentle with Save Page Now
    print(f"submitted {n}/{len(urls)} links to the Wayback Machine")
    return 0


def check_mode(urls):
    text = open(QMD, encoding="utf-8").read()
    replaced, attention = [], []
    for u in urls:
        if skip(u):
            continue
        if is_dead(u):
            snap = wayback_snapshot(u)
            if snap:
                text = text.replace(u, snap)
                replaced.append((u, snap))
            else:
                attention.append((u, "dead, no Wayback capture found"))
    if replaced:
        open(QMD, "w", encoding="utf-8").write(text)
    print("REPLACED with Wayback captures:")
    print("\n".join(f"  {u}\n    -> {s}" for u, s in replaced) or "  (none)")
    print("NEEDS MANUAL ATTENTION:")
    print("\n".join(f"  {u} ({why})" for u, why in attention) or "  (none)")
    return 0


def main(argv):
    mode = argv[1] if len(argv) > 1 else "--check"
    urls = extract_urls(open(QMD, encoding="utf-8").read())
    if mode == "--archive":
        return archive_mode(urls)
    return check_mode(urls)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
