"""
Yelp Fusion API enricher — free tier, 500 req/day, no credit card needed.
Sign up at https://www.yelp.com/developers/ → Create App → copy the API Key.

Returns: rating, review_count, price, categories, hours, phone, full_address,
         yelp_url. The business's own website is NOT in the free API — that
         comes from the Google Maps enricher.
"""

import requests
from difflib import SequenceMatcher
from config import YELP_API_KEY

_BASE = "https://api.yelp.com/v3"
_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def enrich(restaurant: dict) -> dict:
    """Return Yelp fields to merge into the restaurant record, or {} if not found."""
    name = restaurant.get("name", "")
    city = restaurant.get("city", "Los Angeles")
    if not name or not YELP_API_KEY:
        return {}

    biz = _search(name, city)
    if not biz:
        return {}

    details = _details(biz["id"]) or biz
    return _extract(details)


# ── internal ────────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {"Authorization": f"Bearer {YELP_API_KEY}"}


def _search(name: str, city: str) -> dict | None:
    try:
        r = requests.get(
            f"{_BASE}/businesses/search",
            headers=_headers(),
            params={"term": name, "location": city, "limit": 3, "locale": "en_US"},
            timeout=10,
        )
        r.raise_for_status()
        businesses = r.json().get("businesses", [])
    except Exception as e:
        print(f"  [yelp] search error: {e}")
        return None

    for biz in businesses:
        if _name_match(name, biz["name"]):
            return biz
    return None


def _details(biz_id: str) -> dict | None:
    try:
        r = requests.get(
            f"{_BASE}/businesses/{biz_id}",
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [yelp] details error: {e}")
        return None


def _name_match(query: str, candidate: str) -> bool:
    return SequenceMatcher(None, query.lower(), candidate.lower()).ratio() >= 0.6


def _extract(biz: dict) -> dict:
    result: dict = {
        "yelp_id": biz.get("id"),
        "yelp_url": (biz.get("url") or "").split("?")[0],  # strip UTM noise
        "yelp_rating": biz.get("rating"),
        "yelp_review_count": biz.get("review_count"),
        "phone": biz.get("display_phone") or biz.get("phone") or None,
        "price": biz.get("price"),
    }

    cats = [c["title"] for c in biz.get("categories", [])]
    if cats:
        result["yelp_categories"] = cats

    loc = biz.get("location", {})
    parts = loc.get("display_address", [])
    if parts:
        result["full_address"] = ", ".join(parts)

    hours_list = biz.get("hours", [])
    if hours_list:
        result["hours"] = _parse_hours(hours_list[0].get("open", []))
        is_open = hours_list[0].get("is_open_now")
        if is_open is not None:
            result["is_open_now"] = is_open

    return {k: v for k, v in result.items() if v is not None}


def _parse_hours(open_list: list) -> dict:
    hours: dict = {}
    for slot in open_list:
        day = _DAYS[slot["day"]]
        entry = f"{_fmt_time(slot['start'])}–{_fmt_time(slot['end'])}"
        hours.setdefault(day, []).append(entry)
    return hours


def _fmt_time(t: str) -> str:
    h, m = int(t[:2]), int(t[2:])
    period = "AM" if h < 12 else "PM"
    h = h % 12 or 12
    return f"{h}:{m:02d}{period}"
