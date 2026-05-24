"""
登录模式爬虫 — 用小号扫码登录，内容更完整。
第一次运行会弹出浏览器让你扫码；之后 session 保存在 xhs_session/ 目录，
下次运行不需要重新登录（除非 session 过期）。
"""

import asyncio
import random
import json
from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from config import REQUEST_DELAY_MIN, REQUEST_DELAY_MAX

SESSION_DIR = Path("xhs_session")
SESSION_FILE = SESSION_DIR / "state.json"


async def scrape(keywords: list[str], limit: int = 50) -> list[dict]:
    posts = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        # 加载已保存的 session（如果有）
        storage_state = str(SESSION_FILE) if SESSION_FILE.exists() else None
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            storage_state=storage_state,
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()

        # 检查是否已登录
        logged_in = await _ensure_logged_in(page, context)
        if not logged_in:
            await browser.close()
            return []

        for keyword in keywords:
            if len(posts) >= limit:
                break
            print(f"[logged-in] 搜索关键词: {keyword}")
            batch = await _scrape_keyword(page, keyword, limit - len(posts))
            posts.extend(batch)
            print(f"[logged-in] 当前收集: {len(posts)} 条")

        await browser.close()

    return posts


async def _ensure_logged_in(page, context) -> bool:
    await page.goto("https://www.xiaohongshu.com", timeout=30000)
    await asyncio.sleep(2)

    # 检查是否已经登录（有头像或用户菜单）
    avatar = await page.query_selector(
        ".user-avatar, [class*='avatar'], .user-info, [class*='userInfo']"
    )
    if avatar:
        print("[logged-in] 已使用保存的 session 登录")
        return True

    # 需要手动登录
    print("=" * 50)
    print("[logged-in] 请在弹出的浏览器里用小号扫码登录小红书")
    print("登录完成后，按回车键继续...")
    print("=" * 50)

    # 等待用户手动登录
    input()

    # 保存 session
    SESSION_DIR.mkdir(exist_ok=True)
    await context.storage_state(path=str(SESSION_FILE))
    print(f"[logged-in] Session 已保存到 {SESSION_FILE}，下次运行无需重新登录")

    # 验证登录
    avatar = await page.query_selector(
        ".user-avatar, [class*='avatar'], .user-info, [class*='userInfo']"
    )
    if not avatar:
        print("[logged-in] 警告：未检测到登录状态，请确认是否扫码成功")
        return False

    return True


async def _scrape_keyword(page, keyword: str, limit: int) -> list[dict]:
    encoded = quote(keyword)
    url = f"https://www.xiaohongshu.com/search_result?keyword={encoded}&type=51"

    try:
        await page.goto(url, timeout=30000)
        await asyncio.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
    except PlaywrightTimeout:
        print(f"[logged-in] 页面加载超时: {keyword}")
        return []

    posts = []
    seen_urls = set()
    scroll_count = 0

    while len(posts) < limit and scroll_count < 30:
        cards = await page.query_selector_all(
            "section.note-item, .feeds-page .note-item, "
            "[class*='note-item'], .note-list-scroll-container section"
        )

        for card in cards:
            if len(posts) >= limit:
                break
            post = await _extract_card_with_content(page, card)
            if post and post["url"] not in seen_urls:
                seen_urls.add(post["url"])
                post["keyword"] = keyword
                post["mode"] = "logged-in"
                posts.append(post)

        await page.evaluate("window.scrollBy(0, 800)")
        await asyncio.sleep(random.uniform(2.0, 4.5))
        scroll_count += 1

        no_more = await page.query_selector("[class*='noMore'], [class*='no-more']")
        if no_more:
            break

    return posts


async def _extract_card_with_content(page, card) -> dict | None:
    try:
        link_el = await card.query_selector("a")
        if not link_el:
            return None
        href = await link_el.get_attribute("href") or ""
        if not href:
            return None
        url = f"https://www.xiaohongshu.com{href}" if href.startswith("/") else href

        title_el = await card.query_selector(
            ".title, [class*='title'], .note-title, h3, .desc"
        )
        title = (await title_el.inner_text()).strip() if title_el else ""

        author_el = await card.query_selector(
            ".author, [class*='author'], .nickname, .user-name"
        )
        author = (await author_el.inner_text()).strip() if author_el else ""

        likes_el = await card.query_selector(
            ".like-wrapper, [class*='like'], .count, [class*='count']"
        )
        likes = (await likes_el.inner_text()).strip() if likes_el else ""

        # 登录模式：尝试进入帖子获取完整正文
        content = ""
        if url:
            try:
                detail_page = await page.context.new_page()
                await detail_page.goto(url, timeout=15000)
                await asyncio.sleep(random.uniform(1.5, 3.0))

                content_el = await detail_page.query_selector(
                    ".note-content, [class*='noteContent'], "
                    ".content, [class*='desc'], #detail-desc"
                )
                if content_el:
                    content = (await content_el.inner_text()).strip()

                await detail_page.close()
                await asyncio.sleep(random.uniform(1.0, 2.0))
            except Exception:
                pass  # 拿不到正文就用标题

        return {
            "title": title,
            "content": content,
            "author": author,
            "likes": likes,
            "url": url,
            "source": "xiaohongshu",
        }
    except Exception:
        return None
