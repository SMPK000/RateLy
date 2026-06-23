
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
DEFAULT_LANG = os.getenv("DEFAULT_LANG", "en").strip().lower()
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
    "دلار": "USD", "دلار آمریکا": "USD", "us dollar": "USD", "dollar": "USD",
    "یورو": "EUR", "euro": "EUR",
    "پوند": "GBP", "british pound": "GBP", "pound": "GBP", "pound sterling": "GBP",
    "فرانک": "CHF", "swiss franc": "CHF",
    "تومان": "TMN", "toman": "TMN",
    "ریال": "IRR", "rial": "IRR",
    "تتر": "USDT", "tether": "USDT",
    "بیت کوین": "BTC", "بیتکوین": "BTC", "بیت‌کوین": "BTC", "bitcoin": "BTC", "btc": "BTC",
    "اتریوم": "ETH", "ethereum": "ETH", "eth": "ETH",
    "بایننس کوین": "BNB", "binance coin": "BNB", "bnb": "BNB",
    "سولانا": "SOL", "solana": "SOL", "sol": "SOL",
    "ریپل": "XRP", "ripple": "XRP", "xrp": "XRP",
    "دوج کوین": "DOGE", "dogecoin": "DOGE", "doge": "DOGE",
    "کاردانو": "ADA", "cardano": "ADA", "ada": "ADA",
    "ترون": "TRX", "tron": "TRX", "trx": "TRX",
    "لایت کوین": "LTC", "litecoin": "LTC", "ltc": "LTC",
    "پولکادات": "DOT", "polkadot": "DOT", "dot": "DOT",
    "آوالانچ": "AVAX", "avalanche": "AVAX", "avax": "AVAX",
    "چین لینک": "LINK", "chainlink": "LINK", "link": "LINK",
    "پالیگان": "MATIC", "polygon": "MATIC", "matic": "MATIC",
    "شیبا": "SHIB", "shiba inu": "SHIB", "shib": "SHIB",
    "پپه": "PEPE", "pepe": "PEPE",
    "بیت کوین کش": "BCH", "bitcoin cash": "BCH", "bch": "BCH",
    "اتریوم کلاسیک": "ETC", "ethereum classic": "ETC", "etc": "ETC",
    "استلار": "XLM", "stellar": "XLM", "xlm": "XLM",
    "کازماس": "ATOM", "cosmos": "ATOM", "atom": "ATOM",
    "نیر": "NEAR", "near": "NEAR",
    "اپتوس": "APT", "aptos": "APT", "apt": "APT",
    "سویی": "SUI", "sui": "SUI",
    "مونرو": "XMR", "monero": "XMR", "xmr": "XMR",
    "تزوس": "XTZ", "tezos": "XTZ", "xtz": "XTZ",
    "وی چین": "VET", "vechain": "VET", "vet": "VET",
    "آلگوراند": "ALGO", "algorand": "ALGO", "algo": "ALGO",
    "فایل کوین": "FIL", "filecoin": "FIL", "fil": "FIL",
    "طلای جهانی": "XAU", "gold": "XAU", "xau": "XAU", "طلا": "XAU",
    "نقره": "XAG", "silver": "XAG", "xag": "XAG",
    "پلاتین": "XPT", "platinum": "XPT", "xpt": "XPT",
    "پالادیوم": "XPD", "palladium": "XPD", "xpd": "XPD",
    "نفت": "CL=F", "oil": "CL=F",
}
PRICE_WORDS = {
    "price", "rate", "value", "quote", "chart", "graph", "trend",
    "قیمت", "نرخ", "ارزش", "نمودار", "رسم",
    "سعر", "precio", "preço", "kurs", "цена", "график", "fiyat", "değer"
}
FIAT_CODES = {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD","CNY","HKD","SGD","SEK","NOK","DKK","PLN","CZK","HUF","RON","TRY","SAR","AED","QAR","KWD","BHD","INR","PKR","RUB","UAH","ZAR","MXN","BRL","IDR","MYR","THB","PHP","KRW","TWD","ILS","EGP","IRR","KZT","VND","ARS","COP","CLP","NGN","IQD"}
CRYPTO_ALIASES = {"BTC":"bitcoin","ETH":"ethereum","BNB":"binancecoin","SOL":"solana","XRP":"ripple","DOGE":"dogecoin","ADA":"cardano","TON":"the-open-network","TRX":"tron","LTC":"litecoin","DOT":"polkadot","AVAX":"avalanche-2","MATIC":"polygon","LINK":"chainlink","SHIB":"shiba-inu","PEPE":"pepe","USDT":"tether","USDC":"usd-coin","BCH":"bitcoin-cash","ETC":"ethereum-classic","XLM":"stellar","ATOM":"cosmos","NEAR":"near","APT":"aptos","SUI":"sui","XMR":"monero","XTZ":"tezos","VET":"vechain","ALGO":"algorand","FIL":"filecoin"}

# DB helpers# DB helpers
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
BUTTONS = {
    "fa": {
        "prices": "💰 قیمت‌ها",
        "charts": "📈 نمودارها",
        "language": "🌐 زبان",
        "base": "💱 ارز پایه",
        "support": "🆘 پشتیبانی",
        "ads": "📢 تبلیغات",
        "feedback": "📝 نظرات",
        "help": "ℹ️ راهنما",
        "assets": "🗂 دارایی‌ها",
        "ref": "🔗 معرفی",
        "admin": "👑 ادمین",
        "back": "⬅️ بازگشت",
        "line": "📈 خطی",
        "candle": "🕯 کندلی",
        "1h": "⏱ 1س",
        "24h": "🕛 24س",
        "7d": "🗓 7روز",
        "30d": "🗓 30روز",
        "1y": "📅 1سال",
        "cancel": "❌ لغو",
    },
    "en": {
        "prices": "💰 Prices",
        "charts": "📈 Charts",
        "language": "🌐 Language",
        "base": "💱 Base",
        "support": "🆘 Support",
        "ads": "📢 Ads",
        "feedback": "📝 Feedback",
        "help": "ℹ️ Help",
        "assets": "🗂 Assets",
        "ref": "🔗 Referral",
        "admin": "👑 Admin",
        "back": "⬅️ Back",
        "line": "📈 Line",
        "candle": "🕯 Candle",
        "1h": "⏱ 1H",
        "24h": "🕛 24H",
        "7d": "🗓 7D",
        "30d": "🗓 30D",
        "1y": "📅 1Y",
        "cancel": "❌ Cancel",
    },
    "ar": {
        "prices": "💰 الأسعار",
        "charts": "📈 الرسوم",
        "language": "🌐 اللغة",
        "base": "💱 العملة الأساسية",
        "support": "🆘 الدعم",
        "ads": "📢 الإعلانات",
        "feedback": "📝 الآراء",
        "help": "ℹ️ المساعدة",
        "assets": "🗂 الأصول",
        "ref": "🔗 الإحالة",
        "admin": "👑 المدير",
        "back": "⬅️ رجوع",
        "line": "📈 خطي",
        "candle": "🕯 شموع",
        "1h": "⏱ 1س",
        "24h": "🕛 24س",
        "7d": "🗓 7أيام",
        "30d": "🗓 30يوم",
        "1y": "📅 سنة",
        "cancel": "❌ إلغاء",
    },
    "ru": {
        "prices": "💰 Цены",
        "charts": "📈 Графики",
        "language": "🌐 Язык",
        "base": "💱 Валюта",
        "support": "🆘 Поддержка",
        "ads": "📢 Реклама",
        "feedback": "📝 Отзывы",
        "help": "ℹ️ Помощь",
        "assets": "🗂 Активы",
        "ref": "🔗 Реферал",
        "admin": "👑 Админ",
        "back": "⬅️ Назад",
        "line": "📈 Линия",
        "candle": "🕯 Свечи",
        "1h": "⏱ 1ч",
        "24h": "🕛 24ч",
        "7d": "🗓 7д",
        "30d": "🗓 30д",
        "1y": "📅 1г",
        "cancel": "❌ Отмена",
    },
    "tr": {
        "prices": "💰 Fiyatlar",
        "charts": "📈 Grafikler",
        "language": "🌐 Dil",
        "base": "💱 Birim",
        "support": "🆘 Destek",
        "ads": "📢 Reklam",
        "feedback": "📝 Geri bildirim",
        "help": "ℹ️ Yardım",
        "assets": "🗂 Varlıklar",
        "ref": "🔗 Referans",
        "admin": "👑 Yönetici",
        "back": "⬅️ Geri",
        "line": "📈 Çizgi",
        "candle": "🕯 Mum",
        "1h": "⏱ 1s",
        "24h": "🕛 24s",
        "7d": "🗓 7g",
        "30d": "🗓 30g",
        "1y": "📅 1y",
        "cancel": "❌ İptal",
    },
    "es": {
        "prices": "💰 Precios",
        "charts": "📈 Gráficos",
        "language": "🌐 Idioma",
        "base": "💱 Moneda base",
        "support": "🆘 Soporte",
        "ads": "📢 Anuncios",
        "feedback": "📝 Opiniones",
        "help": "ℹ️ Ayuda",
        "assets": "🗂 Activos",
        "ref": "🔗 Referidos",
        "admin": "👑 Admin",
        "back": "⬅️ Volver",
        "line": "📈 Línea",
        "candle": "🕯 Velas",
        "1h": "⏱ 1H",
        "24h": "🕛 24H",
        "7d": "🗓 7D",
        "30d": "🗓 30D",
        "1y": "📅 1Y",
        "cancel": "❌ Cancelar",
    },
}

def lang_name(code: str) -> str:
    return LANGS.get(code, code)

def base_name(code: str) -> str:
    return {"TMN":"تومان","IRR":"ریال","USD":"USD","EUR":"EUR","GBP":"GBP","TRY":"TRY","RUB":"RUB","AED":"AED","SAR":"SAR","IQD":"IQD","QAR":"QAR","KWD":"KWD","CAD":"CAD","AUD":"AUD","JPY":"JPY","CHF":"CHF"}.get(code, code)

def button_label(lang: str, key: str) -> str:
    lang = lang if lang in BUTTONS else "en"
    return BUTTONS[lang].get(key, BUTTONS["en"].get(key, key))

def home_text(user_id: int) -> str:
    lang = get_lang(user_id)
    base = base_name(get_base(user_id))
    return "\n\n".join([
        tr(lang, "welcome"),
        f"💱 {tr(lang, 'choose_base')} {base}",
        tr(lang, "quick"),
        tr(lang, "help"),
    ])

def assets_text(lang: str) -> str:
    cryptos = ", ".join(sorted(list(CRYPTO_ALIASES.keys())[:24]))
    fiats = ", ".join(BASE_CURRENCIES)
    metals = "XAU, XAG, XPT, XPD"
    labels = {
        "fa": "🗂 دارایی‌های پشتیبانی‌شده",
        "en": "🗂 Supported assets",
        "ar": "🗂 الأصول المدعومة",
        "ru": "🗂 Поддерживаемые активы",
        "tr": "🗂 Desteklenen varlıklar",
        "es": "🗂 Activos compatibles",
    }
    note = {
        "fa": "هر نام رایج و نماد معقول هم امتحان می‌شود.",
        "en": "Common names and symbols are also searchable.",
        "ar": "يمكن البحث أيضًا بالأسماء الشائعة والرموز.",
        "ru": "Можно искать и по обычным названиям/رموزм.",
        "tr": "Yaygın isimler ve semboller de aranır.",
        "es": "También se pueden buscar nombres y símbolos comunes.",
    }
    return "\n\n".join([
        labels.get(lang, labels["en"]),
        f"💹 Crypto:\n{cryptos}",
        f"💱 Fiat:\n{fiats}",
        f"🥇 Metals:\n{metals}",
        note.get(lang, note["en"]),
    ])

def ticket_prompt_text(lang: str, kind: str) -> str:
    prompts = {
        "support": {
            "fa": "پیام پشتیبانی‌ات را بفرست تا ناشناس برای ادمین ذخیره شود.",
            "en": "Send your support message. It will be stored anonymously.",
            "ar": "أرسل رسالة الدعم وسيتم حفظها بشكل مجهول.",
            "ru": "Отправьте сообщение в поддержку. Оно сохранится анонимно.",
            "tr": "Destek mesajını gönder. Anonim olarak kaydedilecek.",
            "es": "Envía tu mensaje de soporte. Se guardará de forma anónima.",
        },
        "ads": {
            "fa": "متن تبلیغت را بفرست تا ناشناس برای ادمین ذخیره شود.",
            "en": "Send your ad message. It will be stored anonymously.",
            "ar": "أرسل نص الإعلان وسيتم حفظه بشكل مجهول.",
            "ru": "Отправьте текст рекламы. Он сохранится анонимно.",
            "tr": "Reklam mesajını gönder. Anonim olarak kaydedilecek.",
            "es": "Envía tu anuncio. Se guardará de forma anónima.",
        },
        "feedback": {
            "fa": "نظر یا پیشنهادت را بفرست تا ناشناس برای ادمین ذخیره شود.",
            "en": "Send your feedback. It will be stored anonymously.",
            "ar": "أرسل ملاحظتك وسيتم حفظها بشكل مجهول.",
            "ru": "Отправьте отзыв. Он сохранится анонимно.",
            "tr": "Geri bildiriminizi gönderin. Anonim olarak kaydedilecek.",
            "es": "Envía tu opinión. Se guardará de forma anónima.",
        },
    }
    return prompts.get(kind, prompts["support"]).get(lang, prompts.get(kind, prompts["support"])["en"])

def ticket_prompt_text(lang: str, kind: str) -> str:
    prompts = {
        "support": {
            "fa": "پیام پشتیبانی‌ات را بفرست تا ناشناس برای ادمین ذخیره شود.",
            "en": "Send your support message. It will be stored anonymously.",
            "ar": "أرسل رسالة الدعم وسيتم حفظها بشكل مجهول.",
            "ru": "Отправьте сообщение в поддержку. Оно сохранится анонимно.",
            "tr": "Destek mesajını gönder. Anonim olarak kaydedilecek.",
            "es": "Envía tu mensaje de soporte. Se guardará de forma anónima.",
        },
        "ads": {
            "fa": "متن تبلیغت را بفرست تا ناشناس برای ادمین ذخیره شود.",
            "en": "Send your ad message. It will be stored anonymously.",
            "ar": "أرسل نص الإعلان وسيتم حفظه بشكل مجهول.",
            "ru": "Отправьте текст рекламы. Он сохранится анонимно.",
            "tr": "Reklam mesajını gönder. Anonim olarak kaydedilecek.",
            "es": "Envía tu anuncio. Se guardará de forma anónima.",
        },
        "feedback": {
            "fa": "نظر یا پیشنهادت را بفرست تا ناشناس برای ادمین ذخیره شود.",
            "en": "Send your feedback. It will be stored anonymously.",
            "ar": "أرسل ملاحظتك وسيتم حفظها بشكل مجهول.",
            "ru": "Отправьте отзыв. Он сохранится анонимно.",
            "tr": "Geri bildiriminizi gönderin. Anonim olarak kaydedilecek.",
            "es": "Envía tu opinión. Se guardará de forma anónima.",
        },
    }
    return prompts.get(kind, prompts["support"]).get(lang, prompts.get(kind, prompts["support"])["en"])

def language_keyboard(user_id: int = None):
    lang = get_lang(user_id) if user_id else "en"
    rows, row = [], []
    for code in ["fa", "en", "ar", "ru", "tr", "es"]:
        row.append(InlineKeyboardButton(lang_name(code), callback_data=f"lang:{code}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton(button_label(lang, "back"), callback_data="menu:back")])
    return InlineKeyboardMarkup(rows)

def base_keyboard(user_id: int = None):
    lang = get_lang(user_id) if user_id else "en"
    rows, row = [], []
    for code in BASE_CURRENCIES:
        row.append(InlineKeyboardButton(base_name(code), callback_data=f"base:{code}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton(button_label(lang, "back"), callback_data="menu:back")])
    return InlineKeyboardMarkup(rows)

def chart_keyboard(symbol: str, user_id: int = None):
    lang = get_lang(user_id) if user_id else "en"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(button_label(lang, "line"), callback_data=f"charttype:line:{symbol}"),
         InlineKeyboardButton(button_label(lang, "candle"), callback_data=f"charttype:candle:{symbol}")],
        [InlineKeyboardButton(button_label(lang, "1h"), callback_data=f"charttf:1h:{symbol}"),
         InlineKeyboardButton(button_label(lang, "24h"), callback_data=f"charttf:24h:{symbol}"),
         InlineKeyboardButton(button_label(lang, "7d"), callback_data=f"charttf:7d:{symbol}")],
        [InlineKeyboardButton(button_label(lang, "30d"), callback_data=f"charttf:30d:{symbol}"),
         InlineKeyboardButton(button_label(lang, "1y"), callback_data=f"charttf:1y:{symbol}")],
        [InlineKeyboardButton(button_label(lang, "back"), callback_data="menu:back")],
    ])

def admin_keyboard(user_id: int = None):
    lang = get_lang(user_id) if user_id else "en"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats", callback_data="admin:stats"), InlineKeyboardButton("👥 Users", callback_data="admin:users")],
        [InlineKeyboardButton("💬 Tickets", callback_data="admin:tickets"), InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast")],
        [InlineKeyboardButton("⏱ Schedule", callback_data="admin:schedule"), InlineKeyboardButton("🔒 Ban", callback_data="admin:ban")],
        [InlineKeyboardButton("✅ Unban", callback_data="admin:unban"), InlineKeyboardButton("⭐ VIP", callback_data="admin:vip")],
        [InlineKeyboardButton("🗂 Assets", callback_data="menu:assets"), InlineKeyboardButton(button_label(lang, "back"), callback_data="menu:back")],
    ])

def main_keyboard(user_id: int):
    lang = get_lang(user_id)
    is_admin = admin_only(user_id)
    rows = [
        [InlineKeyboardButton(button_label(lang, "prices"), callback_data="menu:prices"),
         InlineKeyboardButton(button_label(lang, "charts"), callback_data="menu:charts")],
        [InlineKeyboardButton(button_label(lang, "language"), callback_data="menu:lang"),
         InlineKeyboardButton(button_label(lang, "base"), callback_data="menu:base")],
        [InlineKeyboardButton(button_label(lang, "support"), callback_data="menu:support"),
         InlineKeyboardButton(button_label(lang, "ads"), callback_data="menu:ads"),
         InlineKeyboardButton(button_label(lang, "feedback"), callback_data="menu:feedback")],
        [InlineKeyboardButton(button_label(lang, "assets"), callback_data="menu:assets"),
         InlineKeyboardButton(button_label(lang, "ref"), callback_data="menu:ref"),
         InlineKeyboardButton(button_label(lang, "help"), callback_data="menu:help")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(button_label(lang, "admin"), callback_data="menu:admin")])
    return InlineKeyboardMarkup(rows)

def support_keyboard(user_id: int = None):
    lang = get_lang(user_id) if user_id else "en"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(button_label(lang, "support"), callback_data="menu:support"),
         InlineKeyboardButton(button_label(lang, "ads"), callback_data="menu:ads"),
         InlineKeyboardButton(button_label(lang, "feedback"), callback_data="menu:feedback")],
        [InlineKeyboardButton(button_label(lang, "back"), callback_data="menu:back")],
    ])

