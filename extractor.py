"""
用 Claude API 把小红书帖子提取成结构化餐厅数据。
需要设置环境变量 ANTHROPIC_API_KEY 才能使用。
没有 API key 的话，run.py 会自动跳过这一步，把原始帖子存下来。
"""

import json
import anthropic
from config import ANTHROPIC_API_KEY


def extract_restaurant(post: dict) -> dict | None:
    """
    输入一条小红书帖子，返回提取出的餐厅信息。
    如果帖子里没有明确的餐厅，返回 None。
    """
    text = f"标题：{post.get('title', '')}\n正文：{post.get('content', '')}"

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # 用最快最便宜的模型做提取
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": f"""从下面这条小红书帖子里提取餐厅信息。
如果帖子里没有提到具体的餐厅（比如只是泛泛谈美食），返回 null。

帖子内容：
{text}

用 JSON 格式返回，字段如下（不确定的字段填 null）：
{{
  "name": "餐厅名称",
  "city": "城市",
  "area": "区域/街道（比如 Koreatown、蒙特利公园）",
  "cuisine": "菜系（比如 川菜、烤肉、寿司）",
  "price_range": "人均价格（比如 $15、$$、$20-30）",
  "highlights": "一句话亮点（从帖子里提取，不要自己编）",
  "address": "地址（如果帖子里有）"
}}

只返回 JSON，不要其他文字。如果不是餐厅帖子，只返回 null。""",
            }
        ],
    )

    raw = response.content[0].text.strip()

    if raw.lower() == "null" or not raw:
        return None

    try:
        restaurant = json.loads(raw)
        restaurant["source_url"] = post.get("url", "")
        restaurant["source_title"] = post.get("title", "")
        restaurant["keyword"] = post.get("keyword", "")
        return restaurant
    except json.JSONDecodeError:
        return None


def batch_extract(posts: list[dict]) -> list[dict]:
    """批量提取，自动跳过无法提取的帖子，打印进度。"""
    results = []
    for i, post in enumerate(posts, 1):
        print(f"[extract] {i}/{len(posts)}: {post.get('title', '')[:30]}...")
        restaurant = extract_restaurant(post)
        if restaurant:
            results.append(restaurant)
            print(f"  ✓ 提取到: {restaurant.get('name', '?')}")
        else:
            print(f"  - 跳过（非餐厅帖子）")
    return results
