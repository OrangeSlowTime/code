"""全局常量与配置读取。"""
import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ---------------------------------------------------------------
# 大模型配置
# ---------------------------------------------------------------
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("未获取到 DEEPSEEK_API_KEY，请在 .env 中配置后重试。")

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = "deepseek-chat"

# ---------------------------------------------------------------
# 数据文件
# ---------------------------------------------------------------
DB_PATH = os.path.join(BASE_DIR, "tmall.db")
CSV_DIR = os.path.join(BASE_DIR, "TmallData")
CSV_FALLBACK = os.path.join(BASE_DIR, "TmallData.csv")
TABLE_NAME = "tmall_products"

# ---------------------------------------------------------------
# Web 服务
# ---------------------------------------------------------------
SECRET_KEY = "tmall_ai_secret_key_2026"
DEMO_USERNAME = "admin"
DEMO_PASSWORD = "123456"
HOST = "0.0.0.0"
PORT = 5000

# 需要按数值处理的列
NUMERIC_COLUMNS = [
    "年销量",
    "邮费",
    "预售定金",
    "最终促销价",
    "预估凑单价",
    "原价",
    "折后价",
    "当日促销销量",
    "收益比例",
    "近2小时促销销量",
    "推广佣金",
    "佣金比例",
    "补贴金额",
    "补贴比例",
    "补贴上限",
]