# Parsing
def normalize_text(text: str) -> str:
    text = text.replace("‌", " ").replace("＋", "+")
    text = re.sub(r"@\w+", "", text)
    return re.sub(r"\s+", " ", text).strip()

def strip_token(token: str) -> str:
    return token.strip("`'\".,;:!?()[]{}<>+")

def norm_alias(token: str) -> str:
    t = strip_token(token).replace("‌", "").lower()
    return ALIASES.get(t, t.upper())


def resolve_phrase(text: str) -> str:
    t = normalize_text(text)
    low = t.lower()
    if low in ALIASES:
        return ALIASES[low]

    tokens = [strip_token(x) for x in re.split(r"[\s,]+", t) if strip_token(x)]
    tokens = [x for x in tokens if x.lower() not in PRICE_WORDS and x not in {"+", "＋"}]
    if not tokens:
        return ""

    # exact pair first
    for tok in tokens:
        nt = norm_alias(tok)
        if "/" in nt:
            return nt

    joined = " ".join(tokens).lower()
    if joined in ALIASES:
        return ALIASES[joined]

    if len(tokens) == 1:
        # keep original token, but allow generic names like bitcoin / gold / dollar
        return norm_alias(tokens[0])

    return " ".join(tokens)

def is_finance_like(text: str) -> bool:
    q = resolve_phrase(text)
    if not q:
        return False
    if "/" in q:
        a, b = q.split("/", 1)
        return bool(a and b)
    return bool(re.fullmatch(r"[A-Za-z0-9.\- ]{2,30}", q)) or q.upper() in FIAT_CODES or q.upper() in CRYPTO_ALIASES or q.upper() in {"XAU", "XAG", "XPT", "XPD", "CL=F"}

def parse_pair(query: str) -> Tuple[str, Optional[str]]:
    q = query.strip().upper().replace(" ", "").replace("-", "/")
    if "/" in q:
        a, b = q.split("/", 1)
        return a, b
    return q, None

# Data sources / caching# Data sources / caching
_PRICE_CACHE: Dict[str, Tuple[float, float]] = {}
_CACHE_TTL = 15.0

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


_JSON_CACHE: Dict[str, Tuple[float, Any]] = {}
_JSON_CACHE_TTL = 10.0
NOBITEX_ORDERBOOK_ALL_URL = "https://apiv2.nobitex.ir/v3/orderbook/all"

def cached_json_get(key: str) -> Optional[Any]:
    item = _JSON_CACHE.get(key)
    if not item:
        return None
    ts, val = item
    if (datetime.now().timestamp() - ts) > _JSON_CACHE_TTL:
        _JSON_CACHE.pop(key, None)
        return None
    return val

def cached_json_set(key: str, value: Any) -> None:
    _JSON_CACHE[key] = (datetime.now().timestamp(), value)

def _norm_market_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())

def nobitex_orderbook_all() -> Optional[dict]:
    cached = cached_json_get("nobitex:orderbook:all")
    if cached is not None:
        return cached
    data = _safe_json(NOBITEX_ORDERBOOK_ALL_URL, timeout=10)
    if data and data.get("status") == "ok":
        cached_json_set("nobitex:orderbook:all", data)
        return data
    return None

def nobitex_market_row(symbol: str) -> Optional[dict]:
    data = nobitex_orderbook_all()
    if not data:
        return None
    target = _norm_market_key(symbol)
    for key, row in data.items():
        if _norm_market_key(key) == target and isinstance(row, dict):
            return row
    return None

def nobitex_market_last_price(symbol: str) -> Optional[float]:
    row = nobitex_market_row(symbol)
    if not row:
        return None
    for key in ("lastTradePrice", "latest", "mark", "dayClose", "bestSell", "bestBuy"):
        val = row.get(key)
        if val is None or val == "":
            continue
        try:
            return float(val)
        except Exception:
            continue
    return None

def nobitex_usdt_irt_price() -> Optional[float]:
    return nobitex_market_last_price("USDTIRT")

