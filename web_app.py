"""Flask 应用构建、路由定义与安全鉴权。"""
import hashlib
import hmac
import itertools
import json
import math
import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime

import pandas as pd
from flask import (
    jsonify,
    redirect,
    render_template,
    render_template_string,
    request,
    session,
    url_for,
)
from jinja2 import ChoiceLoader, FileSystemLoader
from openai import OpenAI

import config
from vanna.legacy.flask import VannaFlaskApp
from vanna_core import get_vanna

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>天猫数据 AI 分析平台 · 登录</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="flex min-h-screen items-center justify-center bg-[#111827] font-sans text-slate-200">
  <div class="w-[380px] rounded-2xl border border-white/5 bg-[#1F2937] p-8 shadow-2xl shadow-black/40">
    <div class="mb-6 text-center">
      <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-cyan-400 text-xl font-bold text-white">猫</div>
      <h1 class="text-xl font-semibold text-white">天猫数据 AI 分析平台</h1>
      <p class="mt-1 text-xs text-slate-500">电商大数据商业分析与智能助手</p>
    </div>
    {% if error %}
    <p class="mb-4 rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-300">{{ error }}</p>
    {% endif %}
    {% if message %}
    <p class="mb-4 rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">{{ message }}</p>
    {% endif %}
    <form method="POST" action="/login" class="space-y-4">
      <div>
        <label class="mb-1 block text-sm text-slate-400" for="username">用户名</label>
        <input id="username" name="username" type="text" required
               class="w-full rounded-lg border border-[#374151] bg-[#111827] px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-400">
      </div>
      <div>
        <label class="mb-1 block text-sm text-slate-400" for="password">密码</label>
        <input id="password" name="password" type="password" required
               class="w-full rounded-lg border border-[#374151] bg-[#111827] px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-400">
        <div class="mt-2 text-right">
          <a href="/forget_password" class="text-xs text-indigo-400 transition hover:text-indigo-300">忘记密码？</a>
        </div>
      </div>
      <button type="submit"
              class="w-full rounded-lg bg-gradient-to-r from-indigo-500 to-cyan-500 py-2.5 text-sm font-semibold text-white transition hover:opacity-90">
        登录
      </button>
    </form>
    <div class="mt-4 text-center text-sm text-slate-400">
      没有账号？<a href="/register" class="text-indigo-400 transition hover:text-indigo-300">点击注册</a>
    </div>
  </div>
