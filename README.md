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

## 输出文件

| 文件 | 内容 |
|---|---|
| `data/raw_posts_los_angeles.json` | 原始帖子（标题 / 正文 / 链接）|
| `data/restaurants_los_angeles.json` | 结构化餐厅数据（需要 Claude API key）|

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
└── storage.py          JSON 读写 + 去重
```
