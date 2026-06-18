
import asyncio
import logging
import os
import random
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
import requests
import yfinance as yf
from flask import Flask, jsonify
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from waitress import serve

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "rately.db"

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "RateLyBot").strip().lstrip("@")
BOT_NAME = os.getenv("BOT_NAME", "RateLy").strip()
APP_TITLE = os.getenv("APP_TITLE", "RateLy").strip()

ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
DEFAULT_LANG = os.getenv("DEFAULT_LANG", "fa").strip().lower()
PORT = int(os.getenv("PORT", "10000"))
ADS_TEXT = os.getenv("ADS_TEXT", "").strip()
ADS_EVERY = int(os.getenv("ADS_EVERY", "0") or "0")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("RateLy")
app = Flask(__name__)

LANGS = {
    "fa": "فارسی", "en": "English", "ar": "العربية",
    "ru": "Русский", "tr": "Türkçe", "es": "Español",
}
BASE_CURRENCIES = ["TMN", "IRR", "USD", "EUR", "GBP", "TRY", "RUB", "AED"]

T = {
    "fa": {
        "welcome": "به *RateLy* خوش آمدی ✨\nقیمت لحظه‌ای ارزها، رمزارزها، طلا، نقره و نمودارها.",
        "choose_lang": "زبان را انتخاب کن:",
        "choose_base": "ارز پایه را انتخاب کن:",
        "choose_chart": "نوع و بازه‌ی نمودار را انتخاب کن:",
        "help": "نمونه‌ها: `BTC`، `تتر`، `دلار`، `EUR/USD`، `طلا`، `نقره`، `USD/IRR`.",
        "unknown": "این پیام را متوجه نشدم.\nمثلاً `BTC` یا `قیمت دلار` را بفرست.",
        "greet": "سلام 😎\nیک نماد بفرست یا از دکمه‌ها استفاده کن.",
        "thanks": "خواهش می‌کنم 🤝",
        "bye": "فعلاً 👋",
        "support_intro": "پیامت را با `/support` بفرست.\nمثال: `/support من این قیمت را می‌خواهم`",
        "support_saved": "پیام ناشناس تو با شماره #{tid} ثبت شد.",
        "reply_sent": "پاسخ برای تیکت #{tid} ارسال شد.",
        "admin_only": "فقط برای ادمین.",
        "panel": "پنل ادمین",
        "stats": "کاربران: {users}\nدرخواست‌ها: {requests}\nبن‌ها: {banned}\nپرمیوم: {premium}\nتیکت‌ها: {tickets}\nزمان‌بندی‌ها: {jobs}",
        "user_info": "کاربر {uid}\nنام: {name}\nیوزرنیم: {username}\nزبان: {lang}\nپایه: {base}\nپرمیوم: {premium}\nدرخواست‌ها: {requests}\nمعرفی‌ها: {refs}\nآخرین فعالیت: {last_seen}",
        "ban_done": "کاربر {uid} بن شد.",
        "unban_done": "کاربر {uid} آنبن شد.",
        "vip_on": "پرمیوم کاربر {uid} فعال شد.",
        "vip_off": "پرمیوم کاربر {uid} غیرفعال شد.",
        "reset_done": "اطلاعات کاربر {uid} ریست شد.",
        "broadcast_done": "ارسال همگانی تمام شد.\nارسال شد: {sent}\nناموفق: {failed}",
        "schedule_done": "ارسال زمان‌بندی شد: {when}",
        "price_not_found": "برای {symbol} داده پیدا نشد.",
        "chart_not_found": "برای {symbol} نمودار پیدا نشد.",
        "ref_link": "لینک معرفی تو:\n`{link}`",
        "base_saved": "ارز پایه به {base} تغییر کرد.",
        "lang_saved": "زبان به {lang} تغییر کرد.",
        "chart_default": "نمودار پیش‌فرض برای {symbol}",
        "quick": "نمونه‌های سریع: `BTC`، `ETH`، `XAU`، `USD`، `EUR/USD`، `GBP/USD`، `USD/IRR`",
        "ad_label": "تبلیغ",
    },
    "en": {
        "welcome": "Welcome to *RateLy* ✨\nLive prices for currencies, crypto, metals, and charts.",
        "choose_lang": "Choose your language:",
        "choose_base": "Choose your display currency:",
        "choose_chart": "Choose chart type and timeframe:",
        "help": "Examples: `BTC`, `USDT`, `USD`, `EUR/USD`, `gold`, `silver`, `USD/IRR`.",
        "unknown": "I did not understand that message.\nTry sending `BTC` or `USD/IRR`.",
        "greet": "Hello 😎\nSend a symbol or use the buttons.",
        "thanks": "You are welcome 🤝",
        "bye": "Bye 👋",
        "support_intro": "Send `/support` followed by your message.\nExample: `/support I need help`",
        "support_saved": "Your anonymous message was saved as ticket #{tid}.",
        "reply_sent": "Reply sent to ticket #{tid}.",
        "admin_only": "Admin only.",
        "panel": "Admin panel",
        "stats": "Users: {users}\nRequests: {requests}\nBanned: {banned}\nPremium: {premium}\nTickets: {tickets}\nScheduled jobs: {jobs}",
        "user_info": "User {uid}\nName: {name}\nUsername: {username}\nLanguage: {lang}\nDisplay: {base}\nPremium: {premium}\nRequests: {requests}\nReferrals: {refs}\nLast seen: {last_seen}",
        "ban_done": "User {uid} banned.",
        "unban_done": "User {uid} unbanned.",
        "vip_on": "Premium enabled for {uid}.",
        "vip_off": "Premium disabled for {uid}.",
        "reset_done": "User {uid} reset.",
        "broadcast_done": "Broadcast completed.\nSent: {sent}\nFailed: {failed}",
        "schedule_done": "Scheduled for: {when}",
        "price_not_found": "No data found for {symbol}.",
        "chart_not_found": "No chart data found for {symbol}.",
        "ref_link": "Your referral link:\n`{link}`",
        "base_saved": "Display currency set to {base}.",
        "lang_saved": "Language changed to {lang}.",
        "chart_default": "Default chart for {symbol}",
        "quick": "Quick examples: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`",
        "ad_label": "Sponsored",
    },
}
for code in ["ar", "ru", "tr", "es"]:
    T[code] = {
        "welcome": T["en"]["welcome"],
        "choose_lang": T["en"]["choose_lang"],
        "choose_base": T["en"]["choose_base"],
        "choose_chart": T["en"]["choose_chart"],
        "help": T["en"]["help"],
        "unknown": T["en"]["unknown"],
        "greet": T["en"]["greet"],
        "thanks": T["en"]["thanks"],
        "bye": T["en"]["bye"],
        "support_intro": T["en"]["support_intro"],
        "support_saved": T["en"]["support_saved"],
        "reply_sent": T["en"]["reply_sent"],
        "admin_only": T["en"]["admin_only"],
        "panel": T["en"]["panel"],
        "stats": T["en"]["stats"],
        "user_info": T["en"]["user_info"],
        "ban_done": T["en"]["ban_done"],
        "unban_done": T["en"]["unban_done"],
        "vip_on": T["en"]["vip_on"],
        "vip_off": T["en"]["vip_off"],
        "reset_done": T["en"]["reset_done"],
        "broadcast_done": T["en"]["broadcast_done"],
        "schedule_done": T["en"]["schedule_done"],
        "price_not_found": T["en"]["price_not_found"],
        "chart_not_found": T["en"]["chart_not_found"],
        "ref_link": T["en"]["ref_link"],
        "base_saved": T["en"]["base_saved"],
        "lang_saved": T["en"]["lang_saved"],
        "chart_default": T["en"]["chart_default"],
        "quick": T["en"]["quick"],
        "ad_label": T["en"]["ad_label"],
    }