</body>
</html>
"""

REGISTER_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>注册账号 · 天猫数据 AI 分析平台</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="flex min-h-screen items-center justify-center bg-[#111827] font-sans text-slate-200">
  <div class="w-[380px] rounded-2xl border border-white/5 bg-[#1F2937] p-8 shadow-2xl shadow-black/40">
    <div class="mb-6 text-center">
      <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-cyan-400 text-xl font-bold text-white">猫</div>
      <h1 class="text-xl font-semibold text-white">注册新账号</h1>
      <p class="mt-1 text-xs text-slate-500">创建后即可登录天猫数据 AI 分析平台</p>
    </div>
    {% if error %}
    <p class="mb-4 rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-300">{{ error }}</p>
    {% endif %}
    <form method="POST" action="/register" class="space-y-4">
      <div>
        <label class="mb-1 block text-sm text-slate-400" for="username">用户名</label>
        <input id="username" name="username" type="text" required minlength="3" maxlength="20"
               class="w-full rounded-lg border border-[#374151] bg-[#111827] px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-400">
      </div>
      <div>
        <label class="mb-1 block text-sm text-slate-400" for="password">密码（至少 6 位）</label>
        <input id="password" name="password" type="password" required minlength="6"
               class="w-full rounded-lg border border-[#374151] bg-[#111827] px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-400">
      </div>
      <div>
        <label class="mb-1 block text-sm text-slate-400" for="confirm_password">确认密码</label>
        <input id="confirm_password" name="confirm_password" type="password" required minlength="6"
               class="w-full rounded-lg border border-[#374151] bg-[#111827] px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-400">
      </div>
      <div>
        <label class="mb-1 block text-sm text-slate-400" for="email">邮箱（选填）</label>
        <input id="email" name="email" type="email" placeholder="用于找回密码"
               class="w-full rounded-lg border border-[#374151] bg-[#111827] px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-400">
      </div>
      <div>
        <label class="mb-1 block text-sm text-slate-400" for="phone">手机号（选填）</label>
        <input id="phone" name="phone" type="tel" pattern="[0-9+\-\s]{6,20}" placeholder="用于找回密码"
               class="w-full rounded-lg border border-[#374151] bg-[#111827] px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-400">
      </div>
      <p class="text-xs text-slate-500">提示：忘记密码时需要验证注册时填写的邮箱或手机号，建议至少填写一项。</p>
      <button type="submit"
              class="w-full rounded-lg bg-gradient-to-r from-indigo-500 to-cyan-500 py-2.5 text-sm font-semibold text-white transition hover:opacity-90">
        注册
      </button>
    </form>
    <div class="mt-4 text-center text-sm text-slate-400">
      已有账号？<a href="/login" class="text-indigo-400 transition hover:text-indigo-300">返回登录</a>
    </div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------
# 用户表与密码校验
# ---------------------------------------------------------------
DEFAULT_AVATAR = "https://api.dicebear.com/7.x/thumbs/svg?seed=tmall"
USER_EXTRA_COLUMNS = {
    "email": "TEXT",
    "phone": "TEXT",
    "nickname": "TEXT",
    "avatar": "TEXT",
    "status": "INTEGER DEFAULT 1",
}


def init_users_table():
    """初始化 sys_users 表，并自动补齐个人中心所需字段（幂等）。"""
    conn = sqlite3.connect(config.DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sys_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TEXT
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sys_users)")}
        for column, ctype in USER_EXTRA_COLUMNS.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE sys_users ADD COLUMN {column} {ctype}")

        # 首次建表时插入超级管理员；已存在则只保证角色为 admin，不重置密码
        conn.execute(
            """INSERT OR IGNORE INTO sys_users
                   (username, password, role, created_at, nickname, email, phone, avatar, status)
               VALUES (?, ?, 'admin', ?, ?, ?, '', ?, 1)""",
            (
                config.DEMO_USERNAME,
                hash_password(config.DEMO_PASSWORD),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "管理员",
                "admin@example.com",
                DEFAULT_AVATAR,
            ),
        )
        conn.execute(
            "UPDATE sys_users SET role = 'admin' WHERE username = ?",
            (config.DEMO_USERNAME,),
        )
        conn.execute(
            "UPDATE sys_users SET avatar = ? WHERE avatar IS NULL OR avatar = ''",
            (DEFAULT_AVATAR,),
        )
        conn.commit()
    finally:
        conn.close()


def init_ai_logs_table():
    """AI 审计日志表（幂等）。"""
    conn = sqlite3.connect(config.DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                question TEXT,
                sql TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def log_ai_sql(username, question, sql):
    """记录一次 AI 生成的 SQL，供后台审计。"""
    if not sql:
        return
    conn = sqlite3.connect(config.DB_PATH)
    try:
        conn.execute(
            """INSERT INTO ai_logs (username, question, sql, created_at)
               VALUES (?, ?, ?, ?)""",
            (
                username or "unknown",
                (question or "")[:500],
                (sql or "")[:2000],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def hash_password(password, salt=None):
    """PBKDF2-SHA256 加盐哈希，存储格式 salt$hash。"""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000
    ).hex()
    return f"{salt}${digest}"


def verify_password(password, stored):
    if not stored:
        return False
    if "$" not in stored:
        return hmac.compare_digest(password, stored)
    salt = stored.split("$", 1)[0]
    return hmac.compare_digest(hash_password(password, salt), stored)


def authenticate_user(username, password):
    """参数化查询校验数据库账号。"""
    conn = sqlite3.connect(config.DB_PATH)
    try:
        row = conn.execute(
            "SELECT password FROM sys_users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()
    return bool(row) and verify_password(password, row[0])


def get_user_login_info(username):
    """登录用：返回密码哈希、角色与状态，所有账号一视同仁走数据库。"""
    conn = sqlite3.connect(config.DB_PATH)
    try:
        row = conn.execute(
            "SELECT password, role, status FROM sys_users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "password": row[0],
        "role": row[1] or "user",
        "status": 1 if row[2] is None else int(row[2]),
    }


def get_user_profile(username):
    """读取个人中心所需的用户信息。"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT id, username, role, created_at, nickname, email, phone, avatar
               FROM sys_users WHERE username = ?""",
            (username,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    profile = dict(row)
    profile["nickname"] = profile.get("nickname") or profile["username"]
    profile["avatar"] = profile.get("avatar") or DEFAULT_AVATAR
    return profile


def update_user_profile(username, nickname, email, phone, avatar):
    """更新昵称、邮箱、手机号、头像；返回错误信息或 None。"""
    conn = sqlite3.connect(config.DB_PATH)
    try:
        if email:
            row = conn.execute(
                "SELECT username FROM sys_users WHERE email = ? AND username <> ?",
                (email, username),
            ).fetchone()
            if row:
                return "该邮箱已被其他账号使用"
        conn.execute(
            """UPDATE sys_users
               SET nickname = ?, email = ?, phone = ?, avatar = ?
               WHERE username = ?""",
            (nickname, email, phone, avatar or DEFAULT_AVATAR, username),
        )
        conn.commit()
    finally:
        conn.close()
    return None


def update_user_password(username, new_password):
    conn = sqlite3.connect(config.DB_PATH)
    try:
        conn.execute(
            "UPDATE sys_users SET password = ? WHERE username = ?",
            (hash_password(new_password), username),
        )
        conn.commit()
    finally:
        conn.close()


def find_user_by_contact(username, contact):
    """忘记密码：校验用户名与邮箱/手机号是否匹配。"""
    conn = sqlite3.connect(config.DB_PATH)
    try:
        row = conn.execute(
            """SELECT username FROM sys_users
               WHERE username = ? AND (email = ? OR phone = ?)""",
            (username, contact, contact),
        ).fetchone()
    finally:
        conn.close()
    return bool(row)


# ---------------------------------------------------------------
# 会话记忆（进程内存，键为浏览器 session 中的 chat_sid）
# ---------------------------------------------------------------
_CHAT_STORE = {}
CHAT_HISTORY_LIMIT = 40       # 保存的最大消息条数（约 20 轮）
CHAT_CONTEXT_LIMIT = 8        # 每次请求大模型携带的历史消息条数


def get_chat_sid():
    sid = session.get("chat_sid")
    if not sid:
        sid = uuid.uuid4().hex
        session["chat_sid"] = sid
    return sid


def get_chat_history():
    return _CHAT_STORE.get(get_chat_sid(), [])


def append_chat_history(role, content, sql="", data=None, summary="", products=None):
    history = _CHAT_STORE.setdefault(get_chat_sid(), [])
    item = {"role": role, "content": content or "", "sql": sql or ""}
    if data:
        item["data"] = data[:10]
        item["summary"] = summary or ""
    if products:
        item["products"] = products
    history.append(item)
    if len(history) > CHAT_HISTORY_LIMIT:
        del history[: len(history) - CHAT_HISTORY_LIMIT]
    return history


def clear_chat_history():
    _CHAT_STORE.pop(get_chat_sid(), None)


def build_llm_messages(question):
    """系统提示 + 最近若干轮历史 + 当前问题。"""
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    for item in get_chat_history()[-CHAT_CONTEXT_LIMIT:]:
        content = str(item.get("content") or "")[:800]
        if content:
            messages.append({"role": item["role"], "content": content})
    messages.append({"role": "user", "content": question})
    return messages


# ---------------------------------------------------------------
# 推荐条数控制
# ---------------------------------------------------------------
_CN_DIGITS = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}
_RECO_HINT = re.compile(r"(推荐|来点|来些|给我|想要|有没有|有什么|有哪些|便宜点|挑|选)")
_RANK_HINT = re.compile(r"(top\s*\d+|排行|排名|最高|最低|热销|销量榜|前\s*\d+)", re.IGNORECASE)
_COUNT_RE = re.compile(r"(\d+|[一二两三四五六七八九十])\s*(个|款|种|条|件|样|瓶|包|盒|双|台|部|张|斤|袋|支|把)")


def parse_recommend_count(question):
    """解析「推荐 5 个」中的数量；未指定返回 None。"""
    match = _COUNT_RE.search(question)
    if not match:
        return None
    token = match.group(1)
    count = int(token) if token.isdigit() else _CN_DIGITS.get(token, 5)
    return max(1, min(count, 50))


def recommend_target(question):
    """推荐类问题需要返回的条数；非推荐/排行类返回 None。"""
    if not question or _RANK_HINT.search(question) or not _RECO_HINT.search(question):
        return None
    return parse_recommend_count(question) or 5


def apply_recommend_limit(question, sql):
    """推荐类问题按用户要求的条数（默认 5）覆盖 LIMIT；排行类保持原样。"""
    limit = recommend_target(question)
    if not sql or not limit:
        return sql
    if re.search(r"\bLIMIT\s+\d+", sql, re.IGNORECASE):
        return re.sub(
            r"\bLIMIT\s+\d+", f"LIMIT {limit}", sql, count=1, flags=re.IGNORECASE
        )
    stripped = sql.rstrip().rstrip(";")
    return f"{stripped} LIMIT {limit};"


def expand_sql_limit(sql, limit):
    """先多取一些数据，过滤配件/去重后再截断到目标条数。"""
    fetch = max(limit * 10, 60)
    return re.sub(r"\bLIMIT\s+\d+", f"LIMIT {fetch}", sql, count=1, flags=re.IGNORECASE)


# ---------------------------------------------------------------
# 极值查询（销量第一 / 最高 / 最低 / 最便宜）
# ---------------------------------------------------------------
_EXTREME_RE = re.compile(
    r"(第一|最高|最低|最便宜|最贵|最热|最强|最多|销量冠军|top\s*1\b)", re.IGNORECASE
)
# 真正的「推荐 N 个」计数（包/件/斤 等是规格，不算推荐条数）
_RECO_COUNT_RE = re.compile(
    r"(\d+|[一二两三四五六七八九十])\s*(个|款|种|条|样|台|部|张|支)"
)


def is_extreme_query(question):
    """是否是「只要一条」的极值问题（用户明确要推荐多条时除外）。"""
    if not question or not _EXTREME_RE.search(question):
        return False
    match = _RECO_COUNT_RE.search(question)
    if not match:
        return True
    token = match.group(1)
    count = int(token) if token.isdigit() else _CN_DIGITS.get(token, 1)
    return count <= 1


def force_single_limit(sql):
    """把 SQL 的 LIMIT 强制改为 1。"""
    if not sql:
        return sql
    if re.search(r"\bLIMIT\s+\d+", sql, re.IGNORECASE):
        return re.sub(
            r"\bLIMIT\s+\d+", "LIMIT 1", sql, count=1, flags=re.IGNORECASE
        )
    stripped = sql.rstrip().rstrip(";")
    return f"{stripped} LIMIT 1;"


def dedupe_distinct_brands(df):
    """「不同品牌」场景：排除无品牌，并按品牌去重。"""
    if df is None or df.empty or "品牌名称" not in df.columns:
        return df
    brands = df["品牌名称"].astype(str).str.strip()
    df = df[~brands.isin(["无品牌", "未知品牌", "None", "nan", ""])]
    if df.empty:
        return df
    return df.drop_duplicates(subset=["品牌名称"], keep="first")


def run_product_query(question, sql, target=None, single=False):
    """执行 SQL 并做配件过滤、品牌去重、去重、条数截断。"""
    is_detail = "商品标题" in sql
    if single:
        limit = 1
    elif target:
        limit = target
    elif is_detail:
        limit = 10
    else:
        limit = None

    fetch_sql = expand_sql_limit(sql, limit) if limit else sql
    df = _vn.run_sql(fetch_sql)
    df = filter_accessory_results(question, df)
    if "不同品牌" in question:
        df = dedupe_distinct_brands(df)
    df = dedupe_products(df)
    if limit and df is not None and not df.empty:
        df = df.head(limit)
    return df


def missing_product_link(df):
    """商品明细结果缺少「商品链接」列（大模型没按强制规则输出）。"""
    return (
        df is not None
        and not df.empty
        and "商品标题" in df.columns
        and "商品链接" not in df.columns
    )


# ---------------------------------------------------------------
# 多轮上下文改写（Query Rewrite）
# ---------------------------------------------------------------
REWRITE_HISTORY_ROUNDS = 3


def _last_turn_context():
    """取最近 3 轮内的上一轮用户问题和 SQL。"""
    recent = get_chat_history()[-REWRITE_HISTORY_ROUNDS * 2 :]
    prev_question, prev_sql = "", ""
    for item in reversed(recent):
        if item["role"] == "user":
            prev_question = str(item.get("content") or "")
            break
    for item in recent:
        if item["role"] == "assistant" and item.get("sql"):
            prev_sql = str(item["sql"])
    return prev_question, prev_sql


# 追问式片段的特征：修改条件、筛选结果、换商品等
_FOLLOWUP_HINT = re.compile(
    r"(要|不要|只要|只看|再|换成|换一个|改成|改为|价格|预算|便宜|贵一点|"
    r"以上|以下|以内|之间|呢$|吗$)"
)
# 代词/省略语：一定是追问，必须结合上下文
_PRONOUN_HINT = re.compile(
    r"(这个|这些|那些|上面|刚才|刚刚|它们?|其中|哪个|哪款|哪家|哪一个|呢$|吗$)"
)
# 完整问题里出现这些商品名词时，说明用户是独立提问，不做改写
_PRODUCT_NOUNS = (
    "手机", "平板", "耳机", "纸巾", "抽纸", "卷纸", "充电宝", "移动电源", "电宝",
    "笔记本", "牛奶", "零食", "保温杯", "电脑", "键盘", "鼠标", "显示器", "手表",
    "衣服", "外套", "鞋", "包", "电视", "空调", "冰箱", "洗衣机", "面膜", "洗护",
)


def needs_rewrite(question):
    """只有「追问式片段」才改写，避免把上一轮条件污染到新的独立问题。"""
    prev_question, _ = _last_turn_context()
    if not prev_question:
        return False
    if _PRONOUN_HINT.search(question):
        return True
    if any(noun in question for noun in _PRODUCT_NOUNS):
        return False
    if len(question) <= 12:
        return True
    return bool(_FOLLOWUP_HINT.search(question))


def _history_digest(rounds=3):
    """最近 N 轮对话摘要（含上一轮 SQL），供重写时锁定商品类目。"""
    lines = []
    for item in get_chat_history()[-rounds * 2:]:
        role = "用户" if item.get("role") == "user" else "助手"
        content = str(item.get("content") or "")[:150]
        sql = str(item.get("sql") or "")[:220]
        if not content:
            continue
        lines.append(f"{role}：{content}" + (f"（SQL：{sql}）" if sql else ""))
    return "\n".join(lines) or "（无）"


def rewrite_query(question):
    """结合历史对话，把「哪个销量最多」等追问改写为完整查询句。"""
    prev_question, _ = _last_turn_context()
    if not prev_question:
        return question

    prompt = f"""你是意图重写助手。
历史对话记录：
{_history_digest()}
用户当前输入：{question}

