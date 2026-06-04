"""
Google Maps Playwright enricher — no API key, no cost.

Targets two things Yelp's free API doesn't provide:
  1. description  — editorial summary or owner "About" blurb
  2. website      — the restaurant's own URL (not the Yelp/Maps page)

Also captures google_maps_url and google_phone as fallbacks when Yelp missed them.
"""

import asyncio
import random
from urllib.parse import quote

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from config import REQUEST_DELAY_MIN, REQUEST_DELAY_MAX


async def enrich(restaurant: dict, page: Page) -> dict:
    name = restaurant.get("name", "")
    city = restaurant.get("city", "Los Angeles")
    if not name:
        return {}

    query = quote(f"{name} restaurant {city}")
    try:
        await page.goto(
            f"https://www.google.com/maps/search/{query}",
            timeout=30000,
            wait_until="domcontentloaded",
        )
        await _delay()
    except PlaywrightTimeout:
        print(f"  [gmaps] timeout: {name}")
        return {}

    await _dismiss_dialogs(page)

    # Search may give a list of results or navigate straight to a business page.
    if "/search/" in page.url:
        if not await _click_first_result(page):
            print(f"  [gmaps] no result clicked for: {name}")
            return {}
        await _delay()

    return await _extract_business(page)


# ── navigation helpers ───────────────────────────────────────────────────────

async def _dismiss_dialogs(page: Page) -> None:
    for sel in [
        'button:has-text("Accept all")',
        'button:has-text("Reject all")',
        'button[aria-label*="Accept"]',
        'button[aria-label*="Reject"]',
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                await asyncio.sleep(0.8)
                return
        except Exception:
            pass


async def _click_first_result(page: Page) -> bool:
    for sel in [
        ".Nv2PK a",          # standard result card link
        'a[href*="/maps/place/"]',  # any place link
        ".hfpxzc",           # result anchor (older layout)
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                await asyncio.sleep(random.uniform(2.0, 3.5))
                return True
        except Exception:
            pass
    return False


# ── extraction ───────────────────────────────────────────────────────────────

async def _extract_business(page: Page) -> dict:
    result: dict = {}

    # Website — data-item-id="authority" is the most stable Maps selector
    website = await _get_website(page)
    if website:
        result["website"] = website

    # Description — editorial summary or "From the owner" in the About tab
    description = await _get_description(page)
    if description:
        result["description"] = description

    # Phone fallback
    phone = await _get_phone(page)
    if phone:
        result["google_phone"] = phone

    # Strip GPS coords from URL so it doesn't drift between runs
    maps_url = page.url.split("@")[0].rstrip("/")
    if "/maps/place/" in maps_url:
        result["google_maps_url"] = maps_url

    return result


async def _get_website(page: Page) -> str:
    for sel in [
        '[data-item-id="authority"] a',
        'a[data-item-id="authority"]',
        'a[aria-label*="website" i]',
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                href = await el.get_attribute("href") or ""
                if href.startswith("http") and "google.com" not in href:
                    return href
        except Exception:
            pass
    return ""


async def _get_phone(page: Page) -> str:
    for sel in [
        '[data-item-id^="phone:tel:"] [aria-label]',
        '[data-tooltip="Copy phone number"]',
        'button[aria-label*="phone" i]',
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                label = await el.get_attribute("aria-label") or await el.inner_text()
                text = label.replace("Phone:", "").strip()
                if text:
                    return text
        except Exception:
            pass
    return ""


async def _get_description(page: Page) -> str:
    # 1. Try editorial summary — the short blurb below the category tag
    #    Google uses several class patterns; try the ones that survive redesigns.
    for sel in [
        '[jslog*="metadata"] span',       # structured metadata span
        '.PYvSYb',                         # known editorial summary class
        '[data-attrid*="editorial"] span', # attrid-based editorial
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if _looks_like_description(text):
                    return text
        except Exception:
            pass

    # 2. Try the "About" tab → "From the owner" description
    try:
        about_btn = await page.query_selector(
            'button[aria-label*="About" i], '
            'button[data-tab-index="1"][jsaction]'
        )
        if about_btn:
            await about_btn.click()
            await asyncio.sleep(1.2)

            for sel in [
                '[aria-label*="description" i]',
                'div.iN30ob',          # "From the owner" container (Maps)
                '.ZWH3pb',             # about section text
                '[class*="fontBodyMedium"] > span',
            ]:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        text = (await el.inner_text()).strip()
                        if _looks_like_description(text):
                            return text
                except Exception:
                    pass
    except Exception:
        pass

    return ""


def _looks_like_description(text: str) -> bool:
    """Accept text that is plausibly a prose description, not a label or address."""
    if not text or len(text) < 20 or len(text) > 600:
        return False
    if text.startswith("http"):
        return False
    # Reject obvious non-prose patterns (phone numbers, lone digits, etc.)
    digit_ratio = sum(c.isdigit() for c in text) / len(text)
    return digit_ratio < 0.4


async def _delay() -> None:
    await asyncio.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
