# food-data-pipeline

小红书美食帖子爬虫 + Claude 结构化提取。

## 快速开始

### 1. 安装依赖

```bash
cd food-data-pipeline
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置（可选）

```bash
cp .env.example .env
# 用任意编辑器打开 .env，填入 ANTHROPIC_API_KEY
```

没有 API key 也能跑，只是跳过提取步骤。

### 3. 运行

```bash
# 访客模式（不需要账号，推荐先用这个）
python run.py --mode guest

# 登录模式（需要用小红书小号扫码，内容更全）
python run.py --mode logged-in

# 换城市
python run.py --city "New York"

# 多爬一点
python run.py --limit 100

# 只爬不提取
python run.py --no-extract
```

### 4. 丰富数据（Yelp + Google 地图）

爬取并提取出结构化餐厅数据后，可以再用 Yelp API 和 Google 地图补充更多信息
（评分、评论数、价位、营业时间、电话、官网、简介等）。

先在 `.env` 里填入 `YELP_API_KEY`（免费，每天 500 次请求，无需信用卡，
申请地址：https://www.yelp.com/developers/ → Create App → 复制 API Key）。
Google 地图部分用 Playwright 浏览器抓取，不需要 key。

```bash
# 丰富默认城市（洛杉矶）的全部餐厅：Yelp + Google 地图
python enrich.py

# 换城市
python enrich.py --city "New York"

# 只用 Yelp（不打开浏览器，快）
python enrich.py --yelp-only

# 只用 Google 地图（不需要 Yelp key）
python enrich.py --gmaps-only

# 只处理前 N 条
python enrich.py --limit 20

# 断点续跑：跳过已经丰富过的餐厅
python enrich.py --resume
```

数据来源分工：

| 来源 | 提供字段 |
|---|---|
| Yelp API | 评分 `yelp_rating`、评论数 `yelp_review_count`、价位 `price`、分类 `yelp_categories`、营业时间、电话 `phone`、完整地址、`yelp_url` |
| Google 地图 | 简介 `description`、官网 `website`（Yelp 免费 API 没有这两项），并补全 Yelp 缺失的字段 |

> Google 地图用真实浏览器抓取（`headless=False`），运行时会弹出 Chromium 窗口，
> 每条之间有 3–6 秒随机停顿，属于正常现象，不要手动关闭窗口。

## 输出文件

| 文件 | 内容 |
|---|---|
| `data/raw_posts_los_angeles.json` | 原始帖子（标题 / 正文 / 链接）|
| `data/restaurants_los_angeles.json` | 结构化餐厅数据（需要 Claude API key）|
| `data/enriched_los_angeles.json` | 丰富后的餐厅数据（Yelp + Google 地图，由 `enrich.py` 生成）|

## 支持城市

见 `config.py` 的 `SEARCH_KEYWORDS`，目前支持：
- Los Angeles
- New York
- San Francisco
- 广州
- 上海

## 文件说明

```
├── run.py              一键入口（--mode / --city / --limit）
├── config.py           关键词、城市配置
├── scrapers/
│   ├── xhs_guest.py    访客模式（无需账号）
│   └── xhs_logged_in.py 登录模式（小号扫码）
├── extractor.py        Claude API 提取餐厅信息
├── enrich.py           Yelp + Google 地图 丰富数据入口
├── enrichers/
│   ├── yelp.py         Yelp Fusion API（评分 / 价位 / 营业时间等）
│   └── google_maps.py  Google 地图 Playwright 抓取（简介 / 官网）
└── storage.py          JSON 读写 + 去重
```
