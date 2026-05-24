"""
把爬取 / 提取的数据存入 JSON 文件，自动去重。
"""

import json
from pathlib import Path
from datetime import datetime

from config import DATA_DIR


def _get_path(city: str, extracted: bool) -> Path:
    Path(DATA_DIR).mkdir(exist_ok=True)
    city_slug = city.lower().replace(" ", "_")
    suffix = "restaurants" if extracted else "raw_posts"
    return Path(DATA_DIR) / f"{suffix}_{city_slug}.json"


def save_raw_posts(posts: list[dict], city: str) -> Path:
    """保存原始帖子（未经 Claude 提取）。"""
    path = _get_path(city, extracted=False)
    existing = _load(path)

    seen_urls = {p["url"] for p in existing}
    new_posts = [p for p in posts if p.get("url") not in seen_urls]

    for p in new_posts:
        p["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    combined = existing + new_posts
    _write(path, combined)
    print(f"[storage] 新增 {len(new_posts)} 条原始帖子 → {path}")
    return path


def save_restaurants(restaurants: list[dict], city: str) -> Path:
    """保存提取后的结构化餐厅数据。"""
    path = _get_path(city, extracted=True)
    existing = _load(path)

    seen_urls = {r.get("source_url", "") for r in existing}
    new_items = [r for r in restaurants if r.get("source_url", "") not in seen_urls]

    for r in new_items:
        r["extracted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    combined = existing + new_items
    _write(path, combined)
    print(f"[storage] 新增 {len(new_items)} 家餐厅 → {path}")
    return path


def _load(path: Path) -> list:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _write(path: Path, data: list):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