ALIASES = {
    "دلار": "USD", "یورو": "EUR", "پوند": "GBP", "فرانک": "CHF", "تومان": "TMN", "ریال": "IRR",
    "تتر": "USDT", "بیت کوین": "BTC", "بیتکوین": "BTC", "بیت‌کوین": "BTC", "اتریوم": "ETH",
    "طلا": "XAU", "نقره": "XAG", "سکه": "XAU", "gold": "XAU", "silver": "XAG", "oil": "CL=F",
    "btc": "BTC", "eth": "ETH", "usdt": "USDT", "usd": "USD", "eur": "EUR", "gbp": "GBP",
    "jpy": "JPY", "xau": "XAU", "xag": "XAG", "bitcoin": "BTC", "ethereum": "ETH", "tether": "USDT",
}
PRICE_WORDS = {"price", "rate", "value", "quote", "chart", "graph", "trend", "قیمت", "نرخ", "ارزش", "نمودار", "رسم", "سعر", "precio", "preço", "kurs", "цена", "график", "fiyat"}
FIAT_CODES = {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD","CNY","HKD","SGD","SEK","NOK","DKK","PLN","CZK","HUF","RON","TRY","SAR","AED","QAR","KWD","BHD","INR","PKR","RUB","UAH","ZAR","MXN","BRL","IDR","MYR","THB","PHP","KRW","TWD","ILS","EGP","IRR","KZT","VND","ARS","COP","CLP","NGN"}
CRYPTO_ALIASES = {"BTC":"bitcoin","ETH":"ethereum","BNB":"binancecoin","SOL":"solana","XRP":"ripple","DOGE":"dogecoin","ADA":"cardano","TON":"the-open-network","TRX":"tron","LTC":"litecoin","DOT":"polkadot","AVAX":"avalanche-2","MATIC":"polygon","LINK":"chainlink","SHIB":"shiba-inu","PEPE":"pepe","USDT":"tether","USDC":"usd-coin","BCH":"bitcoin-cash","XLM":"stellar","ATOM":"cosmos","NEAR":"near","APT":"aptos","SUI":"sui"}

# DB helpers
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def db():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT, first_name TEXT,
            lang TEXT DEFAULT 'fa',
            base_currency TEXT DEFAULT 'TMN',
            premium INTEGER DEFAULT 0,
            first_seen TEXT, last_seen TEXT,
            requests INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            referrer INTEGER,
            referrals INTEGER DEFAULT 0
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            kind TEXT DEFAULT 'support',
            question TEXT,
            status TEXT DEFAULT 'open',
            answer TEXT,
            created_at TEXT,
            answered_at TEXT
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_broadcasts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT,
            message TEXT,
            created_by INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )""")
        conn.commit()

def get_user(user_id: int):
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()

def get_lang(user_id: int) -> str:
    row = get_user(user_id)
    if row and row["lang"] in LANGS:
        return row["lang"]
    return DEFAULT_LANG if DEFAULT_LANG in LANGS else "fa"

def get_base(user_id: int) -> str:
    row = get_user(user_id)
    if row and row["base_currency"] in BASE_CURRENCIES:
        return row["base_currency"]
    return "TMN"

def tr(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in T else "en"
    return T[lang].get(key, T["en"].get(key, key)).format(**kwargs)

def upsert_user(user):
    with db() as conn:
        conn.execute("""
        INSERT INTO users(user_id, username, first_name, lang, base_currency, first_seen, last_seen)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            last_seen=excluded.last_seen
        """, (user.id, user.username or "", user.first_name or "", get_lang(user.id), get_base(user.id), now_iso(), now_iso()))
        conn.commit()

def set_user_lang(user_id: int, lang: str):
    if lang in LANGS:
        with db() as conn:
            conn.execute("UPDATE users SET lang=?, last_seen=? WHERE user_id=?", (lang, now_iso(), user_id))
            conn.commit()

def set_user_base(user_id: int, base: str):
    if base in BASE_CURRENCIES:
        with db() as conn:
            conn.execute("UPDATE users SET base_currency=?, last_seen=? WHERE user_id=?", (base, now_iso(), user_id))
            conn.commit()

def is_banned(user_id: int) -> bool:
    row = get_user(user_id)
    return bool(row and row["banned"])

def is_premium(user_id: int) -> bool:
    row = get_user(user_id)
    return bool(row and row["premium"])

def admin_only(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def inc_request(user_id: int) -> int:
    with db() as conn:
        conn.execute("UPDATE users SET requests=COALESCE(requests,0)+1, last_seen=? WHERE user_id=?", (now_iso(), user_id))
        row = conn.execute("SELECT requests FROM users WHERE user_id=?", (user_id,)).fetchone()
        conn.commit()
        return int(row["requests"]) if row else 0

def set_ban(user_id: int, val: int):
    with db() as conn:
        conn.execute("UPDATE users SET banned=?, last_seen=? WHERE user_id=?", (val, now_iso(), user_id))
        conn.commit()

def set_vip(user_id: int, val: int):
    with db() as conn:
        conn.execute("UPDATE users SET premium=?, last_seen=? WHERE user_id=?", (val, now_iso(), user_id))
        conn.commit()

def reset_user(user_id: int):
    with db() as conn:
        conn.execute("UPDATE users SET requests=0,banned=0,premium=0,referrer=NULL,referrals=0 WHERE user_id=?", (user_id,))
        conn.commit()

def stats():
    with db() as conn:
        users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        requests = conn.execute("SELECT COALESCE(SUM(requests),0) s FROM users").fetchone()["s"]
        banned = conn.execute("SELECT COUNT(*) c FROM users WHERE banned=1").fetchone()["c"]
        premium = conn.execute("SELECT COUNT(*) c FROM users WHERE premium=1").fetchone()["c"]
        tickets = conn.execute("SELECT COUNT(*) c FROM tickets").fetchone()["c"]
        jobs = conn.execute("SELECT COUNT(*) c FROM scheduled_broadcasts WHERE status='pending'").fetchone()["c"]
        return dict(users=users, requests=requests, banned=banned, premium=premium, tickets=tickets, jobs=jobs)

def record_referral(user_id: int, referrer: int):
    if user_id == referrer:
        return
    with db() as conn:
        row = conn.execute("SELECT referrer FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row and row["referrer"] is None:
            conn.execute("UPDATE users SET referrer=? WHERE user_id=?", (referrer, user_id))
            conn.execute("UPDATE users SET referrals=COALESCE(referrals,0)+1 WHERE user_id=?", (referrer,))
            conn.commit()

def recent_tickets(limit: int = 10):
    with db() as conn:
        return conn.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

# UI
def lang_name(code: str) -> str:
    return LANGS.get(code, code)

def base_name(code: str) -> str:
    return {"TMN":"تومان","IRR":"ریال","USD":"USD","EUR":"EUR","GBP":"GBP","TRY":"TRY","RUB":"RUB","AED":"AED"}.get(code, code)

def language_keyboard():
    rows, row = [], []
    for code in ["fa","en","ar","ru","tr","es"]:
        row.append(InlineKeyboardButton(lang_name(code), callback_data=f"lang:{code}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    return InlineKeyboardMarkup(rows)

def base_keyboard():
    rows, row = [], []
    for code in BASE_CURRENCIES:
        row.append(InlineKeyboardButton(base_name(code), callback_data=f"base:{code}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu:back")])
    return InlineKeyboardMarkup(rows)

def chart_keyboard(symbol: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Line", callback_data=f"charttype:line:{symbol}"), InlineKeyboardButton("🕯 Candle", callback_data=f"charttype:candle:{symbol}")],
        [InlineKeyboardButton("1H", callback_data=f"charttf:1h:{symbol}"), InlineKeyboardButton("24H", callback_data=f"charttf:24h:{symbol}"), InlineKeyboardButton("7D", callback_data=f"charttf:7d:{symbol}")],
        [InlineKeyboardButton("30D", callback_data=f"charttf:30d:{symbol}"), InlineKeyboardButton("1Y", callback_data=f"charttf:1y:{symbol}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:back")],
    ])

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats", callback_data="admin:stats"), InlineKeyboardButton("👥 Users", callback_data="admin:users")],
        [InlineKeyboardButton("💬 Tickets", callback_data="admin:tickets"), InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast")],
        [InlineKeyboardButton("⏱ Schedule", callback_data="admin:schedule"), InlineKeyboardButton("🔒 Ban", callback_data="admin:ban")],
        [InlineKeyboardButton("✅ Unban", callback_data="admin:unban"), InlineKeyboardButton("⭐ VIP", callback_data="admin:vip")],
        [InlineKeyboardButton("♻️ Reset", callback_data="admin:reset"), InlineKeyboardButton("⬅️ Back", callback_data="menu:back")],
    ])

def support_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆘 New Ticket", callback_data="menu:support")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:back")],
    ])

def main_keyboard(user_id: int):
    is_admin = admin_only(user_id)
    rows = [
        [InlineKeyboardButton("🛠 Help", callback_data="menu:help"), InlineKeyboardButton("🌐 Language", callback_data="menu:lang")],
        [InlineKeyboardButton(f"💱 Base: {base_name(get_base(user_id))}", callback_data="menu:base"), InlineKeyboardButton("🆘 Support", callback_data="menu:support")],
        [InlineKeyboardButton("📉 Charts", callback_data="menu:chart"), InlineKeyboardButton("🔗 Referral", callback_data="menu:ref")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("👑 Admin", callback_data="menu:admin")])
    return InlineKeyboardMarkup(rows)

# Parsing
def normalize_text(text: str) -> str:
    text = text.replace("‌", " ").replace("＋", "+")
    text = re.sub(r"@\w+", "", text)
    return re.sub(r"\s+", " ", text).strip()

def strip_token(token: str) -> str:
    return token.strip("`'\".,;:!?()[]{}<>")

def norm_alias(token: str) -> str:
    t = strip_token(token).replace("‌", "").lower()
    return ALIASES.get(t, t.upper())

def resolve_phrase(text: str) -> str:
    t = normalize_text(text)
    low = t.lower()
    if low in ALIASES:
        return ALIASES[low]
    tokens = [strip_token(x) for x in re.split(r"[\s,]+", t) if strip_token(x)]
    tokens = [x for x in tokens if x.lower() not in PRICE_WORDS and x != "+"]
    if not tokens:
        return ""
    for tok in tokens:
        nt = norm_alias(tok)
        if "/" in nt:
            return nt
    for tok in reversed(tokens):
        nt = norm_alias(tok)
        if nt in FIAT_CODES or nt in CRYPTO_ALIASES or nt in {"XAU", "XAG"} or nt in ALIASES.values():
            return nt
    joined = " ".join(x.lower() for x in tokens)
    if joined in ALIASES:
        return ALIASES[joined]
    return norm_alias(tokens[-1])

def is_finance_like(text: str) -> bool:
    q = resolve_phrase(text)
    if not q:
        return False
    if "/" in q:
        a, b = q.split("/", 1)
        return bool(a and b)
    return bool(re.fullmatch(r"[A-Z0-9.\-]{2,15}", q)) or q in FIAT_CODES or q in CRYPTO_ALIASES or q in {"XAU", "XAG"}

def parse_pair(query: str) -> Tuple[str, Optional[str]]:
    q = query.strip().upper().replace(" ", "").replace("-", "/")
    if "/" in q:
        a, b = q.split("/", 1)
        return a, b
    return q, None

# Data sources / caching
_PRICE_CACHE: Dict[str, Tuple[float, float]] = {}
_CACHE_TTL = 45.0

def cached_get(key: str) -> Optional[float]:
    item = _PRICE_CACHE.get(key)
    if not item:
        return None
    ts, val = item
    if (datetime.now().timestamp() - ts) > _CACHE_TTL:
        _PRICE_CACHE.pop(key, None)
        return None
    return val

def cached_set(key: str, value: float) -> None:
    _PRICE_CACHE[key] = (datetime.now().timestamp(), value)

def _safe_json(url: str, params: Optional[dict] = None, timeout: int = 12) -> Optional[dict]:
    try:
        r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": "RateLy/1.0"})
        if r.status_code == 200:
            return r.json()
    except Exception as exc:
        log.warning("request failed %s: %s", url, exc)
    return None

def coin_gecko_search(query: str) -> Optional[dict]:
    data = _safe_json("https://api.coingecko.com/api/v3/search", {"query": query.strip().lower()})
    if not data:
        return None
    coins = data.get("coins", []) or []
    if not coins:
        return None
    exact = [c for c in coins if c.get("symbol", "").lower() == query.lower() or c.get("name", "").lower() == query.lower()]
    if exact:
        exact.sort(key=lambda x: (x.get("market_cap_rank") or 10**9))
        return exact[0]
    coins.sort(key=lambda x: (x.get("market_cap_rank") or 10**9))
    return coins[0]

def get_crypto_price_usd(symbol: str) -> Optional[float]:
    s = symbol.upper()
    key = f"crypto:{s}"
    cached = cached_get(key)
    if cached is not None:
        return cached
    cg_id = CRYPTO_ALIASES.get(s)
    if cg_id:
        data = _safe_json("https://api.coingecko.com/api/v3/simple/price", {"ids": cg_id, "vs_currencies": "usd"})
        if data and cg_id in data and "usd" in data[cg_id]:
            val = float(data[cg_id]["usd"]); cached_set(key, val); return val
    found = coin_gecko_search(s)
    if found and found.get("id"):
        cg_id = found["id"]
        data = _safe_json("https://api.coingecko.com/api/v3/simple/price", {"ids": cg_id, "vs_currencies": "usd"})
        if data and cg_id in data and "usd" in data[cg_id]:
            val = float(data[cg_id]["usd"]); cached_set(key, val); return val
    for t in [f"{s}-USD", f"{s}USD=X", f"{s}USDT=X"]:
        val = yfinance_last_close(t)
        if val:
            cached_set(key, val)
            return val
    return None

def get_fiat_rate_to_usd(code: str) -> Optional[float]:
    code = code.upper()
    if code == "USD":
        return 1.0
    key = f"fiat:{code}"
    cached = cached_get(key)
    if cached is not None:
        return cached
    data = _safe_json("https://open.er-api.com/v6/latest/USD")
    if data and data.get("result") == "success":
        rates = data.get("rates", {})
        if code in rates and rates[code]:
            val = float(rates[code]); cached_set(key, val); return val
    for t in [f"{code}USD=X", f"USD{code}=X"]:
        val = yfinance_last_close(t)
        if val:
            if t.startswith(code):
                cached_set(key, val)
                return val
            cached_set(key, 1 / val)
            return 1 / val
    return None

def get_base_rate_to_usd(code: str) -> Optional[float]:
    code = code.upper()
    if code == "USD":
        return 1.0
    if code == "TMN":
        irr = get_fiat_rate_to_usd("IRR")
        return irr / 10.0 if irr else None
    return get_fiat_rate_to_usd(code)

def yfinance_last_close(ticker: str) -> Optional[float]:
    key = f"yf:{ticker}"
    cached = cached_get(key)
    if cached is not None:
        return cached
    try:
        df = yf.Ticker(ticker).history(period="1d", interval="1m", auto_adjust=False)
        if df is not None and not df.empty and "Close" in df:
            s = df["Close"].dropna()
            if not s.empty:
                val = float(s.iloc[-1]); cached_set(key, val); return val
    except Exception as exc:
        log.warning("yfinance last_close failed %s: %s", ticker, exc)
    return None

def yfinance_history(ticker: str, timeframe: str) -> pd.DataFrame:
    mapping = {"1h": ("1d", "5m"), "24h": ("1d", "5m"), "7d": ("7d", "30m"), "30d": ("1mo", "1d"), "1y": ("1y", "1d")}
    period, interval = mapping.get(timeframe, ("7d", "30m"))
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
        return df.dropna(how="all") if df is not None else pd.DataFrame()
    except Exception as exc:
        log.warning("history failed %s: %s", ticker, exc)
        return pd.DataFrame()

def fiat_pair_rate(base: str, quote: str) -> Optional[float]:
    base = base.upper(); quote = quote.upper()
    if base == quote:
        return 1.0
    if quote == "USD":
        return get_fiat_rate_to_usd(base)
    if base == "USD":
        qrate = get_fiat_rate_to_usd(quote)
        return (1 / qrate) if qrate else None
    br = get_fiat_rate_to_usd(base)
    qr = get_fiat_rate_to_usd(quote)
    if br and qr:
        return br / qr
    return None

def resolve_asset(query: str) -> Tuple[Optional[str], Optional[float], Optional[str], Optional[str], Optional[str]]:
    q = resolve_phrase(query)
    if not q:
        return None, None, None, None, None
    q = q.upper().replace(" ", "").replace("-", "/")
    if q in CRYPTO_ALIASES:
        return q, get_crypto_price_usd(q), "crypto", q, "USD"
    if q in {"XAU", "GOLD"}:
        return "XAUUSD=X", yfinance_last_close("XAUUSD=X"), "metal", "XAU", "USD"
    if q in {"XAG", "SILVER"}:
        return "XAGUSD=X", yfinance_last_close("XAGUSD=X"), "metal", "XAG", "USD"
    if q in {"CL=F", "OIL"}:
        return "CL=F", yfinance_last_close("CL=F"), "commodity", "OIL", "USD"

    base, quote = parse_pair(q)
    if quote:
        if base in FIAT_CODES and quote in FIAT_CODES:
            return f"{base}{quote}=X", fiat_pair_rate(base, quote), "pair", base, quote
        if base in CRYPTO_ALIASES:
            return base, get_crypto_price_usd(base), "crypto", base, quote
        t = f"{base}{quote}=X"
        px = yfinance_last_close(t)
        if px:
            return t, px, "pair", base, quote
        inv = f"{quote}{base}=X"
        inv_px = yfinance_last_close(inv)
        if inv_px and inv_px != 0:
            return inv, 1 / inv_px, "pair", base, quote
        return None, None, None, None, None

    if q in FIAT_CODES:
        if q == "USD":
            return "USD", 1.0, "fiat", "USD", "USD"
        return q, get_fiat_rate_to_usd(q), "fiat", q, "USD"
    if q in CRYPTO_ALIASES:
        return q, get_crypto_price_usd(q), "crypto", q, "USD"
    for t in [q, f"{q}=X", f"{q}-USD"]:
        px = yfinance_last_close(t)
        if px:
            return t, px, "other", q, "USD"
    return None, None, None, None, None

def format_money(value: float, code: str) -> str:
    if code == "TMN":
        return f"{value:,.0f} تومان"
    if code == "IRR":
        return f"{value:,.0f} ریال"
    return f"{value:,.4f} {code}" if abs(value) < 1000 else f"{value:,.2f} {code}"

def display_to_base(usd_value: float, base: str) -> Optional[float]:
    rate = get_base_rate_to_usd(base)
    if rate is None:
        return None
    return usd_value / rate

def format_usd(x: float) -> str:
    return f"${x:,.6f}" if x < 1 else f"${x:,.4f}"

def human_symbol(query: str) -> str:
    q = resolve_phrase(query)
    return (q or query).upper().replace(" ", "")

def format_price_response(query: str, lang: str, base_currency: str) -> str:
    ticker, usd_price, kind, base, quote = resolve_asset(query)
    symbol = human_symbol(query)
    if usd_price is None:
        return tr(lang, "price_not_found", symbol=symbol)

    lines = [f"*{symbol}*"]
    disp = display_to_base(usd_price, base_currency) if usd_price is not None else None

    if kind == "crypto":
        lines.append(f"USD: {format_usd(usd_price)}")
        if disp is not None:
            lines.append(f"{base_name(base_currency)}: {format_money(disp, base_currency)}")
    elif kind in {"fiat", "pair"}:
        if base and quote:
            if quote == "USD":
                lines.append(f"1 {base} = {format_usd(usd_price)}")
            elif base == "USD":
                lines.append(f"1 USD = {usd_price:,.6f} {quote}")
            else:
                lines.append(f"1 {base} = {usd_price:,.6f} {quote}")
        if disp is not None and base_currency != "USD":
            lines.append(f"{base_name(base_currency)}: {format_money(disp, base_currency)}")
    elif kind == "metal":
        lines.append(f"USD: {format_usd(usd_price)} per ounce")
        if disp is not None:
            lines.append(f"{base_name(base_currency)}: {format_money(disp, base_currency)} per ounce")
    else:
        lines.append(f"USD: {format_usd(usd_price)}")
        if disp is not None:
            lines.append(f"{base_name(base_currency)}: {format_money(disp, base_currency)}")
    return "\n".join(lines)

def chart_symbol_for(query: str) -> Optional[str]:
    q = resolve_phrase(query)
    if not q:
        return None
    q = q.upper().replace(" ", "").replace("-", "/")
    if q in CRYPTO_ALIASES:
        return f"{q}-USD"
    if q in {"XAU", "GOLD"}:
        return "XAUUSD=X"
    if q in {"XAG", "SILVER"}:
        return "XAGUSD=X"
    if q in FIAT_CODES:
        if q == "USD":
            return None
        return f"{q}USD=X"
    if "/" in q:
        a, b = q.split("/", 1)
        return f"{a}{b}=X"
    return q if q.endswith("=X") or q.endswith("-USD") else f"{q}-USD"

# Charts
def render_line_chart(df: pd.DataFrame, title: str) -> Optional[BytesIO]:
    if df.empty or "Close" not in df:
        return None
    df = df.dropna(subset=["Close"])
    if df.empty:
        return None
    fig = plt.figure(figsize=(11, 5))
    ax = fig.add_subplot(111)
    ax.plot(df.index, df["Close"])
    ax.set_title(title); ax.set_xlabel("Time"); ax.set_ylabel("Price")
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf

def render_candle_chart(df: pd.DataFrame, title: str) -> Optional[BytesIO]:
    need = {"Open", "High", "Low", "Close"}
    if df.empty or not need.issubset(set(df.columns)):
        return None
    df = df.dropna(subset=list(need))
    if df.empty:
        return None
    fig = plt.figure(figsize=(11, 5))
    ax = fig.add_subplot(111)
    for i, (_, row) in enumerate(df.iterrows()):
        o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
        color = "#2ca02c" if c >= o else "#d62728"
        ax.vlines(i, l, h, color=color, linewidth=1.2)
        bottom = min(o, c)
        height = abs(c - o) or max((h - l) * 0.01, 1e-8)
        ax.add_patch(Rectangle((i - 0.3, bottom), 0.6, height, facecolor=color, edgecolor=color, alpha=0.85))
    step = max(len(df) // 8, 1)
    xt = list(range(0, len(df), step))
    xl = [df.index[i].strftime("%m-%d %H:%M") if hasattr(df.index[i], "strftime") else str(df.index[i]) for i in xt]
    ax.set_xticks(xt); ax.set_xticklabels(xl, rotation=45, ha="right")
    ax.set_title(title); ax.set_xlabel("Time"); ax.set_ylabel("Price")
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf

def chart_history(ticker: str, timeframe: str) -> pd.DataFrame:
    mapping = {"1h": ("1d", "5m"), "24h": ("1d", "5m"), "7d": ("7d", "30m"), "30d": ("1mo", "1d"), "1y": ("1y", "1d")}
    period, interval = mapping.get(timeframe, ("7d", "30m"))
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
        return df.dropna(how="all") if df is not None else pd.DataFrame()
    except Exception as exc:
        log.warning("history failed %s: %s", ticker, exc)
        return pd.DataFrame()

def make_chart(query: str, chart_type: str = "line", timeframe: str = "7d") -> Optional[BytesIO]:
    ticker = chart_symbol_for(query)
    if not ticker:
        return None
    df = chart_history(ticker, timeframe)
    if df.empty:
        return None
    title = f"{human_symbol(query)} | {chart_type.upper()} | {timeframe}"
    return render_candle_chart(df, title) if chart_type == "candle" else render_line_chart(df, title)

# Small talk
GREETINGS = {"سلام", "salam", "hello", "hi", "hey", "مرحبا", "hola", "привет", "merhaba"}
THANKS = {"مرسی", "ممنون", "thanks", "thank you", "teşekkür", "спасибо", "gracias"}
BYE = {"خداحافظ", "bye", "goodbye", "فعلا", "görüşürüz", "пока"}

def maybe_small_talk(text: str) -> Optional[str]:
    t = normalize_text(text).lower()
    if any(x in t for x in GREETINGS):
        return random.choice(["سلام 😎\nمثلاً `BTC`، `دلار`، `طلا` یا `EUR/USD` بفرست.", "Hello 😎\nTry `BTC`, `USD`, `gold`, `EUR/USD`."])
    if any(x in t for x in THANKS):
        return random.choice(["خواهش می‌کنم 🤝", "You are welcome 🤝"])
    if any(x in t for x in BYE):
        return random.choice(["فعلاً 👋", "Bye 👋"])
    return None

# Ads / scheduling
def ad_text(lang: str) -> str:
    if not ADS_TEXT:
        return ""
    return f"🪧 *{tr(lang, 'ad_label')}*\n{ADS_TEXT}"

def maybe_show_ad(chat_id: int, lang: str, context: ContextTypes.DEFAULT_TYPE, req_count: int) -> None:
    if ADS_TEXT and ADS_EVERY > 0 and req_count % ADS_EVERY == 0:
        try:
            context.bot.send_message(chat_id=chat_id, text=ad_text(lang), parse_mode=ParseMode.MARKDOWN)
        except Exception as exc:
            log.warning("ad send failed: %s", exc)

def parse_duration_to_seconds(text: str) -> Optional[int]:
    m = re.fullmatch(r"(\\d+)([smhd])", text.strip().lower())
    if not m:
        return None
    value = int(m.group(1))
    return value * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]

def schedule_broadcast(run_at: datetime, message: str, created_by: int) -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO scheduled_broadcasts(run_at, message, created_by, status, created_at) VALUES(?, ?, ?, 'pending', ?)",
            (run_at.isoformat(), message, created_by, now_iso()),
        )
        conn.commit()
        return int(cur.lastrowid)

def due_jobs():
    with db() as conn:
        return conn.execute("SELECT * FROM scheduled_broadcasts WHERE status='pending' AND run_at <= ? ORDER BY run_at ASC LIMIT 10", (now_iso(),)).fetchall()

def mark_job_done(job_id: int):
    with db() as conn:
        conn.execute("UPDATE scheduled_broadcasts SET status='done' WHERE id=?", (job_id,))
        conn.commit()

# Telegram helpers
async def send_price_and_chart(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, chart_type: str = "line", timeframe: str = "7d") -> None:
    if not update.effective_user or not update.effective_message or not update.effective_chat:
        return
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    base = get_base(user_id)
    if is_banned(user_id):
        await update.effective_message.reply_text(tr(lang, "admin_only"))
        return
    req_count = inc_request(user_id)
    q = resolve_phrase(query)
    if not q:
        await update.effective_message.reply_text(tr(lang, "unknown"))
        return
    text = format_price_response(q, lang, base)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=chart_keyboard(human_symbol(q)))
    chart = await asyncio.to_thread(make_chart, q, chart_type, timeframe)
    if chart:
        await update.effective_message.reply_photo(photo=chart, caption=tr(lang, "chart_default", symbol=human_symbol(q)), reply_markup=chart_keyboard(human_symbol(q)))
    maybe_show_ad(update.effective_chat.id, lang, context, req_count)

async def send_chart_only(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, chart_type: str = "line", timeframe: str = "7d") -> None:
    if not update.effective_user or not update.effective_message or not update.effective_chat:
        return
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if is_banned(user_id):
        await update.effective_message.reply_text(tr(lang, "admin_only"))
        return
    req_count = inc_request(user_id)
    q = resolve_phrase(query)
    if not q:
        await update.effective_message.reply_text(tr(lang, "unknown"))
        return
    chart = await asyncio.to_thread(make_chart, q, chart_type, timeframe)
    if not chart:
        await update.effective_message.reply_text(tr(lang, "chart_not_found", symbol=human_symbol(q)))
        return
    await update.effective_message.reply_photo(photo=chart, caption=f"{human_symbol(q)} | {chart_type.upper()} | {timeframe}", reply_markup=chart_keyboard(human_symbol(q)))
    maybe_show_ad(update.effective_chat.id, lang, context, req_count)

# Commands
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    upsert_user(update.effective_user)
    uid = update.effective_user.id
    lang = get_lang(uid)
    if context.args:
        arg = context.args[0].strip()
        if arg.startswith("ref_") and arg[4:].isdigit():
            record_referral(uid, int(arg[4:]))
    text = f"{tr(lang, 'welcome')}\n\n{tr(lang, 'choose_lang')}\n{tr(lang, 'choose_base')}\n{tr(lang, 'quick')}"
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    lang = get_lang(update.effective_user.id)
    await update.effective_message.reply_text(tr(lang, "help"), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(update.effective_user.id))

async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if context.args and context.args[0].lower() in LANGS:
        new_lang = context.args[0].lower()
        set_user_lang(uid, new_lang)
        await update.effective_message.reply_text(tr(new_lang, "lang_saved", lang=lang_name(new_lang)), reply_markup=main_keyboard(uid))
        return
    await update.effective_message.reply_text(tr(lang, "choose_lang"), reply_markup=language_keyboard())

async def cmd_base(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if context.args and context.args[0].upper() in BASE_CURRENCIES:
        base = context.args[0].upper()
        set_user_base(uid, base)
        await update.effective_message.reply_text(tr(lang, "base_saved", base=base_name(base)), reply_markup=main_keyboard(uid))
        return
    await update.effective_message.reply_text(tr(lang, "choose_base"), reply_markup=base_keyboard())

async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "help"))
        return
    await send_price_and_chart(update, context, " ".join(context.args))

async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "choose_chart"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Line", callback_data="charttype:line:BTC"), InlineKeyboardButton("Candle", callback_data="charttype:candle:BTC")]]))
        return
    symbol = context.args[0]
    tf = context.args[1] if len(context.args) > 1 else "7d"
    await send_chart_only(update, context, symbol, "line", tf)

async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if is_banned(uid):
        await update.effective_message.reply_text(tr(lang, "admin_only"))
        return
    if not context.args:
        await update.effective_message.reply_text(tr(lang, "support_intro"), reply_markup=support_keyboard())
        return
    question = " ".join(context.args).strip()
    with db() as conn:
        cur = conn.execute("INSERT INTO tickets(user_id, kind, question, status, created_at) VALUES(?, 'support', ?, 'open', ?)", (uid, question, now_iso()))
        tid = cur.lastrowid
        conn.commit()
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=f"🆘 Ticket #{tid}\nUser ID: `{uid}`\nName: {update.effective_user.full_name}\nLang: {lang}\nMessage:\n{question}\n\nReply: `/reply {tid} your message`", parse_mode=ParseMode.MARKDOWN)
        except Exception as exc:
            log.warning("notify admin failed: %s", exc)
    await update.effective_message.reply_text(tr(lang, "support_saved", tid=tid))

async def cmd_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /reply <ticket_id> <message>")
        return
    tid = int(context.args[0])
    msg = " ".join(context.args[1:]).strip()
    with db() as conn:
        row = conn.execute("SELECT user_id FROM tickets WHERE id=?", (tid,)).fetchone()
        if not row:
            await update.effective_message.reply_text("Ticket not found.")
            return
        uid = int(row["user_id"])
        conn.execute("UPDATE tickets SET status='closed', answer=?, answered_at=? WHERE id=?", (msg, now_iso(), tid))
        conn.commit()
    try:
        await context.bot.send_message(chat_id=uid, text=f"💬 Reply to ticket #{tid}:\n{msg}")
        await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "reply_sent", tid=tid))
    except Exception as exc:
        await update.effective_message.reply_text(f"Failed: {exc}")

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not admin_only(uid):
        await update.effective_message.reply_text(tr(lang, "admin_only"))
        return
    await update.effective_message.reply_text(tr(lang, "panel"), reply_markup=admin_keyboard())

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    s = stats()
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "stats", **s))

async def cmd_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /user <user_id>")
        return
    uid = int(context.args[0])
    row = get_user(uid)
    if not row:
        await update.effective_message.reply_text("User not found.")
        return
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "user_info", uid=uid, name=row["first_name"] or "", username=("@"+row["username"]) if row["username"] else "-", lang=row["lang"], base=row["base_currency"], premium="YES" if row["premium"] else "NO", requests=row["requests"], refs=row["referrals"], last_seen=row["last_seen"] or "-"))

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /ban <user_id>")
        return
    uid = int(context.args[0]); set_ban(uid, 1)
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "ban_done", uid=uid))

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /unban <user_id>")
        return
    uid = int(context.args[0]); set_ban(uid, 0)
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "unban_done", uid=uid))

async def cmd_vip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /vip <user_id> on|off")
        return
    uid = int(context.args[0]); mode = context.args[1].lower()
    if mode in {"on","1","yes","true"}:
        set_vip(uid, 1); await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "vip_on", uid=uid))
    else:
        set_vip(uid, 0); await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "vip_off", uid=uid))

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /reset <user_id>")
        return
    uid = int(context.args[0]); reset_user(uid)
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "reset_done", uid=uid))

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if not context.args:
        await update.effective_message.reply_text("Usage: /broadcast <message>")
        return
    msg = " ".join(context.args)
    sent = failed = 0
    with db() as conn:
        ids = [r["user_id"] for r in conn.execute("SELECT user_id FROM users WHERE banned=0").fetchall()]
    for uid in ids:
        try:
            await context.bot.send_message(chat_id=uid, text=msg)
            sent += 1
        except Exception:
            failed += 1
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "broadcast_done", sent=sent, failed=failed))

async def cmd_broadcastin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /broadcastin 10m <message>")
        return
    sec = parse_duration_to_seconds(context.args[0])
    if sec is None:
        await update.effective_message.reply_text("Usage: /broadcastin 10m <message>")
        return
    msg = " ".join(context.args[1:])
    run_at = datetime.now(timezone.utc) + timedelta(seconds=sec)
    job_id = schedule_broadcast(run_at, msg, update.effective_user.id)
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "schedule_done", when=run_at.isoformat()) + f"\nJob #{job_id}")

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user and update.effective_message:
        await update.effective_message.reply_text(str(update.effective_user.id))

async def cmd_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    rows = recent_tickets(10)
    if not rows:
        await update.effective_message.reply_text("No tickets.")
        return
    await update.effective_message.reply_text("\n".join([f"#{r['id']} | user {r['user_id']} | {r['status']} | {r['created_at']}" for r in rows]))

# callbacks
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query or not update.effective_user or not update.effective_message:
        return
    q = update.callback_query
    uid = update.effective_user.id
    lang = get_lang(uid)
    await q.answer()
    data = q.data or ""

    if data == "menu:back":
        await q.edit_message_text(tr(lang, "welcome"), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid)); return
    if data == "menu:help":
        await q.edit_message_text(f"{tr(lang, 'help')}\n\n{tr(lang, 'quick')}", parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid)); return
    if data == "menu:lang":
        await q.edit_message_text(tr(lang, "choose_lang"), reply_markup=language_keyboard()); return
    if data == "menu:base":
        await q.edit_message_text(tr(lang, "choose_base"), reply_markup=base_keyboard()); return
    if data == "menu:support":
        await q.edit_message_text(tr(lang, "support_intro"), reply_markup=support_keyboard()); return
    if data == "menu:chart":
        await q.edit_message_text(tr(lang, "choose_chart"), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Line", callback_data="chartpreset:line:7d:BTC"), InlineKeyboardButton("Candle", callback_data="chartpreset:candle:7d:BTC")],
            [InlineKeyboardButton("1H", callback_data="chartpreset:line:1h:BTC"), InlineKeyboardButton("24H", callback_data="chartpreset:line:24h:BTC"), InlineKeyboardButton("7D", callback_data="chartpreset:line:7d:BTC")],
            [InlineKeyboardButton("30D", callback_data="chartpreset:line:30d:BTC"), InlineKeyboardButton("1Y", callback_data="chartpreset:line:1y:BTC")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu:back")],
        ])); return
    if data == "menu:ref":
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        await q.edit_message_text(tr(lang, "ref_link", link=link), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid)); return
    if data == "menu:admin":
        if not admin_only(uid):
            await q.edit_message_text(tr(lang, "admin_only")); return
        await q.edit_message_text(tr(lang, "panel"), reply_markup=admin_keyboard()); return
    if data.startswith("lang:"):
        new_lang = data.split(":", 1)[1]
        if new_lang in LANGS:
            set_user_lang(uid, new_lang)
            await q.edit_message_text(tr(new_lang, "lang_saved", lang=lang_name(new_lang)), reply_markup=main_keyboard(uid))
        return
    if data.startswith("base:"):
        base = data.split(":", 1)[1]
        if base in BASE_CURRENCIES:
            set_user_base(uid, base)
            await q.edit_message_text(tr(lang, "base_saved", base=base_name(base)), reply_markup=main_keyboard(uid))
        return
    if data.startswith("charttype:") or data.startswith("charttf:") or data.startswith("chartpreset:"):
        parts = data.split(":")
        if parts[0] == "charttype" and len(parts) >= 3:
            chart_type, symbol = parts[1], ":".join(parts[2:])
            await send_chart_only(update, context, symbol, chart_type, "7d"); return
        if parts[0] == "charttf" and len(parts) >= 3:
            timeframe, symbol = parts[1], ":".join(parts[2:])
            await send_chart_only(update, context, symbol, "line", timeframe); return
        if parts[0] == "chartpreset" and len(parts) >= 4:
            chart_type, timeframe, symbol = parts[1], parts[2], ":".join(parts[3:])
            await send_chart_only(update, context, symbol, chart_type, timeframe); return
    if data.startswith("admin:"):
        if not admin_only(uid):
            await q.edit_message_text(tr(lang, "admin_only")); return
        action = data.split(":", 1)[1]
        if action == "stats":
            await q.edit_message_text(tr(lang, "stats", **stats()), reply_markup=admin_keyboard())
        elif action == "users":
            with db() as conn:
                rows = conn.execute("SELECT user_id, first_name, username, lang, base_currency, premium, requests FROM users ORDER BY last_seen DESC LIMIT 10").fetchall()
            txt = "\n".join([f"{r['user_id']} | {r['first_name']} | {('@'+r['username']) if r['username'] else '-'} | {r['lang']} | {r['base_currency']} | VIP:{r['premium']} | req:{r['requests']}" for r in rows]) or "No users."
            await q.edit_message_text(txt, reply_markup=admin_keyboard())
        elif action == "tickets":
            rows = recent_tickets(10)
            txt = "\n".join([f"#{r['id']} | u{r['user_id']} | {r['status']} | {r['created_at']}" for r in rows]) or "No tickets."
            await q.edit_message_text(txt, reply_markup=admin_keyboard())
        elif action == "broadcast":
            await q.edit_message_text("Use /broadcast <message>\nOr /broadcastin 10m <message>", reply_markup=admin_keyboard())
        elif action == "schedule":
            await q.edit_message_text("Use /broadcastin 10m <message>\nExample: /broadcastin 2h hello", reply_markup=admin_keyboard())
        elif action == "ban":
            await q.edit_message_text("Use /ban <user_id>", reply_markup=admin_keyboard())
        elif action == "unban":
            await q.edit_message_text("Use /unban <user_id>", reply_markup=admin_keyboard())
        elif action == "vip":
            await q.edit_message_text("Use /vip <user_id> on|off", reply_markup=admin_keyboard())
        elif action == "reset":
            await q.edit_message_text("Use /reset <user_id>", reply_markup=admin_keyboard())
        return

async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    lang = get_lang(update.effective_user.id)
    talk = maybe_small_talk(update.effective_message.text or "")
    if talk:
        await update.effective_message.reply_text(talk, parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(update.effective_user.id))
        return
    await update.effective_message.reply_text(tr(lang, "unknown"), reply_markup=main_keyboard(update.effective_user.id))

# background scheduler
async def process_scheduled_jobs(bot):
    for job in due_jobs():
        msg = job["message"]
        sent = failed = 0
        with db() as conn:
            ids = [r["user_id"] for r in conn.execute("SELECT user_id FROM users WHERE banned=0").fetchall()]
        for uid in ids:
            try:
                await bot.send_message(chat_id=uid, text=msg)
                sent += 1
            except Exception:
                failed += 1
        mark_job_done(int(job["id"]))
        log.info("scheduled broadcast %s done sent=%s failed=%s", job["id"], sent, failed)

def scheduler_loop():
    while True:
        try:
            if app_bot is not None:
                asyncio.run(process_scheduled_jobs(app_bot))
        except Exception as exc:
            log.warning("scheduler error: %s", exc)
        finally:
            threading.Event().wait(20)

# Telegram app
def build_app() -> Application:
    tg = ApplicationBuilder().token(BOT_TOKEN).build()
    tg.add_handler(CommandHandler("start", cmd_start))
    tg.add_handler(CommandHandler("help", cmd_help))
    tg.add_handler(CommandHandler("lang", cmd_lang))
    tg.add_handler(CommandHandler("base", cmd_base))
    tg.add_handler(CommandHandler("price", cmd_price))
    tg.add_handler(CommandHandler("chart", cmd_chart))
    tg.add_handler(CommandHandler("support", cmd_support))
    tg.add_handler(CommandHandler("reply", cmd_reply))
    tg.add_handler(CommandHandler("admin", cmd_admin))
    tg.add_handler(CommandHandler("stats", cmd_stats))
    tg.add_handler(CommandHandler("user", cmd_user))
    tg.add_handler(CommandHandler("ban", cmd_ban))
    tg.add_handler(CommandHandler("unban", cmd_unban))
    tg.add_handler(CommandHandler("vip", cmd_vip))
    tg.add_handler(CommandHandler("reset", cmd_reset))
    tg.add_handler(CommandHandler("broadcast", cmd_broadcast))
    tg.add_handler(CommandHandler("broadcastin", cmd_broadcastin))
    tg.add_handler(CommandHandler("id", cmd_id))
    tg.add_handler(CommandHandler("tickets", cmd_tickets))
    tg.add_handler(CallbackQueryHandler(handle_callback))
    tg.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_unknown))
    tg.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))
    return tg

def run_bot():
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    global app_bot
    application = build_app()
    app_bot = application.bot
    log.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None, close_loop=False)

app_bot = None

@app.get("/")
def home():
    return jsonify(ok=True, name=APP_TITLE, bot_username=BOT_USERNAME, time=now_iso())

@app.get("/health")
def health():
    return jsonify(ok=True)

def main():
    init_db()
    threading.Thread(target=run_bot, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    log.info("Web server on port %s", PORT)
    serve(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