规则：
1. 如果当前输入是追问（如包含"哪个最多"、"这个"、"上面的"、"只要X包"等代词或省略语），你必须结合历史对话中刚刚查询过的商品类别（如纸巾），补全为一个完整的独立问题（如"查询24包纸巾中销量最高的一款"）。
2. 结合上下文时，严禁跨类目跳跃。如果上文聊的是纸巾，绝对不要重写成充电宝。
3. 只输出重写后的完整查询句子，不要任何废话、不要解释、不要引号。"""
    try:
        rewritten = llm_text(
            [{"role": "user", "content": prompt}], temperature=0, max_tokens=80
        )
    except Exception:
        return question

    rewritten = (rewritten or "").strip().strip('"').strip("'").strip("`")
    rewritten = re.sub(r"^(重写后|改写后)[:：]?\s*", "", rewritten).strip()
    if (
        not rewritten
        or len(rewritten) > 80
        or "\n" in rewritten
        or "重写" in rewritten
    ):
        return question
    return rewritten


# ---------------------------------------------------------------
# 凑单/预算方案：实体抽取 + 贪心组合（Greedy Planning）+ 客观文案
# ---------------------------------------------------------------
PLAN_HINTS = re.compile(r"(方案|凑单|规划|预算)")
BUDGET_HINTS = re.compile(r"(\d+(?:\.\d+)?\s*(?:元|块钱|块)|预算)")
MIN_SPEND_RE = re.compile(
    r"(?:至少|最少|起码|不低于)\s*(?:要|得|花|消费|买)*\s*(\d+(?:\.\d+)?)\s*(?:元|块钱|块)?"
)
CHANGE_HINTS = re.compile(r"(换一种|换一批|换几个|换一个|再来一[种批组]|不喜欢|不满意)")
# 动态质量升级指令，例如「耳机质量要好点」
QUALITY_HINTS = re.compile(
    r"(质量(?:要|得|再)?好(?:一)?点?|品质(?:要|得|再)?(?:好|高)(?:一)?点?|"
    r"高(?:端|档)(?:一)?点?|大牌|升级(?:一)?下?|贵(?:一)?点)"
)
QUALITY_ANCHOR = 80.0          # 质量升级后的价格锚点
# 品类最低合理价（低于该价格视为配件/劣质品，宁可不凑）
PRICE_ANCHORS = {
    "保温杯": 20.0,
    "秋衣": 30.0,
    "耳机": 20.0,
}
# 「一箱」等整箱需求：标题词 + 价格区间
BOX_HINTS = re.compile(r"(一箱|整箱|箱装|一箱装)")
BOX_RULES = {
    "纸巾": {"title": "箱", "min": 15.0, "max": 60.0},
}

# 商品词 -> 类目限定条件（未知商品词回退为标题/类目 LIKE）
BUNDLE_ITEM_RULES = {
    "纸巾": "(商品标题 LIKE '%纸巾%' OR 商品标题 LIKE '%抽纸%' OR 商品标题 LIKE '%卷纸%')",
    "耳机": "(商品标题 LIKE '%耳机%' AND 商品标题 NOT LIKE '%清洁%' "
            "AND 商品标题 NOT LIKE '%刷%' AND 商品标题 NOT LIKE '%转接%' "
            "AND 商品标题 NOT LIKE '%转换%' AND 商品标题 NOT LIKE '%适用%' "
            "AND 商品标题 NOT LIKE '%配件%' AND 商品标题 NOT LIKE '%收纳%' "
            "AND 商品标题 NOT LIKE '%耳机套%' AND 商品标题 NOT LIKE '%数据线%' "
            "AND 二级类目名称 NOT LIKE '%清洁工具%')",
    "笔记本": "(商品标题 LIKE '%笔记本%' AND 商品标题 NOT LIKE '%配件%' "
             "AND 商品标题 NOT LIKE '%鼠标垫%' AND 商品标题 NOT LIKE '%打印纸%' "
             "AND 商品标题 NOT LIKE '%电脑%' AND 商品标题 NOT LIKE '%保护套%' "
             "AND 商品标题 NOT LIKE '%支架%' AND 商品标题 NOT LIKE '%膜%' "
             "AND 商品标题 NOT LIKE '%包%' AND 商品标题 NOT LIKE '%玩具%' "
             "AND 商品标题 NOT LIKE '%这本书%')",
    "鼠标": "(商品标题 LIKE '%鼠标%' AND 商品标题 NOT LIKE '%垫%' "
            "AND 商品标题 NOT LIKE '%贴%' AND 商品标题 NOT LIKE '%配件%' "
            "AND 商品标题 NOT LIKE '%收纳%' AND 商品标题 NOT LIKE '%电池%' "
            "AND 商品标题 NOT LIKE '%适用%' AND 商品标题 NOT LIKE '%延长线%' "
            "AND 商品标题 NOT LIKE '%数据线%' AND 商品标题 NOT LIKE '%网卡%' "
            "AND 商品标题 NOT LIKE '%打印%' AND 商品标题 NOT LIKE '%转换%' "
            "AND 商品标题 NOT LIKE '%转接%' AND 商品标题 NOT LIKE '%扩展%' "
            "AND 商品标题 NOT LIKE '%拓展%' AND 商品标题 NOT LIKE '%hub%' "
            "AND 商品标题 NOT LIKE '%一拖%' AND 商品标题 NOT LIKE '%分线%')",
    "充电宝": "(商品标题 LIKE '%充电宝%' AND 商品标题 NOT LIKE '%转换%' "
             "AND 商品标题 NOT LIKE '%转接%' AND 商品标题 NOT LIKE '%数据线%' "
             "AND 商品标题 NOT LIKE '%充电线%' AND 商品标题 NOT LIKE '%适用%' "
             "AND 商品标题 NOT LIKE '%配件%' AND 商品标题 NOT LIKE '%收纳%')",
    "平板": "商品标题 LIKE '%平板%'",
    "手机": "二级类目名称 = '手机'",
    "保温杯": "(商品标题 LIKE '%保温杯%' AND 商品标题 NOT LIKE '%杯刷%' "
             "AND 商品标题 NOT LIKE '%密封圈%' AND 商品标题 NOT LIKE '%配件%' "
             "AND 商品标题 NOT LIKE '%胶圈%' AND 商品标题 NOT LIKE '%杯盖%')",
    "秋衣": "(商品标题 LIKE '%秋衣%' OR 商品标题 LIKE '%保暖内衣%' "
           "OR 商品标题 LIKE '%秋裤%') "
           "AND 商品标题 NOT LIKE '%背心%' AND 商品标题 NOT LIKE '%打底%' "
           "AND 商品标题 NOT LIKE '%半截%'",
    "牛奶": "(商品标题 LIKE '%牛奶%' OR 二级类目名称 LIKE '%牛奶%') "
            "AND 商品标题 NOT LIKE '%麦片%' AND 商品标题 NOT LIKE '%燕麦%' "
            "AND 商品标题 NOT LIKE '%饼干%' AND 商品标题 NOT LIKE '%奶糖%'",
    "零食": "(商品标题 LIKE '%零食%' OR 一级类目名称 LIKE '%零食%')",
}

# 错别字 / 同义词纠正
ITEM_ALIAS = {
    "电宝": "充电宝",
    "移动电源": "充电宝",
    "充电器": "充电宝",
    "抽纸": "纸巾",
    "卷纸": "纸巾",
    "卫生纸": "纸巾",
    "本子": "笔记本",
    "记事本": "笔记本",
    "上衣": "秋衣",
    "外套": "秋衣",
    "酸奶": "牛奶",
}


def canonical_item(word):
    """把商品词纠正为训练库里的标准词（电宝 → 充电宝）。"""
    text = str(word or "").strip()
    if not text:
        return ""
    if text in ITEM_ALIAS:
        return ITEM_ALIAS[text]
    for alias, standard in ITEM_ALIAS.items():
        if alias in text:
            return standard
    for standard in BUNDLE_ITEM_RULES:
        if standard in text or text in standard:
            return standard
    return text


def item_condition(name, box=False):
    """商品词对应的 SQL 条件，限定类目避免乱窜。"""
    if name in BUNDLE_ITEM_RULES:
        cond = BUNDLE_ITEM_RULES[name]
    else:
        safe = name.replace("'", "''")
        cond = (
            f"(商品标题 LIKE '%{safe}%' OR 二级类目名称 LIKE '%{safe}%' "
            f"OR 一级类目名称 LIKE '%{safe}%')"
        )
    rule = BOX_RULES.get(name) if box else None
    if rule:
        cond = f"({cond}) AND 商品标题 LIKE '%{rule['title']}%'"
    return cond


def item_price_floor(name, anchors=None, box=False):
    """类目最低合理价：静态价格锚点 / 整箱下限 / 「质量好点」动态锚点。"""
    floor = float((anchors or {}).get(name, PRICE_ANCHORS.get(name, 0.0)))
    if box and name in BOX_RULES:
        floor = max(floor, BOX_RULES[name]["min"])
    return floor


def item_price_cap(name, box=False):
    """整箱类需求的合理价格上限（如纸巾一箱不超过 60 元）。"""
    return BOX_RULES[name]["max"] if box and name in BOX_RULES else None


def extract_plan_terms(question):
    """正则兜底：从问题中识别需要凑单的商品词（含错别字纠正），长词优先。"""
    matched = []
    for term in sorted(BUNDLE_ITEM_RULES, key=len, reverse=True):
        if term in question and term not in matched:
            matched.append(term)
    for alias, standard in ITEM_ALIAS.items():
        if alias in question and standard not in matched:
            matched.append(standard)
    return matched


def parse_min_spend(question):
    """解析「至少花80」里的最低花费要求，未提及返回 0。"""
    match = MIN_SPEND_RE.search(question or "")
    return float(match.group(1)) if match else 0.0


def extract_bundle_entities(question):
    """调用大模型抽取 {budget, min_spend, items}，失败时回退正则解析。"""
    fallback_budget = parse_budget(question)
    fallback_min = parse_min_spend(question)
    fallback_items = [canonical_item(t) for t in extract_plan_terms(question)]
    prompt = f"""你是电商购物意图解析器。从用户输入中提取预算、最低花费和要购买的商品词，只输出 JSON，不要任何解释。
