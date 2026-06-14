
import asyncio
import logging
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf
from flask import Flask, jsonify
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from waitress import serve

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "rately.db"

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "RateLyBot").strip().lstrip("@")
BOT_NAME = os.getenv("BOT_NAME", "RateLy").strip()

ADS_TEXT = os.getenv("ADS_TEXT", "").strip()
ADS_EVERY = int(os.getenv("ADS_EVERY", "0") or "0")

ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
DEFAULT_LANG = os.getenv("DEFAULT_LANG", "en").strip().lower()
PORT = int(os.getenv("PORT", "10000"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("RateLy")

app = Flask(__name__)

# ---------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------
LANGS = {
    "en": "English",
    "fa": "فارسی",
    "ar": "العربية",
    "ru": "Русский",
    "tr": "Türkçe",
    "es": "Español",
}

T = {
    "en": {
        "welcome": "Welcome to *RateLy* ✨\nYour instant market assistant for crypto, currencies, metals, and charts.",
        "choose_lang": "Choose your language:",
        "lang_set": "Language updated to {lang}.",
        "help": "Send a symbol like `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, or `USD/IRR`.",
        "shortcut": "Examples: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`.",
        "price_query": "Send a symbol or pair, for example `BTC`, `USD`, `XAU`, or `EUR/USD`.",
        "chart_query": "Use `/chart BTC 7d`, `/chart EURUSD 1y`, or `/chart XAU 30d`.",
        "support_intro": "Use `/support your message` to send a support ticket.",
        "unknown": "I could not understand that request.",
        "banned": "Your access is blocked.",
        "no_admin": "Admin only.",
        "price_not_found": "No data found for {symbol}.",
        "chart_not_found": "No chart data found for {symbol}.",
        "ticket_saved": "Support ticket #{tid} sent to admin.",
        "reply_sent": "Reply sent to ticket #{tid}.",
        "broadcast_done": "Broadcast finished.\nSent: {sent}\nFailed: {failed}",
        "ban_done": "User {uid} banned.",
        "unban_done": "User {uid} unbanned.",
        "reset_done": "User {uid} reset.",
        "panel": "Admin panel",
        "stats": "Users: {users}\nRequests: {requests}\nBanned: {banned}\nReferrals: {refs}\nTickets: {tickets}",
        "ad_label": "Sponsored",
        "ref_intro": "Your referral link:\n`{link}`",
        "ref_self": "Referral link ready.",
    },
    "fa": {
        "welcome": "به *RateLy* خوش آمدی ✨\nدستیار لحظه‌ای قیمت ارز، طلا، رمزارز و نمودار.",
        "choose_lang": "زبان را انتخاب کن:",
        "lang_set": "زبان به {lang} تغییر کرد.",
        "help": "یک نماد مثل `BTC`، `ETH`، `XAU`، `USD`، `EUR/USD` یا `USD/IRR` بفرست.",
        "shortcut": "نمونه‌ها: `BTC`، `ETH`، `XAU`، `USD`، `EUR/USD`، `GBP/USD`، `USD/IRR`.",
        "price_query": "یک نماد یا جفت‌ارز بفرست، مثلا `BTC`، `USD`، `XAU` یا `EUR/USD`.",
        "chart_query": "مثال: `/chart BTC 7d`، `/chart EURUSD 1y`، `/chart XAU 30d`.",
        "support_intro": "برای پشتیبانی بنویس: `/support پیام شما`",
        "unknown": "این درخواست را متوجه نشدم.",
        "banned": "دسترسی شما مسدود شده است.",
        "no_admin": "فقط برای ادمین.",
        "price_not_found": "برای {symbol} داده‌ای پیدا نشد.",
        "chart_not_found": "برای {symbol} داده نموداری پیدا نشد.",
        "ticket_saved": "تیکت پشتیبانی #{tid} برای ادمین ارسال شد.",
        "reply_sent": "پاسخ برای تیکت #{tid} ارسال شد.",
        "broadcast_done": "ارسال همگانی تمام شد.\nارسال شد: {sent}\nناموفق: {failed}",
        "ban_done": "کاربر {uid} بن شد.",
        "unban_done": "کاربر {uid} آنبن شد.",
        "reset_done": "اطلاعات کاربر {uid} ریست شد.",
        "panel": "پنل ادمین",
        "stats": "کاربران: {users}\nدرخواست‌ها: {requests}\nبن‌شده‌ها: {banned}\nمعرفی‌ها: {refs}\nتیکت‌ها: {tickets}",
        "ad_label": "تبلیغ",
        "ref_intro": "لینک معرفی تو:\n`{link}`",
        "ref_self": "لینک معرفی آماده شد.",
    },
    "ar": {
        "welcome": "مرحبًا بك في *RateLy* ✨\nمساعد فوري لأسعار العملات والذهب والعملات الرقمية والرسوم البيانية.",
        "choose_lang": "اختر لغتك:",
        "lang_set": "تم تغيير اللغة إلى {lang}.",
        "help": "أرسل رمزًا مثل `BTC` أو `ETH` أو `XAU` أو `USD` أو `EUR/USD` أو `USD/IRR`.",
        "shortcut": "أمثلة: `BTC`، `ETH`، `XAU`، `USD`، `EUR/USD`، `GBP/USD`، `USD/IRR`.",
        "price_query": "أرسل رمزًا أو زوجًا مثل `BTC` أو `USD` أو `XAU` أو `EUR/USD`.",
        "chart_query": "مثال: `/chart BTC 7d` أو `/chart EURUSD 1y` أو `/chart XAU 30d`.",
        "support_intro": "استخدم `/support رسالتك` لإرسال طلب دعم.",
        "unknown": "لم أفهم هذا الطلب.",
        "banned": "تم حظر وصولك.",
        "no_admin": "للمدير فقط.",
        "price_not_found": "لا توجد بيانات لـ {symbol}.",
        "chart_not_found": "لا توجد بيانات رسم لـ {symbol}.",
        "ticket_saved": "تم إرسال تذكرة الدعم #{tid} إلى المدير.",
        "reply_sent": "تم إرسال الرد للتذكرة #{tid}.",
        "broadcast_done": "انتهى الإرسال الجماعي.\nتم الإرسال: {sent}\nفشل: {failed}",
        "ban_done": "تم حظر المستخدم {uid}.",
        "unban_done": "تم إلغاء حظر المستخدم {uid}.",
        "reset_done": "تمت إعادة تعيين المستخدم {uid}.",
        "panel": "لوحة المدير",
        "stats": "المستخدمون: {users}\nالطلبات: {requests}\nالمحظورون: {banned}\nالإحالات: {refs}\nالتذاكر: {tickets}",
        "ad_label": "إعلان",
        "ref_intro": "رابط الإحالة الخاص بك:\n`{link}`",
        "ref_self": "تم تجهيز رابط الإحالة.",
    },
    "ru": {
        "welcome": "Добро пожаловать в *RateLy* ✨\nМгновенный помощник по валютам, золоту, криптовалютам и графикам.",
        "choose_lang": "Выберите язык:",
        "lang_set": "Язык изменён на {lang}.",
        "help": "Отправьте код вроде `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD` или `USD/IRR`.",
        "shortcut": "Примеры: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`.",
        "price_query": "Отправьте символ или пару, например `BTC`, `USD`, `XAU` или `EUR/USD`.",
        "chart_query": "Пример: `/chart BTC 7d`, `/chart EURUSD 1y`, `/chart XAU 30d`.",
        "support_intro": "Используйте `/support ваше сообщение` для обращения в поддержку.",
        "unknown": "Я не понял этот запрос.",
        "banned": "Доступ заблокирован.",
        "no_admin": "Только для администратора.",
        "price_not_found": "Нет данных для {symbol}.",
        "chart_not_found": "Нет данных графика для {symbol}.",
        "ticket_saved": "Тикет поддержки #{tid} отправлен администратору.",
        "reply_sent": "Ответ отправлен в тикет #{tid}.",
        "broadcast_done": "Массовая рассылка завершена.\nОтправлено: {sent}\nОшибок: {failed}",
        "ban_done": "Пользователь {uid} заблокирован.",
        "unban_done": "Пользователь {uid} разблокирован.",
        "reset_done": "Пользователь {uid} сброшен.",
        "panel": "Панель администратора",
        "stats": "Пользователи: {users}\nЗапросы: {requests}\nЗаблокированы: {banned}\nРефералы: {refs}\nТикеты: {tickets}",
        "ad_label": "Реклама",
        "ref_intro": "Ваша реферальная ссылка:\n`{link}`",
        "ref_self": "Реферальная ссылка готова.",
    },
    "tr": {
        "welcome": "*RateLy*'ye hoş geldin ✨\nDöviz, altın, kripto ve grafikler için anlık asistan.",
        "choose_lang": "Dil seç:",
        "lang_set": "Dil {lang} olarak değiştirildi.",
        "help": "`BTC`, `ETH`, `XAU`, `USD`, `EUR/USD` veya `USD/IRR` gibi bir kod gönder.",
        "shortcut": "Örnekler: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`.",
        "price_query": "`BTC`, `USD`, `XAU` veya `EUR/USD` gibi bir sembol ya da parite gönder.",
        "chart_query": "Örnek: `/chart BTC 7d`, `/chart EURUSD 1y`, `/chart XAU 30d`.",
        "support_intro": "Destek için `/support mesajın` yaz.",
        "unknown": "Bu isteği anlayamadım.",
        "banned": "Erişimin engellendi.",
        "no_admin": "Sadece yönetici.",
        "price_not_found": "{symbol} için veri bulunamadı.",
        "chart_not_found": "{symbol} için grafik verisi bulunamadı.",
        "ticket_saved": "Destek talebi #{tid} yöneticiye gönderildi.",
        "reply_sent": "#{tid} numaralı talebe cevap gönderildi.",
        "broadcast_done": "Toplu gönderim tamamlandı.\nGönderilen: {sent}\nHata: {failed}",
        "ban_done": "{uid} numaralı kullanıcı engellendi.",
        "unban_done": "{uid} numaralı kullanıcının engeli kaldırıldı.",
        "reset_done": "{uid} numaralı kullanıcı sıfırlandı.",
        "panel": "Yönetici paneli",
        "stats": "Kullanıcılar: {users}\nİstekler: {requests}\nEngellenenler: {banned}\nReferanslar: {refs}\nTalepler: {tickets}",
        "ad_label": "Sponsorlu",
        "ref_intro": "Referans bağlantın:\n`{link}`",
        "ref_self": "Yönlendirme bağlantın hazır.",
    },
    "es": {
        "welcome": "Bienvenido a *RateLy* ✨\nAsistente instantáneo de divisas, oro, criptomonedas y gráficos.",
        "choose_lang": "Elige tu idioma:",
        "lang_set": "Idioma cambiado a {lang}.",
        "help": "Envía un código como `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD` o `USD/IRR`.",
        "shortcut": "Ejemplos: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`.",
        "price_query": "Envía un símbolo o par como `BTC`, `USD`, `XAU` o `EUR/USD`.",
        "chart_query": "Ejemplo: `/chart BTC 7d`, `/chart EURUSD 1y`, `/chart XAU 30d`.",
        "support_intro": "Usa `/support tu mensaje` para enviar soporte.",
        "unknown": "No entendí esa solicitud.",
        "banned": "Tu acceso está bloqueado.",
        "no_admin": "Solo administrador.",
        "price_not_found": "No hay datos para {symbol}.",
        "chart_not_found": "No hay datos de gráfico para {symbol}.",
        "ticket_saved": "Ticket de soporte #{tid} enviado al admin.",
        "reply_sent": "Respuesta enviada al ticket #{tid}.",
        "broadcast_done": "Difusión completada.\nEnviados: {sent}\nFallos: {failed}",
        "ban_done": "Usuario {uid} bloqueado.",
        "unban_done": "Usuario {uid} desbloqueado.",
        "reset_done": "Usuario {uid} reiniciado.",
        "panel": "Panel de admin",
        "stats": "Usuarios: {users}\nSolicitudes: {requests}\nBloqueados: {banned}\nReferidos: {refs}\nTickets: {tickets}",
        "ad_label": "Patrocinado",
        "ref_intro": "Tu enlace de referidos:\n`{link}`",
        "ref_self": "Enlace de referidos listo.",
    },
}

SUPPORTED_TF = {
    "1d": ("1d", "5m"),
    "7d": ("7d", "30m"),
    "30d": ("1mo", "1d"),
    "1y": ("1y", "1d"),
}

# ---------------------------------------------------------------------
# Market mappings
# ---------------------------------------------------------------------
CRYPTO_MAP = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "BNB": "BNB-USD",
    "XRP": "XRP-USD",
    "SOL": "SOL-USD",
    "DOGE": "DOGE-USD",
    "ADA": "ADA-USD",
    "TON": "TON-USD",
    "LTC": "LTC-USD",
    "TRX": "TRX-USD",
    "AVAX": "AVAX-USD",
    "DOT": "DOT-USD",
    "LINK": "LINK-USD",
    "MATIC": "MATIC-USD",
    "SHIB": "SHIB-USD",
    "PEPE": "PEPE-USD",
    "USDT": "USDT-USD",
}

PRECIOUS_MAP = {
    "XAU": "XAUUSD=X",
    "GOLD": "XAUUSD=X",
    "XAG": "XAGUSD=X",
    "SILVER": "XAGUSD=X",
}

FIAT_CODES = {
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNY", "HKD",
    "SGD", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "RON", "TRY", "SAR",
    "AED", "QAR", "KWD", "BHD", "INR", "PKR", "RUB", "UAH", "ZAR", "MXN",
    "BRL", "IDR", "MYR", "THB", "PHP", "KRW", "TWD", "ILS", "EGP", "IRR",
    "KZT", "NGN", "VND", "CLP", "COP", "ARS",
}

ALIASES = {
    "دلار": "USD",
    "یورو": "EUR",
    "پوند": "GBP",
    "ین": "JPY",
    "فرانک": "CHF",
    "دینار": "IQD",
    "تومان": "IRR",
    "ریال": "IRR",
    "تتر": "USDT",
    "بیتکوین": "BTC",
    "بیت‌کوین": "BTC",
    "بیت کوین": "BTC",
    "اتریوم": "ETH",
    "طلا": "XAU",
    "سکه": "XAU",
    "نقره": "XAG",
    "gold": "XAU",
    "silver": "XAG",
    "bitcoin": "BTC",
    "btc": "BTC",
    "ethereum": "ETH",
    "eth": "ETH",
    "usdt": "USDT",
    "usd": "USD",
    "eur": "EUR",
    "gbp": "GBP",
    "jpy": "JPY",
    "xau": "XAU",
    "xag": "XAG",
}

PRICE_WORDS = {
    "price", "pr", "rate", "value", "quote", "chart", "graph",
    "قیمت", "نرخ", "ارزش", "رسم", "نمودار", "سعر", "precio", "preço",
    "kurs", "geld", "цена", "график", "fiyat", "değer",
}

# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    with db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            lang TEXT DEFAULT 'en',
            first_seen TEXT,
            last_seen TEXT,
            requests INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            referrer INTEGER,
            referrals INTEGER DEFAULT 0
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question TEXT,
            status TEXT DEFAULT 'open',
            answer TEXT,
            created_at TEXT,
            answered_at TEXT
        )
        """)
        conn.commit()

def get_lang(user_id: int) -> str:
    with db() as conn:
        row = conn.execute("SELECT lang FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row and row["lang"] in LANGS:
            return row["lang"]
    return DEFAULT_LANG if DEFAULT_LANG in LANGS else "en"

def tr(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in T else "en"
    text = T[lang].get(key, T["en"].get(key, key))
    return text.format(**kwargs)

def upsert_user(user) -> None:
    with db() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name, lang, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_seen=excluded.last_seen
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            get_lang(user.id),
            now_iso(),
            now_iso(),
        ))
        conn.commit()

def set_user_lang(user_id: int, lang: str) -> None:
    if lang not in LANGS:
        return
    with db() as conn:
        conn.execute("UPDATE users SET lang=?, last_seen=? WHERE user_id=?", (lang, now_iso(), user_id))
        conn.commit()

def is_banned(user_id: int) -> bool:
    with db() as conn:
        row = conn.execute("SELECT banned FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["banned"])

def inc_request(user_id: int) -> int:
    with db() as conn:
        conn.execute(
            "UPDATE users SET requests = COALESCE(requests,0)+1, last_seen=? WHERE user_id=?",
            (now_iso(), user_id),
        )
        val = conn.execute("SELECT requests FROM users WHERE user_id=?", (user_id,)).fetchone()["requests"]
        conn.commit()
        return int(val)

def count_stats():
    with db() as conn:
        users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        requests = conn.execute("SELECT COALESCE(SUM(requests),0) AS s FROM users").fetchone()["s"]
        banned = conn.execute("SELECT COUNT(*) AS c FROM users WHERE banned=1").fetchone()["c"]
        refs = conn.execute("SELECT COUNT(*) AS c FROM users WHERE referrer IS NOT NULL").fetchone()["c"]
        tickets = conn.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()["c"]
        return users, requests, banned, refs, tickets

def admin_only(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ---------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------
def language_keyboard():
    rows = []
    row = []
    for code, label in LANGS.items():
        row.append(InlineKeyboardButton(label, callback_data=f"lang:{code}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)

# ---------------------------------------------------------------------
# Normalization and parsing
# ---------------------------------------------------------------------
def normalize_text(text: str) -> str:
    text = text.replace("‌", " ")
    text = text.replace("＋", "+")
    text = re.sub(r"@[\w_]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def clean_token(token: str) -> str:
    token = token.strip().strip("`'\".,;:!?()[]{}<>")
    token = token.replace("‌", "")
    return token

def normalize_query_token(token: str) -> str:
    token = clean_token(token)
    lowered = token.lower()
    if lowered in ALIASES:
        return ALIASES[lowered]
    return token.upper()

def resolve_alias_phrase(text: str) -> str:
    raw = normalize_text(text)
    lowered = raw.lower()

    # Exact alias hit first
    if lowered in ALIASES:
        return ALIASES[lowered]

    # Remove helper words
    tokens = [clean_token(t) for t in re.split(r"[\s,]+", raw) if clean_token(t)]
    filtered = [t for t in tokens if t.lower() not in PRICE_WORDS and t != "+"]
    if not filtered:
        return ""

    # Look for pair
    for tok in filtered:
        up = normalize_query_token(tok)
        if "/" in up:
            return up

    # Prefer last meaningful token for phrases like "قیمت دلار"
    for tok in reversed(filtered):
        up = normalize_query_token(tok)
        if up in ALIASES.values() or up in CRYPTO_MAP or up in PRECIOUS_MAP or up in FIAT_CODES:
            return up

    # Try joined phrase alias (e.g. "بیت کوین")
    joined = " ".join(t.lower() for t in filtered)
    if joined in ALIASES:
        return ALIASES[joined]

    # Fallback to single token or pair-like token
    first = normalize_query_token(filtered[-1])
    return first

def is_finance_like(text: str) -> bool:
    q = resolve_alias_phrase(text)
    if not q:
        return False
    if "/" in q:
        a, b = q.split("/", 1)
        return bool(a) and bool(b)
    return q in FIAT_CODES or q in CRYPTO_MAP or q in PRECIOUS_MAP or q in {"USD", "USDT", "XAU", "XAG"} or bool(re.fullmatch(r"[A-Z0-9]{2,12}", q))

def parse_pair(query: str) -> Tuple[str, Optional[str]]:
    q = query.strip().upper().replace(" ", "")
    q = q.replace("-", "/")
    if "/" in q:
        base, quote = q.split("/", 1)
        return base, quote
    return q, None

# ---------------------------------------------------------------------
# Market lookup
# ---------------------------------------------------------------------
def history_df(ticker: str, period: str = "1d", interval: str = "1d") -> pd.DataFrame:
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
        if df is not None and not df.empty:
            return df
    except Exception as exc:
        log.warning("history failed %s: %s", ticker, exc)
    return pd.DataFrame()

def last_close(ticker: str) -> Optional[float]:
    df = history_df(ticker, period="1d", interval="1m")
    if not df.empty and "Close" in df:
        series = df["Close"].dropna()
        if not series.empty:
            return float(series.iloc[-1])
    try:
        info = yf.Ticker(ticker).fast_info
        if info and "lastPrice" in info and info["lastPrice"]:
            return float(info["lastPrice"])
    except Exception as exc:
        log.warning("fast_info failed %s: %s", ticker, exc)
    return None

def resolve_market(query: str) -> Tuple[Optional[str], Optional[float], Optional[str], Optional[str], Optional[str]]:
    """
    Returns:
      ticker, price, kind, base, quote
    kind in: fx, crypto, metal, cash
    """
    q = resolve_alias_phrase(query)
    if not q:
        return None, None, None, None, None

    q = q.upper().replace(" ", "")
    q = q.replace("-", "/")
    q = q.replace("PRICE", "").replace("RATE", "")
    q = q.strip()

    # exact known aliases
    if q in CRYPTO_MAP:
        ticker = CRYPTO_MAP[q]
        return ticker, last_close(ticker), "crypto", q, "USD"
    if q in PRECIOUS_MAP:
        ticker = PRECIOUS_MAP[q]
        return ticker, last_close(ticker), "metal", q, "USD"

    if q in FIAT_CODES:
        if q == "USD":
            return "USD", 1.0, "cash", "USD", "USD"
        ticker = f"{q}USD=X"
        price = last_close(ticker)
        if price is None:
            inv = last_close(f"USD{q}=X")
            if inv:
                return f"USD{q}=X", 1 / inv, "fx", q, "USD"
        return ticker, price, "fx", q, "USD"

    base, quote = parse_pair(q)
    if quote:
        # direct
        ticker = f"{base}{quote}=X"
        price = last_close(ticker)
        if price is not None:
            return ticker, price, "fx", base, quote

        # inverse
        inv_ticker = f"{quote}{base}=X"
        inv = last_close(inv_ticker)
        if inv is not None and inv != 0:
            return inv_ticker, 1 / inv, "fx", base, quote

        # pair with crypto/metal or stablecoin
        if base in CRYPTO_MAP:
            ticker = CRYPTO_MAP[base]
            price = last_close(ticker)
            return ticker, price, "crypto", base, quote
        if base in PRECIOUS_MAP:
            ticker = PRECIOUS_MAP[base]
            price = last_close(ticker)
            return ticker, price, "metal", base, quote

        return None, None, None, None, None

    # token alone
    if base in CRYPTO_MAP:
        ticker = CRYPTO_MAP[base]
        return ticker, last_close(ticker), "crypto", base, "USD"
    if base in PRECIOUS_MAP:
        ticker = PRECIOUS_MAP[base]
        return ticker, last_close(ticker), "metal", base, "USD"

    return None, None, None, None, None

def pretty_price(price: float, kind: str, base: str, quote: str) -> str:
    if kind == "crypto":
        return f"${price:,.6f}" if price < 1 else f"${price:,.4f}"
    if kind == "metal":
        return f"${price:,.2f}"
    if kind == "cash":
        return "1.000000"
    # fx
    if price >= 1000:
        return f"{price:,.2f}"
    return f"{price:,.6f}"

def format_price_message(query: str, lang: str) -> str:
    ticker, price, kind, base, quote = resolve_market(query)
    q = resolve_alias_phrase(query) or query
    q = q.upper().replace(" ", "")

    if price is None:
        return tr(lang, "price_not_found", symbol=q)

    if kind == "cash":
        return f"*USD*\n1 USD = 1 USD"

    if kind == "crypto":
        return f"*{base}*\nPrice: {pretty_price(price, kind, base, quote)}"

    if kind == "metal":
        label = "Gold" if base == "XAU" else ("Silver" if base == "XAG" else base)
        return f"*{label} ({base})*\nPrice: {pretty_price(price, kind, base, quote)} per ounce"

    # fx / fiat
    if base and quote:
        if quote == "USD":
            return f"*{base}/USD*\n1 {base} = {price:,.6f} USD"
        if base == "USD":
            return f"*USD/{quote}*\n1 USD = {price:,.6f} {quote}"
        return f"*{base}/{quote}*\n1 {base} = {price:,.6f} {quote}"

    return f"*{q}*\nPrice: {pretty_price(price, kind, base or q, quote or 'USD')}"

def chart_ticker_for(query: str) -> Optional[str]:
    ticker, price, kind, base, quote = resolve_market(query)
    if ticker:
        # For FX and metals, ticker is already best chart source
        return ticker
    q = resolve_alias_phrase(query)
    if not q:
        return None
    q = q.upper().replace(" ", "")
    if q in CRYPTO_MAP:
        return CRYPTO_MAP[q]
    if q in PRECIOUS_MAP:
        return PRECIOUS_MAP[q]
    if q in FIAT_CODES:
        return f"{q}USD=X"
    base, quote = parse_pair(q)
    if quote:
        return f"{base}{quote}=X"
    return None

def make_chart(query: str, timeframe: str = "7d") -> Optional[BytesIO]:
    if timeframe not in SUPPORTED_TF:
        timeframe = "7d"
    ticker = chart_ticker_for(query)
    if not ticker:
        return None

    period, interval = SUPPORTED_TF[timeframe]
    df = history_df(ticker, period=period, interval=interval)
    if df.empty or "Close" not in df:
        return None

    df = df.dropna(subset=["Close"]).copy()
    if df.empty:
        return None

    plt.figure(figsize=(11, 5))
    plt.plot(df.index, df["Close"])
    title = resolve_alias_phrase(query) or query
    plt.title(f"{title.upper()} | {timeframe}")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format="png", dpi=160)
    plt.close()
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------------------
# Ads
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# Sending helpers
# ---------------------------------------------------------------------
async def send_price_and_chart(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    if not update.effective_user or not update.effective_chat or not update.effective_message:
        return

    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.effective_message.reply_text(tr(get_lang(user_id), "banned"))
        return

    lang = get_lang(user_id)
    req_count = inc_request(user_id)

    query = resolve_alias_phrase(query)
    if not query:
        await update.effective_message.reply_text(tr(lang, "unknown"))
        return

    price_text = format_price_message(query, lang)
    await update.effective_message.reply_text(price_text, parse_mode=ParseMode.MARKDOWN)

    chart = await asyncio.to_thread(make_chart, query, "7d")
    if chart:
        caption = f"{(resolve_alias_phrase(query) or query).upper()} | 7d"
        try:
            await update.effective_message.reply_photo(photo=chart, caption=caption)
        except Exception as exc:
            log.warning("chart send failed: %s", exc)
    else:
        # keep chat clean; don't spam with an error if price exists
        pass

    maybe_show_ad(update.effective_chat.id, lang, context, req_count)

async def send_chart(update: Update, context: ContextTypes.DEFAULT_TYPE, symbol: str, timeframe: str = "7d") -> None:
    if not update.effective_user or not update.effective_chat or not update.effective_message:
        return

    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.effective_message.reply_text(tr(get_lang(user_id), "banned"))
        return

    lang = get_lang(user_id)
    req_count = inc_request(user_id)

    symbol = resolve_alias_phrase(symbol)
    data = await asyncio.to_thread(make_chart, symbol, timeframe)
    if not data:
        await update.effective_message.reply_text(tr(lang, "chart_not_found", symbol=(symbol or "").upper()))
        return

    await update.effective_message.reply_photo(photo=data, caption=f"{symbol.upper()} | {timeframe}")
    maybe_show_ad(update.effective_chat.id, lang, context, req_count)

# ---------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return

    upsert_user(update.effective_user)
    user_id = update.effective_user.id
    lang = get_lang(user_id)

    args = context.args or []
    if args:
        code = args[0].strip()
        if code.startswith("ref_") and code[4:].isdigit():
            referrer = int(code[4:])
            if referrer != user_id:
                with db() as conn:
                    row = conn.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
                    if row:
                        conn.execute("UPDATE users SET referrer=? WHERE user_id=? AND referrer IS NULL", (referrer, user_id))
                        conn.execute("UPDATE users SET referrals = COALESCE(referrals,0)+1 WHERE user_id=?", (referrer,))
                        conn.commit()

    text = f"{tr(lang, 'welcome')}\n\n{tr(lang, 'choose_lang')}"
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=language_keyboard(),
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    lang = get_lang(update.effective_user.id)
    await update.effective_message.reply_text(
        f"{tr(lang, 'help')}\n\n{tr(lang, 'support_intro')}\n\n{tr(lang, 'chart_query')}",
        parse_mode=ParseMode.MARKDOWN,
    )

async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    user_id = update.effective_user.id
    lang = get_lang(user_id)

    if context.args:
        new_lang = context.args[0].lower()
        if new_lang in LANGS:
            set_user_lang(user_id, new_lang)
            await update.effective_message.reply_text(
                tr(new_lang, "lang_set", lang=LANGS[new_lang]),
            )
            return

    await update.effective_message.reply_text(
        tr(lang, "choose_lang"),
        reply_markup=language_keyboard(),
    )

async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    if not context.args:
        lang = get_lang(update.effective_user.id)
        await update.effective_message.reply_text(tr(lang, "price_query"))
        return
    await send_price_and_chart(update, context, " ".join(context.args))

async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    if not context.args:
        lang = get_lang(update.effective_user.id)
        await update.effective_message.reply_text(tr(lang, "chart_query"))
        return
    args = context.args
    symbol = args[0]
    tf = args[1] if len(args) > 1 else "7d"
    await send_chart(update, context, symbol, tf)

async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return

    user_id = update.effective_user.id
    lang = get_lang(user_id)

    if is_banned(user_id):
        await update.effective_message.reply_text(tr(lang, "banned"))
        return

    if not context.args:
        await update.effective_message.reply_text(tr(lang, "support_intro"))
        return

    question = " ".join(context.args).strip()
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO tickets (user_id, question, status, created_at) VALUES (?, ?, 'open', ?)",
            (user_id, question, now_iso()),
        )
        tid = cur.lastrowid
        conn.commit()

    if ADMIN_IDS:
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"🆘 Ticket #{tid}\n"
                        f"User: `{user_id}`\n"
                        f"Message:\n{question}\n\n"
                        f"Reply with: `/reply {tid} your message`"
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception as exc:
                log.warning("notify admin failed %s: %s", admin_id, exc)

    await update.effective_message.reply_text(tr(lang, "ticket_saved", tid=tid))

async def cmd_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return

    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /reply <ticket_id> <message>")
        return

    tid = int(context.args[0])
    message = " ".join(context.args[1:]).strip()

    with db() as conn:
        row = conn.execute("SELECT user_id FROM tickets WHERE id=?", (tid,)).fetchone()
        if not row:
            await update.effective_message.reply_text("Ticket not found.")
            return
        user_id = row["user_id"]
        conn.execute(
            "UPDATE tickets SET status='closed', answer=?, answered_at=? WHERE id=?",
            (message, now_iso(), tid),
        )
        conn.commit()

    try:
        await context.bot.send_message(chat_id=user_id, text=f"💬 Reply to ticket #{tid}:\n{message}")
        await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "reply_sent", tid=tid))
    except Exception as exc:
        await update.effective_message.reply_text(f"Failed: {exc}")

async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not admin_only(uid):
        await update.effective_message.reply_text(tr(lang, "no_admin"))
        return
    await update.effective_message.reply_text(tr(lang, "panel"))

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    lang = get_lang(update.effective_user.id)
    users, requests, banned, refs, tickets = count_stats()
    await update.effective_message.reply_text(
        tr(lang, "stats", users=users, requests=requests, banned=banned, refs=refs, tickets=tickets)
    )

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /ban <user_id>")
        return
    uid = int(context.args[0])
    with db() as conn:
        conn.execute("UPDATE users SET banned=1 WHERE user_id=?", (uid,))
        conn.commit()
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "ban_done", uid=uid))

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /unban <user_id>")
        return
    uid = int(context.args[0])
    with db() as conn:
        conn.execute("UPDATE users SET banned=0 WHERE user_id=?", (uid,))
        conn.commit()
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "unban_done", uid=uid))

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /reset <user_id>")
        return
    uid = int(context.args[0])
    with db() as conn:
        conn.execute("UPDATE users SET requests=0, banned=0, referrer=NULL, referrals=0 WHERE user_id=?", (uid,))
        conn.commit()
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
        user_ids = [r["user_id"] for r in conn.execute("SELECT user_id FROM users WHERE banned=0").fetchall()]
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=msg)
            sent += 1
        except Exception:
            failed += 1
    await update.effective_message.reply_text(
        tr(get_lang(update.effective_user.id), "broadcast_done", sent=sent, failed=failed)
    )

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    await update.effective_message.reply_text(str(update.effective_user.id))

# ---------------------------------------------------------------------
# Text and callbacks
# ---------------------------------------------------------------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return

    user = update.effective_user
    upsert_user(user)

    if is_banned(user.id):
        await update.effective_message.reply_text(tr(get_lang(user.id), "banned"))
        return

    text = normalize_text(update.effective_message.text or "")
    if not text or text.startswith("/"):
        return

    # remove bot mention and normalize
    cleaned = re.sub(rf"@{re.escape(BOT_USERNAME)}\b", "", text, flags=re.I).strip()
    lang = get_lang(user.id)
    chat_type = update.effective_chat.type if update.effective_chat else "private"

    # In groups, respond only to finance-like messages or the + shortcut
    if chat_type in {"group", "supergroup"}:
        if cleaned in {"+", "＋"}:
            await update.effective_message.reply_text(
                f"{tr(lang, 'shortcut')}\n\n{tr(lang, 'help')}",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        if not is_finance_like(cleaned):
            return

    query = resolve_alias_phrase(cleaned)
    if not query:
        await update.effective_message.reply_text(tr(lang, "unknown"))
        return

    await send_price_and_chart(update, context, query)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.callback_query:
        return
    q = update.callback_query
    await q.answer()

    user_id = update.effective_user.id
    data = q.data or ""
    if data.startswith("lang:"):
        new_lang = data.split(":", 1)[1]
        if new_lang in LANGS:
            set_user_lang(user_id, new_lang)
            await q.edit_message_text(tr(new_lang, "lang_set", lang=LANGS[new_lang]))
        return

async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    lang = get_lang(update.effective_user.id)
    await update.effective_message.reply_text(tr(lang, "unknown"))

# ---------------------------------------------------------------------
# Telegram application
# ---------------------------------------------------------------------
def build_app() -> Application:
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("lang", cmd_lang))
    application.add_handler(CommandHandler("price", cmd_price))
    application.add_handler(CommandHandler("chart", cmd_chart))
    application.add_handler(CommandHandler("support", cmd_support))
    application.add_handler(CommandHandler("panel", cmd_panel))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("broadcast", cmd_broadcast))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CommandHandler("unban", cmd_unban))
    application.add_handler(CommandHandler("reset", cmd_reset))
    application.add_handler(CommandHandler("reply", cmd_reply))
    application.add_handler(CommandHandler("id", cmd_id))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))
    return application

def run_bot():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    application = build_app()
    log.info("Bot starting...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        stop_signals=None,
        close_loop=False,
    )

# ---------------------------------------------------------------------
# Web server for Render
# ---------------------------------------------------------------------
@app.get("/")
def home():
    return jsonify(
        ok=True,
        name=BOT_NAME,
        bot_username=BOT_USERNAME,
        time=now_iso(),
    )

def main():
    init_db()
    threading.Thread(target=run_bot, daemon=True).start()
    log.info("Web server on port %s", PORT)
    serve(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
