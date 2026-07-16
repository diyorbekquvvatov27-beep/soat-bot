import logging
import re

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, ADMIN_IDS, CATEGORIES, CHANNEL_USERNAME, CHANNEL_URL
import db

# Telefon raqami formati: +998 bilan boshlanib, keyin 9 ta raqam (masalan +998901234567)
PHONE_PATTERN = re.compile(r"^\+998\d{9}$")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- Conversation states ----------
# Admin: mahsulot qo'shish
A_NAME, A_CATEGORY, A_BRAND, A_PRICE, A_PHOTO, A_DESC, A_CONFIRM = range(7)
# Mijoz: buyurtma berish
O_NAME, O_PHONE = range(100, 102)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ============================================================
#                     MIJOZ QISMI — KATALOG
# ============================================================

async def is_subscribed(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramError as e:
        logger.warning(f"Obunani tekshirib bo'lmadi: {e}")
        # Tekshirib bo'lmasa (masalan bot kanalda admin emas), bloklab qo'ymaymiz
        return True


def _subscribe_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=CHANNEL_URL)],
            [InlineKeyboardButton("✅ Obuna bo'ldim", callback_data="check_sub")],
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await is_subscribed(context, user_id):
        await update.message.reply_text(
            "👋 Assalomu alaykum! Bizning soatlar do'konimizga xush kelibsiz.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🛍 Katalog ko'rish", callback_data="back:categories")]]
            ),
        )
    else:
        await update.message.reply_text(
            "👋 Assalomu alaykum!\n\n"
            "Katalogni ko'rish uchun avval kanalimizga obuna bo'ling, "
            "so'ng \"✅ Obuna bo'ldim\" tugmasini bosing:",
            reply_markup=_subscribe_keyboard(),
        )


async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    if await is_subscribed(context, user_id):
        await query.answer("✅ Obuna tasdiqlandi!")
        await query.edit_message_text(
            "🛍 Katalog ko'rish uchun tugmani bosing:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🛍 Katalog ko'rish", callback_data="back:categories")]]
            ),
        )
    else:
        await query.answer("❌ Hali obuna bo'lmagansiz. Avval kanalga obuna bo'ling.", show_alert=True)