输出格式：{{"budget": 数字或null, "min_spend": 数字, "items": ["标准商品名", ...]}}
要求：
1. budget 是预算上限，单位元，例如“158块”=>158，“预算300”=>300；没提则 null。
2. min_spend 是最低花费要求，例如“至少花80”“最少花80”=>80；没提则 0。
3. items 只保留要购买的品类，去掉“方案/凑单/买/帮我”等词。
4. 必须纠正错别字与同义词：电宝/移动电源/充电器→充电宝，抽纸/卷纸/卫生纸→纸巾，本子/记事本→笔记本，上衣/外套→秋衣。
用户输入：{question}"""
    budget, min_spend, items = None, None, []
    try:
        text = llm_text(
            [{"role": "user", "content": prompt}], temperature=0, max_tokens=180
        )
        match = re.search(r"\{.*\}", text or "", re.S)
        data = json.loads(match.group(0)) if match else {}
        for key in ("budget", "min_spend"):
            value = data.get(key)
            if isinstance(value, (int, float)):
                parsed = float(value)
            else:
                found = re.search(r"\d+(?:\.\d+)?", str(value or ""))
                parsed = float(found.group(0)) if found else None
            if key == "budget":
                budget = parsed
            else:
                min_spend = parsed
        items = [str(x) for x in (data.get("items") or []) if str(x).strip()]
    except Exception:
        budget, min_spend, items = None, None, []

    if budget is None:
        budget = fallback_budget
    if min_spend is None:
        min_spend = fallback_min
    items = [canonical_item(x) for x in items] or fallback_items

    unique = []
    for item in items:
        if item and item not in unique:
            unique.append(item)
    return {"budget": budget, "min_spend": float(min_spend or 0), "items": unique[:5]}


def is_bundle_plan_question(question):
    """识别凑单规划：多品类、或明确要方案、或整箱采购。"""
    if not question:
        return False
    items = extract_plan_terms(question)
    if len(items) >= 2:
        return True
    if items and re.search(r"(方案|凑单|规划)", question):
        return True
    if items and BOX_HINTS.search(question) and BUDGET_HINTS.search(question):
        return True
    return False


def parse_budget(question):
    patterns = [
        r"(?:预算|只有|总共|一共)?\s*(\d+(?:\.\d+)?)\s*(?:元|块钱|块)",
        r"预算\s*[:：]?\s*(\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            return float(match.group(1))
    return None


# 最近一次凑单方案（用于「换一种」排除已推荐商品）
_PLAN_MEMORY = {}


def get_plan_memory():
    return _PLAN_MEMORY.get(get_chat_sid()) or {}


def remember_plan(question, records, items=None, anchors=None):
    ids = [str(r.get("商品ID")) for r in records if r.get("商品ID")]
    _PLAN_MEMORY[get_chat_sid()] = {
        "question": question,
        "ids": ids,
        "items": items or [],
        "anchors": anchors or {},
    }


def clear_plan_memory():
    _PLAN_MEMORY.pop(get_chat_sid(), None)


PLAN_RECORD_SQL = (
    "SELECT 商品ID, 商品标题, 品牌名称, 最终促销价, 商品链接, 主图URL, 年销量 "
    "FROM tmall_products WHERE 最终促销价 > 0 "
)


def _exclude_clause(exclude_ids):
    ids = [str(i) for i in (exclude_ids or []) if i]
    if not ids:
        return "", []
    placeholders = ",".join("?" for _ in ids)
    return f" AND 商品ID NOT IN ({placeholders})", ids


def _row_to_record(row, name):
    return {
        "商品名称": name,
        "商品ID": str(row[0] or ""),
        "商品标题": row[1],
        "品牌名称": row[2] or "无品牌",
        "最终促销价": float(row[3] or 0),
        "商品链接": _normalize_link(row[4]),
        "主图URL": row[5] or "",
        "年销量": float(row[6] or 0),
    }


def fetch_tier_options(conn, name, budget, exclude_ids=None, anchors=None, box=False):
    """返回该品类的低配 / 中配 / 高配三个备选（高配不超预算）。"""
    exclude_sql, exclude_params = _exclude_clause(exclude_ids)
    cond_sql = f" AND {item_condition(name, box=box)}{exclude_sql}"
    params = list(exclude_params)

    floor = item_price_floor(name, anchors, box)
    if floor:
        cond_sql += " AND 最终促销价 >= ?"
        params.append(floor)
    cap = item_price_cap(name, box)
    if cap:
        cond_sql += " AND 最终促销价 <= ?"
        params.append(cap)
    if budget:
        cond_sql += " AND 最终促销价 <= ?"
        params.append(budget)

    low = conn.execute(
        f"{PLAN_RECORD_SQL}{cond_sql} ORDER BY 最终促销价 ASC, 年销量 DESC LIMIT 1",
        params,
    ).fetchone()
    if not low:
        return []

    high = conn.execute(
        f"{PLAN_RECORD_SQL}{cond_sql} "
        "ORDER BY 最终促销价 DESC, 年销量 DESC LIMIT 1",
        params,
    ).fetchone()
    low_record = _row_to_record(low, name)
    high_record = _row_to_record(high or low, name)

    mid_target = (low_record["最终促销价"] + high_record["最终促销价"]) / 2
    mid = conn.execute(
        f"{PLAN_RECORD_SQL}{cond_sql} "
        "ORDER BY ABS(最终促销价 - ?) ASC, 年销量 DESC LIMIT 1",
        params + [mid_target],
    ).fetchone()

    options, seen = [], set()
    for record in (low_record, _row_to_record(mid, name) if mid else None, high_record):
        if record and record["商品ID"] not in seen:
            seen.add(record["商品ID"])
            options.append(record)
    return options


def fetch_best_seller(conn, name, exclude_ids=None, anchors=None, box=False):
    """无预算时直接取该品类销量最高的一款（同样受价格锚点约束）。"""
    exclude_sql, exclude_params = _exclude_clause(exclude_ids)
    cond_sql = f" AND {item_condition(name, box=box)}{exclude_sql}"
    params = list(exclude_params)

    floor = item_price_floor(name, anchors, box)
    if floor:
        cond_sql += " AND 最终促销价 >= ?"
        params.append(floor)
    cap = item_price_cap(name, box)
    if cap:
        cond_sql += " AND 最终促销价 <= ?"
        params.append(cap)

    row = conn.execute(
        f"{PLAN_RECORD_SQL}{cond_sql} "
        "ORDER BY 年销量 DESC, 最终促销价 ASC LIMIT 1",
        params,
    ).fetchone()
    return _row_to_record(row, name) if row else None


def _combo_total(combo):
    return round(sum(r["最终促销价"] for r in combo), 2)


def _strip_internal(records):
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in records]


_FLUFF_WORDS = ("宝子们", "闭眼入", "绝绝子", "冲鸭", "家人们", "OMG", "买它")


def polish_plan(question, records, total, budget):
    """大模型只做客观总结，禁止营销废话。"""
    if not records:
        return ""
    goods = "\n".join(
        f"{r['商品名称']}：{r['商品标题']}，品牌 {r['品牌名称']}，"
        f"价格 {r['最终促销价']:.2f} 元，年销量 {int(r['年销量'])}"
        for r in records
    )
    budget_text = f"{budget:.0f} 元" if budget else "未指定"
    prompt = f"""请根据以下商品组合，生成一段客观、干练的推荐语。禁止使用"宝子们"、"闭眼入"、"绝绝子"等营销废话。直接列出商品名、核心属性、价格和总价。
用户需求：{question}
预算：{budget_text}
组合：
{goods}
合计：{total:.2f} 元
要求：
1. 必须原样使用给定的商品名、价格和总价，不得修改或编造数字；
2. 语言克制、信息密度高，不超过 80 字；
3. 只输出一段纯文本引导语，不要列表、不要 Markdown、不要图片、不要链接、不要解释。"""
    try:
        text = llm_text([{"role": "user", "content": prompt}], temperature=0.2, max_tokens=200)
    except Exception:
        return ""
    text = (text or "").strip()
    if not text or len(text) > 200 or any(word in text for word in _FLUFF_WORDS):
        return ""
    return text


def build_product_cards(records):
    """把商品记录转成前端卡片所需的精简结构（左图右文）。"""
    cards = []
    for record in records:
        title = str(record.get("商品标题") or "").strip()
        if not title:
            continue
        sales = float(record.get("年销量") or 0)
        if sales >= 10000:
            sales_text = f"{sales / 10000:.1f}万"
        elif sales > 0:
            sales_text = str(int(sales))
        else:
            sales_text = ""
        brand = str(record.get("品牌名称") or "").strip()
        if brand in ("无品牌", "未知品牌"):
            brand = ""
        cards.append(
            {
                "title": title,
                "brand": brand,
                "price": round(float(record.get("最终促销价") or 0), 2),
                "sales": sales_text,
                "img": str(record.get("主图URL") or "").strip(),
                "link": _normalize_link(record.get("商品链接")),
            }
        )
    return cards


def attach_main_images(records):
    """Vanna 生成的 SQL 未必带主图列，这里按标题补齐主图 URL。"""
    titles = [
        str(r.get("商品标题"))
        for r in records
        if r.get("商品标题") and not str(r.get("主图URL") or "").startswith("http")
    ]
    if not titles:
        return records
    conn = sqlite3.connect(config.DB_PATH)
    try:
        placeholders = ",".join("?" for _ in titles)
        rows = conn.execute(
            f"SELECT 商品标题, 主图URL FROM tmall_products "
            f"WHERE 商品标题 IN ({placeholders})",
            titles,
        ).fetchall()
    finally:
        conn.close()
    mapping = {}
    for title, image in rows:
        if image and title not in mapping:
            mapping[title] = image
    for record in records:
        if not str(record.get("主图URL") or "").startswith("http"):
            record["主图URL"] = mapping.get(str(record.get("商品标题")), "")
    return records


def build_bundle_plan(question, exclude_ids=None, anchors=None):
    """贪心规划：低/中/高三档组合，满足 [min_spend, budget] 且总销量最高。"""
    entities = extract_bundle_entities(question)
    budget = entities["budget"]
    min_spend = entities.get("min_spend") or 0.0
    if not budget:
        min_spend = 0.0
    items = entities["items"]
    anchors = {k: float(v) for k, v in (anchors or {}).items()}
    if not items:
        return None
    box = bool(BOX_HINTS.search(question))

    conn = sqlite3.connect(config.DB_PATH)
    try:
        options, missing = [], []
        for name in items:
            if budget:
                tier = fetch_tier_options(
                    conn, name, budget, exclude_ids, anchors=anchors, box=box
                )
            else:
                best = fetch_best_seller(
                    conn, name, exclude_ids, anchors=anchors, box=box
                )
                tier = [best] if best else []
            if not tier:
                missing.append(name)
                continue
            options.append(tier)

        if not options:
            if budget:
                message = (
                    f"预算 ¥{budget:.0f} 买不到符合品质要求的商品"
                    f"（{'、'.join(missing or items)}）。建议提高预算或更换品类。"
                )
            elif exclude_ids:
                message = "上一批商品已经全部推荐过了，当前没有新的替代商品。"
            else:
                message = "当前条件下没有找到可购买的商品，可以换个品类或提高预算。"
            return {
                "type": "plan",
                "reply_text": message,
                "products": [],
                "sql": "",
                "data": [],
                "row_count": 0,
                "budget": budget,
                "min_spend": min_spend,
                "total_price": 0,
                "feasible": False,
                "missing": missing,
                "items": items,
                "anchors": anchors,
            }

        # 有预算但某类目连「品质底线价」都买不到：宁可提示提高预算，不拿劣质品凑数
        if missing and budget:
            message = (
                f"预算 ¥{budget:.0f} 找不到符合品质要求的商品：{'、'.join(missing)}。"
                "建议提高预算或更换品类。"
            )
            return {
                "type": "plan",
                "reply_text": message,
                "products": [],
                "sql": "",
                "data": [],
                "row_count": 0,
                "budget": budget,
                "min_spend": min_spend,
                "total_price": 0,
                "feasible": False,
                "missing": missing,
                "items": items,
                "anchors": anchors,
            }

        if budget:
            combos = list(itertools.product(*options))
            cheapest_combo = min(combos, key=_combo_total)
            best_combo, best_score = None, None
            for combo in combos:
                total = _combo_total(combo)
                if total < min_spend - 1e-6 or total > budget + 1e-6:
                    continue
                score = (sum(r["年销量"] for r in combo), total)
                if best_score is None or score > best_score:
                    best_combo, best_score = list(combo), score
            if best_combo is None:
                cheapest_total = _combo_total(cheapest_combo)
                max_total = _combo_total(max(combos, key=_combo_total))
                if min_spend and max_total < min_spend:
                    message = (
                        f"当前数据源中最贵的组合为 ¥{max_total:.2f}，"
                        f"无法达到 ¥{min_spend:.0f} 元的最低要求。"
                    )
                else:
                    message = (
                        f"预算不足：最低组合合计 ¥{cheapest_total:.2f}，"
                        f"超出预算 ¥{cheapest_total - budget:.2f}。"
                    )
                return {
                    "type": "plan",
                    "reply_text": message + "\n\n以下是当前可凑到的最低组合：",
                    "products": build_product_cards(list(cheapest_combo)),
                    "sql": "",
                    "data": _strip_internal(list(cheapest_combo)),
                    "row_count": len(cheapest_combo),
                    "budget": budget,
                    "min_spend": min_spend,
                    "total_price": cheapest_total,
                    "feasible": False,
                    "missing": missing,
                    "items": items,
                    "anchors": anchors,
                }
            records = best_combo
        else:
            records = [max(tier, key=lambda r: (r["年销量"], -r["最终促销价"])) for tier in options]

        total = _combo_total(records)
        intro = ""
        if budget:
            intro = (
                f"已按预算 ¥{budget:.0f} 搭配 {len(records)} 件，合计 ¥{total:.2f}，"
                f"预算剩余 ¥{budget - total:.2f}。"
            )
        else:
            intro = f"已搭配 {len(records)} 件，合计 ¥{total:.2f}。"

        polished = polish_plan(question, records, total, budget)
        reply_text = polished or intro
        if missing:
            reply_text += f"\n\n未找到：{'、'.join(missing)}"
    finally:
        conn.close()

    return {
        "type": "plan",
        "reply_text": reply_text,
        "products": build_product_cards(records),
        "sql": "",
        "data": _strip_internal(records),
        "row_count": len(records),
        "budget": budget,
        "min_spend": min_spend,
        "total_price": total,
        "feasible": True,
        "missing": missing,
        "items": items,
        "anchors": anchors,
    }




_vn = None

# 配件关键词：用户问主商品（如手机）时用于排除误命中
ACCESSORY_WORDS = (
    "膜", "壳", "保护套", "保护", "适用", "充电", "数据线",
    "支架", "挂件", "收纳", "散热", "U盘", "闪存卡", "耳机", "贴膜", "包", "袋",
)

CHAT_SYSTEM_PROMPT = """你是「天猫数据 AI 分析助手」，服务于电商数据分析场景。
当前系统数据为天猫商品快照（约 1.1 万个去重商品，字段包括：商品标题、品牌名称、一级/二级类目、最终促销价、原价、预估凑单价、年销量、佣金比例、补贴金额、发货地、店铺类型、商品链接等）。

