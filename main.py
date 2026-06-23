
import asyncio
import json
import logging
import os
import random
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests
import yfinance as yf
from flask import Flask, jsonify
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from waitress import serve

# =============================================================================
# Config
# =============================================================================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "rately.db"

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "RateLyBot").strip().lstrip("@")
BOT_NAME = os.getenv("BOT_NAME", "RateLy").strip()
APP_TITLE = os.getenv("APP_TITLE", "RateLy").strip()

ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
DEFAULT_LANG = os.getenv("DEFAULT_LANG", "en").strip().lower() or "en"
PORT = int(os.getenv("PORT", "10000"))

ADS_TEXT = os.getenv("ADS_TEXT", "").strip()
ADS_EVERY = int(os.getenv("ADS_EVERY", "0") or "0")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("RateLy")

app = Flask(__name__)

# =============================================================================
# Language
# =============================================================================
LANGS = {
    "en": "English",
    "fa": "فارسی",
    "ar": "العربية",
    "ru": "Русский",
    "tr": "Türkçe",
    "es": "Español",
}
LANG_ORDER = ["en", "fa", "ar", "ru", "tr", "es"]

BASE_CURRENCIES = ["TMN", "IRR", "USD", "EUR", "GBP", "TRY", "RUB", "AED"]

T = {
    "en": {
        "welcome": "Welcome to *RateLy* ✨\nLive prices for currencies, crypto, metals, and charts.",
        "quick": "Quick examples: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`.",
        "choose_lang": "Choose your language:",
        "choose_base": "Choose your display currency:",
        "choose_chart": "Choose chart type and timeframe:",
        "help": "Send a symbol like `BTC`, `USDT`, `USD`, `EUR/USD`, `gold`, `silver`, `USD/IRR`.\nYou can also add the bot to a group and ask there.",
        "unknown": "I did not understand that message.",
        "greet": "Hello 😎\nSend a symbol, a conversion like `0.5 btc to toman`, or use the buttons.",
        "thanks": "You are welcome 🤝",
        "bye": "Bye 👋",
        "support_intro": "Tap *Support / Ads / Feedback* and send your message.\nIt will arrive to the admin anonymously.",
        "support_saved": "Your anonymous message was saved as ticket #{tid}.",
        "reply_sent": "Reply sent to ticket #{tid}.",
        "admin_only": "Admin only.",
        "panel": "Admin panel",
        "stats": "Users: {users}\nRequests: {requests}\nBanned: {banned}\nPremium: {premium}\nTickets: {tickets}\nAlerts: {alerts}\nWatchlist items: {watch}",
        "user_info": "User {uid}\nName: {name}\nUsername: {username}\nLanguage: {lang}\nDisplay: {base}\nPremium: {premium}\nRequests: {requests}\nReferrals: {refs}\nLast seen: {last_seen}",
        "ban_done": "User {uid} banned.",
        "unban_done": "User {uid} unbanned.",
        "vip_on": "Premium enabled for {uid}.",
        "vip_off": "Premium disabled for {uid}.",
        "reset_done": "User {uid} reset.",
        "broadcast_done": "Broadcast completed.\nSent: {sent}\nFailed: {failed}",
        "scheduled_done": "Scheduled for {when}.",
        "price_not_found": "No data found for {symbol}.",
        "chart_not_found": "No chart data found for {symbol}.",
        "ref_link": "Your referral link:\n`{link}`",
        "base_saved": "Display currency set to {base}.",
        "lang_saved": "Language changed to {lang}.",
        "ad_label": "Sponsored",
        "watch_added": "Added {symbol} to your watchlist.",
        "watch_removed": "Removed {symbol} from your watchlist.",
        "watch_empty": "Your watchlist is empty.",
        "watch_header": "Your watchlist:",
        "alert_added": "Alert saved: {rule}",
        "alert_empty": "You have no alerts.",
        "alert_header": "Your alerts:",
        "top_gainers": "Top gainers (24h)",
        "top_losers": "Top losers (24h)",
        "conversion_hint": "Try: `0.5 btc to toman`, `100 usd to eur`, `25000 irr to usd`.",
        "group_hint": "The bot can be added to groups.",
        "feedback_hint": "Send a message for support, ads, or feedback.",
        "menu_main": "Main menu",
        "back": "Back",
        "prices": "Prices",
        "charts": "Charts",
        "language": "Language",
        "base": "Display currency",
        "support": "Support / Ads / Feedback",
        "watchlist": "Watchlist",
        "alerts": "Alerts",
        "movers": "Top movers",
        "admin": "Admin",
        "chart_line": "Line",
        "chart_candle": "Candlestick",
        "chart_1h": "1H",
        "chart_24h": "24H",
        "chart_7d": "7D",
        "chart_30d": "30D",
        "chart_1y": "1Y",
        "chart_actions": "Chart actions",
        "refresh": "Refresh",
        "add_watch": "Watch",
        "set_alert": "Alert",
        "add_support": "Support",
    },
    "fa": {
        "welcome": "به *RateLy* خوش آمدی ✨\nقیمت لحظه‌ای ارزها، رمزارزها، فلزات و نمودارها.",
        "quick": "نمونه‌ها: `BTC`، `ETH`، `XAU`، `USD`، `EUR/USD`، `GBP/USD`، `USD/IRR`.",
        "choose_lang": "زبان را انتخاب کن:",
        "choose_base": "ارز نمایش را انتخاب کن:",
        "choose_chart": "نوع و بازه نمودار را انتخاب کن:",
        "help": "نمادهایی مثل `BTC`، `USDT`، `USD`، `EUR/USD`، `gold`، `silver`، `USD/IRR` بفرست.\nربات را می‌توانی به گروه هم اضافه کنی.",
        "unknown": "این پیام را متوجه نشدم.",
        "greet": "سلام 😎\nیک نماد، یک تبدیل مثل `0.5 btc to toman` یا از دکمه‌ها استفاده کن.",
        "thanks": "خواهش می‌کنم 🤝",
        "bye": "فعلاً 👋",
        "support_intro": "روی *پشتیبانی / تبلیغات / نظرات* بزن و پیام را بفرست.\nپیام به‌صورت ناشناس برای ادمین می‌رود.",
        "support_saved": "پیام ناشناس شما با شماره #{tid} ثبت شد.",
        "reply_sent": "پاسخ برای تیکت #{tid} ارسال شد.",
        "admin_only": "فقط برای ادمین.",
        "panel": "پنل ادمین",
        "stats": "کاربران: {users}\nدرخواست‌ها: {requests}\nبن‌شده‌ها: {banned}\nپرمیوم: {premium}\nتیکت‌ها: {tickets}\nهشدارها: {alerts}\nموارد واچ‌لیست: {watch}",
        "user_info": "کاربر {uid}\nنام: {name}\nیوزرنیم: {username}\nزبان: {lang}\nنمایش: {base}\nپرمیوم: {premium}\nدرخواست‌ها: {requests}\nمعرفی‌ها: {refs}\nآخرین فعالیت: {last_seen}",
        "ban_done": "کاربر {uid} بن شد.",
        "unban_done": "کاربر {uid} آنبن شد.",
        "vip_on": "پرمیوم برای {uid} فعال شد.",
        "vip_off": "پرمیوم برای {uid} غیرفعال شد.",
        "reset_done": "کاربر {uid} ریست شد.",
        "broadcast_done": "ارسال همگانی تمام شد.\nارسال شد: {sent}\nناموفق: {failed}",
        "scheduled_done": "برای {when} زمان‌بندی شد.",
        "price_not_found": "برای {symbol} داده‌ای پیدا نشد.",
        "chart_not_found": "برای {symbol} نمودار پیدا نشد.",
        "ref_link": "لینک معرفی تو:\n`{link}`",
        "base_saved": "ارز نمایش به {base} تغییر کرد.",
        "lang_saved": "زبان به {lang} تغییر کرد.",
        "ad_label": "تبلیغ",
        "watch_added": "{symbol} به واچ‌لیست اضافه شد.",
        "watch_removed": "{symbol} از واچ‌لیست حذف شد.",
        "watch_empty": "واچ‌لیست تو خالی است.",
        "watch_header": "واچ‌لیست تو:",
        "alert_added": "هشدار ذخیره شد: {rule}",
        "alert_empty": "هشدار فعالی نداری.",
        "alert_header": "هشدارهای تو:",
        "top_gainers": "بیشترین رشد 24 ساعته",
        "top_losers": "بیشترین ریزش 24 ساعته",
        "conversion_hint": "مثال: `0.5 btc to toman`، `100 usd to eur`، `25000 irr to usd`.",
        "group_hint": "ربات را می‌شود به گروه هم اضافه کرد.",
        "feedback_hint": "برای پشتیبانی، تبلیغات یا نظر پیام بفرست.",
        "menu_main": "منوی اصلی",
        "back": "بازگشت",
        "prices": "قیمت‌ها",
        "charts": "نمودار",
        "language": "زبان",
        "base": "ارز نمایش",
        "support": "پشتیبانی / تبلیغات / نظرات",
        "watchlist": "واچ‌لیست",
        "alerts": "هشدارها",
        "movers": "تاپ‌ها",
        "admin": "ادمین",
        "chart_line": "خطی",
        "chart_candle": "کندلی",
        "chart_1h": "1H",
        "chart_24h": "24H",
        "chart_7d": "7D",
        "chart_30d": "30D",
        "chart_1y": "1Y",
        "chart_actions": "تنظیمات چارت",
        "refresh": "به‌روزرسانی",
        "add_watch": "اضافه به واچ",
        "set_alert": "هشدار",
        "add_support": "پشتیبانی",
    },
    "ar": {
        "welcome": "مرحبًا بك في *RateLy* ✨\nأسعار العملات والرقميات والمعادن والرسوم البيانية.",
        "quick": "أمثلة: `BTC`، `ETH`، `XAU`، `USD`، `EUR/USD`، `GBP/USD`، `USD/IRR`.",
        "choose_lang": "اختر لغتك:",
        "choose_base": "اختر عملة العرض:",
        "choose_chart": "اختر نوع الرسم والمدة:",
        "help": "أرسل رمزًا مثل `BTC` أو `USDT` أو `USD` أو `EUR/USD` أو `gold` أو `silver` أو `USD/IRR`.",
        "unknown": "لم أفهم هذه الرسالة.",
        "greet": "مرحبًا 😎\nأرسل رمزًا أو تحويلًا مثل `0.5 btc to toman` أو استخدم الأزرار.",
        "thanks": "عفوًا 🤝",
        "bye": "إلى اللقاء 👋",
        "support_intro": "اضغط على *الدعم / الإعلانات / الآراء* وأرسل رسالتك.\nستصل بشكل مجهول إلى المدير.",
        "support_saved": "تم حفظ رسالتك المجهولة كطلب رقم #{tid}.",
        "reply_sent": "تم إرسال الرد للطلب #{tid}.",
        "admin_only": "للمدير فقط.",
        "panel": "لوحة المدير",
        "stats": "المستخدمون: {users}\nالطلبات: {requests}\nالمحظورون: {banned}\nالبرميوم: {premium}\nالتذاكر: {tickets}\nالتنبيهات: {alerts}\nقائمة المتابعة: {watch}",
        "user_info": "المستخدم {uid}\nالاسم: {name}\nالمعرف: {username}\nاللغة: {lang}\nالعرض: {base}\nبرميوم: {premium}\nالطلبات: {requests}\nالإحالات: {refs}\nآخر نشاط: {last_seen}",
        "ban_done": "تم حظر المستخدم {uid}.",
        "unban_done": "تم إلغاء حظر المستخدم {uid}.",
        "vip_on": "تم تفعيل البرميوم للمستخدم {uid}.",
        "vip_off": "تم إلغاء البرميوم للمستخدم {uid}.",
        "reset_done": "تمت إعادة ضبط المستخدم {uid}.",
        "broadcast_done": "انتهى الإرسال الجماعي.\nتم الإرسال: {sent}\nفشل: {failed}",
        "scheduled_done": "تم الجدولة لـ {when}.",
        "price_not_found": "لا توجد بيانات لـ {symbol}.",
        "chart_not_found": "لا توجد بيانات للرسم لـ {symbol}.",
        "ref_link": "رابط الإحالة الخاص بك:\n`{link}`",
        "base_saved": "تم تغيير عملة العرض إلى {base}.",
        "lang_saved": "تم تغيير اللغة إلى {lang}.",
        "ad_label": "إعلان",
        "watch_added": "تمت إضافة {symbol} إلى قائمة المتابعة.",
        "watch_removed": "تمت إزالة {symbol} من قائمة المتابعة.",
        "watch_empty": "قائمة المتابعة فارغة.",
        "watch_header": "قائمة المتابعة:",
        "alert_added": "تم حفظ التنبيه: {rule}",
        "alert_empty": "لا توجد تنبيهات.",
        "alert_header": "التنبيهات:",
        "top_gainers": "أكبر الرابحين خلال 24 ساعة",
        "top_losers": "أكبر الخاسرين خلال 24 ساعة",
        "conversion_hint": "جرّب: `0.5 btc to toman` أو `100 usd to eur`.",
        "group_hint": "يمكن إضافة البوت إلى المجموعات.",
        "feedback_hint": "أرسل رسالة للدعم أو الإعلان أو الرأي.",
        "menu_main": "القائمة الرئيسية",
        "back": "رجوع",
        "prices": "الأسعار",
        "charts": "الرسوم",
        "language": "اللغة",
        "base": "عرض العملة",
        "support": "الدعم / الإعلانات / الآراء",
        "watchlist": "قائمة المتابعة",
        "alerts": "التنبيهات",
        "movers": "المتحركون",
        "admin": "المدير",
        "chart_line": "خطي",
        "chart_candle": "شموع",
        "chart_1h": "1H",
        "chart_24h": "24H",
        "chart_7d": "7D",
        "chart_30d": "30D",
        "chart_1y": "1Y",
        "chart_actions": "إعدادات الرسم",
        "refresh": "تحديث",
        "add_watch": "أضف للمتابعة",
        "set_alert": "تنبيه",
        "add_support": "الدعم",
    },
    "ru": {
        "welcome": "Добро пожаловать в *RateLy* ✨\nЦены валют, криптовалют, металлов и графики.",
        "quick": "Примеры: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`.",
        "choose_lang": "Выберите язык:",
        "choose_base": "Выберите валюту отображения:",
        "choose_chart": "Выберите тип и период графика:",
        "help": "Отправьте `BTC`, `USDT`, `USD`, `EUR/USD`, `gold`, `silver`, `USD/IRR`.",
        "unknown": "Я не понял это сообщение.",
        "greet": "Привет 😎\nОтправьте символ или конвертацию вроде `0.5 btc to toman`.",
        "thanks": "Пожалуйста 🤝",
        "bye": "Пока 👋",
        "support_intro": "Нажмите *Поддержка / Реклама / Отзывы* и отправьте сообщение.\nОно придёт анонимно администратору.",
        "support_saved": "Ваше анонимное сообщение сохранено как тикет #{tid}.",
        "reply_sent": "Ответ отправлен в тикет #{tid}.",
        "admin_only": "Только для администратора.",
        "panel": "Панель администратора",
        "stats": "Пользователи: {users}\nЗапросы: {requests}\nЗаблокированы: {banned}\nПремиум: {premium}\nТикеты: {tickets}\nОповещения: {alerts}\nСписок: {watch}",
        "user_info": "Пользователь {uid}\nИмя: {name}\nUsername: {username}\nЯзык: {lang}\nОтображение: {base}\nПремиум: {premium}\nЗапросы: {requests}\nРефералы: {refs}\nПоследняя активность: {last_seen}",
        "ban_done": "Пользователь {uid} заблокирован.",
        "unban_done": "Пользователь {uid} разблокирован.",
        "vip_on": "Премиум включён для {uid}.",
        "vip_off": "Премиум выключен для {uid}.",
        "reset_done": "Пользователь {uid} сброшен.",
        "broadcast_done": "Массовая рассылка завершена.\nОтправлено: {sent}\nОшибок: {failed}",
        "scheduled_done": "Запланировано на {when}.",
        "price_not_found": "Нет данных для {symbol}.",
        "chart_not_found": "Нет данных графика для {symbol}.",
        "ref_link": "Ваша реферальная ссылка:\n`{link}`",
        "base_saved": "Валюта отображения изменена на {base}.",
        "lang_saved": "Язык изменён на {lang}.",
        "ad_label": "Реклама",
        "watch_added": "{symbol} добавлен в список.",
        "watch_removed": "{symbol} удалён из списка.",
        "watch_empty": "Ваш список пуст.",
        "watch_header": "Ваш список:",
        "alert_added": "Оповещение сохранено: {rule}",
        "alert_empty": "У вас нет оповещений.",
        "alert_header": "Оповещения:",
        "top_gainers": "Лидеры роста за 24 часа",
        "top_losers": "Лидеры падения за 24 часа",
        "conversion_hint": "Попробуйте: `0.5 btc to toman`, `100 usd to eur`.",
        "group_hint": "Бот можно добавить в группу.",
        "feedback_hint": "Отправьте сообщение в поддержку, рекламу или отзыв.",
        "menu_main": "Главное меню",
        "back": "Назад",
        "prices": "Цены",
        "charts": "Графики",
        "language": "Язык",
        "base": "Валюта отображения",
        "support": "Поддержка / Реклама / Отзывы",
        "watchlist": "Список",
        "alerts": "Оповещения",
        "movers": "Движение",
        "admin": "Админ",
        "chart_line": "Линия",
        "chart_candle": "Свечи",
        "chart_1h": "1H",
        "chart_24h": "24H",
        "chart_7d": "7D",
        "chart_30d": "30D",
        "chart_1y": "1Y",
        "chart_actions": "Настройки графика",
        "refresh": "Обновить",
        "add_watch": "В список",
        "set_alert": "Оповещение",
        "add_support": "Поддержка",
    },
    "tr": {
        "welcome": "*RateLy*'ye hoş geldin ✨\nCanlı döviz, kripto, metal ve grafikler.",
        "quick": "Örnekler: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`.",
        "choose_lang": "Dil seç:",
        "choose_base": "Görüntüleme para birimini seç:",
        "choose_chart": "Grafik türü ve zaman dilimi seç:",
        "help": "`BTC`, `USDT`, `USD`, `EUR/USD`, `gold`, `silver`, `USD/IRR` gönder.\nBotu gruba da ekleyebilirsin.",
        "unknown": "Bu mesajı anlayamadım.",
        "greet": "Merhaba 😎\nBir sembol veya `0.5 btc to toman` gibi dönüşüm gönder.",
        "thanks": "Rica ederim 🤝",
        "bye": "Görüşürüz 👋",
        "support_intro": "*Destek / Reklam / Yorumlar* düğmesine bas ve mesajını gönder.\nMesaj yöneticiye anonim olarak gider.",
        "support_saved": "Anonim mesajın #{tid} numaralı talep olarak kaydedildi.",
        "reply_sent": "#{tid} numaralı talebe cevap gönderildi.",
        "admin_only": "Sadece yönetici.",
        "panel": "Yönetici paneli",
        "stats": "Kullanıcılar: {users}\nİstekler: {requests}\nEngellenenler: {banned}\nPremium: {premium}\nTalepler: {tickets}\nUyarılar: {alerts}\nListe: {watch}",
        "user_info": "Kullanıcı {uid}\nAd: {name}\nKullanıcı adı: {username}\nDil: {lang}\nGörüntüleme: {base}\nPremium: {premium}\nİstekler: {requests}\nReferanslar: {refs}\nSon aktivite: {last_seen}",
        "ban_done": "{uid} numaralı kullanıcı engellendi.",
        "unban_done": "{uid} numaralı kullanıcının engeli kaldırıldı.",
        "vip_on": "{uid} için premium açıldı.",
        "vip_off": "{uid} için premium kapatıldı.",
        "reset_done": "{uid} numaralı kullanıcı sıfırlandı.",
        "broadcast_done": "Toplu gönderim tamamlandı.\nGönderilen: {sent}\nHata: {failed}",
        "scheduled_done": "{when} için planlandı.",
        "price_not_found": "{symbol} için veri bulunamadı.",
        "chart_not_found": "{symbol} için grafik bulunamadı.",
        "ref_link": "Referans bağlantın:\n`{link}`",
        "base_saved": "Görüntüleme para birimi {base} olarak değişti.",
        "lang_saved": "Dil {lang} olarak değişti.",
        "ad_label": "Sponsorlu",
        "watch_added": "{symbol} izleme listene eklendi.",
        "watch_removed": "{symbol} izleme listesinden çıkarıldı.",
        "watch_empty": "İzleme listen boş.",
        "watch_header": "İzleme listen:",
        "alert_added": "Uyarı kaydedildi: {rule}",
        "alert_empty": "Uyarın yok.",
        "alert_header": "Uyarıların:",
        "top_gainers": "24 saat en çok yükselenler",
        "top_losers": "24 saat en çok düşenler",
        "conversion_hint": "`0.5 btc to toman`, `100 usd to eur` dene.",
        "group_hint": "Bot gruba eklenebilir.",
        "feedback_hint": "Destek, reklam ya da yorum için mesaj gönder.",
        "menu_main": "Ana menü",
        "back": "Geri",
        "prices": "Fiyatlar",
        "charts": "Grafikler",
        "language": "Dil",
        "base": "Görüntüleme",
        "support": "Destek / Reklam / Yorumlar",
        "watchlist": "İzleme",
        "alerts": "Uyarılar",
        "movers": "Hareket",
        "admin": "Yönetici",
        "chart_line": "Çizgi",
        "chart_candle": "Mum",
        "chart_1h": "1H",
        "chart_24h": "24H",
        "chart_7d": "7D",
        "chart_30d": "30D",
        "chart_1y": "1Y",
        "chart_actions": "Grafik ayarları",
        "refresh": "Yenile",
        "add_watch": "Listeye al",
        "set_alert": "Uyarı",
        "add_support": "Destek",
    },
    "es": {
        "welcome": "Bienvenido a *RateLy* ✨\nPrecios en vivo de divisas, cripto, metales y gráficos.",
        "quick": "Ejemplos: `BTC`, `ETH`, `XAU`, `USD`, `EUR/USD`, `GBP/USD`, `USD/IRR`.",
        "choose_lang": "Elige tu idioma:",
        "choose_base": "Elige tu moneda de visualización:",
        "choose_chart": "Elige tipo y periodo del gráfico:",
        "help": "Envía `BTC`, `USDT`, `USD`, `EUR/USD`, `gold`, `silver`, `USD/IRR`.\nTambién puedes añadir el bot a un grupo.",
        "unknown": "No entendí ese mensaje.",
        "greet": "Hola 😎\nEnvía un símbolo o una conversión como `0.5 btc to toman`.",
        "thanks": "De nada 🤝",
        "bye": "Chao 👋",
        "support_intro": "Pulsa *Soporte / Publicidad / Opiniones* y envía tu mensaje.\nLlegará de forma anónima al admin.",
        "support_saved": "Tu mensaje anónimo se guardó como ticket #{tid}.",
        "reply_sent": "Respuesta enviada al ticket #{tid}.",
        "admin_only": "Solo administrador.",
        "panel": "Panel de admin",
        "stats": "Usuarios: {users}\nSolicitudes: {requests}\nBloqueados: {banned}\nPremium: {premium}\nTickets: {tickets}\nAlertas: {alerts}\nLista: {watch}",
        "user_info": "Usuario {uid}\nNombre: {name}\nUsuario: {username}\nIdioma: {lang}\nVisualización: {base}\nPremium: {premium}\nSolicitudes: {requests}\nReferidos: {refs}\nÚltima actividad: {last_seen}",
        "ban_done": "Usuario {uid} bloqueado.",
        "unban_done": "Usuario {uid} desbloqueado.",
        "vip_on": "Premium activado para {uid}.",
        "vip_off": "Premium desactivado para {uid}.",
        "reset_done": "Usuario {uid} reiniciado.",
        "broadcast_done": "Difusión completada.\nEnviados: {sent}\nFallos: {failed}",
        "scheduled_done": "Programado para {when}.",
        "price_not_found": "No hay datos para {symbol}.",
        "chart_not_found": "No hay gráfico para {symbol}.",
        "ref_link": "Tu enlace de referidos:\n`{link}`",
        "base_saved": "Moneda de visualización cambiada a {base}.",
        "lang_saved": "Idioma cambiado a {lang}.",
        "ad_label": "Patrocinado",
        "watch_added": "{symbol} añadido a tu lista.",
        "watch_removed": "{symbol} eliminado de tu lista.",
        "watch_empty": "Tu lista está vacía.",
        "watch_header": "Tu lista:",
        "alert_added": "Alerta guardada: {rule}",
        "alert_empty": "No tienes alertas.",
        "alert_header": "Tus alertas:",
        "top_gainers": "Mayores subidas 24h",
        "top_losers": "Mayores caídas 24h",
        "conversion_hint": "Prueba: `0.5 btc to toman`, `100 usd to eur`.",
        "group_hint": "El bot se puede añadir a grupos.",
        "feedback_hint": "Envía un mensaje para soporte, publicidad u opinión.",
        "menu_main": "Menú principal",
        "back": "Volver",
        "prices": "Precios",
        "charts": "Gráficos",
        "language": "Idioma",
        "base": "Moneda",
        "support": "Soporte / Publicidad / Opiniones",
        "watchlist": "Lista",
        "alerts": "Alertas",
        "movers": "Movimiento",
        "admin": "Admin",
        "chart_line": "Línea",
        "chart_candle": "Velas",
        "chart_1h": "1H",
        "chart_24h": "24H",
        "chart_7d": "7D",
        "chart_30d": "30D",
        "chart_1y": "1Y",
        "chart_actions": "Ajustes del gráfico",
        "refresh": "Actualizar",
        "add_watch": "Seguir",
        "set_alert": "Alerta",
        "add_support": "Soporte",
    },
}