async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Endi kategoriya emas — to'g'ridan-to'g'ri brendlar ro'yxatini ko'rsatadi (katalog ildizi)."""
    query = update.callback_query
    await query.answer()
    await _render_brand_list(update, context)


async def _send_text_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, keyboard: InlineKeyboardMarkup):
    """Joriy xabarni matnli ekranga almashtiradi. Agar joriy xabar rasm (media) bo'lsa,
    tahrirlab bo'lmaydi — o'chirib, yangi matnli xabar yuboriladi."""
    query = update.callback_query
    try:
        await query.edit_message_text(text, reply_markup=keyboard)
    except TelegramError:
        try:
            await query.delete_message()
        except Exception:
            pass
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=keyboard)


async def _render_brand_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    brands = db.get_all_brands()

    if not brands:
        await _send_text_screen(
            update, context,
            "Hozircha katalogda mahsulot yo'q.",
            InlineKeyboardMarkup([]),
        )
        return

    keyboard = [[InlineKeyboardButton(b, callback_data=f"brand:{b}")] for b in brands]
    keyboard.append([InlineKeyboardButton("🔍 Barchasini ko'rish", callback_data="brand:__all__")])

    await _send_text_screen(
        update, context,
        "🛍 Katalog — soat nomini (brendini) tanlang:",
        InlineKeyboardMarkup(keyboard),
    )


async def back_to_brands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _render_brand_list(update, context)


async def choose_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    brand = query.data.split(":", 1)[1]

    if brand == "__all__":
        products = db.list_all_products()
    else:
        products = db.get_products_by_brand(brand)

    if not products:
        await query.edit_message_text("Mahsulot topilmadi.")
        return

    context.user_data["products"] = [p["id"] for p in products]
    context.user_data["idx"] = 0

    await send_product_card(update, context, edit=False)


async def send_product_card(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool):
    ids = context.user_data.get("products", [])
    idx = context.user_data.get("idx", 0)
    if not ids:
        return
    product = db.get_product(ids[idx])
    total = len(ids)

    caption = (
        f"⌚ <b>{product['name']}</b>\n"
        f"🏷 Brend: {product['brand']}\n"
        f"💰 Narx: {product['price']:,} so'm\n"
    )
    if product["description"]:
        caption += f"\n{product['description']}\n"
    caption += f"\n📄 {idx + 1}/{total}"

    nav_row = []
    if total > 1:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data="nav:prev"))
        nav_row.append(InlineKeyboardButton("➡️", callback_data="nav:next"))

    keyboard = []
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("🛒 Buyurtma berish", callback_data=f"order:{product['id']}")])
    keyboard.append([InlineKeyboardButton("⬅️ Ortga", callback_data="back:brands")])

    markup = InlineKeyboardMarkup(keyboard)
    media = InputMediaPhoto(media=product["photo_file_id"], caption=caption, parse_mode="HTML")

    query = update.callback_query
    if edit and query:
        await query.edit_message_media(media=media, reply_markup=markup)
    else:
        chat_id = update.effective_chat.id
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=product["photo_file_id"],
            caption=caption,
            parse_mode="HTML",
            reply_markup=markup,
        )
        if query:
            try:
                await query.delete_message()
            except Exception:
                pass


async def navigate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ids = context.user_data.get("products", [])
    if not ids:
        return
    idx = context.user_data.get("idx", 0)
    if query.data == "nav:next":
        idx = (idx + 1) % len(ids)
    else:
        idx = (idx - 1) % len(ids)
    context.user_data["idx"] = idx
    await send_product_card(update, context, edit=True)


# ---------- Buyurtma berish (ConversationHandler) ----------

async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split(":", 1)[1])
    context.user_data["order_product_id"] = product_id

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Ismingizni kiriting:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return O_NAME


async def order_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order_name"] = update.message.text.strip()
    phone_btn = KeyboardButton("📱 Raqamni yuborish", request_contact=True)
    await update.message.reply_text(
        "Telefon raqamingizni yuboring:\n"
        "— pastdagi tugmani bosing, YOKI\n"
        "— +998 bilan boshlab to'liq yozing (masalan: +998901234567)",
        reply_markup=ReplyKeyboardMarkup([[phone_btn]], one_time_keyboard=True, resize_keyboard=True),
    )
    return O_PHONE


async def order_get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
        if not phone.startswith("+"):
            phone = "+" + phone
    else:
        phone = update.message.text.strip().replace(" ", "")
        if not PHONE_PATTERN.match(phone):
            phone_btn = KeyboardButton("📱 Raqamni yuborish", request_contact=True)
            await update.message.reply_text(
                "❌ Noto'g'ri format. Raqam +998 bilan boshlanib, jami 12 ta belgidan "
                "iborat bo'lishi kerak (masalan: +998901234567).\n\n"
                "Qaytadan yuboring yoki tugmani bosing:",
                reply_markup=ReplyKeyboardMarkup([[phone_btn]], one_time_keyboard=True, resize_keyboard=True),
            )
            return O_PHONE

    product_id = context.user_data.get("order_product_id")
    product = db.get_product(product_id)
    buyer_name = context.user_data.get("order_name")
    user = update.effective_user

    db.save_order(product_id, buyer_name, phone, user.username or "", user.id)

    await update.message.reply_text(
        "✅ Buyurtmangiz qabul qilindi! Tez orada operatorimiz siz bilan bog'lanadi.",
        reply_markup=ReplyKeyboardRemove(),
    )

    # Adminlarga xabar
    admin_text = (
        f"🆕 <b>Yangi buyurtma!</b>\n\n"
        f"⌚ Mahsulot: {product['name']} ({product['brand']})\n"
        f"💰 Narx: {product['price']:,} so'm\n\n"
        f"👤 Xaridor: {buyer_name}\n"
        f"📱 Telefon: {phone}\n"
        f"🔗 Username: @{user.username if user.username else '—'}\n"
        f"🆔 Chat ID: {user.id}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=product["photo_file_id"],
                caption=admin_text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Adminga xabar yuborib bo'lmadi ({admin_id}): {e}")

    return ConversationHandler.END


async def order_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Buyurtma bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ============================================================
#                  ADMIN QISMI — MAHSULOT QO'SHISH
# ============================================================

async def admin_only_guard(update: Update) -> bool:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Bu buyruq faqat adminlar uchun.")
        return False
    return True


async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return ConversationHandler.END
    context.user_data["new_product"] = {}
    await update.message.reply_text(
        "🆕 Yangi mahsulot qo'shish.\n\nSoat nomini kiriting (masalan: Casio MTP-1374):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return A_NAME


async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_product"]["name"] = update.message.text.strip()
    keyboard = [[InlineKeyboardButton(v, callback_data=f"acat:{k}")] for k, v in CATEGORIES.items()]
    await update.message.reply_text(
        "Kategoriyani tanlang:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return A_CATEGORY


async def add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split(":", 1)[1]
    context.user_data["new_product"]["category"] = category
    await query.edit_message_text(f"Kategoriya: {CATEGORIES[category]}\n\nBrend nomini kiriting (masalan: Casio):")
    return A_BRAND


async def add_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_product"]["brand"] = update.message.text.strip()
    await update.message.reply_text("Narxini kiriting (faqat raqam, so'mda, masalan: 450000):")
    return A_PRICE


async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(" ", "").replace(",", "")
    if not text.isdigit():
        await update.message.reply_text("❌ Iltimos faqat raqam kiriting (masalan: 450000):")
        return A_PRICE
    context.user_data["new_product"]["price"] = int(text)
    await update.message.reply_text("Endi soatning rasmini yuboring:")
    return A_PHOTO


async def add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Iltimos rasm yuboring:")
        return A_PHOTO
    file_id = update.message.photo[-1].file_id
    context.user_data["new_product"]["photo_file_id"] = file_id
    await update.message.reply_text(
        "Qisqacha tavsif kiriting (yoki o'tkazib yuborish uchun /skip):"
    )
    return A_DESC


async def add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_product"]["description"] = update.message.text.strip()
    return await add_confirm_prompt(update, context)


async def add_desc_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_product"]["description"] = ""
    return await add_confirm_prompt(update, context)


async def add_confirm_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = context.user_data["new_product"]
    caption = (
        f"Tekshiring:\n\n"
        f"⌚ {p['name']}\n"
        f"🏷 {p['brand']} | {CATEGORIES[p['category']]}\n"
        f"💰 {p['price']:,} so'm\n"
        f"📝 {p['description'] or '—'}\n\n"
        f"Saqlaymizmi?"
    )
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Saqlash", callback_data="aconfirm:yes"),
          InlineKeyboardButton("❌ Bekor qilish", callback_data="aconfirm:no")]]
    )
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=p["photo_file_id"],
        caption=caption,
        reply_markup=keyboard,
    )
    return A_CONFIRM


async def add_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "aconfirm:yes":
        p = context.user_data["new_product"]
        pid = db.add_product(
            p["name"], p["category"], p["brand"], p["price"], p["photo_file_id"], p["description"]
        )
        await query.edit_message_caption(caption=f"✅ Saqlandi! (ID: {pid})")
    else:
        await query.edit_message_caption(caption="❌ Bekor qilindi.")
    context.user_data.pop("new_product", None)
    return ConversationHandler.END


async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("new_product", None)
    await update.message.reply_text("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ---------- Boshqa admin buyruqlari ----------

async def list_products_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return
    products = db.list_all_products()
    if not products:
        await update.message.reply_text("Katalog bo'sh.")
        return
    lines = [f"#{p['id']} — {p['name']} | {p['brand']} | {CATEGORIES[p['category']]} | {p['price']:,} so'm" for p in products]
    text = "\n".join(lines)
    # Telegram xabar uzunligi cheklovi uchun bo'lib yuboramiz
    for i in range(0, len(text), 3500):
        await update.message.reply_text(text[i:i + 3500])


async def delete_product_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: /delproduct <id>\nID larni /listproducts orqali ko'ring.")
        return
    try:
        pid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID raqam bo'lishi kerak.")
        return
    db.delete_product(pid)
    await update.message.reply_text(f"O'chirildi: #{pid}")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return
    count = db.count_products()
    await update.message.reply_text(f"📊 Katalogda {count} ta faol mahsulot bor.")


async def cancel_generic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ============================================================
#                          MAIN
# ============================================================

def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # --- Mijoz: katalog navigatsiyasi ---
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_subscription, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(show_categories, pattern="^back:categories$"))
    app.add_handler(CallbackQueryHandler(back_to_brands, pattern="^back:brands$"))
    app.add_handler(CallbackQueryHandler(choose_brand, pattern="^brand:"))
    app.add_handler(CallbackQueryHandler(navigate, pattern="^nav:"))

    # --- Mijoz: buyurtma berish ---
    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_start, pattern="^order:")],
        states={
            O_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_get_name)],
            O_PHONE: [MessageHandler((filters.CONTACT | filters.TEXT) & ~filters.COMMAND, order_get_phone)],
        },
        fallbacks=[CommandHandler("cancel", order_cancel)],
    )
    app.add_handler(order_conv)

    # --- Admin: mahsulot qo'shish ---
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("addproduct", add_product_start)],
        states={
            A_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            A_CATEGORY: [CallbackQueryHandler(add_category, pattern="^acat:")],
            A_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_brand)],
            A_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            A_PHOTO: [MessageHandler(filters.PHOTO, add_photo)],
            A_DESC: [
                CommandHandler("skip", add_desc_skip),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_desc),
            ],
            A_CONFIRM: [CallbackQueryHandler(add_confirm, pattern="^aconfirm:")],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
    )
    app.add_handler(add_conv)

    # --- Admin: qo'shimcha buyruqlar ---
    app.add_handler(CommandHandler("listproducts", list_products_cmd))
    app.add_handler(CommandHandler("delproduct", delete_product_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
