"""
一键入口。

用法：
  python run.py                          # 默认：访客模式 + 洛杉矶 + 50条
  python run.py --mode guest             # 访客模式（不需要账号）
  python run.py --mode logged-in         # 登录模式（需要小号扫码）
  python run.py --city "New York"        # 换城市
  python run.py --limit 100             # 爬更多条
  python run.py --no-extract             # 跳过 Claude 提取，只存原始帖子
"""

import asyncio
import argparse
import sys

from config import DEFAULT_CITY, DEFAULT_LIMIT, SEARCH_KEYWORDS, USE_CLAUDE_EXTRACTION
import storage


def parse_args():
    parser = argparse.ArgumentParser(description="小红书美食爬虫")
    parser.add_argument(
        "--mode",
        choices=["guest", "logged-in"],
        default="guest",
        help="guest=不需要账号 / logged-in=用小号登录（内容更全）",
    )
    parser.add_argument("--city", default=DEFAULT_CITY, help="目标城市")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="最多爬几条帖子")
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="跳过 Claude 提取，只保存原始帖子",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    city = args.city
    mode = args.mode
    limit = args.limit
    do_extract = not args.no_extract and USE_CLAUDE_EXTRACTION

    keywords = SEARCH_KEYWORDS.get(city)
    if not keywords:
        print(f"[错误] 城市 '{city}' 不在 config.py 的 SEARCH_KEYWORDS 里")
        print(f"支持的城市: {list(SEARCH_KEYWORDS.keys())}")
        sys.exit(1)

    print("=" * 50)
    print(f"模式: {mode}")
    print(f"城市: {city}")
    print(f"关键词: {keywords}")
    print(f"目标数量: {limit} 条")
    print(f"Claude 提取: {'开启' if do_extract else '关闭（跳过或无 API Key）'}")
    print("=" * 50)

    # 选择爬虫
    if mode == "guest":
        from scrapers import xhs_guest as scraper
    else:
        from scrapers import xhs_logged_in as scraper

    # 爬取
    print(f"\n[1/3] 开始爬取...")
    posts = await scraper.scrape(keywords, limit=limit)
    print(f"[1/3] 爬取完成，共 {len(posts)} 条帖子")

    if not posts:
        print("没有爬到任何帖子，请检查网络或调整关键词")
        return

    # 保存原始帖子
    print(f"\n[2/3] 保存原始帖子...")
    storage.save_raw_posts(posts, city)

    # Claude 提取
    if do_extract:
        print(f"\n[3/3] 用 Claude 提取结构化餐厅数据...")
        from extractor import batch_extract
        restaurants = batch_extract(posts)
        storage.save_restaurants(restaurants, city)
        print(f"\n完成！提取到 {len(restaurants)} 家餐厅")
    else:
        if not USE_CLAUDE_EXTRACTION:
            print(f"\n[3/3] 跳过 Claude 提取（未设置 ANTHROPIC_API_KEY）")
            print("设置 API key 后重新运行可自动提取结构化数据")
        else:
            print(f"\n[3/3] 跳过 Claude 提取（--no-extract）")
        print(f"\n完成！原始帖子已保存，共 {len(posts)} 条")


if __name__ == "__main__":
    asyncio.run(main())