def nobitex_crypto_usd(symbol: str) -> Optional[float]:
    s = symbol.upper().replace(" ", "")
    candidates = [s]
    if s not in CRYPTO_ALIASES:
        found = coin_gecko_search(s.lower())
        if found and found.get("symbol"):
            candidates = [found["symbol"].upper()]
    for cand in candidates:
        p_usdt = nobitex_market_last_price(f"{cand}USDT")
        if p_usdt is not None:
            return p_usdt
        p_irt = nobitex_market_last_price(f"{cand}IRT")
        if p_irt is not None:
            usdt_irt = nobitex_usdt_irt_price()
            if usdt_irt and usdt_irt != 0:
                return p_irt / usdt_irt
            irr = get_fiat_rate_to_usd("IRR")
            if irr and irr != 0:
                return p_irt / irr
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
    s = symbol.upper().replace(" ", "")
    key = f"crypto:{s}"
    cached = cached_get(key)
    if cached is not None:
        return cached

    # 1) Nobitex live public orderbook first
    nb = nobitex_crypto_usd(s)
    if nb is not None:
        cached_set(key, nb)
        return nb

    # 2) CoinGecko fallback
    cg_id = CRYPTO_ALIASES.get(s)
    if cg_id:
        data = _safe_json("https://api.coingecko.com/api/v3/simple/price", {"ids": cg_id, "vs_currencies": "usd"})
        if data and cg_id in data and "usd" in data[cg_id]:
            val = float(data[cg_id]["usd"])
            cached_set(key, val)
            return val

    found = coin_gecko_search(s.lower())
    if found and found.get("id"):
        cg_id = found["id"]
        data = _safe_json("https://api.coingecko.com/api/v3/simple/price", {"ids": cg_id, "vs_currencies": "usd"})
        if data and cg_id in data and "usd" in data[cg_id]:
            val = float(data[cg_id]["usd"])
            cached_set(key, val)
            return val

    # 3) yfinance fallback
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

    # direct fiat/crypto/metal aliases first
    if q in CRYPTO_ALIASES:
        return q, get_crypto_price_usd(q), "crypto", q, "USD"
    if q in {"XAU", "GOLD"}:
        return "XAUUSD=X", yfinance_last_close("XAUUSD=X"), "metal", "XAU", "USD"
    if q in {"XAG", "SILVER"}:
        return "XAGUSD=X", yfinance_last_close("XAGUSD=X"), "metal", "XAG", "USD"
    if q in {"XPT", "PLATINUM"}:
        return "XPTUSD=X", yfinance_last_close("XPTUSD=X"), "metal", "XPT", "USD"
    if q in {"XPD", "PALLADIUM"}:
        return "XPDUSD=X", yfinance_last_close("XPDUSD=X"), "metal", "XPD", "USD"
    if q in {"CL=F", "OIL"}:
        return "CL=F", yfinance_last_close("CL=F"), "commodity", "OIL", "USD"

    # fiat codes (and any 3-letter ISO code)
    if q in FIAT_CODES or (re.fullmatch(r"[A-Z]{3}", q) and q not in {"BTC", "ETH", "BNB"}):
        if q == "USD":
            return "USD", 1.0, "fiat", "USD", "USD"
        rate = get_fiat_rate_to_usd(q)
        if rate is not None:
            return q, rate, "fiat", q, "USD"

    base, quote = parse_pair(q)
    if quote:
        if base in FIAT_CODES and quote in FIAT_CODES:
            r = fiat_pair_rate(base, quote)
            return f"{base}{quote}=X", r, "pair", base, quote

        # crypto pairs: ask Nobitex first
        if base in CRYPTO_ALIASES or coin_gecko_search(base.lower()):
            price = get_crypto_price_usd(base)
            if price is not None:
                return base, price, "crypto", base, quote

        # direct yfinance pair
        t = f"{base}{quote}=X"
        px = yfinance_last_close(t)
        if px:
            return t, px, "pair", base, quote
        inv = f"{quote}{base}=X"
        inv_px = yfinance_last_close(inv)
        if inv_px:
            return inv, 1 / inv_px if inv_px != 0 else None, "pair", base, quote

        # maybe one side is a crypto symbol/name
        if base in CRYPTO_ALIASES or coin_gecko_search(base.lower()):
            price = get_crypto_price_usd(base)
            if price is not None:
                return base, price, "crypto", base, quote

        return None, None, None, None, None

    # single-word names / symbols
    if q in FIAT_CODES:
        rate = get_fiat_rate_to_usd(q)
        return q, rate, "fiat", q, "USD"

    crypto = get_crypto_price_usd(q)
    if crypto is not None:
        return q, crypto, "crypto", q, "USD"

    found = coin_gecko_search(q.lower())
    if found and found.get("symbol"):
        sym = found["symbol"].upper()
        price = get_crypto_price_usd(sym)
        if price is not None:
            return sym, price, "crypto", sym, "USD"

    # yfinance fallback for commodities/indices
    for t in [q, f"{q}=X", f"{q}-USD"]:
        px = yfinance_last_close(t)
        if px:
            return t, px, "other", q, "USD"

    return None, None, None, None, None


def chart_symbol_for(query: str) -> Optional[str]:
    q = resolve_phrase(query)
    if not q:
        return None
    raw = q.strip().upper().replace(" ", "").replace("-", "/")

    if raw in CRYPTO_ALIASES:
        return f"{raw}-USD"
    if raw in {"XAU", "GOLD"}:
        return "XAUUSD=X"
    if raw in {"XAG", "SILVER"}:
        return "XAGUSD=X"
    if raw in {"XPT", "PLATINUM"}:
        return "XPTUSD=X"
    if raw in {"XPD", "PALLADIUM"}:
        return "XPDUSD=X"
    if raw in FIAT_CODES:
        if raw == "USD":
            return None
        return f"{raw}USD=X"
    if "/" in raw:
        a, b = raw.split("/", 1)
        return f"{a}{b}=X"
    if raw.endswith("=X") or raw.endswith("-USD"):
        return raw

    found = coin_gecko_search(raw.lower())
    if found and found.get("symbol"):
        return f"{found['symbol'].upper()}-USD"
    return f"{raw}-USD"

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
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=chart_keyboard(human_symbol(q), user_id))
    chart = await asyncio.to_thread(make_chart, q, chart_type, timeframe)
    if chart:
        await update.effective_message.reply_photo(photo=chart, caption=tr(lang, "chart_default", symbol=human_symbol(q)), reply_markup=chart_keyboard(human_symbol(q), user_id))
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
    await update.effective_message.reply_photo(photo=chart, caption=f"{human_symbol(q)} | {chart_type.upper()} | {timeframe}", reply_markup=chart_keyboard(human_symbol(q), user_id))
    maybe_show_ad(update.effective_chat.id, lang, context, req_count)