# =============================================================================
# Aliases / currencies
# =============================================================================
ALIASES = {
    "دلار": "USD", "یورو": "EUR", "پوند": "GBP", "ین": "JPY", "فرانک": "CHF",
    "تتر": "USDT", "بیت کوین": "BTC", "بیتکوین": "BTC", "بیت‌کوین": "BTC",
    "اتریوم": "ETH", "طلا": "XAU", "نقره": "XAG", "پلاتین": "XPT", "پالادیوم": "XPD",
    "نفت": "CL=F", "oil": "CL=F", "gold": "XAU", "silver": "XAG",
    "bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH",
    "usdt": "USDT", "usd": "USD", "eur": "EUR", "gbp": "GBP", "jpy": "JPY",
    "xau": "XAU", "xag": "XAG", "xpt": "XPT", "xpd": "XPD",
    "ریال": "IRR", "تومان": "TMN", "تومـان": "TMN",
}
PRICE_WORDS = {
    "price", "pr", "rate", "value", "quote", "chart", "graph", "trend",
    "قیمت", "نرخ", "ارزش", "نمودار", "رسم", "سعر", "precio", "preço",
    "kurs", "цена", "график", "fiyat", "değer", "fiyatı",
}

FIAT_CODES: set[str] = {
    "USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD","CNY","HKD","SGD","SEK","NOK","DKK","PLN","CZK","HUF","RON",
    "TRY","SAR","AED","QAR","KWD","BHD","INR","PKR","RUB","UAH","ZAR","MXN","BRL","IDR","MYR","THB","PHP","KRW",
    "TWD","ILS","EGP","IRR","KZT","VND","ARS","COP","CLP","NGN","LKR","BDT","PKR","PKR","UZS","TJS","GEL","AMD",
    "MNT","ISK","MAD","TND","DZD","JOD","OMR","BAM","HRK","RSD","BGN","ALL","MKD","KGS","AZN","TZS","KES","UGX",
    "GHS","XOF","XAF","ZMW","ETB","RSD","BWP","NAD","MUR","MZN","GMD","SYP","LBP","IQD"
}
METALS = {"XAU", "XAG", "XPT", "XPD"}

