
import asyncio
import logging
import os
import re
import random
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
import requests
import yfinance as yf
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from waitress import serve

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "rately.db"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "RateLyBot").strip()
BOT_NAME = os.getenv("BOT_NAME", "RateLy").strip()
ADS_TEXT = os.getenv("ADS_TEXT", "").strip()
ADS_EVERY = int(os.getenv("ADS_EVERY", "0") or "0")
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
}
DEFAULT_LANG = os.getenv("DEFAULT_LANG", "en").strip().lower()
PORT = int(os.getenv("PORT", "10000"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("RateLy")

app = Flask(__name__)

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
        "welcome": "Welcome to *RateLy* ✨\nYour multi-language market assistant for currencies, gold, and crypto.",
        "choose_lang": "Choose your language:",
        "menu": "Main menu:",
        "help": "Send a symbol like `EUR`, `USD/IRR`, `BTC`, `XAU`, or use `/price` and `/chart`.",
        "support_intro": "Send `/support` followed by your message.\nExample: `/support My chart is not loading`",
        "ref_intro": "Your referral link:\n`{link}`",
        "price_query": "Send a symbol or pair, e.g. `BTC`, `XAU`, `EUR/USD`.",
        "chart_query": "Send `/chart BTC 7d` or `/chart EURUSD 1y`.",
        "unknown": "I could not understand that request.",
        "banned": "Your access is blocked.",
        "no_admin": "Admin only.",
        "lang_set": "Language updated to {lang}.",
        "panel": "Admin panel",
        "stats": "Users: {users}\nRequests: {requests}\nBanned: {banned}\nReferrals: {refs}\nTickets: {tickets}",
        "broadcast_done": "Broadcast finished.\nSent: {sent}\nFailed: {failed}",
        "ban_done": "User {uid} banned.",
        "unban_done": "User {uid} unbanned.",
        "reset_done": "User {uid} reset.",
        "ticket_saved": "Support ticket #{tid} sent to admin.",
        "reply_sent": "Reply sent to ticket #{tid}.",
        "ad_label": "Sponsored",
        "price_not_found": "No data found for {symbol}.",
        "chart_not_found": "No chart data found for {symbol}.",
        "ref_self": "Referral link ready.",
        "shortcut": "Try `BTC`, `ETH`, `XAU`, `EUR/USD`, `GBP/USD`.",
    },
    "fa": {
        "welcome": "به *RateLy* خوش آمدی ✨\nربات چندزبانه قیمت ارز، طلا و رمزارز.",
        "choose_lang": "زبان را انتخاب کن:",
        "menu": "منوی اصلی:",
        "help": "یک نماد مثل `EUR`، `USD/IRR`، `BTC` یا `XAU` بفرست یا از `/price` و `/chart` استفاده کن.",
        "support_intro": "با `/support` پیام خودت را بفرست.\nمثال: `/support نمودار باز نمی‌شود`",
        "ref_intro": "لینک معرفی تو:\n`{link}`",
        "price_query": "یک نماد یا جفت‌ارز بفرست، مثل `BTC`، `XAU`، `EUR/USD`.",
        "chart_query": "مثال: `/chart BTC 7d` یا `/chart EURUSD 1y`.",
        "unknown": "این درخواست را متوجه نشدم.",
        "banned": "دسترسی شما مسدود شده است.",
        "no_admin": "فقط برای ادمین.",
        "lang_set": "زبان به {lang} تغییر کرد.",
        "panel": "پنل ادمین",
        "stats": "کاربران: {users}\nدرخواست‌ها: {requests}\nبن‌شده‌ها: {banned}\nمعرفی‌ها: {refs}\nتیکت‌ها: {tickets}",
        "broadcast_done": "ارسال همگانی تمام شد.\nارسال شد: {sent}\nناموفق: {failed}",
        "ban_done": "کاربر {uid} بن شد.",
        "unban_done": "کاربر {uid} آنبن شد.",
        "reset_done": "اطلاعات کاربر {uid} ریست شد.",
        "ticket_saved": "تیکت پشتیبانی #{tid} برای ادمین ارسال شد.",
        "reply_sent": "پاسخ برای تیکت #{tid} ارسال شد.",
        "ad_label": "تبلیغ",
        "price_not_found": "برای {symbol} داده‌ای پیدا نشد.",
        "chart_not_found": "برای {symbol} داده نموداری پیدا نشد.",
        "ref_self": "لینک معرفی آماده شد.",
        "shortcut": "مثال‌ها: `BTC`، `ETH`، `XAU`، `EUR/USD`، `GBP/USD`.",
    },
    "ar": {
        "welcome": "مرحبًا بك في *RateLy* ✨\nمساعد متعدد اللغات لأسعار العملات والذهب والعملات الرقمية.",
        "choose_lang": "اختر لغتك:",
        "menu": "القائمة الرئيسية:",
        "help": "أرسل رمزًا مثل `EUR` أو `USD/IRR` أو `BTC` أو `XAU` أو استخدم `/price` و `/chart`.",
        "support_intro": "أرسل `/support` ثم رسالتك.\nمثال: `/support لا يعمل الرسم البياني`",
        "ref_intro": "رابط الإحالة الخاص بك:\n`{link}`",
        "price_query": "أرسل رمزًا أو زوجًا مثل `BTC` أو `XAU` أو `EUR/USD`.",
        "chart_query": "مثال: `/chart BTC 7d` أو `/chart EURUSD 1y`.",
        "unknown": "لم أفهم هذا الطلب.",
        "banned": "تم حظر وصولك.",
        "no_admin": "للمدير فقط.",
        "lang_set": "تم تغيير اللغة إلى {lang}.",
        "panel": "لوحة المدير",
        "stats": "المستخدمون: {users}\nالطلبات: {requests}\nالمحظورون: {banned}\nالإحالات: {refs}\nالتذاكر: {tickets}",
        "broadcast_done": "انتهى الإرسال الجماعي.\nتم الإرسال: {sent}\nفشل: {failed}",
        "ban_done": "تم حظر المستخدم {uid}.",
        "unban_done": "تم إلغاء حظر المستخدم {uid}.",
        "reset_done": "تمت إعادة تعيين المستخدم {uid}.",
        "ticket_saved": "تم إرسال تذكرة الدعم #{tid} إلى المدير.",
        "reply_sent": "تم إرسال الرد للتذكرة #{tid}.",
        "ad_label": "إعلان",
        "price_not_found": "لا توجد بيانات لـ {symbol}.",
        "chart_not_found": "لا توجد بيانات رسم لـ {symbol}.",
        "ref_self": "تم تجهيز رابط الإحالة.",
        "shortcut": "أمثلة: `BTC`، `ETH`، `XAU`، `EUR/USD`، `GBP/USD`.",
    },
    "ru": {
        "welcome": "Добро пожаловать в *RateLy* ✨\nМногоязычный помощник по валютам, золоту и криптовалютам.",
        "choose_lang": "Выберите язык:",
        "menu": "Главное меню:",
        "help": "Отправьте код, например `EUR`, `USD/IRR`, `BTC`, `XAU`, или используйте `/price` и `/chart`.",
        "support_intro": "Отправьте `/support` и ваш текст.\nПример: `/support График не загружается`",
        "ref_intro": "Ваша реферальная ссылка:\n`{link}`",
        "price_query": "Отправьте символ или пару, например `BTC`, `XAU`, `EUR/USD`.",
        "chart_query": "Пример: `/chart BTC 7d` или `/chart EURUSD 1y`.",
        "unknown": "Я не понял этот запрос.",
        "banned": "Доступ заблокирован.",
        "no_admin": "Только для администратора.",
        "lang_set": "Язык изменён на {lang}.",
        "panel": "Панель администратора",
        "stats": "Пользователи: {users}\nЗапросы: {requests}\nЗаблокированы: {banned}\nРефералы: {refs}\nТикеты: {tickets}",
        "broadcast_done": "Массовая рассылка завершена.\nОтправлено: {sent}\nОшибок: {failed}",
        "ban_done": "Пользователь {uid} заблокирован.",
        "unban_done": "Пользователь {uid} разблокирован.",
        "reset_done": "Пользователь {uid} сброшен.",
        "ticket_saved": "Тикет поддержки #{tid} отправлен администратору.",
        "reply_sent": "Ответ отправлен в тикет #{tid}.",
        "ad_label": "Реклама",
        "price_not_found": "Нет данных для {symbol}.",
        "chart_not_found": "Нет данных графика для {symbol}.",
        "ref_self": "Реферальная ссылка готова.",
        "shortcut": "Примеры: `BTC`, `ETH`, `XAU`, `EUR/USD`, `GBP/USD`.",
    },
    "tr": {
        "welcome": "*RateLy*'ye hoş geldin ✨\nDöviz, altın ve kripto için çok dilli asistan.",
        "choose_lang": "Dil seç:",
        "menu": "Ana menü:",
        "help": "`EUR`, `USD/IRR`, `BTC`, `XAU` gibi bir kod gönder veya `/price` ve `/chart` kullan.",
        "support_intro": "`/support` ile mesajını gönder.\nÖrnek: `/support Grafik yüklenmiyor`",
        "ref_intro": "Referans bağlantın:\n`{link}`",
        "price_query": "`BTC`, `XAU`, `EUR/USD` gibi bir sembol ya da parite gönder.",
        "chart_query": "Örnek: `/chart BTC 7d` veya `/chart EURUSD 1y`.",
        "unknown": "Bu isteği anlayamadım.",
        "banned": "Erişimin engellendi.",
        "no_admin": "Sadece yönetici.",
        "lang_set": "Dil {lang} olarak değiştirildi.",
        "panel": "Yönetici paneli",
        "stats": "Kullanıcılar: {users}\nİstekler: {requests}\nEngellenenler: {banned}\nReferanslar: {refs}\nTalepler: {tickets}",
        "broadcast_done": "Toplu gönderim tamamlandı.\nGönderilen: {sent}\nHata: {failed}",
        "ban_done": "{uid} numaralı kullanıcı engellendi.",
        "unban_done": "{uid} numaralı kullanıcının engeli kaldırıldı.",
        "reset_done": "{uid} numaralı kullanıcı sıfırlandı.",
        "ticket_saved": "Destek talebi #{tid} yöneticiye gönderildi.",
        "reply_sent": "#{tid} numaralı talebe cevap gönderildi.",
        "ad_label": "Sponsorlu",
        "price_not_found": "{symbol} için veri bulunamadı.",
        "chart_not_found": "{symbol} için grafik verisi bulunamadı.",
        "ref_self": "Yönlendirme bağlantın hazır.",
        "shortcut": "Örnekler: `BTC`, `ETH`, `XAU`, `EUR/USD`, `GBP/USD`.",
    },
    "es": {
        "welcome": "Bienvenido a *RateLy* ✨\nAsistente multilingüe de divisas, oro y criptomonedas.",
        "choose_lang": "Elige tu idioma:",
        "menu": "Menú principal:",
        "help": "Envía un código como `EUR`, `USD/IRR`, `BTC`, `XAU`, o usa `/price` y `/chart`.",
        "support_intro": "Envía `/support` seguido de tu mensaje.\nEjemplo: `/support El gráfico no carga`",
        "ref_intro": "Tu enlace de referidos:\n`{link}`",
        "price_query": "Envía un símbolo o par como `BTC`, `XAU`, `EUR/USD`.",
        "chart_query": "Ejemplo: `/chart BTC 7d` o `/chart EURUSD 1y`.",
        "unknown": "No entendí esa solicitud.",
        "banned": "Tu acceso está bloqueado.",
        "no_admin": "Solo administrador.",
        "lang_set": "Idioma cambiado a {lang}.",
        "panel": "Panel de admin",
        "stats": "Usuarios: {users}\nSolicitudes: {requests}\nBloqueados: {banned}\nReferidos: {refs}\nTickets: {tickets}",
        "broadcast_done": "Difusión completada.\nEnviados: {sent}\nFallos: {failed}",
        "ban_done": "Usuario {uid} bloqueado.",
        "unban_done": "Usuario {uid} desbloqueado.",
        "reset_done": "Usuario {uid} reiniciado.",
        "ticket_saved": "Ticket de soporte #{tid} enviado al admin.",
        "reply_sent": "Respuesta enviada al ticket #{tid}.",
        "ad_label": "Patrocinado",
        "price_not_found": "No hay datos para {symbol}.",
        "chart_not_found": "No hay datos de gráfico para {symbol}.",
        "ref_self": "Enlace de referidos listo.",
        "shortcut": "Ejemplos: `BTC`, `ETH`, `XAU`, `EUR/USD`, `GBP/USD`.",
    },
}

