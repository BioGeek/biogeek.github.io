#!/usr/bin/env python3
"""Fetch Strava activities and write a JSON summary for the blog post.

Uses the Strava API in "single player mode" (your own data only). Needs three
GitHub Actions secrets / env vars, obtained once via the OAuth flow (see
SETUP-data-posts.md):

    STRAVA_CLIENT_ID
    STRAVA_CLIENT_SECRET
    STRAVA_REFRESH_TOKEN

Run via the update-strava GitHub Action (or `make strava`), which commits the
JSON and re-renders the site.

Writes: posts/trail-running-strava/strava_runs.json

If the secrets are absent (e.g. local render, or a fork) the script prints a
notice and exits 0 without touching the existing JSON, so the build never fails.
"""
import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median

OUT = "posts/trail-running-strava/strava_runs.json"
TOKEN_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
FOOT_TYPES = {"Run", "TrailRun", "Hike"}   # foot activities we keep
# Rough kcal/km by activity kind (no body weight available, so clearly an estimate).
KCAL_PER_KM = {"run": 65, "trail": 72, "hike": 55}

# ---------------------------------------------------------------------------
# FUTURE CROSSOVERS (TODO) — other free/open APIs to layer onto tracks/sightings:
#   - GBIF (no key): global record counts per species -> "rarity score" for iNat finds.
#   - eBird (free key, x-ebirdapitoken): birds reported on my trails I haven't logged.
#   - Xeno-canto (no key): a sound recording per bird species seen.
#   - IUCN Red List (free token): authoritative status + population trend for sightings.
#   - OpenStreetMap / Overpass (no key): match tracks to NAMED trails / reserves.
#   - Protected Planet / WDPA (free token): % of km inside protected areas.
#   - Wikipedia geosearch (no key): landmarks passed near each track.
#   - Wikidata (no key): one-line natural-history blurb per species.
#   - Open Library (no key): a "currently reading" shelf.
#   - ListenBrainz (open) / Last.fm (free key): what I listen to while running.
#   - Photo EXIF (no API): map my own trail photos against the tracks.
# ---------------------------------------------------------------------------


def kind_of(activity):
    st = activity.get("sport_type", activity.get("type"))
    if st == "Hike":
        return "hike"
    if st == "TrailRun":
        return "trail"
    return "run"