# =============================================================================
# DB
# =============================================================================
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
            base_currency TEXT DEFAULT 'TMN',
            premium INTEGER DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            requests INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            referrer INTEGER,
            referrals INTEGER DEFAULT 0,
            watchlist TEXT DEFAULT '[]',
            pending_mode TEXT DEFAULT '',
            pending_data TEXT DEFAULT ''
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            kind TEXT DEFAULT 'support',
            question TEXT,
            status TEXT DEFAULT 'open',
            answer TEXT,
            created_at TEXT,
            answered_at TEXT
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            symbol TEXT,
            operator TEXT,
            target REAL,
            active INTEGER DEFAULT 1,
            created_at TEXT,
            last_notified TEXT
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT,
            message TEXT,
            created_by INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
        """)
        conn.commit()

def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()

def ensure_user(user) -> None:
    with db() as conn:
        row = conn.execute("SELECT user_id FROM users WHERE user_id=?", (user.id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET username=?, first_name=?, last_seen=? WHERE user_id=?",
                (user.username or "", user.first_name or "", now_iso(), user.id),
            )
        else:
            conn.execute("""
                INSERT INTO users (user_id, username, first_name, lang, base_currency, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user.id, user.username or "", user.first_name or "", DEFAULT_LANG if DEFAULT_LANG in LANGS else "en",
                "TMN", now_iso(), now_iso()
            ))
        conn.commit()

def get_lang(user_id: int) -> str:
    row = get_user(user_id)
    if row and row["lang"] in LANGS:
        return row["lang"]
    return DEFAULT_LANG if DEFAULT_LANG in LANGS else "en"

def get_base(user_id: int) -> str:
    row = get_user(user_id)
    if row and row["base_currency"] in BASE_CURRENCIES:
        return row["base_currency"]
    return "TMN"

def set_lang(user_id: int, lang: str) -> None:
    if lang not in LANGS:
        return
    with db() as conn:
        conn.execute("UPDATE users SET lang=?, last_seen=? WHERE user_id=?", (lang, now_iso(), user_id))
        conn.commit()

def set_base(user_id: int, base: str) -> None:
    if base not in BASE_CURRENCIES:
        return
    with db() as conn:
        conn.execute("UPDATE users SET base_currency=?, last_seen=? WHERE user_id=?", (base, now_iso(), user_id))
        conn.commit()

def is_banned(user_id: int) -> bool:
    row = get_user(user_id)
    return bool(row and row["banned"])

def is_premium(user_id: int) -> bool:
    row = get_user(user_id)
    return bool(row and row["premium"])

def set_ban(user_id: int, value: int) -> None:
    with db() as conn:
        conn.execute("UPDATE users SET banned=?, last_seen=? WHERE user_id=?", (value, now_iso(), user_id))
        conn.commit()

def set_premium(user_id: int, value: int) -> None:
    with db() as conn:
        conn.execute("UPDATE users SET premium=?, last_seen=? WHERE user_id=?", (value, now_iso(), user_id))
        conn.commit()

def reset_user(user_id: int) -> None:
    with db() as conn:
        conn.execute("UPDATE users SET requests=0, banned=0, premium=0, referrer=NULL, referrals=0, watchlist='[]', pending_mode='', pending_data='' WHERE user_id=?", (user_id,))
        conn.commit()

def inc_request(user_id: int) -> int:
    with db() as conn:
        conn.execute("UPDATE users SET requests=COALESCE(requests,0)+1, last_seen=? WHERE user_id=?", (now_iso(), user_id))
        row = conn.execute("SELECT requests FROM users WHERE user_id=?", (user_id,)).fetchone()
        conn.commit()
        return int(row["requests"]) if row else 0