回答要求：
1. 全程使用中文，语气专业、友好、简洁。
2. 用户询问数据中不存在的字段（如利润、成本）时，给出可执行的估算方法：
   - 毛利 ≈ 原价 - 最终促销价（数据无成本字段，只能做估算）
   - 毛利率 ≈ (原价 - 最终促销价) / 原价
3. 解释业务概念时结合本数据集，例如：
   - 预估凑单价：参与平台凑单后的价格，可能低于最终促销价，属正常现象
   - 佣金比例：原始数值（如 128、766、2125），不是百分比
   - 年销量：已从「7000+」「1.8万+」转换为数值
4. 如果用户想查具体商品或榜单，主动提示可以这样问，例如「推荐3000元以内的手机」「热销商品TOP10」。
5. 不要编造数据库里不存在的统计数字。"""

# 明确属于「闲聊/业务答疑」的信号
_TEXT_HINTS = re.compile(
    r"(你是谁|你是什么|你能做什么|有什么功能|介绍一下|怎么用|怎么算|如何计算|什么是|什么意思|"
    r"利润|毛利|成本|凑单价.*(意思|计算)|佣金比例.*(意思|计算)|你好|您好|hello|hi)",
    re.IGNORECASE,
)
# 倾向「数据查询」的信号
_DATA_HINTS = (
    "查", "找", "统计", "最高", "最低", "推荐", "多少", "排名", "销量", "价格",
    "佣金", "补贴", "发货地", "类目", "品牌", "包邮", "对比", "top", "热销", "占比", "趋势",
)

_llm_client = None


def get_llm_client():
    global _llm_client
    if _llm_client is None:
        _llm_client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL
        )
    return _llm_client


def llm_text(messages, temperature=0.3, max_tokens=800):
    response = get_llm_client().chat.completions.create(
        model=config.MODEL_NAME,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()


_SMALLTALK = re.compile(r"(谢谢|谢了|再见|拜拜|好的|好吧|嗯+|哦+|在吗|早上好|中午好|下午好|晚上好|666)", re.IGNORECASE)


def classify_intent(question):
    """意图识别：A=数据查询（走 Vanna），B=闲聊/业务答疑（直接对话）。"""
    if _TEXT_HINTS.search(question):
        return "B"
    if _SMALLTALK.search(question):
        return "B"
    # 短名词（如「华为」「平板」「充电宝」）直接走数据查询，避免被误判为闲聊
    if len(question.strip()) <= 8:
        return "A"
    prompt = f"""你是一个意图分类器。请判断用户输入属于哪一类：