LANG_CHOICES = list(LANGS.keys())

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
    "SHIB": "SHIB-USD",
    "PEPE": "PEPE-USD",
    "AVAX": "AVAX-USD",
    "DOT": "DOT-USD",
    "MATIC": "MATIC-USD",
    "LINK": "LINK-USD",
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
    "BRL", "IDR", "MYR", "THB", "PHP", "KRW", "TWD", "ILS", "EGP",
}

SUPPORTED_TF = {
    "1d": ("1d", "5m"),
    "7d": ("7d", "30m"),
    "30d": ("1mo", "1d"),
    "1y": ("1y", "1d"),
}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def get_lang(user_id: int) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT lang FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row and row[0] in LANGS:
            return row[0]
    return DEFAULT_LANG if DEFAULT_LANG in LANGS else "en"

def tr(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in T else "en"
    text = T[lang].get(key, T["en"].get(key, key))
    return text.format(**kwargs)

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
        conn.execute("UPDATE users SET requests = COALESCE(requests,0)+1, last_seen=? WHERE user_id=?", (now_iso(), user_id))
        cur = conn.execute("SELECT requests FROM users WHERE user_id=?", (user_id,))
        val = int(cur.fetchone()["requests"])
        conn.commit()
        return val

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

def main_keyboard(lang: str, is_admin: bool = False):
    rows = [
        [
            InlineKeyboardButton("💲 Price", callback_data="menu:price"),
            InlineKeyboardButton("📈 Chart", callback_data="menu:chart"),
        ],
        [
            InlineKeyboardButton("🌐 Language", callback_data="menu:lang"),
            InlineKeyboardButton("🆘 Support", callback_data="menu:support"),
        ],
        [
            InlineKeyboardButton("🔗 Referral", callback_data="menu:ref"),
            InlineKeyboardButton("ℹ️ Help", callback_data="menu:help"),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("👑 Admin", callback_data="menu:admin")])
    return InlineKeyboardMarkup(rows)

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
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu:back")])
    return InlineKeyboardMarkup(rows)

def admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Stats", callback_data="admin:stats"),
            InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast"),
        ],
        [
            InlineKeyboardButton("🚫 Ban", callback_data="admin:ban"),
            InlineKeyboardButton("✅ Unban", callback_data="admin:unban"),
        ],
        [
            InlineKeyboardButton("♻️ Reset", callback_data="admin:reset"),
            InlineKeyboardButton("💬 Tickets", callback_data="admin:tickets"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:back")],
    ])