def admin_only(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def stats() -> Dict[str, int]:
    with db() as conn:
        users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        requests = conn.execute("SELECT COALESCE(SUM(requests),0) AS s FROM users").fetchone()["s"]
        banned = conn.execute("SELECT COUNT(*) AS c FROM users WHERE banned=1").fetchone()["c"]
        premium = conn.execute("SELECT COUNT(*) AS c FROM users WHERE premium=1").fetchone()["c"]
        tickets = conn.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()["c"]
        alerts = conn.execute("SELECT COUNT(*) AS c FROM alerts WHERE active=1").fetchone()["c"]
        watch = conn.execute("SELECT COUNT(*) AS c FROM users WHERE watchlist <> '[]'").fetchone()["c"]
        return dict(users=users, requests=requests, banned=banned, premium=premium, tickets=tickets, alerts=alerts, watch=watch)

def pending_mode(user_id: int) -> Tuple[str, str]:
    row = get_user(user_id)
    if not row:
        return "", ""
    return row["pending_mode"] or "", row["pending_data"] or ""

def set_pending(user_id: int, mode: str = "", data: str = "") -> None:
    with db() as conn:
        conn.execute("UPDATE users SET pending_mode=?, pending_data=?, last_seen=? WHERE user_id=?", (mode, data, now_iso(), user_id))
        conn.commit()

def get_watchlist(user_id: int) -> List[str]:
    row = get_user(user_id)
    if not row:
        return []
    try:
        return json.loads(row["watchlist"] or "[]")
    except Exception:
        return []

def save_watchlist(user_id: int, items: List[str]) -> None:
    with db() as conn:
        conn.execute("UPDATE users SET watchlist=?, last_seen=? WHERE user_id=?", (json.dumps(items[:30]), now_iso(), user_id))
        conn.commit()

def add_watch(user_id: int, symbol: str) -> bool:
    wl = get_watchlist(user_id)
    s = normalize_symbol(symbol)
    if s not in wl:
        wl.append(s)
        save_watchlist(user_id, wl)
        return True
    return False

def remove_watch(user_id: int, symbol: str) -> bool:
    wl = get_watchlist(user_id)
    s = normalize_symbol(symbol)
    if s in wl:
        wl.remove(s)
        save_watchlist(user_id, wl)
        return True
    return False

def record_referral(user_id: int, referrer: int) -> None:
    if user_id == referrer:
        return
    with db() as conn:
        row = conn.execute("SELECT referrer FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row and row["referrer"] is None:
            conn.execute("UPDATE users SET referrer=? WHERE user_id=?", (referrer, user_id))
            conn.execute("UPDATE users SET referrals=COALESCE(referrals,0)+1 WHERE user_id=?", (referrer,))
            conn.commit()

# =============================================================================
# UI
# =============================================================================
def tr(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in T else "en"
    text = T[lang].get(key, T["en"].get(key, key))
    return text.format(**kwargs)

def lang_name(code: str) -> str:
    return LANGS.get(code, code)

def base_name(code: str) -> str:
    return {"TMN":"تومان", "IRR":"ریال", "USD":"USD", "EUR":"EUR", "GBP":"GBP", "TRY":"TRY", "RUB":"RUB", "AED":"AED"}.get(code, code)

def main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    lang = get_lang(user_id)
    rows = [
        [InlineKeyboardButton(tr(lang, "prices"), callback_data="menu:prices"), InlineKeyboardButton(tr(lang, "charts"), callback_data="menu:charts")],
        [InlineKeyboardButton(tr(lang, "language"), callback_data="menu:lang"), InlineKeyboardButton(tr(lang, "base"), callback_data="menu:base")],
        [InlineKeyboardButton(tr(lang, "support"), callback_data="menu:support"), InlineKeyboardButton(tr(lang, "watchlist"), callback_data="menu:watch")],
        [InlineKeyboardButton(tr(lang, "alerts"), callback_data="menu:alerts"), InlineKeyboardButton(tr(lang, "movers"), callback_data="menu:movers")],
    ]
    if admin_only(user_id):
        rows.append([InlineKeyboardButton(tr(lang, "admin"), callback_data="menu:admin")])
    return InlineKeyboardMarkup(rows)

def language_keyboard() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for code in LANG_ORDER:
        row.append(InlineKeyboardButton(lang_name(code), callback_data=f"lang:{code}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️", callback_data="menu:back")])
    return InlineKeyboardMarkup(rows)

def base_keyboard() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for code in BASE_CURRENCIES:
        row.append(InlineKeyboardButton(base_name(code), callback_data=f"base:{code}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️", callback_data="menu:back")])
    return InlineKeyboardMarkup(rows)

def chart_keyboard(symbol: str, lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(tr(lang, "chart_line"), callback_data=f"charttype:line:{symbol}"), InlineKeyboardButton(tr(lang, "chart_candle"), callback_data=f"charttype:candle:{symbol}")],
        [InlineKeyboardButton(tr(lang, "chart_1h"), callback_data=f"charttf:1h:{symbol}"), InlineKeyboardButton(tr(lang, "chart_24h"), callback_data=f"charttf:24h:{symbol}")],
        [InlineKeyboardButton(tr(lang, "chart_7d"), callback_data=f"charttf:7d:{symbol}"), InlineKeyboardButton(tr(lang, "chart_30d"), callback_data=f"charttf:30d:{symbol}")],
        [InlineKeyboardButton(tr(lang, "chart_1y"), callback_data=f"charttf:1y:{symbol}")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="menu:back")],
    ]
    return InlineKeyboardMarkup(rows)

def price_actions_keyboard(symbol: str, lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(tr(lang, "refresh"), callback_data=f"refresh:{symbol}"), InlineKeyboardButton(tr(lang, "add_watch"), callback_data=f"watch:add:{symbol}")],
        [InlineKeyboardButton(tr(lang, "set_alert"), callback_data=f"alert:prompt:{symbol}"), InlineKeyboardButton(tr(lang, "charts"), callback_data=f"menu:chartpick:{symbol}")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="menu:back")],
    ]
    return InlineKeyboardMarkup(rows)

def support_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(lang, "add_support"), callback_data="menu:support")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="menu:back")],
    ])

def admin_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats", callback_data="admin:stats"), InlineKeyboardButton("👥 Users", callback_data="admin:users")],
        [InlineKeyboardButton("💬 Tickets", callback_data="admin:tickets"), InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast")],
        [InlineKeyboardButton("⏱ Schedule", callback_data="admin:schedule"), InlineKeyboardButton("⭐ VIP", callback_data="admin:vip")],
        [InlineKeyboardButton("🔒 Ban", callback_data="admin:ban"), InlineKeyboardButton("✅ Unban", callback_data="admin:unban")],
        [InlineKeyboardButton("♻️ Reset", callback_data="admin:reset"), InlineKeyboardButton("⬅️", callback_data="menu:back")],
    ])

def movers_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(lang, "top_gainers"), callback_data="movers:gainers"), InlineKeyboardButton(tr(lang, "top_losers"), callback_data="movers:losers")],
        [InlineKeyboardButton(tr(lang, "back"), callback_data="menu:back")],
    ])

# =============================================================================
# Normalization / parsing
# =============================================================================
def normalize_text(text: str) -> str:
    text = text.replace("‌", " ").replace("＋", "+")
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def strip_token(token: str) -> str:
    return token.strip("`'\".,;:!?()[]{}<>")

def normalize_symbol(s: str) -> str:
    q = strip_token(s).replace("‌", "").upper().replace(" ", "")
    q = q.replace("-", "/")
    if q in ALIASES:
        return ALIASES[q]
    return q

def resolve_alias_phrase(text: str) -> str:
    raw = normalize_text(text)
    low = raw.lower()

    if low in ALIASES:
        return ALIASES[low]

    tokens = [strip_token(t) for t in re.split(r"[\s,]+", raw) if strip_token(t)]
    tokens = [t for t in tokens if t.lower() not in PRICE_WORDS and t != "+"]
    if not tokens:
        return ""

    # explicit pair
    for tok in tokens:
        nt = normalize_symbol(tok)
        if "/" in nt:
            return nt

    # last meaningful token
    for tok in reversed(tokens):
        nt = normalize_symbol(tok)
        if nt in FIAT_CODES or nt in {"USD","USDT","TMN","IRR"} or nt in METALS or nt in ALIASES.values() or re.fullmatch(r"[A-Z0-9.\-]{2,15}", nt):
            return nt

    joined = " ".join(x.lower() for x in tokens)
    if joined in ALIASES:
        return ALIASES[joined]

    return normalize_symbol(tokens[-1])

def is_finance_like(text: str) -> bool:
    q = resolve_alias_phrase(text)
    if not q:
        return False
    if "/" in q:
        a, b = q.split("/", 1)
        return bool(a and b)
    return bool(re.fullmatch(r"[A-Z0-9.\-]{2,18}", q)) or q in FIAT_CODES or q in {"USD","USDT","TMN","IRR"} or q in METALS

def parse_amount_conversion(text: str) -> Optional[Tuple[float, str, str]]:
    t = normalize_text(text)
    m = re.fullmatch(r"(?i)\s*([0-9]+(?:\.[0-9]+)?)\s+(.+?)\s+(?:to|=>|=)\s+(.+?)\s*", t)
    if not m:
        return None
    amount = float(m.group(1))
    src = resolve_alias_phrase(m.group(2))
    dst = resolve_alias_phrase(m.group(3))
    if not src or not dst:
        return None
    return amount, src, dst

def parse_alert_rule(text: str) -> Optional[Tuple[str, str, float]]:
    t = normalize_text(text)
    m = re.fullmatch(r"(?i)\s*([0-9]+(?:\.[0-9]+)?)\s+(.+?)\s*([<>]=?|==|=)\s*([0-9]+(?:\.[0-9]+)?)\s*", t)
    if not m:
        return None
    # left amount not used; expect something like BTC > 120000
    return None

def parse_simple_alert(text: str) -> Optional[Tuple[str, str, float]]:
    t = normalize_text(text)
    m = re.fullmatch(r"(?i)\s*(.+?)\s*([<>]=?|==|=)\s*([0-9]+(?:\.[0-9]+)?)\s*", t)
    if not m:
        return None
    sym = resolve_alias_phrase(m.group(1))
    if not sym:
        return None
    op = m.group(2)
    target = float(m.group(3))
    return sym, op, target

# =============================================================================
# Public APIs / data sources
# =============================================================================
REQUEST_TIMEOUT = 12
FX_CACHE: Dict[str, Tuple[float, dict]] = {}
COINSEARCH_CACHE: Dict[str, Tuple[float, list]] = {}
PRICE_CACHE: Dict[str, Tuple[float, float]] = {}
CACHE_TTL = 45.0
LONG_CACHE_TTL = 300.0

def _cache_get(cache: Dict[str, Tuple[float, Any]], key: str, ttl: float):
    item = cache.get(key)
    if not item:
        return None
    ts, val = item
    if time.time() - ts > ttl:
        cache.pop(key, None)
        return None
    return val

def _cache_set(cache: Dict[str, Tuple[float, Any]], key: str, value: Any):
    cache[key] = (time.time(), value)

