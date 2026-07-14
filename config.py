import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Bir nechta admin bo'lishi mumkin, vergul bilan ajratilgan: 123456789,987654321
_admin_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_raw.split(",") if x.strip()]

DB_PATH = os.getenv("DB_PATH", "shop.db")

CATEGORIES = {
    "erkak": "👨 Erkak",
    "ayol": "👩 Ayol",
    "unisex": "⚪ Unisex",
}

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. .env faylini tekshiring (config.py)")

if not ADMIN_IDS:
    print("OGOHLANTIRISH: ADMIN_IDS bo'sh. Hech kim admin buyruqlarini ishlata olmaydi.")
