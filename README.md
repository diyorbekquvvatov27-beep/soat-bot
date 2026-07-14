# Soat do'koni — Telegram katalog bot

Mijozlar kategoriya (erkak/ayol/unisex) → brend → mahsulot bo'yicha katalogni ko'rib,
rasm + narxni ko'radi va "Buyurtma berish" tugmasi orqali ism+telefon qoldiradi.
Buyurtma haqida siz (admin) darhol Telegram orqali xabar olasiz.

Mahsulot qo'shish CSV yoki kod yozish orqali emas — botning o'zida, `/addproduct`
buyrug'i bilan amalga oshiriladi (rasmni to'g'ridan-to'g'ri botga yuborasiz).

## 1. Bot yaratish (5 daqiqa)

1. Telegram'da **@BotFather** ni oching
2. `/newbot` yuboring, botga nom va username bering (username `bot` bilan tugashi kerak, masalan `SoatShopBot`)
3. BotFather sizga **token** beradi (masalan `123456:AAH...`) — uni saqlab qo'ying, hech kimga bermang

## 2. O'z Telegram ID'ingizni bilib olish

1. Telegram'da **@userinfobot** ga `/start` yuboring
2. U sizga ID raqamingizni beradi (masalan `123456789`) — bu sizni admin qiladi

## 3. Loyihani sozlash

```bash
# Papkaga o'ting
cd watch_shop_bot

# Virtual muhit yaratish (tavsiya etiladi)
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Kutubxonalarni o'rnatish
pip install -r requirements.txt

# .env faylini yaratish
cp .env.example .env
```

`.env` faylini oching va to'ldiring:

```
BOT_TOKEN=BotFather_bergan_token
ADMIN_IDS=sizning_telegram_id_ingiz
DB_PATH=shop.db
```

Bir nechta admin bo'lsa, vergul bilan yozing: `ADMIN_IDS=111111,222222`

## 4. Lokal test qilish

```bash
python bot.py
```

Konsolda "Bot ishga tushdi..." chiqsa — Telegram'da botingizga `/start` yuboring.

### Mahsulot qo'shish

Botga (admin sifatida) `/addproduct` yuboring va bosqichma-bosqich javob bering:
nomi → kategoriya (tugma) → brend → narx → rasm → tavsif (yoki `/skip`) → tasdiqlash.

Boshqa foydali buyruqlar:
- `/listproducts` — barcha mahsulotlar va ID raqamlari
- `/delproduct <id>` — mahsulotni o'chirish (masalan `/delproduct 5`)
- `/stats` — nechta mahsulot borligi

## 5. Serverga joylashtirish (doim ishlab turishi uchun)

Kompyuteringiz o'chganda bot ham to'xtaydi, shuning uchun uni serverga qo'yish kerak.
Eng oson va arzon yo'llardan biri — kichik VPS (masalan Timeweb, Selectel, yoki Contabo, ~$4-5/oy)
yoki bepul/arzon **Railway.app** / **Render.com** platformalari.

### A) VPS + systemd (Ubuntu) — eng barqaror variant

```bash
# Serverga ulanib, loyihani yuklang (masalan git yoki scp orqali)
sudo apt update && sudo apt install -y python3-venv python3-pip

cd watch_shop_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # BOT_TOKEN va ADMIN_IDS ni to'ldiring
```

Doim ishlab turishi uchun systemd service yarating:

```bash
sudo nano /etc/systemd/system/watchbot.service
```

Quyidagini joylashtiring (yo'llarni o'zingiznikiga moslang):

```ini
[Unit]
Description=Watch Shop Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/watch_shop_bot
ExecStart=/root/watch_shop_bot/venv/bin/python /root/watch_shop_bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Ishga tushirish:

```bash
sudo systemctl daemon-reload
sudo systemctl enable watchbot
sudo systemctl start watchbot

# Holatini tekshirish
sudo systemctl status watchbot

# Loglarni ko'rish
journalctl -u watchbot -f
```

Endi bot server qayta yoqilsa ham avtomatik ishga tushadi.

### B) Railway.app (kod bilan ovora bo'lmasdan tez joylashtirish)

1. Loyihani GitHub'ga yuklang (yangi repo yarating, fayllarni push qiling)
2. [railway.app](https://railway.app) da GitHub bilan kiring
3. "New Project" → "Deploy from GitHub repo" → repongizni tanlang
4. "Variables" bo'limida `BOT_TOKEN` va `ADMIN_IDS` ni qo'shing
5. Railway avtomatik `requirements.txt` ni o'qib botni ishga tushiradi

**Muhim:** `.env` faylini GitHub'ga yuklamang — `.gitignore` fayl yarating:

```
.env
venv/
shop.db
__pycache__/
```

## 6. Katalogni 100+ mahsulotgacha kengaytirish

Kod hech qanday o'zgarishsiz 100+ mahsulotni qo'llab-quvvatlaydi — SQLite bazasi
buning uchun yetarli. Faqat `/addproduct` orqali qo'shishda davom eting.
Agar bir vaqtda ko'p mahsulot qo'shish kerak bo'lsa (masalan Excel'dan), ayting —
bulk import skriptini alohida yozib beraman.

## Muammo yuzaga kelsa

- **Bot javob bermayapti** — token to'g'ri yozilganini va bot ishga tushganini tekshiring (`systemctl status watchbot`)
- **"⛔ Bu buyruq faqat adminlar uchun"** — `.env` dagi `ADMIN_IDS` ichida sizning ID'ingiz borligini tekshiring
- **Rasm yuklanmayapti** — rasmni fayl sifatida emas, oddiy rasm (photo) sifatida yuboring