def http_json(url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> Optional[dict]:
    try:
        r = requests.get(url, params=params, headers=headers or {"User-Agent": "RateLy/1.0"}, timeout=REQUEST_TIMEOUT)
        if r.ok:
            return r.json()
    except Exception as e:
        log.warning("HTTP error %s: %s", url, e)
    return None

def fiat_rates_usd() -> Dict[str, float]:
    cached = _cache_get(FX_CACHE, "usd_rates", LONG_CACHE_TTL)
    if cached:
        return cached
    data = http_json("https://open.er-api.com/v6/latest/USD")
    if data and data.get("result") == "success" and isinstance(data.get("rates"), dict):
        rates = {k.upper(): float(v) for k, v in data["rates"].items() if isinstance(v, (int, float)) or str(v).replace(".", "", 1).isdigit()}
        _cache_set(FX_CACHE, "usd_rates", rates)
        return rates
    return {}

def fiat_to_usd(code: str) -> Optional[float]:
    code = code.upper()
    if code == "USD":
        return 1.0
    rates = fiat_rates_usd()
    if code in rates and rates[code]:
        return float(rates[code])
    # fallback to yfinance
    for t in [f"{code}USD=X", f"USD{code}=X"]:
        px = yfinance_last_close(t)
        if px:
            if t.startswith(code):
                return float(px)
            if px != 0:
                return 1 / float(px)
    return None

def yfinance_last_close(ticker: str) -> Optional[float]:
    key = f"last:{ticker}"
    cached = _cache_get(PRICE_CACHE, key, CACHE_TTL)
    if cached is not None:
        return cached
    try:
        df = yf.Ticker(ticker).history(period="1d", interval="1m", auto_adjust=False)
        if df is not None and not df.empty and "Close" in df:
            s = df["Close"].dropna()
            if not s.empty:
                px = float(s.iloc[-1])
                _cache_set(PRICE_CACHE, key, px)
                return px
    except Exception as e:
        log.warning("yfinance error %s: %s", ticker, e)
    return None

def coingecko_search(query: str) -> list:
    key = f"search:{query.lower()}"
    cached = _cache_get(COINSEARCH_CACHE, key, LONG_CACHE_TTL)
    if cached:
        return cached
    data = http_json("https://api.coingecko.com/api/v3/search", params={"query": query})
    coins = (data or {}).get("coins", []) or []
    _cache_set(COINSEARCH_CACHE, key, coins)
    return coins

def coingecko_simple_price(ids: list[str]) -> dict:
    ids = [i for i in ids if i]
    if not ids:
        return {}
    data = http_json("https://api.coingecko.com/api/v3/simple/price", params={"ids": ",".join(ids), "vs_currencies": "usd", "include_24hr_change": "true"})
    return data or {}

def coingecko_coin_id_for(query: str) -> Optional[str]:
    q = query.lower().strip()
    # direct symbol/name search
    coins = coingecko_search(q)
    if not coins:
        return None
    exact = [c for c in coins if (c.get("symbol","").lower() == q or c.get("name","").lower() == q)]
    pool = exact or coins
    pool.sort(key=lambda x: (x.get("market_cap_rank") or 10**9))
    return pool[0].get("id")

def nobitex_market_stats(src: str, dst: str) -> Optional[dict]:
    src = src.lower()
    dst = dst.lower()
    key = f"nobitex:{src}:{dst}"
    cached = _cache_get(PRICE_CACHE, key, CACHE_TTL)
    if cached is not None:
        return {"latest": cached}
    url = "https://apiv2.nobitex.ir/market/stats"
    data = http_json(url, params={"srcCurrency": src, "dstCurrency": dst})
    if data and data.get("status") == "ok":
        stats = data.get("stats", {})
        # choose first market entry
        if isinstance(stats, dict) and stats:
            first = next(iter(stats.values()))
            latest = first.get("latest") or first.get("dayClose") or first.get("mark") or first.get("bestSell")
            if latest:
                try:
                    latest_f = float(latest)
                    _cache_set(PRICE_CACHE, key, latest_f)
                    return first
                except Exception:
                    pass
    return None

def nobitex_pair_price(src: str, dst: str) -> Optional[float]:
    stats = nobitex_market_stats(src, dst)
    if not stats:
        return None
    for field in ["latest", "dayClose", "mark", "bestSell", "bestBuy"]:
        if field in stats and stats[field] is not None:
            try:
                return float(stats[field])
            except Exception:
                continue
    return None

def resolve_crypto_usd(symbol: str) -> Optional[float]:
    s = symbol.upper()
    # try Nobitex in iranian markets for common assets
    for pair in [(s.lower(), "usdt"), (s.lower(), "rls")]:
        try:
            px = nobitex_pair_price(pair[0], pair[1])
            if px:
                if pair[1] == "usdt":
                    return float(px)
                if pair[1] == "rls":
                    return float(px)
        except Exception:
            pass

    # common symbols from CoinGecko
    cid = None
    if s in {"BTC", "BITCOIN"}:
        cid = "bitcoin"
    elif s in {"ETH", "ETHEREUM"}:
        cid = "ethereum"
    elif s in {"USDT", "TETHER"}:
        cid = "tether"
    elif s in {"BNB"}:
        cid = "binancecoin"
    elif s in {"XRP"}:
        cid = "ripple"
    elif s in {"SOL"}:
        cid = "solana"
    elif s in {"DOGE"}:
        cid = "dogecoin"
    elif s in {"ADA"}:
        cid = "cardano"
    elif s in {"TON"}:
        cid = "the-open-network"
    elif s in {"TRX"}:
        cid = "tron"
    elif s in {"LTC"}:
        cid = "litecoin"
    elif s in {"DOT"}:
        cid = "polkadot"
    elif s in {"AVAX"}:
        cid = "avalanche-2"
    elif s in {"LINK"}:
        cid = "chainlink"
    elif s in {"MATIC", "POL"}:
        cid = "polygon"
    elif s in {"SHIB"}:
        cid = "shiba-inu"
    elif s in {"PEPE"}:
        cid = "pepe"
    elif s in {"XLM"}:
        cid = "stellar"
    elif s in {"BCH"}:
        cid = "bitcoin-cash"
    elif s in {"ATOM"}:
        cid = "cosmos"
    elif s in {"NEAR"}:
        cid = "near"
    elif s in {"SUI"}:
        cid = "sui"
    elif s in {"APT"}:
        cid = "aptos"
    else:
        cid = coingecko_coin_id_for(s) or coingecko_coin_id_for(symbol)

    if cid:
        data = coingecko_simple_price([cid]).get(cid, {})
        if data and "usd" in data:
            try:
                return float(data["usd"])
            except Exception:
                pass

    # fallback on yfinance
    for t in [f"{s}-USD", f"{s}USD=X", f"{s}USDT=X"]:
        px = yfinance_last_close(t)
        if px:
            return float(px)
    return None

def metal_usd_per_ounce(symbol: str) -> Optional[float]:
    s = symbol.upper()
    ticker_map = {
        "XAU": "XAUUSD=X", "GOLD": "XAUUSD=X",
        "XAG": "XAGUSD=X", "SILVER": "XAGUSD=X",
        "XPT": "PL=F", "PLATINUM": "PL=F",
        "XPD": "PA=F", "PALLADIUM": "PA=F",
    }
    t = ticker_map.get(s)
    if not t:
        return None
    return yfinance_last_close(t)

def last_price_in_usd(query: str) -> Optional[float]:
    q = resolve_alias_phrase(query)
    if not q:
        return None
    q = normalize_symbol(q)

    if q == "USD":
        return 1.0
    if q == "TMN":
        irr = fiat_to_usd("IRR")
        return irr / 10.0 if irr else None
    if q == "IRR":
        return fiat_to_usd("IRR")
    if q in FIAT_CODES:
        return fiat_to_usd(q)
    if q in METALS:
        return metal_usd_per_ounce(q)
    if q == "CL=F":
        return yfinance_last_close("CL=F")
    if q in {"BTC","ETH","USDT","BNB","XRP","SOL","DOGE","ADA","TON","TRX","LTC","DOT","AVAX","LINK","MATIC","SHIB","PEPE","XLM","BCH","ATOM","NEAR","APT","SUI"}:
        return resolve_crypto_usd(q)

    # generic pair or one-token crypto
    base, quote = parse_pair(q)
    if quote:
        if base in FIAT_CODES and quote in FIAT_CODES:
            br = fiat_to_usd(base)
            qr = fiat_to_usd(quote)
            if br and qr:
                return br / qr
        if base in {"BTC","ETH","USDT","BNB","XRP","SOL","DOGE","ADA","TON","TRX","LTC","DOT","AVAX","LINK","MATIC","SHIB","PEPE","XLM","BCH","ATOM","NEAR","APT","SUI"}:
            return resolve_crypto_usd(base)
        px = nobitex_pair_price(base.lower(), quote.lower())
        if px:
            return float(px)
        t = f"{base}{quote}=X"
        px = yfinance_last_close(t)
        if px:
            return float(px)
        inv = f"{quote}{base}=X"
        px = yfinance_last_close(inv)
        if px:
            return 1 / float(px)
        return None

    # try search-based crypto
    coin_id = coingecko_coin_id_for(q)
    if coin_id:
        data = coingecko_simple_price([coin_id]).get(coin_id, {})
        if data and "usd" in data:
            return float(data["usd"])

    # maybe commodity/metal by yfinance ticker
    px = metal_usd_per_ounce(q)
    if px:
        return float(px)

    return None

def market_class(query: str) -> str:
    q = resolve_alias_phrase(query)
    if not q:
        return "unknown"
    q = normalize_symbol(q)
    if q in FIAT_CODES or q in {"USD", "IRR", "TMN"}:
        return "fiat"
    if q in METALS or q in {"CL=F"}:
        return "metal"
    if q in {"BTC","ETH","USDT","BNB","XRP","SOL","DOGE","ADA","TON","TRX","LTC","DOT","AVAX","LINK","MATIC","SHIB","PEPE","XLM","BCH","ATOM","NEAR","APT","SUI"}:
        return "crypto"
    if "/" in q:
        a, b = q.split("/", 1)
        if a in FIAT_CODES and b in FIAT_CODES:
            return "fiatpair"
    return "crypto"

def display_value_from_usd(usd: float, base: str) -> Optional[float]:
    base = base.upper()
    if base == "USD":
        return usd
    if base == "TMN":
        irr = fiat_to_usd("IRR")
        if irr:
            return usd / (irr / 10.0)
        return None
    if base == "IRR":
        irr = fiat_to_usd("IRR")
        if irr:
            return usd / irr
        return None
    rate = fiat_to_usd(base)
    if rate:
        return usd / rate
    return None

def format_money(val: float, currency: str) -> str:
    if currency == "TMN":
        return f"{val:,.0f} تومان"
    if currency == "IRR":
        return f"{val:,.0f} ریال"
    if currency in {"USD", "EUR", "GBP", "TRY", "RUB", "AED"}:
        return f"{val:,.4f} {currency}" if abs(val) < 1000 else f"{val:,.2f} {currency}"
    return f"{val:,.4f} {currency}"

def human_symbol(query: str) -> str:
    q = resolve_alias_phrase(query)
    return normalize_symbol(q or query)

def format_price_message(query: str, lang: str, base_currency: str) -> Tuple[str, str]:
    symbol = human_symbol(query)
    usd = last_price_in_usd(query)
    if usd is None:
        return tr(lang, "price_not_found", symbol=symbol), symbol

    cls = market_class(query)
    lines = [f"*{symbol}*"]
    if cls == "crypto":
        lines.append(f"USD: {format_money(usd, 'USD')}")
    elif cls == "fiat":
        if symbol == "USD":
            lines.append("1 USD = 1 USD")
        elif symbol == "IRR":
            lines.append(f"1 USD = {format_money(usd, 'IRR')}")
        elif symbol == "TMN":
            lines.append(f"1 USD = {format_money(usd, 'TMN')}")
        else:
            lines.append(f"1 {symbol} = {format_money(usd, 'USD')}")
    elif cls == "fiatpair":
        base, quote = symbol.split("/", 1)
        lines.append(f"1 {base} = {usd:,.6f} {quote}")
    elif cls == "metal":
        lines.append(f"USD/oz: {format_money(usd, 'USD')}")
        per_gram = usd / 31.1034768
        lines.append(f"USD/g: {format_money(per_gram, 'USD')}")
    else:
        lines.append(f"USD: {format_money(usd, 'USD')}")

    disp = display_value_from_usd(usd, base_currency)
    if disp is not None and base_currency != "USD":
        lines.append(f"{base_name(base_currency)}: {format_money(disp, base_currency)}")
    return "\n".join(lines), symbol

def convert_value(amount: float, source: str, target: str) -> Optional[Tuple[float, str]]:
    source = normalize_symbol(source)
    target = normalize_symbol(target)

    # convert source to USD
    src_usd = None
    if source in {"USD"}:
        src_usd = 1.0
    elif source in {"TMN"}:
        irr = fiat_to_usd("IRR")
        if irr:
            src_usd = irr / 10.0
    elif source in {"IRR"}:
        src_usd = fiat_to_usd("IRR")
    elif source in FIAT_CODES:
        src_usd = fiat_to_usd(source)
    elif source in METALS:
        src_usd = metal_usd_per_ounce(source)
    else:
        src_usd = last_price_in_usd(source)
    if src_usd is None:
        return None

    usd_amount = amount * src_usd
    # convert USD to target
    if target == "USD":
        return usd_amount, "USD"
    if target == "TMN":
        val = display_value_from_usd(usd_amount, "TMN")
        return (val, "TMN") if val is not None else None
    if target == "IRR":
        val = display_value_from_usd(usd_amount, "IRR")
        return (val, "IRR") if val is not None else None
    if target in FIAT_CODES:
        rate = fiat_to_usd(target)
        if rate:
            return usd_amount / rate, target
        return None
    if target in METALS:
        m = metal_usd_per_ounce(target)
        if m:
            return usd_amount / m, target
        return None
    if target in {"BTC","ETH","USDT","BNB","XRP","SOL","DOGE","ADA","TON","TRX","LTC","DOT","AVAX","LINK","MATIC","SHIB","PEPE","XLM","BCH","ATOM","NEAR","APT","SUI"}:
        p = resolve_crypto_usd(target)
        if p:
            return usd_amount / p, target
        return None
    # generic crypto by search
    p = last_price_in_usd(target)
    if p:
        return usd_amount / p, target
    return None

# =============================================================================
# Charts
# =============================================================================
def chart_history(ticker: str, timeframe: str) -> pd.DataFrame:
    mapping = {
        "1h": ("1d", "5m"),
        "24h": ("1d", "5m"),
        "7d": ("7d", "30m"),
        "30d": ("1mo", "1d"),
        "1y": ("1y", "1d"),
    }
    period, interval = mapping.get(timeframe, ("7d", "30m"))
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        log.warning("history error %s: %s", ticker, e)
        return pd.DataFrame()

def make_chart(query: str, chart_type: str = "line", timeframe: str = "7d") -> Optional[BytesIO]:
    q = resolve_alias_phrase(query)
    if not q:
        return None
    q = normalize_symbol(q)

    ticker = None
    if q in {"BTC","ETH","USDT","BNB","XRP","SOL","DOGE","ADA","TON","TRX","LTC","DOT","AVAX","LINK","MATIC","SHIB","PEPE","XLM","BCH","ATOM","NEAR","APT","SUI"}:
        ticker = f"{q}-USD"
    elif q in METALS:
        ticker = {"XAU":"XAUUSD=X","XAG":"XAGUSD=X","XPT":"PL=F","XPD":"PA=F"}[q]
    elif q in FIAT_CODES:
        if q == "USD":
            return None
        ticker = f"{q}USD=X"
    elif "/" in q:
        a, b = q.split("/", 1)
        ticker = f"{a}{b}=X"
    else:
        ticker = q if "=" in q or q.endswith("-USD") else f"{q}-USD"

    df = chart_history(ticker, timeframe)
    if df.empty or "Close" not in df:
        return None
    title = f"{human_symbol(q)} | {chart_type.upper()} | {timeframe}"
    if chart_type == "candle":
        need = {"Open", "High", "Low", "Close"}
        if not need.issubset(set(df.columns)):
            return None
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        if df.empty:
            return None
        fig = plt.figure(figsize=(11, 5))
        ax = fig.add_subplot(111)
        for i, (_, row) in enumerate(df.iterrows()):
            o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
            color = "#2ca02c" if c >= o else "#d62728"
            ax.vlines(i, l, h, color=color, linewidth=1.1)
            bottom = min(o, c)
            height = max(abs(c - o), (h - l) * 0.01)
            ax.add_patch(plt.Rectangle((i - 0.3, bottom), 0.6, height, facecolor=color, edgecolor=color, alpha=0.85))
        step = max(len(df) // 10, 1)
        idxs = list(range(0, len(df), step))
        labels = [df.index[i].strftime("%m-%d %H:%M") if hasattr(df.index[i], "strftime") else str(df.index[i]) for i in idxs]
        ax.set_xticks(idxs)
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_title(title)
        ax.set_xlabel("Time")
        ax.set_ylabel("Price")
        fig.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=160)
        plt.close(fig)
        buf.seek(0)
        return buf

    fig = plt.figure(figsize=(11, 5))
    ax = fig.add_subplot(111)
    ax.plot(df.index, df["Close"])
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel("Price")
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf

# =============================================================================
# Top movers
# =============================================================================
def coingecko_markets() -> List[dict]:
    key = "cg_markets"
    cached = _cache_get(FX_CACHE, key, 180.0)
    if cached:
        return cached
    data = http_json(
        "https://api.coingecko.com/api/v3/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        },
    )
    markets = data or []
    _cache_set(FX_CACHE, key, markets)
    return markets

def top_movers(kind: str) -> List[dict]:
    rows = coingecko_markets()
    items = []
    for r in rows:
        pct = r.get("price_change_percentage_24h")
        if pct is None:
            pct = r.get("price_change_percentage_24h_in_currency")
        if pct is None:
            continue
        items.append({
            "name": r.get("name") or r.get("symbol") or "",
            "symbol": (r.get("symbol") or "").upper(),
            "pct": float(pct),
            "price": float(r.get("current_price") or 0),
        })
    if kind == "gainers":
        items.sort(key=lambda x: x["pct"], reverse=True)
    else:
        items.sort(key=lambda x: x["pct"])
    return items[:10]

# =============================================================================
# Small talk
# =============================================================================
def maybe_small_talk(text: str, lang: str) -> Optional[str]:
    t = normalize_text(text).lower()
    if any(x in t for x in ["سلام", "salam", "hello", "hi", "hey", "مرحبا", "привет", "merhaba", "hola"]):
        return tr(lang, "greet")
    if any(x in t for x in ["مرسی", "ممنون", "thanks", "thank you", "شکرم", "teşekkür", "спасибо", "gracias"]):
        return tr(lang, "thanks")
    if any(x in t for x in ["خداحافظ", "bye", "goodbye", "فعلا", "görüşürüz", "пока"]):
        return tr(lang, "bye")
    return None

# =============================================================================
# Helpers
# =============================================================================
def ad_text(lang: str) -> str:
    if not ADS_TEXT:
        return ""
    return f"🪧 *{tr(lang, 'ad_label')}*\n{ADS_TEXT}"

def maybe_show_ad(chat_id: int, lang: str, context: ContextTypes.DEFAULT_TYPE, req_count: int) -> None:
    if ADS_TEXT and ADS_EVERY > 0 and req_count % ADS_EVERY == 0:
        try:
            context.bot.send_message(chat_id=chat_id, text=ad_text(lang), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            log.warning("ad failed: %s", e)

def parse_duration_to_seconds(text: str) -> Optional[int]:
    m = re.fullmatch(r"(\d+)([smhd])", text.strip().lower())
    if not m:
        return None
    n = int(m.group(1))
    return n * {"s":1, "m":60, "h":3600, "d":86400}[m.group(2)]

def schedule_broadcast(run_at: datetime, message: str, created_by: int) -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO scheduled_broadcasts (run_at, message, created_by, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (run_at.isoformat(), message, created_by, now_iso()),
        )
        conn.commit()
        return int(cur.lastrowid)

def due_jobs() -> List[sqlite3.Row]:
    with db() as conn:
        return conn.execute("SELECT * FROM scheduled_broadcasts WHERE status='pending' AND run_at <= ? ORDER BY run_at ASC LIMIT 10", (now_iso(),)).fetchall()

def mark_job_done(job_id: int) -> None:
    with db() as conn:
        conn.execute("UPDATE scheduled_broadcasts SET status='done' WHERE id=?", (job_id,))
        conn.commit()

# =============================================================================
# Sending messages
# =============================================================================
async def send_price_and_chart(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, chart_type: str = "line", timeframe: str = "7d") -> None:
    if not update.effective_user or not update.effective_message or not update.effective_chat:
        return
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.effective_message.reply_text(tr(get_lang(user_id), "admin_only"))
        return
    lang = get_lang(user_id)
    base = get_base(user_id)
    req = inc_request(user_id)
    text, symbol = format_price_message(query, lang, base)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=price_actions_keyboard(symbol, lang))
    chart = await asyncio.to_thread(make_chart, query, chart_type, timeframe)
    if chart:
        await update.effective_message.reply_photo(photo=chart, caption=f"{symbol} | {chart_type.upper()} | {timeframe}", reply_markup=chart_keyboard(symbol, lang))
    maybe_show_ad(update.effective_chat.id, lang, context, req)

async def send_chart_only(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, chart_type: str = "line", timeframe: str = "7d") -> None:
    if not update.effective_user or not update.effective_message or not update.effective_chat:
        return
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.effective_message.reply_text(tr(get_lang(user_id), "admin_only"))
        return
    lang = get_lang(user_id)
    req = inc_request(user_id)
    sym = human_symbol(query)
    chart = await asyncio.to_thread(make_chart, query, chart_type, timeframe)
    if not chart:
        await update.effective_message.reply_text(tr(lang, "chart_not_found", symbol=sym))
        return
    await update.effective_message.reply_photo(photo=chart, caption=f"{sym} | {chart_type.upper()} | {timeframe}", reply_markup=chart_keyboard(sym, lang))
    maybe_show_ad(update.effective_chat.id, lang, context, req)

async def show_watchlist(update: Update, user_id: int) -> None:
    lang = get_lang(user_id)
    wl = get_watchlist(user_id)
    if not wl:
        await update.effective_message.reply_text(tr(lang, "watch_empty"), reply_markup=main_keyboard(user_id))
        return
    lines = [tr(lang, "watch_header")]
    for s in wl[:20]:
        usd = last_price_in_usd(s)
        if usd is None:
            lines.append(f"• {s} — ?")
            continue
        lines.append(f"• {s} — {format_money(usd, 'USD')}")
    await update.effective_message.reply_text("\n".join(lines), reply_markup=main_keyboard(user_id))

async def show_alerts(update: Update, user_id: int) -> None:
    lang = get_lang(user_id)
    with db() as conn:
        rows = conn.execute("SELECT * FROM alerts WHERE user_id=? AND active=1 ORDER BY id DESC LIMIT 20", (user_id,)).fetchall()
    if not rows:
        await update.effective_message.reply_text(tr(lang, "alert_empty"), reply_markup=main_keyboard(user_id))
        return
    lines = [tr(lang, "alert_header")]
    for r in rows:
        lines.append(f"• {r['symbol']} {r['operator']} {r['target']}")
    await update.effective_message.reply_text("\n".join(lines), reply_markup=main_keyboard(user_id))

async def show_movers(update: Update, user_id: int, kind: str) -> None:
    lang = get_lang(user_id)
    items = top_movers(kind)
    title = tr(lang, "top_gainers") if kind == "gainers" else tr(lang, "top_losers")
    lines = [title]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {item['symbol']} {item['pct']:+.2f}%  ${item['price']:,.4f}")
    await update.effective_message.reply_text("\n".join(lines), reply_markup=movers_keyboard(lang))

# =============================================================================
# Commands
# =============================================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    ensure_user(update.effective_user)
    user_id = update.effective_user.id
    lang = get_lang(user_id)

    if context.args:
        arg = context.args[0].strip()
        if arg.startswith("ref_") and arg[4:].isdigit():
            record_referral(user_id, int(arg[4:]))

    text = f"{tr(lang, 'welcome')}\n\n{tr(lang, 'choose_lang')}\n{tr(lang, 'choose_base')}\n{tr(lang, 'quick')}\n\n{tr(lang, 'group_hint')}"
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(user_id))

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    lang = get_lang(update.effective_user.id)
    await update.effective_message.reply_text(f"{tr(lang, 'help')}\n\n{tr(lang, 'conversion_hint')}\n\n{tr(lang, 'feedback_hint')}", parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(update.effective_user.id))