def support_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="menu:back")]
    ])

def ad_text(lang: str) -> str:
    if not ADS_TEXT:
        return ""
    return f"🪧 *{tr(lang, 'ad_label')}*\n{ADS_TEXT}"

def maybe_show_ad(chat_id: int, lang: str, context: ContextTypes.DEFAULT_TYPE, req_count: int) -> None:
    if ADS_TEXT and ADS_EVERY > 0 and req_count % ADS_EVERY == 0:
        context.bot.send_message(chat_id=chat_id, text=ad_text(lang), parse_mode=ParseMode.MARKDOWN)

def normalize_symbol(query: str) -> str:
    q = query.strip().upper().replace(" ", "")
    q = q.replace("-", "/")
    return q

def parse_pair(query: str) -> Tuple[str, Optional[str]]:
    q = normalize_symbol(query)
    if "/" in q:
        base, quote = q.split("/", 1)
        return base, quote
    return q, None

def try_history(ticker: str, period: str = "1d", interval: str = "1d") -> pd.DataFrame:
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
        if df is not None and not df.empty:
            return df
    except Exception as exc:
        log.warning("history failed %s: %s", ticker, exc)
    return pd.DataFrame()

def last_close(ticker: str) -> Optional[float]:
    df = try_history(ticker, period="1d", interval="1m")
    if not df.empty:
        s = df["Close"].dropna()
        if not s.empty:
            return float(s.iloc[-1])
    try:
        info = yf.Ticker(ticker).fast_info
        if info and "lastPrice" in info and info["lastPrice"]:
            return float(info["lastPrice"])
    except Exception as exc:
        log.warning("fast_info failed %s: %s", ticker, exc)
    return None