A. 数据查询：想查询商品、销量、价格、品牌、类目、佣金、补贴、发货地，或要求推荐/排行/统计对比。
B. 闲聊问答：询问系统功能、业务概念（如"利润怎么算""什么是凑单价"）、打招呼等，不需要查数据库。
只输出一个字母 A 或 B，不要输出任何其他内容。
用户输入：{question}"""
    try:
        result = llm_text([{"role": "user", "content": prompt}], temperature=0, max_tokens=4).upper()
        if result.startswith("B"):
            return "B"
        if result.startswith("A"):
            return "A"
    except Exception:
        pass
    return "A" if any(word in question for word in _DATA_HINTS) else "B"


# ---------------------------------------------------------------
# 商品首页数据（支持关键词、品牌、品类、排序、价格区间）
# ---------------------------------------------------------------
HOME_BASE_SQL = """
SELECT 商品ID, 主图URL, 白底图URL, 商品标题, 最终促销价, 年销量, 品牌名称, 商品链接
FROM tmall_products
WHERE 商品标题 IS NOT NULL
"""

PRICE_RANGE_OPTIONS = [
    ("0-50", "0 - 50 元"),
    ("50-100", "50 - 100 元"),
    ("100-", "100 元以上"),
]

SORT_OPTIONS = {"sales": "按销量排序", "price_asc": "按价格排序（从低到高）"}


def _build_home_where(keyword="", brand="", category="", price_range=""):
    clauses, params = [], []
    if keyword:
        like = f"%{keyword}%"
        clauses.append(
            "(商品标题 LIKE ? OR 品牌名称 LIKE ? OR 一级类目名称 LIKE ? OR 二级类目名称 LIKE ?)"
        )
        params.extend([like, like, like, like])
    if brand:
        clauses.append("品牌名称 = ?")
        params.append(brand)
    if category:
        clauses.append("一级类目名称 = ?")
        params.append(category)
    if price_range == "0-50":
        clauses.append("最终促销价 >= 0 AND 最终促销价 < 50")
    elif price_range == "50-100":
        clauses.append("最终促销价 >= 50 AND 最终促销价 < 100")
    elif price_range == "100-":
        clauses.append("最终促销价 >= 100")
    return clauses, params


def get_home_products(keyword="", brand="", category="", sort="", price_range=""):
    """按筛选条件查询商品，返回 (商品列表, 命中总数)。"""
    if not os.path.exists(config.DB_PATH) or os.path.getsize(config.DB_PATH) == 0:
        raise FileNotFoundError("tmall.db 不存在或为空")

    clauses, params = _build_home_where(keyword, brand, category, price_range)
    where_sql = (" AND " + " AND ".join(clauses)) if clauses else ""

    if sort == "sales":
        order_sql = "ORDER BY (年销量 IS NULL), 年销量 DESC"
    elif sort == "price_asc":
        order_sql = "ORDER BY (最终促销价 IS NULL OR 最终促销价 <= 0), 最终促销价 ASC"
    else:
        order_sql = "ORDER BY RANDOM()"

    limit = 48 if (keyword or brand or category or price_range or sort) else 24

    conn = sqlite3.connect(config.DB_PATH)
    try:
        cursor = conn.execute(
            f"{HOME_BASE_SQL}{where_sql} {order_sql} LIMIT ?", (*params, limit)
        )
        names = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) FROM tmall_products WHERE 商品标题 IS NOT NULL{where_sql}",
            params,
        ).fetchone()[0]
    finally:
        conn.close()

    products = []
    for row in rows:
        item = dict(zip(names, row))
        image = _normalize_link(item.get("白底图URL")) or _normalize_link(item.get("主图URL"))
        products.append(
            {
                "商品ID": item.get("商品ID"),
                "图片": image,
                "商品标题": item.get("商品标题"),
                "最终促销价": item.get("最终促销价"),
                "年销量": item.get("年销量"),
                "品牌名称": item.get("品牌名称"),
                "商品链接": _normalize_link(item.get("商品链接")),
            }
        )
    return products, int(total or 0)


def get_home_filter_options():
    """品牌、一级类目下拉选项。"""
    if not os.path.exists(config.DB_PATH) or os.path.getsize(config.DB_PATH) == 0:
        return [], []
    conn = sqlite3.connect(config.DB_PATH)
    try:
        brands = [
            row[0]
            for row in conn.execute(
                """SELECT 品牌名称 FROM tmall_products
                   WHERE 品牌名称 IS NOT NULL AND 品牌名称 NOT IN ('无品牌', '未知品牌')
                   GROUP BY 品牌名称 ORDER BY COUNT(*) DESC, 品牌名称 LIMIT 300"""
            ).fetchall()
        ]
        categories = [
            row[0]
            for row in conn.execute(
                """SELECT 一级类目名称 FROM tmall_products
                   WHERE 一级类目名称 IS NOT NULL
                   GROUP BY 一级类目名称 ORDER BY COUNT(*) DESC, 一级类目名称"""
            ).fetchall()
        ]
    finally:
        conn.close()
    return brands, categories


# ---------------------------------------------------------------
# 数据查询
# ---------------------------------------------------------------
def _top_with_others(rows, limit=10, others_label="其他"):
    if len(rows) <= limit:
        return [r[0] for r in rows], [r[1] for r in rows]
    head = rows[:limit]
    others = sum(r[1] for r in rows[limit:])
    return [r[0] for r in head] + [others_label], [r[1] for r in head] + [others]


def get_dashboard_data():
    conn = sqlite3.connect(config.DB_PATH)
    try:
        cur = conn.cursor()
        table = config.TABLE_NAME
        total_products = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        total_brands = cur.execute(
            f"SELECT COUNT(DISTINCT 品牌名称) FROM {table} WHERE 品牌名称 IS NOT NULL"
        ).fetchone()[0]
        total_sales = cur.execute(
            f"SELECT COALESCE(SUM(年销量), 0) FROM {table}"
        ).fetchone()[0]
        avg_price = cur.execute(
            f"SELECT COALESCE(AVG(最终促销价), 0) FROM {table} WHERE 最终促销价 > 0"
        ).fetchone()[0]

        price_rows = cur.execute(
            f"""SELECT CASE
                    WHEN 最终促销价 < 50 THEN '0-50元'
                    WHEN 最终促销价 < 100 THEN '50-100元'
                    WHEN 最终促销价 < 300 THEN '100-300元'
                    WHEN 最终促销价 < 1000 THEN '300-1000元'
                    WHEN 最终促销价 < 3000 THEN '1000-3000元'
                    ELSE '3000元以上' END AS bucket,
                   COUNT(*) AS c, COALESCE(AVG(年销量), 0) AS avg_sales
                FROM {table} WHERE 最终促销价 > 0
                GROUP BY bucket"""
        ).fetchall()
        price_map = {r[0]: (int(r[1] or 0), float(r[2] or 0)) for r in price_rows}
        bucket_names = ["0-50元", "50-100元", "100-300元", "300-1000元", "1000-3000元", "3000元以上"]

        brand_rows = cur.execute(
            f"""SELECT 品牌名称, COUNT(*) AS c FROM {table}
                WHERE 品牌名称 IS NOT NULL AND 品牌名称 NOT IN ('无品牌', '未知品牌')
                GROUP BY 品牌名称 ORDER BY c DESC LIMIT 10"""
        ).fetchall()

        category_price_rows = cur.execute(
            f"""SELECT 一级类目名称, AVG(最终促销价) AS p, COUNT(*) AS c FROM {table}
                WHERE 最终促销价 > 0 AND 一级类目名称 IS NOT NULL
                GROUP BY 一级类目名称 HAVING c >= 100
                ORDER BY p DESC LIMIT 10"""
        ).fetchall()
        free_shipping = cur.execute(
            f"SELECT SUM(CASE WHEN 邮费 = 0 THEN 1 ELSE 0 END), COUNT(*) FROM {table}"
        ).fetchone()
        shipping_rows = cur.execute(
            f"""SELECT 发货地, COUNT(*) AS c FROM {table}
                WHERE 发货地 IS NOT NULL GROUP BY 发货地 ORDER BY c DESC"""
        ).fetchall()
        category_rows = cur.execute(
            f"""SELECT 一级类目名称, COUNT(*) AS c FROM {table}
                WHERE 一级类目名称 IS NOT NULL GROUP BY 一级类目名称 ORDER BY c DESC"""
        ).fetchall()
    finally:
        conn.close()

    ship_names, ship_values = _top_with_others(shipping_rows, 10)
    cat_names, cat_values = _top_with_others(category_rows, 10)

    return {
        "kpi": {
            "total_products": int(total_products or 0),
            "total_brands": int(total_brands or 0),
            "total_sales": float(total_sales or 0),
            "avg_price": float(avg_price or 0),
            "free_shipping": int((free_shipping or (0, 0))[0] or 0),
            "free_shipping_rate": round(
                (float((free_shipping or (0, 1))[0] or 0) / float((free_shipping or (0, 1))[1] or 1)) * 100,
                1,
            ),
        },
        "price_buckets": {
            "names": bucket_names,
            "counts": [price_map.get(n, (0, 0))[0] for n in bucket_names],
            "avg_sales": [round(price_map.get(n, (0, 0))[1], 0) for n in bucket_names],
        },
        "top_brands": {
            "names": [str(r[0]) for r in brand_rows],
            "counts": [int(r[1] or 0) for r in brand_rows],
        },
        "category_price": {
            "names": [str(r[0]) for r in category_price_rows],
            "values": [round(float(r[1] or 0), 2) for r in category_price_rows],
            "counts": [int(r[2] or 0) for r in category_price_rows],
        },
        "shipping": {"names": ship_names, "values": [int(v) for v in ship_values]},
        "category": {"names": cat_names, "values": [int(v) for v in cat_values]},
    }


# ---------------------------------------------------------------
# 结果后处理：去重 + 主商品配件过滤
# ---------------------------------------------------------------
def dedupe_products(df):
    """按 商品ID（缺失时按商品标题）去重，避免推荐结果重复。"""
    if df is None or df.empty:
        return df
    for column in ("商品ID", "商品标题"):
        if column in df.columns:
            return df.drop_duplicates(subset=[column], keep="first")
    return df


def filter_accessory_results(question, df):
    """问主商品时剔除配件；服装类只保留女装/男装类目。"""
    if df is None or df.empty or "商品标题" not in df.columns:
        return df

    title = df["商品标题"].astype(str)

    if "笔记本" in question and "纸质" in question:
        # 纸质笔记本：排除鼠标垫、打印纸、电脑等易混淆商品
        main_mask = title.str.contains("笔记本", na=False)
        noise_mask = title.str.contains(
            "鼠标垫|打印纸|电脑|键盘|鼠标|包|贴膜|支架", na=False
        )
        return df[main_mask & ~noise_mask]

    if "手机" in question:
        accessory_mask = title.str.contains("|".join(ACCESSORY_WORDS), na=False)
        if "二级类目名称" in df.columns:
            main_mask = df["二级类目名称"].astype(str).eq("手机")
            return df[main_mask | ~accessory_mask]
        return df[~accessory_mask]

    if "充电宝" in question or "电宝" in question:
        accessory_mask = title.str.contains(
            "数据线|充电线|延长线|转接头|转换头|收纳|保护套|手机壳|支架|耳机",
            na=False,
        )
        return df[~accessory_mask]

    if "平板" in question:
        # 兜底过滤：数据集里「平板」会命中贴膜、保护壳、拖把、支架、电视、纸巾等
        accessory_mask = title.str.contains(
            "膜|壳|拖把|支架|数据线|充电|内存卡|tf卡|sd卡|集线器|扩展坞|灯|纸|打印|"
            "阅读架|键盘|鼠标|转接头|保护套|电容笔|触控笔|手写笔|电视|画板|推车|轮子|玩具|清洁",
            na=False,
        )
        return df[~accessory_mask]

    if any(word in question for word in ("衣服", "秋衣", "冬装", "外套", "女装", "男装")):
        if "一级类目名称" in df.columns:
            main_mask = df["一级类目名称"].astype(str).str.contains("女装|男装", na=False)
            return df[main_mask]
        edge_mask = title.str.contains("毛线|鞋垫|面罩", na=False)
        return df[~edge_mask]

    return df


# ---------------------------------------------------------------
# 中文回答生成
# ---------------------------------------------------------------
def _fmt_number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(value):
        return ""
    if abs(value) >= 10000:
        return f"{value:,.0f}"
    if abs(value) >= 100:
        return f"{value:,.1f}".rstrip("0").rstrip(".")
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _normalize_link(link):
    if isinstance(link, str) and link:
        if link.startswith("//"):
            return "https:" + link
        return link
    return ""


def _row_to_text(row, columns):
    parts = []
    for column in columns:
        value = row.get(column)
        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue
        if isinstance(value, (int, float)):
            parts.append(f"{column}={_fmt_number(value)}")
        else:
            parts.append(f"{column}={value}")
    return "，".join(parts)


def compose_answer(question, df):
    if df is None or df.empty:
        return "没有查询到符合条件的数据。可以换一种问法，或适当放宽价格、类目等筛选条件。"

    columns = list(df.columns)
    lines = [f"关于「{question}」，共命中 {len(df):,} 条数据（已按商品去重）："]

    if "商品标题" in columns:
        for i, (_, row) in enumerate(df.head(10).iterrows(), start=1):
            title = str(row.get("商品标题", ""))[:60]
            brand = row.get("品牌名称")
            headline = f"{i}. "
            if isinstance(brand, str) and brand and brand not in ("无品牌", "未知品牌"):
                headline += f"【{brand}】"
            meta = [headline + title]
            price = row.get("最终促销价")
            if price is not None and not pd.isna(price):
                meta.append(f"到手价 ¥{_fmt_number(price)}")
            sales = row.get("年销量")
            if sales is not None and not pd.isna(sales):
                meta.append(f"年销量 {_fmt_number(sales)}")
            commission = row.get("佣金比例")
            if commission is not None and not pd.isna(commission):
                meta.append(f"佣金比例 {_fmt_number(commission)}")
            subsidy = row.get("补贴金额")
            if subsidy is not None and not pd.isna(subsidy):
                meta.append(f"补贴 ¥{_fmt_number(subsidy)}")
            lines.append("，".join(meta))

            link = _normalize_link(row.get("商品链接"))
            if link.startswith("http"):
                lines.append(f"   商品链接：[点击查看商品]({link})")

        analysis = []
        if "最终促销价" in columns:
            prices = pd.to_numeric(df["最终促销价"], errors="coerce").dropna()
            if not prices.empty:
                analysis.append(
                    f"到手价区间 ¥{prices.min():.2f} ~ ¥{prices.max():.2f}，"
                    f"平均 ¥{prices.mean():.2f}，中位数 ¥{prices.median():.2f}"
                )
        if "年销量" in columns:
            sales = pd.to_numeric(df["年销量"], errors="coerce").dropna()
            if not sales.empty:
                analysis.append(
                    f"累计年销 {_fmt_number(sales.sum())} 件，"
                    f"头部商品贡献 {_fmt_number(sales.iloc[0])} 件"
                )
        if analysis:
            lines.append("")
            lines.append("分析结论：" + "；".join(analysis) + "。建议优先关注销量靠前且价格符合预算的商品。")
    else:
        for i, (_, row) in enumerate(df.head(10).iterrows(), start=1):
            lines.append(f"{i}. {_row_to_text(row.to_dict(), columns)}")

        numeric_columns = [c for c in columns if pd.api.types.is_numeric_dtype(df[c])]
        if len(columns) >= 2 and numeric_columns and len(df) >= 2:
            dimension, metric = columns[0], numeric_columns[0]
            top, bottom = df.iloc[0], df.iloc[-1]
            lines.append("")
            lines.append(
                f"分析结论：按 {dimension} 维度看，{top[dimension]} 的 {metric} 最高，"
                f"为 {_fmt_number(top[metric])}；{bottom[dimension]} 最低，"
                f"为 {_fmt_number(bottom[metric])}，头部集中效应明显。"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------
# 应用工厂
# ---------------------------------------------------------------
def create_app():
    global _vn
    _vn = get_vanna()
    init_users_table()
    init_ai_logs_table()

    vanna_app = VannaFlaskApp(
        _vn,
        debug=False,
        title="天猫数据 AI 助手",
        subtitle="基于 DeepSeek 的电商数据智能分析",
        summarization=True,
        auto_fix_sql=True,
        allow_llm_to_see_data=True,
    )
    app = vanna_app.flask_app
    app.secret_key = config.SECRET_KEY

    # Vanna 内部 Flask 的模板目录在它自己的包里，这里追加项目 templates
    app.jinja_loader = ChoiceLoader(
        [
            FileSystemLoader(os.path.join(config.BASE_DIR, "templates")),
            app.jinja_loader,
        ]
    )
    try:
        app.json.ensure_ascii = False
    except AttributeError:
        pass

    # 接管 Vanna 的 catch-all（端点 hello）：根路径跳看板，其余仍交给 Vanna SPA
    vanna_index = app.view_functions.get("hello")

    def spa_dispatch(path=""):
        if path == "":
            return redirect(url_for("home"))
        if path.rstrip("/") == "vanna":
            return vanna_index("")
        return vanna_index(path)

    if vanna_index is not None:
        app.view_functions["hello"] = spa_dispatch

    PUBLIC_PREFIXES = (
        "/static", "/assets", "/favicon.ico", "/vanna.svg", "/auth/", "/register",
        "/forget_password",
    )

    @app.before_request
    def require_login():
        path = request.path
        if path in ("/login", "/logout") or path.startswith(PUBLIC_PREFIXES):
            return None
        if not session.get("logged_in"):
            if path.startswith("/api/"):
                return jsonify({"ok": False, "error": "登录已过期，请先登录"}), 401
            return redirect(url_for("login_page"))
        # RBAC：数据看板与系统后台仅管理员可见
        if path.startswith(("/dashboard", "/admin", "/api/admin")):
            if session.get("role") != "admin":
                if path.startswith("/api/"):
                    return jsonify({"ok": False, "error": "无权访问"}), 403
                return redirect(url_for("home", denied=1))
        return None

    @app.route("/login", methods=["GET", "POST"])
    def login_page():
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""

            # 所有账号（包括 admin）统一走数据库校验，不存在任何硬编码后门
            user = get_user_login_info(username)
            if not user or not verify_password(password, user["password"]):
                return render_template_string(LOGIN_HTML, error="账号或密码错误", message="")
            if user["status"] == 0:
                return render_template_string(
                    LOGIN_HTML, error="该账号已被封禁，请联系管理员", message=""
                )

            session.clear()
            session["logged_in"] = True
            session["user"] = username
            session["username"] = username
            session["role"] = user["role"]
            return redirect(url_for("home"))

        message = "注册成功，请使用新账号登录" if request.args.get("registered") else ""
        if request.args.get("reset"):
            message = "密码已重置，请使用新密码登录"
        return render_template_string(LOGIN_HTML, error="", message=message)

    @app.route("/register", methods=["GET", "POST"])
    def register_page():
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            confirm = request.form.get("confirm_password") or ""
            email = (request.form.get("email") or "").strip()
            phone = (request.form.get("phone") or "").strip()

            error = ""
            if not username or not password:
                error = "用户名和密码不能为空"
            elif len(username) < 3 or len(username) > 20:
                error = "用户名长度需为 3 - 20 个字符"
            elif len(password) < 6:
                error = "密码长度不能少于 6 位"
            elif password != confirm:
                error = "两次输入的密码不一致"
            elif email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                error = "邮箱格式不正确"
            elif phone and not re.match(r"^[0-9+\-\s]{6,20}$", phone):
                error = "手机号格式不正确"
            elif username.lower() == config.DEMO_USERNAME.lower():
                error = "用户名已被注册"

            if error:
                return render_template_string(REGISTER_HTML, error=error)

            try:
                conn = sqlite3.connect(config.DB_PATH)
                try:
                    conn.execute(
                        """INSERT INTO sys_users
                               (username, password, role, created_at, nickname, email, phone, avatar, status)
                           VALUES (?, ?, 'user', ?, ?, ?, ?, ?, 1)""",
                        (
                            username,
                            hash_password(password),
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            username,
                            email,
                            phone,
                            DEFAULT_AVATAR,
                        ),
                    )
                    conn.commit()
                finally:
                    conn.close()
            except sqlite3.IntegrityError:
                return render_template_string(REGISTER_HTML, error="用户名已被注册")
            except sqlite3.Error as exc:
                return render_template_string(REGISTER_HTML, error=f"注册失败：{exc}")

            return redirect(url_for("login_page", registered=1))

        return render_template_string(REGISTER_HTML, error="")

    @app.route("/logout")
    def logout_page():
        session.clear()
        return redirect(url_for("login_page"))

    @app.route("/profile", methods=["GET", "POST"])
    def profile_page():
        username = session.get("username") or session.get("user")
        profile = get_user_profile(username) if username else None
        if not profile:
            return redirect(url_for("logout_page"))

        message, error = "", ""
        if request.method == "POST":
            nickname = (request.form.get("nickname") or "").strip() or username
            email = (request.form.get("email") or "").strip()
            phone = (request.form.get("phone") or "").strip()
            avatar = (request.form.get("avatar") or "").strip()
            current = request.form.get("current_password") or ""
            new = request.form.get("new_password") or ""
            confirm = request.form.get("confirm_password") or ""

            if len(nickname) > 30:
                error = "昵称不能超过 30 个字符"
            elif email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                error = "邮箱格式不正确"
            elif phone and not re.match(r"^[0-9+\-\s]{6,20}$", phone):
                error = "手机号格式不正确"
            elif avatar and not avatar.startswith(("http://", "https://")):
                error = "头像需填写 http(s) 开头的图片地址"
            elif new:
                if len(new) < 6:
                    error = "新密码长度不能少于 6 位"
                elif new != confirm:
                    error = "两次输入的新密码不一致"
                elif not authenticate_user(username, current):
                    error = "当前密码不正确"

            if not error:
                error = update_user_profile(username, nickname, email, phone, avatar)
            if not error:
                if new:
                    update_user_password(username, new)
                message = "资料已保存" + ("，密码已更新" if new else "")
                profile = get_user_profile(username)

        return render_template(
            "profile.html",
            profile=profile,
            message=message,
            error=error,
            default_avatar=DEFAULT_AVATAR,
        )

    @app.route("/forget_password", methods=["GET", "POST"])
    def forget_password_page():
        error = ""
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            contact = (request.form.get("contact") or "").strip()
            new = request.form.get("new_password") or ""
            confirm = request.form.get("confirm_password") or ""

            if not username or not contact:
                error = "用户名和邮箱/手机号不能为空"
            elif len(new) < 6:
                error = "新密码长度不能少于 6 位"
            elif new != confirm:
                error = "两次输入的新密码不一致"
            elif not find_user_by_contact(username, contact):
                error = "用户名与注册邮箱/手机号不匹配"
            else:
                update_user_password(username, new)
                return redirect(url_for("login_page", reset=1))

        return render_template("forget_password.html", error=error)

    @app.route("/home")
    def home():
        filters = {
            "keyword": (request.args.get("keyword") or "").strip(),
            "brand": (request.args.get("brand") or "").strip(),
            "category": (request.args.get("category") or "").strip(),
            "sort": (request.args.get("sort") or "").strip(),
            "price_range": (request.args.get("price_range") or "").strip(),
        }
        products, total, brands, categories = [], 0, [], []
        error = None
        try:
            products, total = get_home_products(**filters)
            brands, categories = get_home_filter_options()
            # 已选品牌不在热门品牌列表中时补进去，避免下拉框丢失选中项
            if filters["brand"] and filters["brand"] not in brands:
                brands.append(filters["brand"])
        except FileNotFoundError:
            error = "数据库 tmall.db 不存在或为空，请先在项目根目录运行：python load_data.py"
        except sqlite3.Error as exc:
            error = f"数据库查询失败：{exc}"
        return render_template(
            "home.html",
            products=products,
            total=total,
            brands=brands,
            categories=categories,
            filters=filters,
            price_options=PRICE_RANGE_OPTIONS,
            error=error,
        )

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html", data=get_dashboard_data())

    @app.route("/admin")
    def admin_page():
        tab = (request.args.get("tab") or "users").strip()
        if tab not in ("users", "products", "logs"):
            tab = "users"
        q = (request.args.get("q") or "").strip()
        try:
            page = max(1, int(request.args.get("page") or 1))
        except ValueError:
            page = 1
        per_page = 10
        context = {
            "tab": tab,
            "q": q,
            "page": page,
            "per_page": per_page,
            "total": 0,
            "total_pages": 1,
            "users": [],
            "products": [],
            "logs": [],
            "message": (request.args.get("message") or "").strip(),
        }
        if not os.path.exists(config.DB_PATH):
            context["message"] = "数据库不存在，请先运行 python load_data.py"
            return render_template("admin.html", **context)

        where_sql = ""
        params = ()
        if tab == "products" and q:
            where_sql = " WHERE 商品标题 LIKE ?"
            params = (f"%{q}%",)

        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            if tab == "users":
                count_sql = "SELECT COUNT(*) FROM sys_users"
            elif tab == "products":
                count_sql = f"SELECT COUNT(*) FROM tmall_products{where_sql}"
            else:
                count_sql = "SELECT COUNT(*) FROM ai_logs"

            total = int(conn.execute(count_sql, params).fetchone()[0] or 0)
            total_pages = max(1, math.ceil(total / per_page))
            page = min(page, total_pages)
            offset = (page - 1) * per_page

            if tab == "users":
                rows = conn.execute(
                    """SELECT username, nickname, email, phone, role, status, created_at
                       FROM sys_users
                       ORDER BY (role = 'admin') DESC, id ASC
                       LIMIT ? OFFSET ?""",
                    (per_page, offset),
                ).fetchall()
                context["users"] = [dict(row) for row in rows]
            elif tab == "products":
                rows = conn.execute(
                    f"""SELECT 商品ID, 商品标题, 品牌名称, 一级类目名称,
                               最终促销价, 年销量
                        FROM tmall_products{where_sql}
                        ORDER BY (年销量 IS NULL), 年销量 DESC
                        LIMIT ? OFFSET ?""",
                    (*params, per_page, offset),
                ).fetchall()
                context["products"] = [dict(row) for row in rows]
            else:
                rows = conn.execute(
                    """SELECT id, username, question, sql, created_at
                       FROM ai_logs ORDER BY id DESC LIMIT ? OFFSET ?""",
                    (per_page, offset),
                ).fetchall()
                context["logs"] = [dict(row) for row in rows]
        except sqlite3.Error as exc:
            context["message"] = f"数据读取失败：{exc}"
            total, total_pages = 0, 1
        finally:
            conn.close()

        context["total"] = total
        context["total_pages"] = total_pages
        context["page"] = page
        return render_template("admin.html", **context)

    @app.route("/admin/users/toggle", methods=["POST"])
    def admin_toggle_user():
        username = (request.form.get("username") or "").strip()
        if not username:
            return redirect(url_for("admin_page", tab="users", message="参数错误"))
        if username == (session.get("username") or session.get("user")):
            return redirect(
                url_for("admin_page", tab="users", message="不能封禁当前登录账号")
            )

        conn = sqlite3.connect(config.DB_PATH)
        try:
            row = conn.execute(
                "SELECT role, status FROM sys_users WHERE username = ?", (username,)
            ).fetchone()
            if not row:
                message = "用户不存在"
            elif (row[0] or "user") == "admin":
                message = "管理员账号不可封禁"
            else:
                new_status = 0 if row[1] is None or int(row[1]) == 1 else 1
                conn.execute(
                    "UPDATE sys_users SET status = ? WHERE username = ?",
                    (new_status, username),
                )
                conn.commit()
                message = f"{username} 已{'封禁' if new_status == 0 else '解封'}"
        finally:
            conn.close()
        return redirect(url_for("admin_page", tab="users", message=message))

    @app.route("/assistant")
    def assistant():
        return render_template("assistant.html")

    @app.route("/api/history", methods=["GET", "DELETE"])
    def api_history():
        if request.method == "DELETE":
            clear_chat_history()
            clear_plan_memory()
            return jsonify({"ok": True})
        return jsonify({"ok": True, "history": get_chat_history()})

    @app.route("/api/ask", methods=["POST"])
    def api_ask():
        payload = request.get_json(silent=True) or {}
        question = (payload.get("question") or "").strip()
        if not question:
            return jsonify({"ok": False, "error": "问题不能为空"}), 400

        def plan_response(plan_text, exclude_ids=None, anchors=None):
            plan = build_bundle_plan(
                plan_text, exclude_ids=exclude_ids, anchors=anchors
            )
            if not plan:
                return (
                    jsonify({"ok": False, "error": "未能识别要购买的商品，请说明具体品类"}),
                    400,
                )
            log_ai_sql(session.get("username"), question, plan.get("sql"))
            if plan.get("data"):
                remember_plan(
                    plan_text,
                    plan["data"],
                    items=plan.get("items"),
                    anchors=plan.get("anchors"),
                )
            append_chat_history("user", question)
            append_chat_history(
                "assistant",
                plan["reply_text"],
                sql=plan["sql"],
                data=plan["data"],
                summary=plan["reply_text"],
                products=plan["products"],
            )
            return jsonify({"ok": True, **plan})

        # 0. 「耳机质量要好点」：提高对应类目价格锚点后重新规划
        if QUALITY_HINTS.search(question):
            memory = get_plan_memory()
            if memory.get("question"):
                try:
                    targets = extract_plan_terms(question) or memory.get("items") or []
                    anchors = dict(memory.get("anchors") or {})
                    for name in targets:
                        anchors[name] = max(
                            float(anchors.get(name, 0)), QUALITY_ANCHOR
                        )
                    return plan_response(
                        memory["question"],
                        exclude_ids=memory.get("ids") or [],
                        anchors=anchors,
                    )
                except Exception as exc:
                    return jsonify({"ok": False, "error": f"升级方案失败：{exc}"}), 500

        # 0.1 「换一种」：沿用上一轮方案，排除已推荐商品后重新规划
        if CHANGE_HINTS.search(question):
            memory = get_plan_memory()
            if memory.get("question"):
                try:
                    return plan_response(
                        memory["question"],
                        exclude_ids=memory.get("ids") or [],
                        anchors=memory.get("anchors") or {},
                    )
                except Exception as exc:
                    return jsonify({"ok": False, "error": f"换一批失败：{exc}"}), 500

        # 0.2 凑单/预算方案：贪心组合，不走 Vanna
        if is_bundle_plan_question(question):
            try:
                return plan_response(question)
            except Exception as exc:
                return jsonify({"ok": False, "error": f"凑单方案生成失败：{exc}"}), 500

        # 1. 意图识别：A=数据查询，B=闲聊/业务答疑
        intent = classify_intent(question)

        # 2. 闲聊 / 业务概念：携带历史对话，跳过 SQL 直接作答
        if intent == "B":
            try:
                answer = llm_text(
                    build_llm_messages(question), temperature=0.4, max_tokens=800
                )
                append_chat_history("user", question)
                append_chat_history("assistant", answer)
                return jsonify(
                    {"ok": True, "type": "text", "reply_text": answer, "products": []}
                )
            except Exception as exc:
                return jsonify({"ok": False, "error": f"回答失败：{exc}"}), 500

        # 3. 多轮改写：把「要3000以上的」补全为「推荐3000元以上的手机」
        query = rewrite_query(question) if needs_rewrite(question) else question
        rewritten = "" if query == question else query

        # 改写后可能变成凑单问题
        if query != question and is_bundle_plan_question(query):
            try:
                return plan_response(query)
            except Exception as exc:
                return jsonify({"ok": False, "error": f"凑单方案生成失败：{exc}"}), 500

        # 4. 数据查询：Vanna 生成并执行 SQL
        sql = ""
        try:
            single = is_extreme_query(query)
            target = None if single else recommend_target(query)

            sql = _vn.generate_sql(question=query, allow_llm_to_see_data=True)
            sql = apply_recommend_limit(query, sql)
            if single:
                sql = force_single_limit(sql)
            df = run_product_query(query, sql, target, single=single)

            # 后置兜底：商品明细必须包含「商品链接」，缺失则重生成一次
            if missing_product_link(df):
                retry_question = (
                    f"{query}\n\n【强制要求】重新生成 SQL：SELECT 中必须包含 商品链接 字段，"
                    "保留原有筛选、排序和条数条件，只输出 SQL。"
                )
                retry_sql = _vn.generate_sql(
                    question=retry_question, allow_llm_to_see_data=True
                )
                retry_sql = apply_recommend_limit(query, retry_sql)
                if single:
                    retry_sql = force_single_limit(retry_sql)
                retry_df = run_product_query(
                    query, retry_sql, target, single=single
                )
                if missing_product_link(retry_df):
                    return (
                        jsonify(
                            {
                                "ok": False,
                                "error": "AI 生成的 SQL 缺少「商品链接」字段，请重试或换个问法",
                                "sql": retry_sql,
                            }
                        ),
                        500,
                    )
                sql, df = retry_sql, retry_df

            log_ai_sql(session.get("username"), query, sql)
            detail = compose_answer(query, df)

            summary = ""
            if df is not None and not df.empty:
                if single:
                    summary_rule = (
                        "这是极值问题（第一/最高/最低/最便宜）。"
                        "只回答该商品的名称和对应指标（销量或价格），一句话，"
                        "不要分析、不要罗列多条。"
                        "禁止使用'宝子们''闭眼入''绝绝子'等营销废话。"
                    )
                else:
                    summary_rule = (
                        "请用一到两句中文给出客观结论，只陈述结果中的事实，不要编造数字；"
                        "禁止使用'宝子们''闭眼入''绝绝子'等营销废话，不要夸张形容词。"
                    )
                try:
                    summary = llm_text(
                        [
                            {
                                "role": "user",
                                "content": (
                                    f"用户问题：{query}\n"
                                    f"查询结果：\n{df.head(10).to_string(index=False)}\n"
                                    f"{summary_rule}"
                                ),
                            }
                        ],
                        temperature=0,
                        max_tokens=200,
                    )
                except Exception:
                    summary = ""

            records = []
            if df is not None and not df.empty:
                records = json.loads(
                    df.head(20).to_json(orient="records", force_ascii=False)
                )
                for record in records:
                    if "商品链接" in record:
                        record["商品链接"] = _normalize_link(record.get("商品链接"))
                attach_main_images(records)

            products = (
                build_product_cards(records)
                if records and any(r.get("商品标题") for r in records)
                else []
            )
            if products:
                reply_text = summary or f"为你找到 {len(products)} 件符合条件的商品："
            else:
                reply_text = detail

            append_chat_history("user", question)
            append_chat_history(
                "assistant",
                reply_text,
                sql=sql,
                data=records,
                summary=summary,
                products=products,
            )

            return jsonify(
                {
                    "ok": True,
                    "type": "sql",
                    "reply_text": reply_text,
                    "products": products,
                    "sql": sql,
                    "rewritten": rewritten,
                    "row_count": 0 if df is None else int(len(df)),
                    "data": records,
                }
            )
        except Exception as exc:
            return (
                jsonify({"ok": False, "error": f"查询失败：{exc}", "sql": sql}),
                500,
            )

    return app