async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if context.args and context.args[0].lower() in LANGS:
        new_lang = context.args[0].lower()
        set_lang(uid, new_lang)
        await update.effective_message.reply_text(tr(new_lang, "lang_saved", lang=lang_name(new_lang)), reply_markup=main_keyboard(uid))
        return
    await update.effective_message.reply_text(tr(lang, "choose_lang"), reply_markup=language_keyboard())

async def cmd_base(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if context.args and context.args[0].upper() in BASE_CURRENCIES:
        b = context.args[0].upper()
        set_base(uid, b)
        await update.effective_message.reply_text(tr(lang, "base_saved", base=base_name(b)), reply_markup=main_keyboard(uid))
        return
    await update.effective_message.reply_text(tr(lang, "choose_base"), reply_markup=base_keyboard())

async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "help"), reply_markup=main_keyboard(update.effective_user.id))
        return
    await send_price_and_chart(update, context, " ".join(context.args))

async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    if not context.args:
        lang = get_lang(update.effective_user.id)
        await update.effective_message.reply_text(tr(lang, "choose_chart"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(lang, "back"), callback_data="menu:back")]]))
        return
    sym = context.args[0]
    tf = context.args[1] if len(context.args) > 1 else "7d"
    await send_chart_only(update, context, sym, "line", tf)

