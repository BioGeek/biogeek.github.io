#!/usr/bin/env python3
"""Fetch iNaturalist observations and write a JSON summary for the blog post.

Public API, no authentication or secrets needed. Run via the
update-inaturalist GitHub Action (or `make inat`), which commits the JSON and
re-renders the site.

Writes: posts/inaturalist-sightings/inat.json

Config: set INAT_USER below (your iNaturalist login). Optionally list favourite
observation IDs in FAVOURITE_IDS; if empty, the most-faved observations are used.
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

INAT_USER = "biogeek"            # <- your iNaturalist login
FAVOURITE_IDS: list[int] = []        # <- e.g. [12345678, 23456789]; empty -> top-faved
N_FAVOURITES = 12
TOP_SPECIES = 10
API = "https://api.inaturalist.org/v1"
OUT = "posts/inaturalist-sightings/inat.json"
UA = {"User-Agent": f"biogeek-site (https://jeroen.vangoey.be; iNat:{INAT_USER})"}


def get(path, **params):
    """GET a v1 endpoint, politely (<=1 req/sec)."""
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(f"{API}/{path}?{qs}", headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    time.sleep(1.1)
    return data


def large(url: str) -> str:
    """Turn a square thumbnail URL into the large version."""
    return (url or "").replace("square.", "large.")


def summarise_observation(o: dict) -> dict:
    t = o.get("taxon") or {}
    cs = t.get("conservation_status") or {}
    photo = (o.get("photos") or [{}])[0]
    return {
        "id": o.get("id"),
        "species": t.get("name"),
        "common_name": t.get("preferred_common_name"),
        "group": t.get("iconic_taxon_name"),
        "observed_on": o.get("observed_on"),
        "place": o.get("place_guess"),
        "quality_grade": o.get("quality_grade"),
        "faves": o.get("faves_count", 0),
        "photo": large(photo.get("url")),
        "uri": (o.get("uri") or "").replace("http://", "https://"),
        "conservation_status": cs.get("status_name") or cs.get("status"),
        "iucn": cs.get("iucn"),
    }


def main():
    # --- aggregate stats -------------------------------------------------
    # No verifiable filter: count every observation, matching the totals shown
    # on the iNaturalist profile (verifiable="true" would drop casual/no-media
    # observations and undercount). The map/coords still only use observations
    # that carry non-obscured coordinates, and the gallery still filters photos.
    base = dict(user_login=INAT_USER)
    total = get("observations", per_page=0, **base)["total_results"]
    species = get("observations/species_counts", per_page=0, **base)["total_results"]
    threatened = get("observations", per_page=0, threatened="true", **base)["total_results"]
    research = get("observations", per_page=0, quality_grade="research", **base)["total_results"]

    by_group, by_year = {}, {}
    coords = []                       # non-obscured points only (privacy)
    page, seen = 1, 0
    while True:                       # paginate every observation once
        d = get("observations", per_page=200, page=page, order_by="observed_on",
                order="asc", **base)
        results = d["results"]
        if not results:
            break
        for o in results:
            t = o.get("taxon") or {}
            g = t.get("iconic_taxon_name") or "Unknown"
            by_group[g] = by_group.get(g, 0) + 1
            yr = (o.get("observed_on") or "")[:4]
            if yr:
                by_year[yr] = by_year.get(yr, 0) + 1
            # Only keep precise coordinates iNaturalist has NOT obscured. Threatened
            # taxa are obscured server-side, so this never pinpoints a sensitive species.
            geo = o.get("geojson") or {}
            if not o.get("coordinates_obscured") and geo.get("type") == "Point":
                lng, lat = geo["coordinates"]
                coords.append({
                    "lat": round(lat, 5), "lng": round(lng, 5),
                    "group": g,
                    "common_name": t.get("preferred_common_name"),
                    "species": t.get("name"),
                })
        seen += len(results)
        page += 1
        if seen >= total or page > 60:   # safety cap (~12k observations)
            break

    top_species = [
        {"species": r["taxon"]["name"],
         "common_name": r["taxon"].get("preferred_common_name"),
         "count": r["count"]}
        for r in get("observations/species_counts", per_page=TOP_SPECIES, **base)["results"]
    ]

    # --- favourite sightings --------------------------------------------
    if FAVOURITE_IDS:
        ids = ",".join(str(i) for i in FAVOURITE_IDS[:30])
        favs = get(f"observations/{ids}")["results"]
    else:
        favs = get("observations", per_page=N_FAVOURITES, order_by="votes",
                   photos="true", **base)["results"]
    favourites = [summarise_observation(o) for o in favs]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user": INAT_USER,
        "stats": {
            "observations": total,
            "species": species,
            "threatened_observations": threatened,
            "research_grade": research,
            "by_group": dict(sorted(by_group.items(), key=lambda kv: -kv[1])),
            "by_year": dict(sorted(by_year.items())),
            "top_species": top_species,
        },
        "favourites": favourites,
        "coords": coords,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {OUT}: {total} observations, {species} species, "
          f"{threatened} threatened, {len(favourites)} favourites.")


if __name__ == "__main__":
    main()