# Commands
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    upsert_user(update.effective_user)
    uid = update.effective_user.id
    if context.args:
        arg = context.args[0].strip()
        if arg.startswith("ref_") and arg[4:].isdigit():
            record_referral(uid, int(arg[4:]))
    await update.effective_message.reply_text(
        home_text(uid),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(uid),
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    await update.effective_message.reply_text(
        f"{tr(lang, 'help')}\n\n{tr(lang, 'quick')}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(uid),
    )

async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if context.args and context.args[0].lower() in LANGS:
        new_lang = context.args[0].lower()
        set_user_lang(uid, new_lang)
        await update.effective_message.reply_text(
            home_text(uid),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard(uid),
        )
        return
    await update.effective_message.reply_text(tr(lang, "choose_lang"), reply_markup=language_keyboard(uid))

async def cmd_base(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if context.args and context.args[0].upper() in BASE_CURRENCIES:
        base = context.args[0].upper()
        set_user_base(uid, base)
        await update.effective_message.reply_text(
            home_text(uid),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard(uid),
        )
        return
    await update.effective_message.reply_text(tr(lang, "choose_base"), reply_markup=base_keyboard(uid))

async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    if not context.args:
        await update.effective_message.reply_text(tr(get_lang(uid), "help"), reply_markup=main_keyboard(uid))
        return
    await send_price_and_chart(update, context, " ".join(context.args))

async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not context.args:
        await update.effective_message.reply_text(
            f"{tr(lang, 'choose_chart')}\n\n{tr(lang, 'quick')}",
            reply_markup=chart_keyboard("BTC", uid),
        )
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
        await update.effective_message.reply_text(tr(lang, "admin_only"), reply_markup=main_keyboard(uid))
        return
    if not context.args:
        context.user_data["pending_ticket_kind"] = "support"
        await update.effective_message.reply_text(ticket_prompt_text(lang, "support"), reply_markup=support_keyboard(uid))
        return
    question = " ".join(context.args).strip()
    kind, tid = save_ticket(uid, "support", question, update.effective_user.full_name, lang)
    await notify_admins_about_ticket(context, uid, kind, tid, question, update.effective_user.full_name, lang)
    await update.effective_message.reply_text(tr(lang, "support_saved", tid=tid), reply_markup=main_keyboard(uid))


def save_ticket(user_id: int, kind: str, question: str, full_name: str, lang: str) -> Tuple[str, int]:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO tickets(user_id, kind, question, status, created_at) VALUES(?, ?, ?, 'open', ?)",
            (user_id, kind, question, now_iso()),
        )
        tid = cur.lastrowid
        conn.commit()
    return kind, int(tid)

async def notify_admins_about_ticket(context: ContextTypes.DEFAULT_TYPE, uid: int, kind: str, tid: int, question: str, full_name: str, lang: str) -> None:
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🆘 {kind.upper()} Ticket #{tid}\n"
                    f"User ID: `{uid}`\n"
                    f"Name: {full_name}\n"
                    f"Lang: {lang}\n"
                    f"Message:\n{question}\n\n"
                    f"Reply: `/reply {tid} your message`"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as exc:
            log.warning("notify admin failed: %s", exc)

async def cmd_assets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    lang = get_lang(update.effective_user.id)
    await update.effective_message.reply_text(assets_text(lang), reply_markup=main_keyboard(update.effective_user.id))

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
    await update.effective_message.reply_text(tr(lang, "panel"), reply_markup=admin_keyboard(uid))

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
        await q.edit_message_text(home_text(uid), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:help":
        await q.edit_message_text(f"{tr(lang, 'help')}\n\n{tr(lang, 'quick')}", parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:prices":
        await q.edit_message_text(f"{tr(lang, 'help')}\n\n{tr(lang, 'quick')}", parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:charts":
        await q.edit_message_text(f"{tr(lang, 'choose_chart')}\n\n{tr(lang, 'quick')}", reply_markup=chart_keyboard("BTC", uid))
        return
    if data == "menu:lang":
        await q.edit_message_text(tr(lang, "choose_lang"), reply_markup=language_keyboard(uid))
        return
    if data == "menu:base":
        await q.edit_message_text(tr(lang, "choose_base"), reply_markup=base_keyboard(uid))
        return
    if data == "menu:support":
        context.user_data["pending_ticket_kind"] = "support"
        await q.edit_message_text(ticket_prompt_text(lang, "support"), reply_markup=support_keyboard(uid))
        return
    if data == "menu:ads":
        context.user_data["pending_ticket_kind"] = "ads"
        await q.edit_message_text(ticket_prompt_text(lang, "ads"), reply_markup=support_keyboard(uid))
        return
    if data == "menu:feedback":
        context.user_data["pending_ticket_kind"] = "feedback"
        await q.edit_message_text(ticket_prompt_text(lang, "feedback"), reply_markup=support_keyboard(uid))
        return
    if data == "menu:assets":
        await q.edit_message_text(assets_text(lang), reply_markup=main_keyboard(uid))
        return
    if data == "menu:ref":
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        await q.edit_message_text(tr(lang, "ref_link", link=link), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:admin":
        if not admin_only(uid):
            await q.edit_message_text(tr(lang, "admin_only"))
            return
        await q.edit_message_text(tr(lang, "panel"), reply_markup=admin_keyboard(uid))
        return
    if data.startswith("lang:"):
        new_lang = data.split(":", 1)[1]
        if new_lang in LANGS:
            set_user_lang(uid, new_lang)
            await q.edit_message_text(home_text(uid), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data.startswith("base:"):
        base = data.split(":", 1)[1]
        if base in BASE_CURRENCIES:
            set_user_base(uid, base)
            await q.edit_message_text(home_text(uid), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data.startswith("charttype:") or data.startswith("charttf:") or data.startswith("chartpreset:"):
        parts = data.split(":")
        if parts[0] == "charttype" and len(parts) >= 3:
            chart_type, symbol = parts[1], ":".join(parts[2:])
            await send_chart_only(update, context, symbol, chart_type, "7d")
            return
        if parts[0] == "charttf" and len(parts) >= 3:
            timeframe, symbol = parts[1], ":".join(parts[2:])
            await send_chart_only(update, context, symbol, "line", timeframe)
            return
        if parts[0] == "chartpreset" and len(parts) >= 4:
            chart_type, timeframe, symbol = parts[1], parts[2], ":".join(parts[3:])
            await send_chart_only(update, context, symbol, chart_type, timeframe)
            return
    if data.startswith("admin:"):
        if not admin_only(uid):
            await q.edit_message_text(tr(lang, "admin_only"))
            return
        action = data.split(":", 1)[1]
        if action == "stats":
            await q.edit_message_text(tr(lang, "stats", **stats()), reply_markup=admin_keyboard(uid))
        elif action == "users":
            with db() as conn:
                rows = conn.execute("SELECT user_id, first_name, username, lang, base_currency, premium, requests FROM users ORDER BY last_seen DESC LIMIT 10").fetchall()
            txt = "\n".join([f"{r['user_id']} | {r['first_name']} | {('@'+r['username']) if r['username'] else '-'} | {r['lang']} | {r['base_currency']} | VIP:{r['premium']} | req:{r['requests']}" for r in rows]) or "No users."
            await q.edit_message_text(txt, reply_markup=admin_keyboard(uid))
        elif action == "tickets":
            rows = recent_tickets(10)
            txt = "\n".join([f"#{r['id']} | {r['kind']} | u{r['user_id']} | {r['status']} | {r['created_at']}" for r in rows]) or "No tickets."
            await q.edit_message_text(txt, reply_markup=admin_keyboard(uid))
        elif action == "broadcast":
            await q.edit_message_text("Use /broadcast <message>\nOr /broadcastin 10m <message>", reply_markup=admin_keyboard(uid))
        elif action == "schedule":
            await q.edit_message_text("Use /broadcastin 10m <message>\nExample: /broadcastin 2h hello", reply_markup=admin_keyboard(uid))
        elif action == "ban":
            await q.edit_message_text("Use /ban <user_id>", reply_markup=admin_keyboard(uid))
        elif action == "unban":
            await q.edit_message_text("Use /unban <user_id>", reply_markup=admin_keyboard(uid))
        elif action == "vip":
            await q.edit_message_text("Use /vip <user_id> on|off", reply_markup=admin_keyboard(uid))
        elif action == "reset":
            await q.edit_message_text("Use /reset <user_id>", reply_markup=admin_keyboard(uid))
        return

async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    text = normalize_text(update.effective_message.text or "")
    if not text or text.startswith("/"):
        return

    pending = context.user_data.get("pending_ticket_kind")
    if pending in {"support", "ads", "feedback"}:
        question = text.strip()
        context.user_data.pop("pending_ticket_kind", None)
        kind, tid = save_ticket(uid, pending, question, update.effective_user.full_name, lang)
        await notify_admins_about_ticket(context, uid, kind, tid, question, update.effective_user.full_name, lang)
        await update.effective_message.reply_text(tr(lang, "support_saved", tid=tid), reply_markup=main_keyboard(uid))
        return

    talk = maybe_small_talk(text)
    if talk:
        await update.effective_message.reply_text(talk, parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return

    cleaned = re.sub(rf"@{re.escape(BOT_USERNAME)}", "", text, flags=re.I).strip().lstrip("+").strip()
    q = resolve_phrase(cleaned)
    if q:
        await send_price_and_chart(update, context, q)
        return

    await update.effective_message.reply_text(tr(lang, "unknown"), reply_markup=main_keyboard(uid))

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


# =============================================================================
# RateLy fixes / polish
# =============================================================================

# Keep English as the default language unless a user selects otherwise.
DEFAULT_LANG = "en"

# Extra labels for translated admin buttons
BUTTONS["fa"].update({
    "stats": "📊 آمار",
    "users": "👥 کاربران",
    "tickets": "💬 پیام‌ها",
    "broadcast": "📢 ارسال همگانی",
    "schedule": "⏱ زمان‌بندی",
    "ban": "🔒 بن",
    "unban": "✅ آنبن",
    "vip": "⭐ پرمیوم",
    "reset": "♻️ ریست",
})
BUTTONS["en"].update({
    "stats": "📊 Stats",
    "users": "👥 Users",
    "tickets": "💬 Tickets",
    "broadcast": "📢 Broadcast",
    "schedule": "⏱ Schedule",
    "ban": "🔒 Ban",
    "unban": "✅ Unban",
    "vip": "⭐ Premium",
    "reset": "♻️ Reset",
})
BUTTONS["ar"].update({
    "stats": "📊 الإحصاءات",
    "users": "👥 المستخدمون",
    "tickets": "💬 الرسائل",
    "broadcast": "📢 إرسال جماعي",
    "schedule": "⏱ جدولة",
    "ban": "🔒 حظر",
    "unban": "✅ إلغاء الحظر",
    "vip": "⭐ برميوم",
    "reset": "♻️ إعادة ضبط",
})
BUTTONS["ru"].update({
    "stats": "📊 Статистика",
    "users": "👥 Пользователи",
    "tickets": "💬 Тикеты",
    "broadcast": "📢 Рассылка",
    "schedule": "⏱ Планирование",
    "ban": "🔒 Бан",
    "unban": "✅ Разбан",
    "vip": "⭐ Премиум",
    "reset": "♻️ Сброс",
})
BUTTONS["tr"].update({
    "stats": "📊 İstatistik",
    "users": "👥 Kullanıcılar",
    "tickets": "💬 Talepler",
    "broadcast": "📢 Toplu gönderim",
    "schedule": "⏱ Planlama",
    "ban": "🔒 Ban",
    "unban": "✅ Ban kaldır",
    "vip": "⭐ Premium",
    "reset": "♻️ Sıfırla",
})
BUTTONS["es"].update({
    "stats": "📊 Estadísticas",
    "users": "👥 Usuarios",
    "tickets": "💬 Tickets",
    "broadcast": "📢 Difusión",
    "schedule": "⏱ Programación",
    "ban": "🔒 Bloquear",
    "unban": "✅ Desbloquear",
    "vip": "⭐ Premium",
    "reset": "♻️ Reiniciar",
})

# Broader translation polish and better English default
T["en"].update({
    "welcome": "Welcome to *RateLy* ✨\nLive prices for currencies, crypto, metals, and charts.\nWorks in private chats and groups.",
    "help": "Send a symbol or name like `BTC`, `bitcoin`, `USD`, `EUR/USD`, `gold`, `silver`, `USD/IRR`, or `+btc` in groups.",
    "quick": "Quick examples: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`, `bitcoin`, `gold`, `oil`",
    "support_intro": "Use /support for help, ads, or feedback. Your message will be saved anonymously.",
    "support_saved": "Your anonymous message was saved as ticket #{tid}.",
    "ref_link": "Your referral link:\n`{link}`",
    "base_saved": "Display currency changed to {base}.",
    "lang_saved": "Language changed to {lang}.",
    "price_not_found": "No data found for {symbol}.",
    "chart_not_found": "No chart data found for {symbol}.",
    "admin_only": "Admin only.",
    "choose_base": "Choose your display currency:",
    "choose_lang": "Choose your language:",
    "choose_chart": "Choose chart type and timeframe:",
    "unknown": "I did not understand that message.\nTry sending a price like `BTC`, `USD/IRR`, `gold`, or `EUR/USD`.",
    "greet": "Hello 😎\nSend a symbol or use the buttons.",
    "ad_label": "Ad",
})
T["fa"].update({
    "welcome": "به *RateLy* خوش آمدی ✨\nقیمت لحظه‌ای ارزها، رمزارزها، طلا، نقره و نمودارها.\nهم در پیوی و هم در گروه کار می‌کند.",
    "help": "نمونه‌ها: `BTC`، `bitcoin`، `دلار`، `EUR/USD`، `طلا`، `نقره`، `USD/IRR`، `+btc` در گروه.",
    "quick": "نمونه‌های سریع: `BTC`، `ETH`، `XAU`، `USD`، `EUR/USD`، `GBP/USD`، `USD/IRR`، `bitcoin`، `طلا`، `نفت`",
    "support_intro": "برای پشتیبانی، تبلیغات یا نظرات از /support استفاده کن. پیام تو ناشناس ذخیره می‌شود.",
    "support_saved": "پیام ناشناس تو با شماره #{tid} ثبت شد.",
    "ref_link": "لینک معرفی تو:\n`{link}`",
    "base_saved": "ارز پایه به {base} تغییر کرد.",
    "lang_saved": "زبان به {lang} تغییر کرد.",
    "price_not_found": "برای {symbol} داده پیدا نشد.",
    "chart_not_found": "برای {symbol} نمودار پیدا نشد.",
    "admin_only": "فقط برای ادمین.",
    "choose_base": "ارز پایه را انتخاب کن:",
    "choose_lang": "زبان را انتخاب کن:",
    "choose_chart": "نوع و بازه‌ی نمودار را انتخاب کن:",
    "unknown": "این پیام را متوجه نشدم.\nمثلاً `BTC`، `USD/IRR`، `طلا` یا `EUR/USD` را بفرست.",
    "greet": "سلام 😎\nیک نماد بفرست یا از دکمه‌ها استفاده کن.",
    "ad_label": "تبلیغ",
})
T["ar"].update({
    "welcome": "مرحبًا بك في *RateLy* ✨\nأسعار فورية للعملات والذهب والعملات الرقمية والرسوم البيانية.\nيعمل في الخاص والمجموعات.",
    "help": "أرسل رمزًا أو اسمًا مثل `BTC` أو `bitcoin` أو `USD` أو `EUR/USD` أو `gold` أو `silver` أو `USD/IRR` أو `+btc` في المجموعات.",
    "quick": "أمثلة سريعة: `BTC`، `ETH`، `XAU`، `USD`، `EUR/USD`، `GBP/USD`، `USD/IRR`، `bitcoin`، `gold`، `oil`",
    "support_intro": "استخدم /support للدعم أو الإعلانات أو الآراء. سيتم حفظ رسالتك بشكل مجهول.",
    "support_saved": "تم حفظ رسالتك المجهولة كطلب رقم #{tid}.",
    "ref_link": "رابط الإحالة الخاص بك:\n`{link}`",
    "base_saved": "تم تغيير عملة العرض إلى {base}.",
    "lang_saved": "تم تغيير اللغة إلى {lang}.",
    "price_not_found": "لا توجد بيانات لـ {symbol}.",
    "chart_not_found": "لا توجد بيانات رسم لـ {symbol}.",
    "admin_only": "للمدير فقط.",
    "choose_base": "اختر عملة العرض:",
    "choose_lang": "اختر لغتك:",
    "choose_chart": "اختر نوع الرسم والمدة:",
    "unknown": "لم أفهم هذه الرسالة.\nجرّب إرسال سعر مثل `BTC` أو `USD/IRR` أو `gold` أو `EUR/USD`.",
    "greet": "مرحبًا 😎\nأرسل رمزًا أو استخدم الأزرار.",
    "ad_label": "إعلان",
})
T["ru"].update({
    "welcome": "Добро пожаловать в *RateLy* ✨\nЦены на валюты, криптовалюты, металлы и графики.\nРаботает в личке и в группах.",
    "help": "Отправьте символ или название вроде `BTC`, `bitcoin`, `USD`, `EUR/USD`, `gold`, `silver`, `USD/IRR` или `+btc` в группе.",
    "quick": "Быстрые примеры: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`, `bitcoin`, `gold`, `oil`",
    "support_intro": "Используйте /support для поддержки, рекламы или отзывов. Ваше сообщение сохранится анонимно.",
    "support_saved": "Ваше анонимное сообщение сохранено как тикет #{tid}.",
    "ref_link": "Ваша реферальная ссылка:\n`{link}`",
    "base_saved": "Валюта отображения изменена на {base}.",
    "lang_saved": "Язык изменён на {lang}.",
    "price_not_found": "Нет данных для {symbol}.",
    "chart_not_found": "Нет данных графика для {symbol}.",
    "admin_only": "Только для администратора.",
    "choose_base": "Выберите валюту отображения:",
    "choose_lang": "Выберите язык:",
    "choose_chart": "Выберите тип графика и период:",
    "unknown": "Я не понял это сообщение.\nПопробуйте отправить цену вроде `BTC`, `USD/IRR`, `gold` или `EUR/USD`.",
    "greet": "Привет 😎\nОтправьте символ или используйте кнопки.",
    "ad_label": "Реклама",
})
T["tr"].update({
    "welcome": "*RateLy*'ye hoş geldin ✨\nDöviz, kripto, metal ve grafikler için canlı fiyatlar.\nÖzelde ve gruplarda çalışır.",
    "help": "`BTC`, `bitcoin`, `USD`, `EUR/USD`, `gold`, `silver`, `USD/IRR` veya grupta `+btc` gibi bir kod gönder.",
    "quick": "Hızlı örnekler: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`, `bitcoin`, `gold`, `oil`",
    "support_intro": "Destek, reklam veya geri bildirim için /support kullan. Mesajın anonim kaydedilir.",
    "support_saved": "Anonim mesajın #{tid} numaralı talep olarak kaydedildi.",
    "ref_link": "Referans bağlantın:\n`{link}`",
    "base_saved": "Görüntüleme para birimi {base} olarak değişti.",
    "lang_saved": "Dil {lang} olarak değiştirildi.",
    "price_not_found": "{symbol} için veri bulunamadı.",
    "chart_not_found": "{symbol} için grafik verisi bulunamadı.",
    "admin_only": "Sadece yönetici.",
    "choose_base": "Görüntüleme para birimini seç:",
    "choose_lang": "Dil seç:",
    "choose_chart": "Grafik türünü ve zaman aralığını seç:",
    "unknown": "Bu mesajı anlayamadım.\n`BTC`, `USD/IRR`, `gold` veya `EUR/USD` gibi bir fiyat gönder.",
    "greet": "Merhaba 😎\nBir sembol gönder veya butonları kullan.",
    "ad_label": "Reklam",
})
T["es"].update({
    "welcome": "Bienvenido a *RateLy* ✨\nPrecios en vivo de divisas, criptomonedas, metales y gráficos.\nFunciona en privado y en grupos.",
    "help": "Envía un símbolo o nombre como `BTC`, `bitcoin`, `USD`, `EUR/USD`, `gold`, `silver`, `USD/IRR` o `+btc` en grupos.",
    "quick": "Ejemplos rápidos: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`, `bitcoin`, `gold`, `oil`",
    "support_intro": "Usa /support para soporte, anuncios u opiniones. Tu mensaje se guardará de forma anónima.",
    "support_saved": "Tu mensaje anónimo se guardó como ticket #{tid}.",
    "ref_link": "Tu enlace de referidos:\n`{link}`",
    "base_saved": "Moneda de visualización cambiada a {base}.",
    "lang_saved": "Idioma cambiado a {lang}.",
    "price_not_found": "No se encontraron datos para {symbol}.",
    "chart_not_found": "No se encontraron datos de gráfico para {symbol}.",
    "admin_only": "Solo administrador.",
    "choose_base": "Elige tu moneda de visualización:",
    "choose_lang": "Elige tu idioma:",
    "choose_chart": "Elige tipo de gráfico y periodo:",
    "unknown": "No entendí este mensaje.\nPrueba enviar un precio como `BTC`, `USD/IRR`, `gold` o `EUR/USD`.",
    "greet": "Hola 😎\nEnvía un símbolo o usa los botones.",
    "ad_label": "Anuncio",
})

# Extra assets / aliases for broader recognition
CRYPTO_ALIASES.update({
    "USDC": "usd-coin",
    "BCH": "bitcoin-cash",
    "XLM": "stellar",
    "ATOM": "cosmos",
    "NEAR": "near",
    "APT": "aptos",
    "SUI": "sui",
    "ETC": "ethereum-classic",
    "ICP": "internet-computer",
    "FIL": "filecoin",
    "INJ": "injective-protocol",
    "OP": "optimism",
    "ARB": "arbitrum",
    "UNI": "uniswap",
    "AAVE": "aave",
    "HBAR": "hedera-hashgraph",
    "VET": "vechain",
    "QNT": "quant-network",
    "RENDER": "render-token",
    "RNDR": "render-token",
    "TAO": "bittensor",
    "ONDO": "ondo-finance",
    "FET": "fetch-ai",
    "IMX": "immutable-x",
    "GRT": "the-graph",
    "MANA": "decentraland",
    "SAND": "the-sandbox",
    "ZEC": "zcash",
    "DASH": "dash",
    "XMR": "monero",
    "EOS": "eos",
    "ALGO": "algorand",
    "XTZ": "tezos",
    "THETA": "theta-token",
    "MKR": "maker",
    "COMP": "compound-governance-token",
    "LDO": "lido-dao",
    "STX": "stacks",
    "KAS": "kaspa",
    "AR": "arweave",
    "EGLD": "elrond-erd-2",
    "SEI": "sei-network",
    "RUNE": "thorchain",
    "FLOKI": "floki",
    "BONK": "bonk",
    "PYTH": "pyth-network",
    "PEPE": "pepe",
    "WIF": "dogwifcoin",
})
ALIASES.update({
    "دلار امریکا": "USD",
    "دلار آمریکا": "USD",
    "دلار امریکاى": "USD",
    "دلار آزاد": "USD",
    "دلار ایالات متحده": "USD",
    "یورو": "EUR",
    "پوند": "GBP",
    "لیر": "TRY",
    "روبل": "RUB",
    "درهم": "AED",
    "ریال": "IRR",
    "ریال ایران": "IRR",
    "تومان": "TMN",
    "تومان ایران": "TMN",
    "طلای جهانی": "XAU",
    "طلا": "XAU",
    "نقره": "XAG",
    "پلاتین": "XPT",
    "پالادیوم": "XPD",
    "نفت": "OIL",
    "gold": "XAU",
    "silver": "XAG",
    "platinum": "XPT",
    "palladium": "XPD",
    "oil": "OIL",
    "wti": "OIL",
    "brent": "BRENT",
    "bitcoin": "BTC",
    "bit coin": "BTC",
    "ethereum": "ETH",
    "tether": "USDT",
    "usd coin": "USDC",
    "binance coin": "BNB",
    "solana": "SOL",
    "ripple": "XRP",
    "dogecoin": "DOGE",
    "cardano": "ADA",
    "tron": "TRX",
    "litecoin": "LTC",
    "polkadot": "DOT",
    "avalanche": "AVAX",
    "chainlink": "LINK",
    "shiba inu": "SHIB",
    "monero": "XMR",
    "dash": "DASH",
    "zcash": "ZEC",
    "metals": "XAU",
})
# give search more room for common names
FIAT_CODES.update({"MXN","SGD","HKD","PLN","CZK","HUF","RON","ILS","EGP","KZT","NGN","VND","CLP","COP","ARS","PKR","UAH"})

# Better names for IRR/TMN
def base_name(code: str) -> str:
    return {
        "TMN": "تومان ایران",
        "IRR": "ریال ایران",
        "USD": "USD",
        "EUR": "EUR",
        "GBP": "GBP",
        "TRY": "TRY",
        "RUB": "RUB",
        "AED": "AED",
        "SAR": "SAR",
        "IQD": "IQD",
        "QAR": "QAR",
        "KWD": "KWD",
        "CAD": "CAD",
        "AUD": "AUD",
        "JPY": "JPY",
        "CHF": "CHF",
        "MXN": "MXN",
        "SGD": "SGD",
        "HKD": "HKD",
    }.get(code, code)

def home_text(user_id: int) -> str:
    lang = get_lang(user_id)
    base = base_name(get_base(user_id))
    group_note = {
        "fa": "➕ ربات را می‌توان به گروه هم اضافه کرد.",
        "en": "➕ The bot can also be added to groups.",
        "ar": "➕ يمكن إضافة البوت إلى المجموعات.",
        "ru": "➕ Бота можно добавить в группы.",
        "tr": "➕ Bot gruplara da eklenebilir.",
        "es": "➕ El bot también se puede añadir a grupos.",
    }.get(lang, "➕ The bot can also be added to groups.")
    return "\n\n".join([
        tr(lang, "welcome"),
        f"💱 {tr(lang, 'choose_base')} {base}",
        group_note,
        tr(lang, "quick"),
        tr(lang, "help"),
    ])

def assets_text(lang: str) -> str:
    crypto_list = [
        "BTC","ETH","BNB","SOL","XRP","DOGE","ADA","TON","TRX","LTC","DOT","AVAX","LINK","MATIC","SHIB",
        "PEPE","USDT","USDC","BCH","XLM","ATOM","NEAR","APT","SUI","ETC","ICP","FIL","INJ","OP","ARB",
        "UNI","AAVE","HBAR","VET","QNT","RENDER","TAO","ONDO","FET","IMX","GRT","MANA","SAND","ZEC",
        "DASH","XMR","EOS","ALGO","XTZ","THETA","MKR","COMP","LDO","STX","KAS","AR","EGLD","SEI","RUNE",
        "FLOKI","BONK","PYTH","WIF"
    ]
    fiat_list = ["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD","CNY","HKD","SGD","SEK","NOK","DKK","PLN","CZK","HUF","RON","TRY","SAR","AED","QAR","KWD","BHD","INR","PKR","RUB","UAH","ZAR","MXN","BRL","IDR","MYR","THB","PHP","KRW","TWD","ILS","EGP","IRR","TMN","KZT","NGN","VND","CLP","COP","ARS"]
    metals_list = ["XAU / GOLD", "XAG / SILVER", "XPT / PLATINUM", "XPD / PALLADIUM"]
    commodities = ["OIL / WTI", "BRENT"]

    labels = {
        "fa": "🗂 دارایی‌های پشتیبانی‌شده",
        "en": "🗂 Supported assets",
        "ar": "🗂 الأصول المدعومة",
        "ru": "🗂 Поддерживаемые активы",
        "tr": "🗂 Desteklenen varlıklar",
        "es": "🗂 Activos compatibles",
    }
    note = {
        "fa": "هم با نام رایج و هم با نماد قابل جستجو هستند.",
        "en": "Search works by both symbol and common name.",
        "ar": "يمكن البحث بالاسم الشائع أو بالرمز.",
        "ru": "Поиск работает и по символу, и по названию.",
        "tr": "Arama hem sembol hem de yaygın ad ile çalışır.",
        "es": "La búsqueda funciona por símbolo y por nombre común.",
    }
    return "\n\n".join([
        labels.get(lang, labels["en"]),
        "💹 Crypto:\n" + ", ".join(crypto_list),
        "💱 Fiat:\n" + ", ".join(fiat_list),
        "🥇 Metals:\n" + ", ".join(metals_list),
        "🛢 Commodities:\n" + ", ".join(commodities),
        note.get(lang, note["en"]),
    ])

def ticket_prompt_text(lang: str, kind: str) -> str:
    prompts = {
        "support": {
            "fa": "پیام پشتیبانی‌ات را بفرست تا ناشناس برای ادمین ذخیره شود.",
            "en": "Send your support message. It will be stored anonymously.",
            "ar": "أرسل رسالة الدعم وسيتم حفظها بشكل مجهول.",
            "ru": "Отправьте сообщение в поддержку. Оно сохранится анонимно.",
            "tr": "Destek mesajını gönder. Anonim olarak kaydedilecek.",
            "es": "Envía tu mensaje de soporte. Se guardará de forma anónima.",
        },
        "ads": {
            "fa": "لطفاً متن تبلیغ، شرایط همکاری و بودجه پیشنهادی‌ات را بفرست تا برای بررسی و هماهنگی به ادمین ارسال شود.",
            "en": "Send your ad proposal, conditions, and budget so it can be reviewed and forwarded to the admin.",
            "ar": "أرسل اقتراح الإعلان والشروط والميزانية ليتم مراجعتها وإرسالها للمدير.",
            "ru": "Отправьте предложение по рекламе, условия и бюджет — это будет передано администратору.",
            "tr": "Reklam teklifini, şartlarını ve bütçeni gönder; kontrol edilip yöneticiye iletilecek.",
            "es": "Envía tu propuesta de anuncio, condiciones y presupuesto para revisarlo y pasarlo al admin.",
        },
        "feedback": {
            "fa": "نظر یا پیشنهادت را بفرست تا ناشناس برای ادمین ذخیره شود.",
            "en": "Send your feedback. It will be stored anonymously.",
            "ar": "أرسل ملاحظتك وسيتم حفظها بشكل مجهول.",
            "ru": "Отправьте отзыв. Он сохранится анонимно.",
            "tr": "Geri bildiriminizi gönderin. Anonim olarak kaydedilecek.",
            "es": "Envía tu opinión. Se guardará de forma anónima.",
        },
    }
    return prompts.get(kind, prompts["support"]).get(lang, prompts.get(kind, prompts["support"])["en"])

def admin_keyboard(user_id: int = None):
    lang = get_lang(user_id) if user_id else "en"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(button_label(lang, "stats"), callback_data="admin:stats"),
         InlineKeyboardButton(button_label(lang, "users"), callback_data="admin:users")],
        [InlineKeyboardButton(button_label(lang, "tickets"), callback_data="admin:tickets"),
         InlineKeyboardButton(button_label(lang, "broadcast"), callback_data="admin:broadcast")],
        [InlineKeyboardButton(button_label(lang, "schedule"), callback_data="admin:schedule"),
         InlineKeyboardButton(button_label(lang, "ban"), callback_data="admin:ban")],
        [InlineKeyboardButton(button_label(lang, "unban"), callback_data="admin:unban"),
         InlineKeyboardButton(button_label(lang, "vip"), callback_data="admin:vip")],
        [InlineKeyboardButton(button_label(lang, "reset"), callback_data="admin:reset"),
         InlineKeyboardButton(button_label(lang, "assets"), callback_data="menu:assets")],
        [InlineKeyboardButton(button_label(lang, "back"), callback_data="menu:back")],
    ])

def resolve_phrase(text: str) -> str:
    t = normalize_text(text)
    if not t:
        return ""
    low = t.lower()
    if low in ALIASES:
        return ALIASES[low]

    tokens = [strip_token(x) for x in re.split(r"[\s,]+", t) if strip_token(x)]
    tokens = [x for x in tokens if x.lower() not in PRICE_WORDS and x not in {"+", "＋"}]
    if not tokens:
        return ""

    for tok in tokens:
        nt = norm_alias(tok)
        if "/" in nt:
            return nt

    joined = " ".join(tokens).lower()
    if joined in ALIASES:
        return ALIASES[joined]

    for tok in reversed(tokens):
        nt = norm_alias(tok)
        if nt in ALIASES.values() or nt in CRYPTO_ALIASES or nt in FIAT_CODES or nt in {"XAU", "XAG", "XPT", "XPD"}:
            return nt

    # Search alias substrings in the raw text to catch phrases like "قیمت دلار"
    ordered_aliases = sorted(ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True)
    for alias, symbol in ordered_aliases:
        if alias and alias in low:
            return symbol

    return norm_alias(tokens[-1])

def fiat_units_per_usd(code: str) -> Optional[float]:
    # This function returns how many units of `code` equal 1 USD.
    return get_fiat_rate_to_usd(code)

def fiat_usd_per_unit(code: str) -> Optional[float]:
    units = fiat_units_per_usd(code)
    if units is None or units == 0:
        return None
    return 1 / units

def fiat_pair_rate(base: str, quote: str) -> Optional[float]:
    base = base.upper()
    quote = quote.upper()
    if base == quote:
        return 1.0
    if quote == "USD":
        # 1 base = ? USD
        return fiat_usd_per_unit(base)
    if base == "USD":
        # 1 USD = ? quote
        return fiat_units_per_usd(quote)
    bu = fiat_units_per_usd(base)
    qu = fiat_units_per_usd(quote)
    if bu and qu:
        # quote per base
        return qu / bu
    return None

def resolve_asset(query: str) -> Tuple[Optional[str], Optional[float], Optional[str], Optional[str], Optional[str]]:
    q = resolve_phrase(query)
    if not q:
        return None, None, None, None, None
    raw = q.upper().replace(" ", "").replace("-", "/")

    # Direct fiat / crypto / metal symbols
    if raw in {"XAU", "GOLD"}:
        # prefer spot; fallback to futures
        for t in ["XAUUSD=X", "GC=F", "GLD"]:
            px = yfinance_last_close(t)
            if px:
                return t, px, "metal", "XAU", "USD"
        return "XAUUSD=X", None, "metal", "XAU", "USD"
    if raw in {"XAG", "SILVER"}:
        for t in ["XAGUSD=X", "SI=F"]:
            px = yfinance_last_close(t)
            if px:
                return t, px, "metal", "XAG", "USD"
        return "XAGUSD=X", None, "metal", "XAG", "USD"
    if raw in {"XPT", "PLATINUM"}:
        for t in ["XPTUSD=X", "PL=F"]:
            px = yfinance_last_close(t)
            if px:
                return t, px, "metal", "XPT", "USD"
        return "XPTUSD=X", None, "metal", "XPT", "USD"
    if raw in {"XPD", "PALLADIUM"}:
        for t in ["XPDUSD=X", "PA=F"]:
            px = yfinance_last_close(t)
            if px:
                return t, px, "metal", "XPD", "USD"
        return "XPDUSD=X", None, "metal", "XPD", "USD"
    if raw in {"OIL", "WTI"}:
        for t in ["CL=F", "BZ=F"]:
            px = yfinance_last_close(t)
            if px:
                return t, px, "commodity", "OIL", "USD"
        return "CL=F", None, "commodity", "OIL", "USD"

    base, quote = parse_pair(raw)
    if quote:
        if base in FIAT_CODES and quote in FIAT_CODES:
            return f"{base}{quote}=X", fiat_pair_rate(base, quote), "pair", base, quote
        if base in CRYPTO_ALIASES or coin_gecko_search(base.lower()):
            px = get_crypto_price_usd(base)
            if px is not None:
                return base, px, "crypto", base, quote
        t = f"{base}{quote}=X"
        px = yfinance_last_close(t)
        if px:
            return t, px, "pair", base, quote
        inv = f"{quote}{base}=X"
        inv_px = yfinance_last_close(inv)
        if inv_px and inv_px != 0:
            return inv, 1 / inv_px, "pair", base, quote
        # if a crypto pair is entered in reverse, still try to identify base
        if base in CRYPTO_ALIASES or coin_gecko_search(base.lower()):
            px = get_crypto_price_usd(base)
            if px is not None:
                return base, px, "crypto", base, quote
        return None, None, None, None, None

    if raw in FIAT_CODES:
        if raw == "USD":
            return "USD", 1.0, "fiat", "USD", "USD"
        usd_per_unit = fiat_usd_per_unit(raw)
        return raw, usd_per_unit, "fiat", raw, "USD"
    if raw in CRYPTO_ALIASES:
        return raw, get_crypto_price_usd(raw), "crypto", raw, "USD"

    # broad CoinGecko fallback for names/symbols
    if len(raw) >= 2 and len(raw) <= 24:
        cg = coin_gecko_search(raw.lower())
        if cg and cg.get("id"):
            data = _safe_json("https://api.coingecko.com/api/v3/simple/price", {"ids": cg["id"], "vs_currencies": "usd"})
            if data and cg["id"] in data and "usd" in data[cg["id"]]:
                px = float(data[cg["id"]]["usd"])
                return cg["symbol"].upper(), px, "crypto", cg["symbol"].upper(), "USD"

    # yfinance fallback
    for t in [raw, f"{raw}=X", f"{raw}-USD", f"{raw}-USDT"]:
        px = yfinance_last_close(t)
        if px:
            return t, px, "other", raw, "USD"

    return None, None, None, None, None

def display_to_base(usd_value: float, base: str) -> Optional[float]:
    rate = get_base_rate_to_usd(base)
    if rate is None:
        return None
    return usd_value * rate

def format_money(value: float, code: str) -> str:
    if code == "TMN":
        return f"{value:,.0f} تومان ایران"
    if code == "IRR":
        return f"{value:,.0f} ریال ایران"
    return f"{value:,.4f} {code}" if abs(value) < 1000 else f"{value:,.2f} {code}"

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
    raw = q.upper().replace(" ", "").replace("-", "/")
    if raw in CRYPTO_ALIASES:
        return f"{raw}-USD"
    if raw in {"XAU", "GOLD"}:
        return "XAUUSD=X"
    if raw in {"XAG", "SILVER"}:
        return "XAGUSD=X"
    if raw in {"XPT", "PLATINUM"}:
        return "XPTUSD=X"
    if raw in {"XPD", "PALLADIUM"}:
        return "XPDUSD=X"
    if raw in {"OIL", "WTI"}:
        return "CL=F"
    if raw in FIAT_CODES:
        if raw == "USD":
            return None
        return f"{raw}USD=X"
    if "/" in raw:
        a, b = raw.split("/", 1)
        return f"{a}{b}=X"
    found = coin_gecko_search(raw.lower())
    if found and found.get("symbol"):
        return f"{found['symbol'].upper()}-USD"
    return f"{raw}-USD"

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
        await update.effective_message.reply_text(tr(lang, "unknown"), reply_markup=main_keyboard(user_id))
        return
    text = format_price_response(q, lang, base)
    # No chart controls here; only show them with chart/photo.
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    chart = await asyncio.to_thread(make_chart, q, chart_type, timeframe)
    if chart:
        await update.effective_message.reply_photo(
            photo=chart,
            caption=tr(lang, "chart_default", symbol=human_symbol(q)),
            reply_markup=chart_keyboard(human_symbol(q), user_id),
        )
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
        await update.effective_message.reply_text(tr(lang, "unknown"), reply_markup=main_keyboard(user_id))
        return
    chart = await asyncio.to_thread(make_chart, q, chart_type, timeframe)
    if not chart:
        await update.effective_message.reply_text(tr(lang, "chart_not_found", symbol=human_symbol(q)), reply_markup=main_keyboard(user_id))
        return
    await update.effective_message.reply_photo(
        photo=chart,
        caption=f"{human_symbol(q)} | {chart_type.upper()} | {timeframe}",
        reply_markup=chart_keyboard(human_symbol(q), user_id),
    )
    maybe_show_ad(update.effective_chat.id, lang, context, req_count)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    upsert_user(update.effective_user)
    uid = update.effective_user.id
    if context.args:
        arg = context.args[0].strip()
        if arg.startswith("ref_") and arg[4:].isdigit():
            record_referral(uid, int(arg[4:]))
    await update.effective_message.reply_text(
        home_text(uid),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(uid),
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    await update.effective_message.reply_text(
        f"{tr(lang, 'help')}\n\n{tr(lang, 'quick')}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(uid),
    )

async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if context.args and context.args[0].lower() in LANGS:
        new_lang = context.args[0].lower()
        set_user_lang(uid, new_lang)
        await update.effective_message.reply_text(
            home_text(uid),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard(uid),
        )
        return
    await update.effective_message.reply_text(tr(lang, "choose_lang"), reply_markup=language_keyboard(uid))

async def cmd_base(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if context.args and context.args[0].upper() in BASE_CURRENCIES:
        base = context.args[0].upper()
        set_user_base(uid, base)
        await update.effective_message.reply_text(
            home_text(uid),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard(uid),
        )
        return
    await update.effective_message.reply_text(tr(lang, "choose_base"), reply_markup=base_keyboard(uid))

async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    if not context.args:
        await update.effective_message.reply_text(tr(get_lang(uid), "help"), reply_markup=main_keyboard(uid))
        return
    await send_price_and_chart(update, context, " ".join(context.args))

async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not context.args:
        await update.effective_message.reply_text(
            f"{tr(lang, 'choose_chart')}\n\n{tr(lang, 'quick')}",
            reply_markup=chart_keyboard("BTC", uid),
        )
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
        await update.effective_message.reply_text(tr(lang, "admin_only"), reply_markup=main_keyboard(uid))
        return
    if not context.args:
        context.user_data["pending_ticket_kind"] = "support"
        await update.effective_message.reply_text(ticket_prompt_text(lang, "support"), reply_markup=support_keyboard(uid))
        return
    question = " ".join(context.args).strip()
    kind, tid = save_ticket(uid, "support", question, update.effective_user.full_name, lang)
    await notify_admins_about_ticket(context, uid, kind, tid, question, update.effective_user.full_name, lang)
    await update.effective_message.reply_text(tr(lang, "support_saved", tid=tid), reply_markup=main_keyboard(uid))

async def cmd_assets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    lang = get_lang(update.effective_user.id)
    await update.effective_message.reply_text(assets_text(lang), reply_markup=main_keyboard(update.effective_user.id))

async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    text = normalize_text(update.effective_message.text or "")
    if not text or text.startswith("/"):
        return

    pending = context.user_data.get("pending_ticket_kind")
    if pending in {"support", "ads", "feedback"}:
        question = text.strip()
        context.user_data.pop("pending_ticket_kind", None)
        kind, tid = save_ticket(uid, pending, question, update.effective_user.full_name, lang)
        await notify_admins_about_ticket(context, uid, kind, tid, question, update.effective_user.full_name, lang)
        await update.effective_message.reply_text(tr(lang, "support_saved", tid=tid), reply_markup=main_keyboard(uid))
        return

    talk = maybe_small_talk(text)
    if talk:
        await update.effective_message.reply_text(talk, parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return

    cleaned = re.sub(rf"@{re.escape(BOT_USERNAME)}\b", "", text, flags=re.I).strip().lstrip("+").strip()
    q = resolve_phrase(cleaned)
    if q:
        await send_price_and_chart(update, context, q)
        return

    await update.effective_message.reply_text(tr(lang, "unknown"), reply_markup=main_keyboard(uid))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query or not update.effective_user or not update.effective_message:
        return
    q = update.callback_query
    uid = update.effective_user.id
    lang = get_lang(uid)
    await q.answer()
    data = q.data or ""

    if data == "menu:back":
        await q.edit_message_text(home_text(uid), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:help":
        await q.edit_message_text(f"{tr(lang, 'help')}\n\n{tr(lang, 'quick')}", parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:prices":
        await q.edit_message_text(f"{tr(lang, 'help')}\n\n{tr(lang, 'quick')}", parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:charts":
        await q.edit_message_text(f"{tr(lang, 'choose_chart')}\n\n{tr(lang, 'quick')}", reply_markup=chart_keyboard("BTC", uid))
        return
    if data == "menu:lang":
        await q.edit_message_text(tr(lang, "choose_lang"), reply_markup=language_keyboard(uid))
        return
    if data == "menu:base":
        await q.edit_message_text(tr(lang, "choose_base"), reply_markup=base_keyboard(uid))
        return
    if data == "menu:support":
        context.user_data["pending_ticket_kind"] = "support"
        await q.edit_message_text(ticket_prompt_text(lang, "support"), reply_markup=support_keyboard(uid))
        return
    if data == "menu:ads":
        context.user_data["pending_ticket_kind"] = "ads"
        await q.edit_message_text(ticket_prompt_text(lang, "ads"), reply_markup=support_keyboard(uid))
        return
    if data == "menu:feedback":
        context.user_data["pending_ticket_kind"] = "feedback"
        await q.edit_message_text(ticket_prompt_text(lang, "feedback"), reply_markup=support_keyboard(uid))
        return
    if data == "menu:assets":
        await q.edit_message_text(assets_text(lang), reply_markup=main_keyboard(uid))
        return
    if data == "menu:ref":
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        await q.edit_message_text(tr(lang, "ref_link", link=link), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:admin":
        if not admin_only(uid):
            await q.edit_message_text(tr(lang, "admin_only"))
            return
        await q.edit_message_text(tr(lang, "panel"), reply_markup=admin_keyboard(uid))
        return
    if data.startswith("lang:"):
        new_lang = data.split(":", 1)[1]
        if new_lang in LANGS:
            set_user_lang(uid, new_lang)
            await q.edit_message_text(home_text(uid), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data.startswith("base:"):
        base = data.split(":", 1)[1]
        if base in BASE_CURRENCIES:
            set_user_base(uid, base)
            await q.edit_message_text(home_text(uid), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data.startswith("charttype:") or data.startswith("charttf:") or data.startswith("chartpreset:"):
        parts = data.split(":")
        if parts[0] == "charttype" and len(parts) >= 3:
            chart_type, symbol = parts[1], ":".join(parts[2:])
            await send_chart_only(update, context, symbol, chart_type, "7d")
            return
        if parts[0] == "charttf" and len(parts) >= 3:
            timeframe, symbol = parts[1], ":".join(parts[2:])
            await send_chart_only(update, context, symbol, "line", timeframe)
            return
        if parts[0] == "chartpreset" and len(parts) >= 4:
            chart_type, timeframe, symbol = parts[1], parts[2], ":".join(parts[3:])
            await send_chart_only(update, context, symbol, chart_type, timeframe)
            return
    if data.startswith("admin:"):
        if not admin_only(uid):
            await q.edit_message_text(tr(lang, "admin_only"))
            return
        action = data.split(":", 1)[1]
        if action == "stats":
            await q.edit_message_text(tr(lang, "stats", **stats()), reply_markup=admin_keyboard(uid))
        elif action == "users":
            with db() as conn:
                rows = conn.execute("SELECT user_id, first_name, username, lang, base_currency, premium, requests FROM users ORDER BY last_seen DESC LIMIT 10").fetchall()
            txt = "\n".join([f"{r['user_id']} | {r['first_name']} | {('@'+r['username']) if r['username'] else '-'} | {r['lang']} | {r['base_currency']} | VIP:{r['premium']} | req:{r['requests']}" for r in rows]) or "No users."
            await q.edit_message_text(txt, reply_markup=admin_keyboard(uid))
        elif action == "tickets":
            rows = recent_tickets(10)
            txt = "\n".join([f"#{r['id']} | {r['kind']} | u{r['user_id']} | {r['status']} | {r['created_at']}" for r in rows]) or "No tickets."
            await q.edit_message_text(txt, reply_markup=admin_keyboard(uid))
        elif action == "broadcast":
            await q.edit_message_text("Use /broadcast <message>\nOr /broadcastin 10m <message>", reply_markup=admin_keyboard(uid))
        elif action == "schedule":
            await q.edit_message_text("Use /broadcastin 10m <message>\nExample: /broadcastin 2h hello", reply_markup=admin_keyboard(uid))
        elif action == "ban":
            await q.edit_message_text("Use /ban <user_id>", reply_markup=admin_keyboard(uid))
        elif action == "unban":
            await q.edit_message_text("Use /unban <user_id>", reply_markup=admin_keyboard(uid))
        elif action == "vip":
            await q.edit_message_text("Use /vip <user_id> on|off", reply_markup=admin_keyboard(uid))
        elif action == "reset":
            await q.edit_message_text("Use /reset <user_id>", reply_markup=admin_keyboard(uid))
        return


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
    tg.add_handler(CommandHandler("assets", cmd_assets))
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


# =============================================================================
# FIX OVERRIDES
# =============================================================================
OUNCE_TO_GRAM = 31.1034768
POUND_TO_GRAM = 453.59237
SUPPORTED_METALS = {
    "XAU": ("XAUUSD=X", "oz", "Gold"),
    "GOLD": ("XAUUSD=X", "oz", "Gold"),
    "XAG": ("XAGUSD=X", "oz", "Silver"),
    "SILVER": ("XAGUSD=X", "oz", "Silver"),
    "XPT": ("XPTUSD=X", "oz", "Platinum"),
    "PLATINUM": ("XPTUSD=X", "oz", "Platinum"),
    "XPD": ("XPDUSD=X", "oz", "Palladium"),
    "PALLADIUM": ("XPDUSD=X", "oz", "Palladium"),
    "COPPER": ("HG=F", "lb", "Copper"),
    "CU": ("HG=F", "lb", "Copper"),
    "OIL": ("CL=F", "bbl", "Oil"),
    "WTI": ("CL=F", "bbl", "Oil"),
}

def home_text(user_id: int) -> str:
    lang = get_lang(user_id)
    base = base_name(get_base(user_id))
    group_note = {
        "fa": "🤖 ربات داخل گروه هم کار می‌کند.",
        "en": "🤖 The bot also works inside groups.",
        "ar": "🤖 يعمل البوت داخل المجموعات أيضًا.",
        "ru": "🤖 Бот работает и в группах.",
        "tr": "🤖 Bot gruplarda da çalışır.",
        "es": "🤖 El bot también funciona en grupos.",
    }.get(lang, "🤖 The bot also works inside groups.")
    return "\n\n".join([
        tr(lang, "welcome"),
        f"💱 {tr(lang, 'choose_base')} {base}",
        group_note,
        tr(lang, "quick"),
        tr(lang, "help"),
    ])


def assets_text(lang: str) -> str:
    cryptos = ", ".join(sorted(list(CRYPTO_ALIASES.keys())))
    fiats = ", ".join(sorted(BASE_CURRENCIES))
    metals = "XAU, XAG, XPT, XPD, COPPER"
    labels = {
        "fa": "🗂 دارایی‌های پشتیبانی‌شده",
        "en": "🗂 Supported assets",
        "ar": "🗂 الأصول المدعومة",
        "ru": "🗂 Поддерживаемые активы",
        "tr": "🗂 Desteklenen varlıklar",
        "es": "🗂 Activos compatibles",
    }
    note = {
        "fa": "همچنین هر کد ۳ حرفی معتبر ارز کشورها هم قابل جستجو است.",
        "en": "Any valid 3-letter ISO currency code can also be searched.",
        "ar": "يمكن أيضًا البحث بأي رمز عملة صحيح من 3 أحرف.",
        "ru": "Также можно искать любой корректный 3-буквенный код валюты.",
        "tr": "Geçerli herhangi bir 3 harfli para birimi kodu da aranabilir.",
        "es": "También se puede buscar cualquier código de divisa válido de 3 letras.",
    }
    return "\n\n".join([
        labels.get(lang, labels["en"]),
        f"💹 Crypto:\n{cryptos}",
        f"💱 Fiat:\n{fiats}",
        f"🥇 Metals:\n{metals}",
        note.get(lang, note["en"]),
    ])


def ticket_prompt_text(lang: str, kind: str) -> str:
    prompts = {
        "support": {
            "fa": "پیام پشتیبانی‌ات را بفرست تا ناشناس برای ادمین ذخیره شود.",
            "en": "Send your support message. It will be stored anonymously.",
            "ar": "أرسل رسالة الدعم وسيتم حفظها بشكل مجهول.",
            "ru": "Отправьте сообщение в поддержку. Оно сохранится анонимно.",
            "tr": "Destek mesajını gönder. Anonim olarak kaydedilecek.",
            "es": "Envía tu mensaje de soporte. Se guardará de forma anónima.",
        },
        "ads": {
            "fa": "شرایط، متن و قیمت پیشنهادی تبلیغت را بفرست تا برای بررسی به ادمین منتقل شود.",
            "en": "Send your ad proposal, conditions, and price so it can be forwarded to the admin.",
            "ar": "أرسل عرض الإعلان والشروط والسعر المقترح ليتم تحويله إلى المدير.",
            "ru": "Отправьте предложение по рекламе, условия и цену — я передам их администратору.",
            "tr": "Reklam teklifini, şartları ve fiyatı gönder; yöneticiye iletilecek.",
            "es": "Envía tu propuesta de anuncio, condiciones y precio para enviarlo al admin.",
        },
        "feedback": {
            "fa": "نظر یا پیشنهادت را بفرست تا ناشناس برای ادمین ذخیره شود.",
            "en": "Send your feedback. It will be stored anonymously.",
            "ar": "أرسل ملاحظتك وسيتم حفظها بشكل مجهول.",
            "ru": "Отправьте отзыв. Он сохранится анонимно.",
            "tr": "Geri bildiriminizi gönderin. Anonim olarak kaydedilecek.",
            "es": "Envía tu opinión. Se guardará de forma anónima.",
        },
    }
    return prompts.get(kind, prompts["support"]).get(lang, prompts.get(kind, prompts["support"])["en"])


def resolve_phrase(text: str) -> str:
    t = normalize_text(text)
    if not t:
        return ""
    low = t.lower()
    if low in ALIASES:
        return ALIASES[low]

    tokens = [strip_token(x) for x in re.split(r"[\s,]+", t) if strip_token(x)]
    tokens = [x for x in tokens if x.lower() not in PRICE_WORDS and x not in {"+", "＋"}]
    if not tokens:
        return ""

    for tok in tokens:
        nt = norm_alias(tok)
        if "/" in nt:
            return nt
        if nt in ALIASES.values() or nt in CRYPTO_ALIASES or nt in FIAT_CODES or nt in SUPPORTED_METALS:
            return nt

    joined = " ".join(tokens).lower()
    if joined in ALIASES:
        return ALIASES[joined]

    # Substring search catches phrases like "قیمت دلار" or "buy bitcoin now"
    ordered_aliases = sorted(ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True)
    for alias, symbol in ordered_aliases:
        if alias and alias in low:
            return symbol

    m = re.search(r"\b([A-Za-z]{3,12})(?:\s*/\s*([A-Za-z]{3,12}))?\b", t)
    if m:
        a = m.group(1).upper()
        b = m.group(2).upper() if m.group(2) else None
        if b:
            return f"{a}/{b}"
        return a

    return norm_alias(tokens[-1])


def is_finance_like(text: str) -> bool:
    q = resolve_phrase(text)
    if not q:
        return False
    if "/" in q:
        a, b = q.split("/", 1)
        return bool(a and b)
    if q in CRYPTO_ALIASES or q in SUPPORTED_METALS:
        return True
    if len(q) == 3 and q.isalpha():
        return True
    return bool(re.fullmatch(r"[A-Za-z0-9.\-]{2,20}", q))


def get_fiat_rate_to_usd(code: str) -> Optional[float]:
    """Return USD value of 1 unit of `code`."""
    code = code.upper().strip()
    if code == "USD":
        return 1.0
    if code == "TMN":
        code = "IRR"

    key = f"fiat:{code}"
    cached = cached_get(key)
    if cached is not None:
        return cached

    # Prefer market-based yfinance tickers first (more current than generic fx APIs).
    for ticker in (f"{code}USD=X", f"USD{code}=X"):
        val = yfinance_last_close(ticker)
        if val:
            usd_per_unit = val if ticker.endswith("USD=X") else (1 / val if val else None)
            if usd_per_unit:
                cached_set(key, usd_per_unit)
                return usd_per_unit

    # Fallback: generic FX API (rates are units per USD, so invert).
    data = _safe_json("https://open.er-api.com/v6/latest/USD")
    if data and data.get("result") == "success":
        rates = data.get("rates", {}) or {}
        rate = rates.get(code)
        if rate:
            try:
                rate = float(rate)
                if rate != 0:
                    usd_per_unit = 1 / rate
                    cached_set(key, usd_per_unit)
                    return usd_per_unit
            except Exception:
                pass
    return None


def fiat_units_per_usd(code: str) -> Optional[float]:
    usd_per_unit = get_fiat_rate_to_usd(code)
    if usd_per_unit is None or usd_per_unit == 0:
        return None
    return 1 / usd_per_unit


def fiat_usd_per_unit(code: str) -> Optional[float]:
    return get_fiat_rate_to_usd(code)


def fiat_pair_rate(base: str, quote: str) -> Optional[float]:
    base = base.upper().strip()
    quote = quote.upper().strip()
    if base == quote:
        return 1.0
    bu = fiat_usd_per_unit(base)
    qu = fiat_usd_per_unit(quote)
    if bu and qu:
        # quote per base
        return bu / qu
    return None


def get_base_rate_to_usd(code: str) -> Optional[float]:
    code = code.upper()
    if code == "USD":
        return 1.0
    if code == "TMN":
        irr = get_fiat_rate_to_usd("IRR")
        return irr * 10.0 if irr else None
    return get_fiat_rate_to_usd(code)


def display_to_base(usd_value: float, base: str) -> Optional[float]:
    rate = get_base_rate_to_usd(base)
    if rate is None or rate == 0:
        return None
    return usd_value / rate


def resolve_asset(query: str):
    q = resolve_phrase(query)
    if not q:
        return None, None, None, None, None

    raw = q.upper().replace(" ", "").replace("-", "/")

    # Metals / commodities with their preferred price units.
    if raw in SUPPORTED_METALS:
        ticker, unit_kind, label = SUPPORTED_METALS[raw]
        # Try spot / futures / related instrument in order.
        candidates = [ticker]
        if raw in {"XAU", "GOLD"}:
            candidates += ["GC=F", "GLD"]
        elif raw in {"XAG", "SILVER"}:
            candidates += ["SI=F"]
        elif raw in {"XPT", "PLATINUM"}:
            candidates += ["PL=F"]
        elif raw in {"XPD", "PALLADIUM"}:
            candidates += ["PA=F"]
        elif raw in {"COPPER", "CU"}:
            candidates += ["HG=F"]
        elif raw in {"OIL", "WTI"}:
            candidates += ["BZ=F"]

        px = None
        used = ticker
        for cand in candidates:
            px = yfinance_last_close(cand)
            used = cand
            if px:
                break

        kind = f"metal_{unit_kind}"
        return used, px, kind, raw, "USD"

    # Fiat currencies: accept any valid 3-letter ISO code when a rate exists.
    if len(raw) == 3 and raw.isalpha():
        fx = get_fiat_rate_to_usd(raw)
        if fx is not None:
            return raw, fx, "fiat", raw, "USD"

    # Pairs.
    base, quote = parse_pair(raw)
    if quote:
        # Fiat pair if both sides look like currencies.
        if len(base) == 3 and base.isalpha() and len(quote) == 3 and quote.isalpha():
            pair = fiat_pair_rate(base, quote)
            if pair is not None:
                return f"{base}{quote}=X", pair, "pair", base, quote

        # Crypto with fiat quote: keep the crypto USD value and let display conversion handle local base.
        if base in CRYPTO_ALIASES or coin_gecko_search(base.lower()):
            px = get_crypto_price_usd(base)
            if px is not None:
                return base, px, "crypto", base, quote

        # FX via yfinance.
        cand = f"{base}{quote}=X"
        px = yfinance_last_close(cand)
        if px:
            return cand, px, "pair", base, quote
        inv = f"{quote}{base}=X"
        inv_px = yfinance_last_close(inv)
        if inv_px and inv_px != 0:
            return inv, 1 / inv_px, "pair", base, quote

        # Still allow crypto/fiat mixed input.
        if base in CRYPTO_ALIASES or coin_gecko_search(base.lower()):
            px = get_crypto_price_usd(base)
            if px is not None:
                return base, px, "crypto", base, quote

        return None, None, None, None, None

    # Crypto single.
    if raw in CRYPTO_ALIASES or coin_gecko_search(raw.lower()):
        px = get_crypto_price_usd(raw)
        if px is not None:
            return raw, px, "crypto", raw, "USD"

    # Fallback market symbols.
    for cand in [raw, f"{raw}=X", f"{raw}-USD"]:
        px = yfinance_last_close(cand)
        if px:
            return cand, px, "other", raw, "USD"

    return None, None, None, None, None


def format_price_response(query: str, lang: str, base_currency: str) -> str:
    ticker, value, kind, base, quote = resolve_asset(query)
    symbol = human_symbol(query)
    if value is None:
        return tr(lang, "price_not_found", symbol=symbol)

    lines = [f"*{symbol}*"]

    def local_line(usd_amount: float, unit_suffix: str = "") -> Optional[str]:
        disp = display_to_base(usd_amount, base_currency)
        if disp is None:
            return None
        return f"{base_name(base_currency)}: {format_money(disp, base_currency)}{unit_suffix}"

    if kind == "crypto":
        lines.append(f"USD: {format_usd(value)}")
        ll = local_line(value)
        if ll:
            lines.append(ll)

    elif kind == "fiat":
        # `value` is USD per 1 unit of currency.
        if quote == "USD" and base:
            lines.append(f"1 {base} = {format_usd(value)}")
        else:
            lines.append(f"USD: {format_usd(value)}")
        ll = local_line(value)
        if ll:
            lines.append(ll)

    elif kind == "pair":
        if base and quote:
            lines.append(f"1 {base} = {value:,.6f} {quote}")
            # If the pair isn't quoted in USD, also provide a local display line using the quote currency value.
            quote_usd = get_fiat_rate_to_usd(quote) if len(quote) == 3 and quote.isalpha() else None
            if quote_usd:
                usd_amount = value * quote_usd
                ll = local_line(usd_amount)
                if ll:
                    lines.append(ll)
        else:
            lines.append(f"USD: {format_usd(value)}")

    elif kind.startswith("metal_"):
        unit = "gram"
        if kind.endswith("oz"):
            usd_per_gram = value / OUNCE_TO_GRAM
            label = "per gram"
        elif kind.endswith("lb"):
            usd_per_gram = value / POUND_TO_GRAM
            label = "per gram"
        else:
            usd_per_gram = value
            label = "per gram"
        lines.append(f"USD/{unit}: {usd_per_gram:,.6f}")
        ll = local_line(usd_per_gram)
        if ll:
            lines.append(f"{ll} / {unit}")
        lines.append(f"Unit: {label}")

    else:
        lines.append(f"USD: {format_usd(value)}")
        ll = local_line(value)
        if ll:
            lines.append(ll)

    return "\n".join(lines)


def chart_symbol_for(query: str) -> Optional[str]:
    q = resolve_phrase(query)
    if not q:
        return None
    raw = q.upper().replace(" ", "").replace("-", "/")

    if raw in SUPPORTED_METALS:
        return SUPPORTED_METALS[raw][0]
    if raw in CRYPTO_ALIASES:
        return f"{raw}-USD"
    if len(raw) == 3 and raw.isalpha() and get_fiat_rate_to_usd(raw) is not None:
        if raw == "USD":
            return None
        return f"{raw}USD=X"
    if "/" in raw:
        a, b = raw.split("/", 1)
        return f"{a}{b}=X"
    found = coin_gecko_search(raw.lower())
    if found and found.get("symbol"):
        return f"{found['symbol'].upper()}-USD"
    return f"{raw}-USD"


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
        await update.effective_message.reply_text(tr(lang, "unknown"), reply_markup=main_keyboard(user_id))
        return
    text = format_price_response(q, lang, base)
    # Keep chart controls ONLY with the chart/photo, not under the price text.
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    chart = await asyncio.to_thread(make_chart, q, chart_type, timeframe)
    if chart:
        await update.effective_message.reply_photo(
            photo=chart,
            caption=tr(lang, "chart_default", symbol=human_symbol(q)),
            reply_markup=chart_keyboard(human_symbol(q), user_id),
        )
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
        await update.effective_message.reply_text(tr(lang, "unknown"), reply_markup=main_keyboard(user_id))
        return
    chart = await asyncio.to_thread(make_chart, q, chart_type, timeframe)
    if not chart:
        await update.effective_message.reply_text(tr(lang, "chart_not_found", symbol=human_symbol(q)))
        return
    await update.effective_message.reply_photo(
        photo=chart,
        caption=f"{human_symbol(q)} | {chart_type.upper()} | {timeframe}",
        reply_markup=chart_keyboard(human_symbol(q), user_id),
    )
    maybe_show_ad(update.effective_chat.id, lang, context, req_count)


async def _show_main_menu(q, uid: int):
    lang = get_lang(uid)
    text = home_text(uid)
    markup = main_keyboard(uid)
    try:
        await q.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        return
    except Exception:
        pass
    try:
        await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    except Exception:
        pass


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query or not update.effective_user or not update.effective_message:
        return
    q = update.callback_query
    uid = update.effective_user.id
    lang = get_lang(uid)
    await q.answer()
    data = q.data or ""

    if data == "menu:back":
        await _show_main_menu(q, uid)
        return
    if data == "menu:help":
        await q.edit_message_text(f"{tr(lang, 'help')}\n\n{tr(lang, 'quick')}", parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:prices":
        await q.edit_message_text(f"{tr(lang, 'help')}\n\n{tr(lang, 'quick')}", parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:charts":
        await q.edit_message_text(f"{tr(lang, 'choose_chart')}\n\n{tr(lang, 'quick')}", reply_markup=chart_keyboard("BTC", uid))
        return
    if data == "menu:lang":
        await q.edit_message_text(tr(lang, "choose_lang"), reply_markup=language_keyboard(uid))
        return
    if data == "menu:base":
        await q.edit_message_text(tr(lang, "choose_base"), reply_markup=base_keyboard(uid))
        return
    if data == "menu:support":
        context.user_data["pending_ticket_kind"] = "support"
        await q.edit_message_text(ticket_prompt_text(lang, "support"), reply_markup=support_keyboard(uid))
        return
    if data == "menu:ads":
        context.user_data["pending_ticket_kind"] = "ads"
        await q.edit_message_text(ticket_prompt_text(lang, "ads"), reply_markup=support_keyboard(uid))
        return
    if data == "menu:feedback":
        context.user_data["pending_ticket_kind"] = "feedback"
        await q.edit_message_text(ticket_prompt_text(lang, "feedback"), reply_markup=support_keyboard(uid))
        return
    if data == "menu:assets":
        await q.edit_message_text(assets_text(lang), reply_markup=main_keyboard(uid))
        return
    if data == "menu:ref":
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        await q.edit_message_text(tr(lang, "ref_link", link=link), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:admin":
        if not admin_only(uid):
            await q.edit_message_text(tr(lang, "admin_only"))
            return
        await q.edit_message_text(tr(lang, "panel"), reply_markup=admin_keyboard(uid))
        return
    if data.startswith("lang:"):
        new_lang = data.split(":", 1)[1]
        if new_lang in LANGS:
            set_user_lang(uid, new_lang)
            await _show_main_menu(q, uid)
        return
    if data.startswith("base:"):
        base = data.split(":", 1)[1]
        if base in BASE_CURRENCIES:
            set_user_base(uid, base)
            await _show_main_menu(q, uid)
        return
    if data.startswith("charttype:") or data.startswith("charttf:") or data.startswith("chartpreset:"):
        parts = data.split(":")
        if parts[0] == "charttype" and len(parts) >= 3:
            chart_type, symbol = parts[1], ":".join(parts[2:])
            await send_chart_only(update, context, symbol, chart_type, "7d")
            return
        if parts[0] == "charttf" and len(parts) >= 3:
            timeframe, symbol = parts[1], ":".join(parts[2:])
            await send_chart_only(update, context, symbol, "line", timeframe)
            return
        if parts[0] == "chartpreset" and len(parts) >= 4:
            chart_type, timeframe, symbol = parts[1], parts[2], ":".join(parts[3:])
            await send_chart_only(update, context, symbol, chart_type, timeframe)
            return
    if data.startswith("admin:"):
        if not admin_only(uid):
            await q.edit_message_text(tr(lang, "admin_only"))
            return
        action = data.split(":", 1)[1]
        if action == "stats":
            await q.edit_message_text(tr(lang, "stats", **stats()), reply_markup=admin_keyboard(uid))
        elif action == "users":
            with db() as conn:
                rows = conn.execute("SELECT user_id, first_name, username, lang, base_currency, premium, requests FROM users ORDER BY last_seen DESC LIMIT 10").fetchall()
            txt = "\n".join([f"{r['user_id']} | {r['first_name']} | {('@'+r['username']) if r['username'] else '-'} | {r['lang']} | {r['base_currency']} | VIP:{r['premium']} | req:{r['requests']}" for r in rows]) or "No users."
            await q.edit_message_text(txt, reply_markup=admin_keyboard(uid))
        elif action == "tickets":
            rows = recent_tickets(10)
            txt = "\n".join([f"#{r['id']} | {r['kind']} | u{r['user_id']} | {r['status']} | {r['created_at']}" for r in rows]) or "No tickets."
            await q.edit_message_text(txt, reply_markup=admin_keyboard(uid))
        elif action == "broadcast":
            await q.edit_message_text("Use /broadcast <message>\nOr /broadcastin 10m <message>", reply_markup=admin_keyboard(uid))
        elif action == "schedule":
            await q.edit_message_text("Use /broadcastin 10m <message>\nExample: /broadcastin 2h hello", reply_markup=admin_keyboard(uid))
        elif action == "ban":
            await q.edit_message_text("Use /ban <user_id>", reply_markup=admin_keyboard(uid))
        elif action == "unban":
            await q.edit_message_text("Use /unban <user_id>", reply_markup=admin_keyboard(uid))
        elif action == "vip":
            await q.edit_message_text("Use /vip <user_id> on|off", reply_markup=admin_keyboard(uid))
        elif action == "reset":
            await q.edit_message_text("Use /reset <user_id>", reply_markup=admin_keyboard(uid))
        return

if __name__ == "__main__":
    main()