async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if is_banned(uid):
        await update.effective_message.reply_text(tr(lang, "admin_only"))
        return
    if not context.args:
        await update.effective_message.reply_text(tr(lang, "support_intro"), reply_markup=support_keyboard(lang))
        return
    message = " ".join(context.args).strip()
    with db() as conn:
        cur = conn.execute("INSERT INTO tickets (user_id, kind, question, status, created_at) VALUES (?, 'support', ?, 'open', ?)", (uid, message, now_iso()))
        tid = cur.lastrowid
        conn.commit()
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=f"🆘 Ticket #{tid}\nUser: `{uid}`\nName: {update.effective_user.full_name}\nLang: {lang}\nMessage:\n{message}\n\nReply: `/reply {tid} your message`", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            log.warning("notify admin failed: %s", e)
    await update.effective_message.reply_text(tr(lang, "support_saved", tid=tid))

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
        uid = int(row["user_id"])
        conn.execute("UPDATE tickets SET status='closed', answer=?, answered_at=? WHERE id=?", (message, now_iso(), tid))
        conn.commit()
    try:
        await context.bot.send_message(chat_id=uid, text=f"💬 Reply to ticket #{tid}:\n{message}")
        await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "reply_sent", tid=tid))
    except Exception as e:
        await update.effective_message.reply_text(f"Failed: {e}")

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not admin_only(uid):
        await update.effective_message.reply_text(tr(lang, "admin_only"))
        return
    await update.effective_message.reply_text(tr(lang, "panel"), reply_markup=admin_keyboard(lang))

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    lang = get_lang(update.effective_user.id)
    await update.effective_message.reply_text(tr(lang, "stats", **stats()), reply_markup=admin_keyboard(lang))

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
    lang = get_lang(update.effective_user.id)
    await update.effective_message.reply_text(tr(lang, "user_info", uid=uid, name=row["first_name"] or "", username=f"@{row['username']}" if row["username"] else "-", lang=row["lang"], base=row["base_currency"], premium="YES" if row["premium"] else "NO", requests=row["requests"], refs=row["referrals"], last_seen=row["last_seen"] or "-"))

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /ban <user_id>")
        return
    uid = int(context.args[0])
    set_ban(uid, 1)
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "ban_done", uid=uid))

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /unban <user_id>")
        return
    uid = int(context.args[0])
    set_ban(uid, 0)
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "unban_done", uid=uid))

