import difflib
import os
import requests
import time
import yaml
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


def _get(endpoint: str, **params) -> Dict[str, Any]:
    params["api_key"] = API_KEY
    r = requests.get(f"{BASE_URL}{endpoint}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def _safe_movie(mid: int) -> Optional[Dict[str, Any]]:
    try:
        return _get(f"/movie/{mid}", append_to_response="credits")
    except requests.HTTPError as e:
        return None if e.response.status_code == 404 else (_ for _ in ()).throw(e)


def _safe_tv(tid: int) -> Optional[Dict[str, Any]]:
    try:
        return _get(f"/tv/{tid}")
    except requests.HTTPError as e:
        return None if e.response.status_code == 404 else (_ for _ in ()).throw(e)


def _norm(s: str) -> str:
    return "".join(c.lower() for c in s if c.isalnum())


def _close_enough(q: str, candidate: str) -> bool:
    return difflib.SequenceMatcher(None, _norm(q), _norm(candidate)).ratio() >= 0.8


def _ask_choice(title: str, options: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    print(f"Multiple matches found for “{title}”. Which one did you mean?")
    for idx, opt in enumerate(options, 1):
        year = opt.get("release_date") or opt.get("first_air_date") or "????"
        year = year[:4]
        lbl = opt.get("title") or opt.get("name")
        kind = opt["media_type"]
        print(f"  {idx}. {lbl}  ({year}, {kind})")
    print("  0. Skip this title")

    while True:
        sel = input("Pick a number (default 1): ").strip() or "1"
        if sel.isdigit():
            sel = int(sel)
            if 0 <= sel <= len(options):
                break
        print("Invalid choice — try again.")
    return None if sel == 0 else options[sel - 1]


def enrich(raw_title: str) -> Dict[str, Any]:
    hits = _get("/search/multi", query=raw_title).get("results", [])
    if not hits:
        return {"title": raw_title, "note": "Not found"}

    best = hits[0]
    auto_pick = (
            _close_enough(raw_title, best.get("title") or best.get("name") or "")
            or len(hits) == 1
    )
    if not auto_pick:
        menu_hits = [h for h in hits if h["media_type"] in ("movie", "tv")][:5]
        if not menu_hits:
            return {"title": raw_title, "note": "No valid movie/series found"}
        chosen = _ask_choice(raw_title, menu_hits)
        if not chosen:
            return {"title": raw_title, "note": "Skipped by user"}
        best = chosen

    details = None
    if best["media_type"] == "movie":
        details = _safe_movie(best["id"])
    elif best["media_type"] == "tv":
        details = _safe_tv(best["id"])

    if not details:
        for h in hits[1:]:
            if h["media_type"] == "movie":
                details = _safe_movie(h["id"])
            elif h["media_type"] == "tv":
                details = _safe_tv(h["id"])
            if details:
                best = h
                break
        if not details:
            return {"title": raw_title, "note": "All candidates invalid"}

    # Build record
    media_type = best["media_type"]
    if media_type == "movie":
        director = next((c["name"] for c in details["credits"]["crew"]
                         if c["job"] == "Director"), None)
        year = details.get("release_date", "")[:4]
        country = details.get("production_countries", [{}])[0].get("iso_3166_1", "")
    else:
        director = None
        year = details.get("first_air_date", "")[:4]
        country = details.get("origin_country", [""])[0]

    genres = ", ".join(g["name"] for g in details.get("genres", []))
    poster = f"{IMAGE_BASE}{details['poster_path']}" if details.get("poster_path") else ""

    rec: Dict[str, Any] = {
        "title": details.get("title") or details.get("name") or raw_title,
        "year": int(year) if year.isdigit() else year,
        "type": "movie" if media_type == "movie" else "series",
        "poster": poster or None,
        "genre": genres or None,
        "country": country or None,
    }
    if director:
        rec["director"] = director
    return {k: v for k, v in rec.items() if v}


def main() -> None:
    raw = input("Titles (comma-separated): ").strip()
    titles: List[str] = [t.strip() for t in raw.split(",") if t.strip()]
    if not titles:
        raise SystemExit("No titles provided.")

    catalogue: List[Dict[str, Any]] = []
    for i, t in enumerate(titles, 1):
        print(f"[{i}/{len(titles)}] {t}")
        catalogue.append(enrich(t))
        time.sleep(0.2)

    print("\n" + yaml.dump(catalogue, allow_unicode=True, sort_keys=False))


if __name__ == "__main__":
    main()
