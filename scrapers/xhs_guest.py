"""
访客模式爬虫 — 不需要小红书账号，0 封号风险。
能看到的内容比登录模式少，但足够起步。
"""

import asyncio
import random
from urllib.parse import quote
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from config import REQUEST_DELAY_MIN, REQUEST_DELAY_MAX


async def scrape(keywords: list[str], limit: int = 50) -> list[dict]:
    posts = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # 显示浏览器窗口，减少被识别为 bot 的概率
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )

        # 隐藏 webdriver 标记
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()

        for keyword in keywords:
            if len(posts) >= limit:
                break
            print(f"[guest] 搜索关键词: {keyword}")
            batch = await _scrape_keyword(page, keyword, limit - len(posts))
            posts.extend(batch)
            print(f"[guest] 当前收集: {len(posts)} 条")

        await browser.close()

    return posts


async def _scrape_keyword(page, keyword: str, limit: int) -> list[dict]:
    encoded = quote(keyword)
    url = f"https://www.xiaohongshu.com/search_result?keyword={encoded}&type=51"

    try:
        await page.goto(url, timeout=30000)
        await asyncio.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
    except PlaywrightTimeout:
        print(f"[guest] 页面加载超时: {keyword}")
        return []

    # 检查是否跳到登录页
    if "login" in page.url or "signin" in page.url:
        print("[guest] 小红书要求登录，访客模式获取到的内容有限")
        return []

    posts = []
    seen_urls = set()
    scroll_count = 0

    while len(posts) < limit and scroll_count < 25:
        # 尝试多种选择器（XHS 会不定期改 class 名）
        cards = await page.query_selector_all(
            "section.note-item, .feeds-page .note-item, "
            "[class*='note-item'], .note-list-scroll-container section"
        )

        for card in cards:
            if len(posts) >= limit:
                break
            post = await _extract_card(card)
            if post and post["url"] not in seen_urls:
                seen_urls.add(post["url"])
                post["keyword"] = keyword
                post["mode"] = "guest"
                posts.append(post)

        # 滚动
        await page.evaluate("window.scrollBy(0, 800)")
        await asyncio.sleep(random.uniform(1.5, 3.5))
        scroll_count += 1

        # 检查是否出现"没有更多"
        no_more = await page.query_selector("[class*='noMore'], [class*='no-more']")
        if no_more:
            break

    return posts


async def _extract_card(card) -> dict | None:
    try:
        # 获取链接
        link_el = await card.query_selector("a")
        if not link_el:
            return None
        href = await link_el.get_attribute("href") or ""
        if not href:
            return None
        url = f"https://www.xiaohongshu.com{href}" if href.startswith("/") else href

        # 标题
        title_el = await card.query_selector(
            ".title, [class*='title'], .note-title, h3, .desc"
        )
        title = (await title_el.inner_text()).strip() if title_el else ""

        # 发布者
        author_el = await card.query_selector(
            ".author, [class*='author'], .nickname, .user-name"
        )
        author = (await author_el.inner_text()).strip() if author_el else ""

        # 点赞数
        likes_el = await card.query_selector(
            ".like-wrapper, [class*='like'], .count, [class*='count']"
        )
        likes = (await likes_el.inner_text()).strip() if likes_el else ""

        return {
            "title": title,
            "author": author,
            "likes": likes,
            "url": url,
            "source": "xiaohongshu",
        }
    except Exception:
        return None