def resolve_fx(query: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    q = normalize_symbol(query)
    if q in CRYPTO_MAP:
        ticker = CRYPTO_MAP[q]
        price = last_close(ticker)
        return ticker, price, "crypto"
    if q in PRECIOUS_MAP:
        ticker = PRECIOUS_MAP[q]
        price = last_close(ticker)
        return ticker, price, "metal"
    base, quote = parse_pair(q)
    if quote:
        direct = f"{base}{quote}=X"
        price = last_close(direct)
        if price is not None:
            return direct, price, "fx"
        inverse = f"{quote}{base}=X"
        inv_price = last_close(inverse)
        if inv_price is not None and inv_price != 0:
            return inverse, 1 / inv_price, "fx"
        return None, None, None
    if base in FIAT_CODES and base != "USD":
        direct = f"{base}USD=X"
        price = last_close(direct)
        if price is not None:
            return direct, price, "fx"
        inverse = f"USD{base}=X"
        inv = last_close(inverse)
        if inv is not None and inv != 0:
            return inverse, 1 / inv, "fx"
        return None, None, None
    if base == "USD":
        return "USD", 1.0, "fx"
    if base in CRYPTO_MAP:
        ticker = CRYPTO_MAP[base]
        price = last_close(ticker)
        return ticker, price, "crypto"
    if base in PRECIOUS_MAP:
        ticker = PRECIOUS_MAP[base]
        price = last_close(ticker)
        return ticker, price, "metal"
    return None, None, None

def pretty_price(symbol: str, price: float, kind: str) -> str:
    if kind == "crypto":
        return f"${price:,.4f}"
    if kind == "metal":
        return f"${price:,.2f}"
    return f"{price:,.6f}"

def format_price_message(query: str, lang: str) -> str:
    ticker, price, kind = resolve_fx(query)
    if price is None:
        return tr(lang, "price_not_found", symbol=query.upper())
    q = normalize_symbol(query)
    if kind == "fx":
        if "/" in q:
            base, quote = parse_pair(q)
            if ticker and ticker.startswith(f"{base}{quote}"):
                return f"*{base}/{quote}*\n1 {base} = {price:,.6f} {quote}"
            if ticker and ticker.startswith(f"{quote}{base}"):
                return f"*{base}/{quote}*\n1 {base} = {price:,.6f} {quote}"
        if q in FIAT_CODES:
            return f"*{q}/USD*\n1 {q} = {price:,.6f} USD"
        return f"*{q}*\nPrice: {price:,.6f}"
    if kind == "crypto":
        return f"*{q}*\nPrice: {pretty_price(q, price, kind)}"
    if kind == "metal":
        label = "Gold" if q in {"XAU", "GOLD"} else "Silver"
        return f"*{label} ({q})*\nPrice: {pretty_price(q, price, kind)} per ounce"
    return f"*{q}*\nPrice: {pretty_price(q, price, kind)}"

def make_chart(symbol: str, timeframe: str = "7d") -> Optional[BytesIO]:
    q = normalize_symbol(symbol)
    ticker, _, _ = resolve_fx(q)
    if not ticker:
        if q in FIAT_CODES:
            ticker = f"{q}USD=X"
        elif q in CRYPTO_MAP:
            ticker = CRYPTO_MAP[q]
        elif q in PRECIOUS_MAP:
            ticker = PRECIOUS_MAP[q]
        else:
            ticker = None
    if not ticker:
        return None
    if timeframe not in SUPPORTED_TF:
        timeframe = "7d"
    period, interval = SUPPORTED_TF[timeframe]
    df = try_history(ticker, period=period, interval=interval)
    if df.empty or "Close" not in df:
        return None
    df = df.dropna(subset=["Close"]).copy()
    if df.empty:
        return None
    plt.figure(figsize=(10, 5))
    plt.plot(df.index, df["Close"])
    plt.title(f"{q} | {timeframe}")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.tight_layout()
    buffer = BytesIO()
    plt.savefig(buffer, format="png", dpi=160)
    plt.close()
    buffer.seek(0)
    return buffer

async def send_price(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    if not update.effective_user or not update.effective_chat:
        return
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.effective_message.reply_text(tr(get_lang(user_id), "banned"))
        return
    lang = get_lang(user_id)
    inc = inc_request(user_id)
    text = format_price_message(query, lang)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    maybe_show_ad(update.effective_chat.id, lang, context, inc)

async def send_chart(update: Update, context: ContextTypes.DEFAULT_TYPE, symbol: str, timeframe: str = "7d") -> None:
    if not update.effective_user or not update.effective_chat:
        return
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.effective_message.reply_text(tr(get_lang(user_id), "banned"))
        return
    lang = get_lang(user_id)
    inc = inc_request(user_id)
    data = await asyncio.to_thread(make_chart, symbol, timeframe)
    if not data:
        await update.effective_message.reply_text(tr(lang, "chart_not_found", symbol=symbol.upper()))
        return
    await update.effective_message.reply_photo(photo=data, caption=f"{symbol.upper()} | {timeframe}")
    maybe_show_ad(update.effective_chat.id, lang, context, inc)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    upsert_user(update.effective_user)
    user_id = update.effective_user.id
    lang = get_lang(user_id)

    # Referral tracking
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

    is_admin = admin_only(user_id)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    text = (
        f"{tr(lang, 'welcome')}\n\n"
        f"{tr(lang, 'shortcut')}\n\n"
        f"{tr(lang, 'ref_intro', link=link)}"
    )
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(lang, is_admin),
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    await update.effective_message.reply_text(
        f"{tr(lang, 'help')}\n\n{tr(lang, 'chart_query')}\n\n{tr(lang, 'support_intro')}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(lang, admin_only(user_id)),
    )

async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if context.args:
        new_lang = context.args[0].lower()
        if new_lang in LANGS:
            set_user_lang(user_id, new_lang)
            await update.effective_message.reply_text(
                tr(new_lang, "lang_set", lang=LANGS[new_lang]),
                reply_markup=main_keyboard(new_lang, admin_only(user_id)),
            )
            return
    await update.effective_message.reply_text(
        tr(lang, "choose_lang"),
        reply_markup=language_keyboard(),
    )

async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        lang = get_lang(update.effective_user.id if update.effective_user else 0)
        await update.effective_message.reply_text(tr(lang, "price_query"))
        return
    await send_price(update, context, " ".join(context.args))

async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        lang = get_lang(update.effective_user.id if update.effective_user else 0)
        await update.effective_message.reply_text(tr(lang, "chart_query"))
        return
    args = context.args
    symbol = args[0]
    tf = args[1] if len(args) > 1 else "7d"
    await send_chart(update, context, symbol, tf)

async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.effective_message.reply_text(tr(get_lang(user_id), "banned"))
        return
    lang = get_lang(user_id)
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
    if not update.effective_user or not admin_only(update.effective_user.id):
        return
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /reply <ticket_id> <message>")
        return
    tid = int(context.args[0])
    message = " ".join(context.args[1:]).strip()
    with db() as conn:
        row = conn.execute("SELECT user_id, status FROM tickets WHERE id=?", (tid,)).fetchone()
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
    if not update.effective_user:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not admin_only(uid):
        await update.effective_message.reply_text(tr(lang, "no_admin"))
        return
    await update.effective_message.reply_text(
        tr(lang, "panel"),
        reply_markup=admin_keyboard(),
    )

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not admin_only(update.effective_user.id):
        return
    lang = get_lang(update.effective_user.id)
    users, requests, banned, refs, tickets = count_stats()
    await update.effective_message.reply_text(
        tr(lang, "stats", users=users, requests=requests, banned=banned, refs=refs, tickets=tickets)
    )

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not admin_only(update.effective_user.id):
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
    if not update.effective_user or not admin_only(update.effective_user.id):
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
    if not update.effective_user or not admin_only(update.effective_user.id):
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
    if not update.effective_user or not admin_only(update.effective_user.id):
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
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "broadcast_done", sent=sent, failed=failed))

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    await update.effective_message.reply_text(str(update.effective_user.id))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    user = update.effective_user
    upsert_user(user)
    if is_banned(user.id):
        await update.effective_message.reply_text(tr(get_lang(user.id), "banned"))
        return
    text = (update.effective_message.text or "").strip()
    if not text or text.startswith("/"):
        return

    cleaned = re.sub(rf"@{re.escape(BOT_USERNAME)}\b", "", text, flags=re.I).strip()
    tokens = cleaned.split()
    lang = get_lang(user.id)
    chat_type = update.effective_chat.type if update.effective_chat else "private"

    # In groups, be conservative: answer only to explicit finance-style messages
    if chat_type in {"group", "supergroup"}:
        if cleaned in {"+", "＋"}:
            await update.effective_message.reply_text(
                f"{tr(lang, 'shortcut')}\n\n{tr(lang, 'help')}",
                reply_markup=main_keyboard(lang, admin_only(user.id)),
            )
            return

        short_symbol = bool(re.fullmatch(r"[A-Za-z0-9/._-]{1,12}", cleaned))
        explicit = tokens and tokens[0].lower() in {"price", "pr", "قیمت", "chart", "graph", "نمودار"}
        if not (short_symbol or explicit):
            return

    if len(tokens) == 1:
        await send_price(update, context, cleaned)
        return
    if tokens[0].lower() in {"price", "pr", "قیمت"}:
        await send_price(update, context, " ".join(tokens[1:]))
        return
    if tokens[0].lower() in {"chart", "graph", "نمودار"}:
        symbol = tokens[1] if len(tokens) > 1 else ""
        tf = tokens[2] if len(tokens) > 2 else "7d"
        if symbol:
            await send_chart(update, context, symbol, tf)
            return

    await send_price(update, context, cleaned)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query or not update.effective_user:
        return
    q = update.callback_query
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    await q.answer()
    data = q.data or ""

    if data == "menu:back":
        await q.edit_message_text(tr(lang, "menu"), reply_markup=main_keyboard(lang, admin_only(user_id)))
        return
    if data == "menu:lang":
        await q.edit_message_text(tr(lang, "choose_lang"), reply_markup=language_keyboard())
        return
    if data == "menu:help":
        await q.edit_message_text(
            f"{tr(lang, 'help')}\n\n{tr(lang, 'chart_query')}\n\n{tr(lang, 'support_intro')}",
            reply_markup=main_keyboard(lang, admin_only(user_id)),
        )
        return
    if data == "menu:price":
        await q.edit_message_text(f"{tr(lang, 'price_query')}\n\n{tr(lang, 'shortcut')}", reply_markup=main_keyboard(lang, admin_only(user_id)))
        return
    if data == "menu:chart":
        await q.edit_message_text(tr(lang, "chart_query"), reply_markup=main_keyboard(lang, admin_only(user_id)))
        return
    if data == "menu:support":
        await q.edit_message_text(tr(lang, "support_intro"), reply_markup=support_keyboard())
        return
    if data == "menu:ref":
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        await q.edit_message_text(tr(lang, "ref_intro", link=link), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(lang, admin_only(user_id)))
        return
    if data == "menu:admin":
        if not admin_only(user_id):
            await q.edit_message_text(tr(lang, "no_admin"))
            return
        await q.edit_message_text(tr(lang, "panel"), reply_markup=admin_keyboard())
        return
    if data.startswith("lang:"):
        new_lang = data.split(":", 1)[1]
        if new_lang in LANGS:
            set_user_lang(user_id, new_lang)
            await q.edit_message_text(
                tr(new_lang, "lang_set", lang=LANGS[new_lang]),
                reply_markup=main_keyboard(new_lang, admin_only(user_id)),
            )
        return
    if data.startswith("admin:"):
        if not admin_only(user_id):
            await q.edit_message_text(tr(lang, "no_admin"))
            return
        action = data.split(":", 1)[1]
        if action == "stats":
            users, requests, banned, refs, tickets = count_stats()
            await q.edit_message_text(tr(lang, "stats", users=users, requests=requests, banned=banned, refs=refs, tickets=tickets), reply_markup=admin_keyboard())
        elif action == "broadcast":
            await q.edit_message_text("Use: /broadcast <message>", reply_markup=admin_keyboard())
        elif action == "ban":
            await q.edit_message_text("Use: /ban <user_id>", reply_markup=admin_keyboard())
        elif action == "unban":
            await q.edit_message_text("Use: /unban <user_id>", reply_markup=admin_keyboard())
        elif action == "reset":
            await q.edit_message_text("Use: /reset <user_id>", reply_markup=admin_keyboard())
        elif action == "tickets":
            with db() as conn:
                rows = conn.execute("SELECT id, user_id, status, created_at FROM tickets ORDER BY id DESC LIMIT 10").fetchall()
            if not rows:
                await q.edit_message_text("No tickets.", reply_markup=admin_keyboard())
            else:
                lines = []
                for r in rows:
                    lines.append(f"#{r['id']} | user {r['user_id']} | {r['status']} | {r['created_at']}")
                await q.edit_message_text("\n".join(lines), reply_markup=admin_keyboard())
        return

async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    lang = get_lang(update.effective_user.id)
    await update.effective_message.reply_text(tr(lang, "unknown"))

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
    application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None, close_loop=False)

@app.get("/")
def home():
    return {
        "ok": True,
        "name": BOT_NAME,
        "time": now_iso(),
    }

def main():
    init_db()
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.getenv("PORT", "10000"))
    log.info("Web server on %s", port)
    serve(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
