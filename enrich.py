"""
Enrich saved restaurant data with Yelp API (structured info) +
Google Maps Playwright scraper (description + website).

Flow per restaurant:
  1. Yelp  → rating, review_count, price, categories, hours, phone, address
  2. Google Maps → description, website  (also fills any gap Yelp left)

Usage:
  python enrich.py                    # default city (Los Angeles), all restaurants
  python enrich.py --city "New York"
  python enrich.py --yelp-only        # skip Google Maps browser
  python enrich.py --gmaps-only       # skip Yelp API
  python enrich.py --limit 20         # only process first N records
  python enrich.py --resume           # skip records already enriched
"""

import asyncio
import argparse
import json
import random
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from config import DATA_DIR, DEFAULT_CITY, YELP_API_KEY
import enrichers.yelp as yelp_enricher
import enrichers.google_maps as gmaps_enricher


# ── I/O ─────────────────────────────────────────────────────────────────────

def load_restaurants(city: str) -> list[dict]:
    city_slug = city.lower().replace(" ", "_")
    path = Path(DATA_DIR) / f"restaurants_{city_slug}.json"
    if not path.exists():
        print(f"[enrich] File not found: {path}")
        print("Run 'python run.py' first to scrape and extract restaurant data.")
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"[enrich] Loaded {len(data)} restaurants from {path}")
    return data


def load_enriched(city: str) -> dict:
    """Return a dict keyed by restaurant name for fast lookup of existing work."""
    city_slug = city.lower().replace(" ", "_")
    path = Path(DATA_DIR) / f"enriched_{city_slug}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r.get("name", ""): r for r in data}


def save_enriched(restaurants: list[dict], city: str) -> Path:
    city_slug = city.lower().replace(" ", "_")
    path = Path(DATA_DIR) / f"enriched_{city_slug}.json"
    path.write_text(json.dumps(restaurants, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[enrich] Saved {len(restaurants)} enriched restaurants → {path}")
    return path


# ── core pipeline ────────────────────────────────────────────────────────────

async def process_all(
    restaurants: list[dict],
    use_yelp: bool,
    use_gmaps: bool,
    existing: dict,
    resume: bool,
) -> list[dict]:
    results = []

    if use_gmaps:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            for i, restaurant in enumerate(restaurants, 1):
                enriched = await _enrich_one(
                    restaurant, i, len(restaurants),
                    use_yelp, True, page, existing, resume,
                )
                results.append(enriched)
                # Polite pause between Maps requests
                await asyncio.sleep(random.uniform(3.0, 6.0))

            await browser.close()
    else:
        for i, restaurant in enumerate(restaurants, 1):
            enriched = await _enrich_one(
                restaurant, i, len(restaurants),
                use_yelp, False, None, existing, resume,
            )
            results.append(enriched)

    return results


async def _enrich_one(
    restaurant: dict,
    idx: int,
    total: int,
    use_yelp: bool,
    use_gmaps: bool,
    page,
    existing: dict,
    resume: bool,
) -> dict:
    name = restaurant.get("name", "?")
    print(f"\n[{idx}/{total}] {name}")

    # Resume mode: skip if already enriched from both sources
    if resume and name in existing:
        prev = existing[name]
        if "yelp" in prev.get("enriched_from", "") and "google_maps" in prev.get("enriched_from", ""):
            print("  → already fully enriched, skipping")
            return prev

    enriched = dict(restaurant)
    sources: list[str] = []

    # ── Yelp ────────────────────────────────────────────────────────────────
    if use_yelp:
        yelp_data = yelp_enricher.enrich(restaurant)
        if yelp_data:
            enriched.update(yelp_data)
            sources.append("yelp")
            rating = yelp_data.get("yelp_rating")
            reviews = yelp_data.get("yelp_review_count")
            print(f"  [yelp] ✓  rating={rating}  reviews={reviews}")
        else:
            print("  [yelp] not found")

    # ── Google Maps ─────────────────────────────────────────────────────────
    if use_gmaps and page is not None:
        gmaps_data = await gmaps_enricher.enrich(restaurant, page)
        if gmaps_data:
            # Only fill fields that Yelp didn't already provide
            for k, v in gmaps_data.items():
                if v and not enriched.get(k):
                    enriched[k] = v
            sources.append("google_maps")
            got = [k for k in ("description", "website") if gmaps_data.get(k)]
            print(f"  [gmaps] ✓  got: {', '.join(got) or 'basic info only'}")
        else:
            print("  [gmaps] not found")

    enriched["enriched_from"] = "+".join(sources) or "none"
    enriched["enriched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return enriched


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Enrich restaurant data via Yelp + Google Maps")
    parser.add_argument("--city", default=DEFAULT_CITY, help="City to enrich")
    parser.add_argument("--yelp-only", action="store_true", help="Skip Google Maps")
    parser.add_argument("--gmaps-only", action="store_true", help="Skip Yelp API")
    parser.add_argument("--limit", type=int, default=None, help="Max restaurants to process")
    parser.add_argument("--resume", action="store_true", help="Skip already-enriched records")
    args = parser.parse_args()

    use_yelp = not args.gmaps_only
    use_gmaps = not args.yelp_only
    city = args.city

    if use_yelp and not YELP_API_KEY:
        print("[enrich] Warning: YELP_API_KEY not set — Yelp enrichment will be skipped.")
        print("         Set it in .env or export YELP_API_KEY=... to use Yelp.")
        use_yelp = False

    restaurants = load_restaurants(city)
    if not restaurants:
        return

    if args.limit:
        restaurants = restaurants[: args.limit]

    existing = load_enriched(city) if args.resume else {}

    print("=" * 55)
    print(f"City:         {city}")
    print(f"Restaurants:  {len(restaurants)}")
    print(f"Yelp:         {'on' if use_yelp else 'off'}")
    print(f"Google Maps:  {'on' if use_gmaps else 'off'}")
    print(f"Resume:       {'on' if args.resume else 'off'}")
    print("=" * 55)

    enriched_all = asyncio.run(
        process_all(restaurants, use_yelp, use_gmaps, existing, args.resume)
    )

    save_enriched(enriched_all, city)

    found = sum(1 for r in enriched_all if r.get("enriched_from", "none") != "none")
    has_desc = sum(1 for r in enriched_all if r.get("description"))
    has_web = sum(1 for r in enriched_all if r.get("website"))
    print(f"\nDone! {found}/{len(enriched_all)} restaurants enriched")
    print(f"      {has_desc} have descriptions  |  {has_web} have websites")


if __name__ == "__main__":
    main()