async def cmd_vip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /vip <user_id> on|off")
        return
    uid = int(context.args[0])
    mode = context.args[1].lower()
    if mode in {"on","1","yes","true"}:
        set_premium(uid, 1)
        await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "vip_on", uid=uid))
    else:
        set_premium(uid, 0)
        await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "vip_off", uid=uid))

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message or not admin_only(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /reset <user_id>")
        return
    uid = int(context.args[0])
    reset_user(uid)
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
    jid = schedule_broadcast(run_at, msg, update.effective_user.id)
    await update.effective_message.reply_text(tr(get_lang(update.effective_user.id), "scheduled_done", when=run_at.isoformat()) + f"\nJob #{jid}")

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    await update.effective_message.reply_text(str(update.effective_user.id))

async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not context.args:
        await show_watchlist(update, uid)
        return
    action = context.args[0].lower()
    if len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /watch add BTC | /watch remove BTC")
        return
    sym = context.args[1]
    if action == "add":
        if add_watch(uid, sym):
            await update.effective_message.reply_text(tr(lang, "watch_added", symbol=human_symbol(sym)), reply_markup=main_keyboard(uid))
        else:
            await update.effective_message.reply_text(human_symbol(sym))
    elif action in {"remove", "del", "delete"}:
        if remove_watch(uid, sym):
            await update.effective_message.reply_text(tr(lang, "watch_removed", symbol=human_symbol(sym)), reply_markup=main_keyboard(uid))
        else:
            await update.effective_message.reply_text(human_symbol(sym))
    else:
        await update.effective_message.reply_text("Usage: /watch add BTC | /watch remove BTC")

async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    if not context.args:
        await show_alerts(update, uid)
        return
    rule = parse_simple_alert(" ".join(context.args))
    if not rule:
        await update.effective_message.reply_text("Usage: /alert BTC > 120000")
        return
    sym, op, target = rule
    with db() as conn:
        conn.execute("INSERT INTO alerts (user_id, symbol, operator, target, active, created_at) VALUES (?, ?, ?, ?, 1, ?)", (uid, sym, op, float(target), now_iso()))
        conn.commit()
    await update.effective_message.reply_text(tr(lang, "alert_added", rule=f"{sym} {op} {target}"), reply_markup=main_keyboard(uid))

async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    await show_alerts(update, update.effective_user.id)

# =============================================================================
# Background alerts / scheduled broadcasts
# =============================================================================
ALERT_BOT = None
PTB_APP: Optional[Application] = None

async def process_due_jobs():
    for job in due_jobs():
        message = job["message"]
        with db() as conn:
            users = [r["user_id"] for r in conn.execute("SELECT user_id FROM users WHERE banned=0").fetchall()]
        sent = failed = 0
        for uid in users:
            try:
                await ALERT_BOT.send_message(chat_id=uid, text=message)
                sent += 1
            except Exception:
                failed += 1
        mark_job_done(int(job["id"]))
        log.info("Scheduled broadcast #%s done: sent=%s failed=%s", job["id"], sent, failed)

async def process_due_alerts():
    with db() as conn:
        rows = conn.execute("SELECT * FROM alerts WHERE active=1 ORDER BY id ASC LIMIT 100").fetchall()
    for r in rows:
        sym = r["symbol"]
        op = r["operator"]
        target = float(r["target"])
        uid = int(r["user_id"])
        price = last_price_in_usd(sym)
        if price is None:
            continue
        ok = False
        if op == ">":
            ok = price > target
        elif op == ">=":
            ok = price >= target
        elif op == "<":
            ok = price < target
        elif op == "<=":
            ok = price <= target
        elif op in {"=", "=="}:
            ok = abs(price - target) / (target or 1) < 0.0001
        if ok:
            lang = get_lang(uid)
            base = get_base(uid)
            msg = f"🔔 {human_symbol(sym)} hit {op} {target}\n{format_money(price, 'USD')}"
            if base != "USD":
                disp = display_value_from_usd(price, base)
                if disp is not None:
                    msg += f"\n{format_money(disp, base)}"
            try:
                await ALERT_BOT.send_message(chat_id=uid, text=msg, reply_markup=main_keyboard(uid))
                with db() as conn:
                    conn.execute("UPDATE alerts SET active=0, last_notified=? WHERE id=?", (now_iso(), int(r["id"])))
                    conn.commit()
            except Exception:
                pass

def background_loop():
    while True:
        try:
            if ALERT_BOT is not None:
                asyncio.run(process_due_jobs())
                asyncio.run(process_due_alerts())
        except Exception as e:
            log.warning("background loop error: %s", e)
        time.sleep(30)

# =============================================================================
# Callbacks
# =============================================================================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query or not update.effective_user or not update.effective_message:
        return
    q = update.callback_query
    uid = update.effective_user.id
    lang = get_lang(uid)
    await q.answer()
    data = q.data or ""

    if data == "menu:back":
        await q.edit_message_text(tr(lang, "welcome"), parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:prices":
        await q.edit_message_text(f"{tr(lang, 'help')}\n\n{tr(lang, 'conversion_hint')}", parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data == "menu:charts":
        await q.edit_message_text(tr(lang, "choose_chart"), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tr(lang, "chart_line"), callback_data="chartpreset:line:7d:BTC"), InlineKeyboardButton(tr(lang, "chart_candle"), callback_data="chartpreset:candle:7d:BTC")],
            [InlineKeyboardButton(tr(lang, "back"), callback_data="menu:back")],
        ]))
        return
    if data == "menu:lang":
        await q.edit_message_text(tr(lang, "choose_lang"), reply_markup=language_keyboard())
        return
    if data == "menu:base":
        await q.edit_message_text(tr(lang, "choose_base"), reply_markup=base_keyboard())
        return
    if data == "menu:support":
        await q.edit_message_text(tr(lang, "support_intro"), reply_markup=support_keyboard(lang))
        set_pending(uid, "support", "")
        return
    if data == "menu:watch":
        await show_watchlist(update, uid)
        return
    if data == "menu:alerts":
        await show_alerts(update, uid)
        return
    if data == "menu:movers":
        await q.edit_message_text(tr(lang, "top_gainers"), reply_markup=movers_keyboard(lang))
        return
    if data == "menu:admin":
        if not admin_only(uid):
            await q.edit_message_text(tr(lang, "admin_only"))
            return
        await q.edit_message_text(tr(lang, "panel"), reply_markup=admin_keyboard(lang))
        return
    if data == "menu:chartpick:BTC":
        await q.edit_message_text(tr(lang, "choose_chart"), reply_markup=chart_keyboard("BTC", lang))
        return

    if data.startswith("lang:"):
        new_lang = data.split(":", 1)[1]
        if new_lang in LANGS:
            set_lang(uid, new_lang)
            await q.edit_message_text(tr(new_lang, "lang_saved", lang=lang_name(new_lang)), reply_markup=main_keyboard(uid))
        return
    if data.startswith("base:"):
        base = data.split(":", 1)[1]
        if base in BASE_CURRENCIES:
            set_base(uid, base)
            await q.edit_message_text(tr(lang, "base_saved", base=base_name(base)), reply_markup=main_keyboard(uid))
        return
    if data.startswith("refresh:"):
        sym = data.split(":", 1)[1]
        await send_price_and_chart(update, context, sym)
        return
    if data.startswith("watch:add:"):
        sym = data.split(":", 2)[2]
        if add_watch(uid, sym):
            await q.edit_message_text(tr(lang, "watch_added", symbol=human_symbol(sym)), reply_markup=main_keyboard(uid))
        else:
            await q.edit_message_text(human_symbol(sym), reply_markup=main_keyboard(uid))
        return
    if data.startswith("alert:prompt:"):
        sym = data.split(":", 2)[2]
        set_pending(uid, "alert", sym)
        await q.edit_message_text(f"Send alert like:\n`{human_symbol(sym)} > 120000`", parse_mode=ParseMode.MARKDOWN, reply_markup=main_keyboard(uid))
        return
    if data.startswith("charttype:") or data.startswith("charttf:") or data.startswith("chartpreset:"):
        parts = data.split(":")
        if parts[0] == "charttype" and len(parts) >= 3:
            ctype = parts[1]
            sym = ":".join(parts[2:])
            await send_chart_only(update, context, sym, ctype, "7d")
            return
        if parts[0] == "charttf" and len(parts) >= 3:
            tf = parts[1]
            sym = ":".join(parts[2:])
            await send_chart_only(update, context, sym, "line", tf)
            return
        if parts[0] == "chartpreset" and len(parts) >= 4:
            ctype = parts[1]
            tf = parts[2]
            sym = ":".join(parts[3:])
            await send_chart_only(update, context, sym, ctype, tf)
            return

    if data.startswith("movers:"):
        kind = data.split(":", 1)[1]
        await show_movers(update, uid, kind)
        return

    if data.startswith("admin:"):
        if not admin_only(uid):
            await q.edit_message_text(tr(lang, "admin_only"))
            return
        action = data.split(":", 1)[1]
        if action == "stats":
            await q.edit_message_text(tr(lang, "stats", **stats()), reply_markup=admin_keyboard(lang))
        elif action == "users":
            with db() as conn:
                rows = conn.execute("SELECT * FROM users ORDER BY last_seen DESC LIMIT 10").fetchall()
            text = "\n".join([f"{r['user_id']} | {r['first_name']} | {('@'+r['username']) if r['username'] else '-'} | {r['lang']} | {r['base_currency']} | VIP:{r['premium']} | req:{r['requests']}" for r in rows]) or "No users."
            await q.edit_message_text(text, reply_markup=admin_keyboard(lang))
        elif action == "tickets":
            with db() as conn:
                rows = conn.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 10").fetchall()
            text = "\n".join([f"#{r['id']} | u{r['user_id']} | {r['status']} | {r['created_at']}" for r in rows]) or "No tickets."
            await q.edit_message_text(text, reply_markup=admin_keyboard(lang))
        elif action == "broadcast":
            await q.edit_message_text("Use /broadcast <message>\nOr /broadcastin 10m <message>", reply_markup=admin_keyboard(lang))
        elif action == "schedule":
            await q.edit_message_text("Use /broadcastin 10m <message>\nExample: /broadcastin 2h hello", reply_markup=admin_keyboard(lang))
        elif action == "vip":
            await q.edit_message_text("Use /vip <user_id> on|off", reply_markup=admin_keyboard(lang))
        elif action == "ban":
            await q.edit_message_text("Use /ban <user_id>", reply_markup=admin_keyboard(lang))
        elif action == "unban":
            await q.edit_message_text("Use /unban <user_id>", reply_markup=admin_keyboard(lang))
        elif action == "reset":
            await q.edit_message_text("Use /reset <user_id>", reply_markup=admin_keyboard(lang))
        return

async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    lang = get_lang(uid)
    text = update.effective_message.text or ""
    mode, data = pending_mode(uid)
    if mode == "support":
        set_pending(uid, "", "")
        await cmd_support(update, context)
        return
    if mode == "alert":
        rule = parse_simple_alert(text)
        if rule:
            sym, op, target = rule
            with db() as conn:
                conn.execute("INSERT INTO alerts (user_id, symbol, operator, target, active, created_at) VALUES (?, ?, ?, ?, 1, ?)", (uid, sym, op, float(target), now_iso()))
                conn.commit()
            await update.effective_message.reply_text(tr(lang, "alert_added", rule=f"{sym} {op} {target}"), reply_markup=main_keyboard(uid))
            set_pending(uid, "", "")
            return
    conv = parse_amount_conversion(text)
    if conv:
        amount, src, dst = conv
        result = convert_value(amount, src, dst)
        if result:
            value, target = result
            await update.effective_message.reply_text(f"{amount:g} {src} = {format_money(value, target)}", reply_markup=main_keyboard(uid))
            return
    talk = maybe_small_talk(text, lang)
    if talk:
        await update.effective_message.reply_text(talk, reply_markup=main_keyboard(uid))
        return
    if is_finance_like(text):
        await send_price_and_chart(update, context, text)
        return
    await update.effective_message.reply_text(tr(lang, "unknown"), reply_markup=main_keyboard(uid))

# =============================================================================
# Scheduler worker
# =============================================================================
async def send_scheduled_jobs():
    for job in due_jobs():
        msg = job["message"]
        sent = failed = 0
        with db() as conn:
            user_ids = [r["user_id"] for r in conn.execute("SELECT user_id FROM users WHERE banned=0").fetchall()]
        for uid in user_ids:
            try:
                await ALERT_BOT.send_message(chat_id=uid, text=msg)
                sent += 1
            except Exception:
                failed += 1
        mark_job_done(int(job["id"]))
        log.info("job %s sent=%s failed=%s", job["id"], sent, failed)

async def send_alerts():
    with db() as conn:
        rows = conn.execute("SELECT * FROM alerts WHERE active=1 ORDER BY id ASC LIMIT 300").fetchall()
    for r in rows:
        sym = r["symbol"]
        op = r["operator"]
        target = float(r["target"])
        uid = int(r["user_id"])
        price = last_price_in_usd(sym)
        if price is None:
            continue
        ok = False
        if op == ">":
            ok = price > target
        elif op == ">=":
            ok = price >= target
        elif op == "<":
            ok = price < target
        elif op == "<=":
            ok = price <= target
        elif op in {"=", "=="}:
            ok = abs(price - target) / max(target, 1e-9) < 0.0005
        if ok:
            lang = get_lang(uid)
            base = get_base(uid)
            msg = f"🔔 {human_symbol(sym)} {op} {target}\nUSD: {format_money(price, 'USD')}"
            if base != "USD":
                d = display_value_from_usd(price, base)
                if d is not None:
                    msg += f"\n{base_name(base)}: {format_money(d, base)}"
            try:
                await ALERT_BOT.send_message(chat_id=uid, text=msg, reply_markup=main_keyboard(uid))
                with db() as conn:
                    conn.execute("UPDATE alerts SET active=0, last_notified=? WHERE id=?", (now_iso(), int(r["id"])))
                    conn.commit()
            except Exception:
                pass

def background_worker():
    while True:
        try:
            if ALERT_BOT is not None:
                asyncio.run(send_scheduled_jobs())
                asyncio.run(send_alerts())
        except Exception as e:
            log.warning("background error: %s", e)
        time.sleep(30)

# =============================================================================
# Build app / web
# =============================================================================
def build_app() -> Application:
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CommandHandler("base", cmd_base))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("chart", cmd_chart))
    app.add_handler(CommandHandler("support", cmd_support))
    app.add_handler(CommandHandler("reply", cmd_reply))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("user", cmd_user))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("vip", cmd_vip))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("broadcastin", cmd_broadcastin))
    app.add_handler(CommandHandler("watch", cmd_watch))
    app.add_handler(CommandHandler("alert", cmd_alert))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_unknown))
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))
    return app

def run_bot():
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    global PTB_APP, ALERT_BOT
    PTB_APP = build_app()
    ALERT_BOT = PTB_APP.bot
    log.info("Bot starting...")
    PTB_APP.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None, close_loop=False)

@app.get("/")
def home():
    return jsonify(ok=True, name=APP_TITLE, bot_username=BOT_USERNAME, time=now_iso())

@app.get("/health")
def health():
    return jsonify(ok=True)

def main():
    init_db()
    threading.Thread(target=run_bot, daemon=True).start()
    threading.Thread(target=background_worker, daemon=True).start()
    log.info("Web server on port %s", PORT)
    serve(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
