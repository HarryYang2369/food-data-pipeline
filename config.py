import os

# 每个城市对应的小红书搜索关键词
SEARCH_KEYWORDS = {
    "Los Angeles": ["洛杉矶美食", "LA美食", "洛杉矶好吃的", "洛杉矶餐厅推荐"],
    "New York":    ["纽约美食", "纽约好吃的", "纽约餐厅推荐"],
    "San Francisco": ["旧金山美食", "湾区美食"],
    "广州": ["广州美食", "广州好吃的", "广州餐厅推荐"],
    "上海": ["上海美食", "上海好吃的", "上海餐厅推荐"],
}

DEFAULT_CITY = "Los Angeles"
DEFAULT_LIMIT = 50
DATA_DIR = "data"

# 请求间隔（秒），模拟真人操作
REQUEST_DELAY_MIN = 2.0
REQUEST_DELAY_MAX = 5.0

# Claude API（可选，用于结构化提取）
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
USE_CLAUDE_EXTRACTION = bool(ANTHROPIC_API_KEY)

# Yelp Fusion API（可选，用于丰富餐厅数据）
# 免费，每天 500 次请求，无需信用卡
# 申请地址：https://www.yelp.com/developers/ → Create App → API Key
YELP_API_KEY = os.getenv("YELP_API_KEY", "")