def _post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def decode_polyline(s):
    """Decode a Google-encoded polyline into [(lat, lng), ...]."""
    index = lat = lng = 0
    coords = []
    while index < len(s):
        for is_lat in (True, False):
            shift = result = 0
            while True:
                b = ord(s[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            d = ~(result >> 1) if (result & 1) else (result >> 1)
            if is_lat:
                lat += d
            else:
                lng += d
        coords.append((round(lat / 1e5, 5), round(lng / 1e5, 5)))
    return coords


def track_from(activity, max_points=60, privacy_crop=3):
    """A downsampled, privacy-cropped (lat, lng) track for one activity.

    privacy_crop drops the first/last few points so home/start locations aren't
    pinpointed (in addition to any Strava privacy zones, which are applied
    server-side)."""
    poly = (activity.get("map") or {}).get("summary_polyline")
    if not poly:
        return None
    pts = decode_polyline(poly)
    if len(pts) > 2 * privacy_crop + 4:
        pts = pts[privacy_crop:-privacy_crop]
    if len(pts) > max_points:
        step = len(pts) / max_points
        pts = [pts[int(i * step)] for i in range(max_points)]
    return pts


# --- Open-Meteo weather crossover (free, no API key) ----------------------
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def _start_coord(a):
    ll = a.get("start_latlng")
    if ll and len(ll) == 2 and (ll[0] or ll[1]):
        return ll[0], ll[1]
    poly = (a.get("map") or {}).get("summary_polyline")
    if poly:
        pts = decode_polyline(poly)
        if pts:
            return pts[0]
    return None


def _weather_category(code):
    """WMO weather code -> coarse category."""
    if code is None:
        return "unknown"
    if code == 0:
        return "clear"
    if code in (1, 2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if 95 <= code <= 99:
        return "storm"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    return "other"


def attach_weather(runs):
    """Attach hourly weather to each activity using ONE Open-Meteo archive call.

    City-scale weather barely varies across a 20 km area, so we query the
    centroid of all start points for the whole date range and look up each
    activity's start hour. Free, no key. Fails soft (no weather -> no panel)."""
    coords = [c for c in (_start_coord(a) for a in runs) if c]
    if not coords:
        return
    clat = sum(c[0] for c in coords) / len(coords)
    clng = sum(c[1] for c in coords) / len(coords)
    days = sorted(a["start_date_local"][:10] for a in runs)
    params = {
        "latitude": round(clat, 3), "longitude": round(clng, 3),
        "start_date": days[0], "end_date": days[-1],
        "hourly": "temperature_2m,precipitation,wind_speed_10m,relative_humidity_2m,weather_code",
        "timezone": "auto",
    }
    url = f"{ARCHIVE_URL}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "biogeek-site"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            h = json.load(resp)["hourly"]
    except Exception as exc:                       # fail soft
        print(f"Open-Meteo weather fetch failed: {exc}")
        return
    idx = {t[:13]: i for i, t in enumerate(h["time"])}   # "YYYY-MM-DDTHH" -> row
    for a in runs:
        i = idx.get(a["start_date_local"].replace("Z", "")[:13])
        if i is None:
            continue
        a["_weather"] = {
            "temp": h["temperature_2m"][i],
            "precip": h["precipitation"][i],
            "wind": h["wind_speed_10m"][i],
            "humidity": h["relative_humidity_2m"][i],
            "cat": _weather_category(h["weather_code"][i]),
        }


def access_token():
    return _post(TOKEN_URL, {
        "client_id": os.environ["STRAVA_CLIENT_ID"],
        "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
        "grant_type": "refresh_token",
        "refresh_token": os.environ["STRAVA_REFRESH_TOKEN"],
    })["access_token"]


def all_activities(token):
    page, out = 1, []
    while True:
        url = f"{ACTIVITIES_URL}?{urllib.parse.urlencode({'per_page': 200, 'page': page})}"
        batch = _get(url, token)
        if not batch:
            break
        out.extend(batch)
        page += 1
        if page > 50:     # safety cap (~10k activities)
            break
    return out


def summarise(runs):
    by_month, by_year = defaultdict(float), defaultdict(float)
    total_d = total_e = total_t = 0.0
    total_cal = 0.0
    active_dates = set()
    first_date = None
    longest = biggest = None
    recent = []
    tracks = []
    weather_counts = defaultdict(int)
    weather_points = []          # {temp, pace, kind} for pace-vs-temp
    temps = []
    rain_outings = 0
    time_grid = [[0] * 24 for _ in range(7)]   # [weekday Mon..Sun][hour]
    for a in runs:
        km = a["distance"] / 1000.0
        elev = a.get("total_elevation_gain", 0.0)
        secs = a.get("moving_time", 0)
        local = a["start_date_local"].replace("Z", "")
        day = local[:10]
        month = local[:7]
        k = kind_of(a)
        total_d += km; total_e += elev; total_t += secs
        total_cal += km * KCAL_PER_KM.get(k, 65)
        active_dates.add(day)
        if first_date is None or day < first_date:
            first_date = day
        by_month[month] += km
        by_year[month[:4]] += km
        try:
            dt = datetime.fromisoformat(local)
            time_grid[dt.weekday()][dt.hour] += 1
        except ValueError:
            pass
        track = track_from(a)
        if track:
            tracks.append(track)
        pace = round((secs / 60.0) / km, 2) if km else None
        w = a.get("_weather")
        if w:
            weather_counts[w["cat"]] += 1
            temps.append(w["temp"])
            if w["cat"] in ("rain", "storm") or w["precip"] > 0.2:
                rain_outings += 1
            if pace is not None:
                weather_points.append({"temp": round(w["temp"], 1), "pace": pace, "kind": k})
        if longest is None or km > longest["distance_km"]:
            longest = {"name": a["name"], "distance_km": round(km, 1)}
        if biggest is None or elev > biggest["elev_gain_m"]:
            biggest = {"name": a["name"], "elev_gain_m": round(elev)}
        recent.append({
            "id": a["id"],
            "name": a["name"],
            "date": day,
            "distance_km": round(km, 2),
            "elev_gain_m": round(elev),
            "pace_min_km": pace,
            "temp_c": round(w["temp"], 1) if w else None,
            "weather": w["cat"] if w else None,
            "sport_type": a.get("sport_type", a.get("type")),
            "kind": k,
            "is_trail": a.get("sport_type") == "TrailRun",
        })
    recent.sort(key=lambda r: r["date"], reverse=True)
    n_trail = sum(r["kind"] == "trail" for r in recent)
    n_hike = sum(r["kind"] == "hike" for r in recent)
    weather = {
        "available": bool(weather_points),
        "counts": dict(sorted(weather_counts.items(), key=lambda kv: -kv[1])),
        "points": weather_points,
        "median_temp": round(median(temps), 1) if temps else None,
        "rain_pct": round(100 * rain_outings / len(runs)) if runs else 0,
    }
    return {
        "runs": len(runs),
        "trail_runs": n_trail,
        "hikes": n_hike,
        "weather": weather,
        "total_distance_km": round(total_d),
        "total_elevation_m": round(total_e),
        "total_moving_hours": round(total_t / 3600.0),
        "total_moving_seconds": int(total_t),
        "total_calories": round(total_cal),
        "active_days": len(active_dates),
        "first_date": first_date,
        "longest_run": longest,
        "biggest_climb": biggest,
        "by_month": dict(sorted(by_month.items())),
        "by_year": {k: round(v) for k, v in sorted(by_year.items())},
        "time_grid": time_grid,
        "tracks": tracks,
        "recent": recent[:200],
    }


def main():
    missing = [k for k in ("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET",
                           "STRAVA_REFRESH_TOKEN") if not os.environ.get(k)]
    if missing:
        print(f"Strava secrets not set ({', '.join(missing)}); leaving {OUT} unchanged.")
        return
    token = access_token()
    runs = [a for a in all_activities(token)
            if a.get("sport_type", a.get("type")) in FOOT_TYPES]
    attach_weather(runs)         # Open-Meteo crossover (one request)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stats": summarise(runs),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    st = payload["stats"]
    print(f"Wrote {OUT}: {st['runs']} activities ({st['trail_runs']} trail runs, "
          f"{st['hikes']} hikes), {st['total_distance_km']} km, "
          f"{st['total_elevation_m']} m climbed.")


if __name__ == "__main__":
    main()
