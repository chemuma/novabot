from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ConversationHandler, ContextTypes

import config
import database as db
import helpers
import states


HELP_TEXT = (
    "ℹ️ راهنمای ربات کافه «نُوا»\n\n"
    f"{config.BTN_NEW_ORDER}: شروع یک سفارش جدید از منوی کافه\n"
    f"{config.BTN_CART}: مشاهده و مدیریت سبد خریدت\n"
    f"{config.BTN_DISCOUNT}: وارد کردن کد تخفیف\n"
    f"{config.BTN_MENU_GUIDE}: مشاهده کامل منو با قیمت‌ها\n"
    f"{config.BTN_SATISFACTION}: ثبت امتیاز و نظر برای سفارش‌های قبلی\n"
    f"{config.BTN_TRACK_ORDER}: پیگیری وضعیت سفارش فعلی\n"
    f"{config.BTN_CONTACT}: شماره تماس و ساعات کاری کافه\n"
    f"{config.BTN_EDIT_NAME}: تغییر نام یا نام مستعار شما\n\n"
    "هر سوالی داشتی، از دکمه «📞 تماس با کافه» استفاده کن 🙂"
)


# ---------- راهنمای ربات ----------

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, reply_markup=helpers.main_menu_keyboard())


# ---------- تماس با کافه ----------

async def contact_cafe_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = db.get_setting("cafe_phone", "نامشخص")
    open_hour = db.get_setting("open_hour", "؟")
    close_hour = db.get_setting("close_hour", "؟")

    text = (
        "📞 اطلاعات تماس با کافه «نُوا»\n\n"
        f"شماره تماس: {phone}\n"
        f"ساعت کاری: {open_hour} تا {close_hour}\n\n"
        "همیشه خوشحال می‌شیم صداتو بشنویم ☕"
    )
    await update.message.reply_text(text, reply_markup=helpers.main_menu_keyboard())


# ---------- راهنمای منو ----------

async def menu_guide_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categories = db.get_active_categories()
    if not categories:
        await update.message.reply_text(
            "هنوز منویی ثبت نشده. به‌زودی منو رو کامل می‌کنیم 🙏",
            reply_markup=helpers.main_menu_keyboard(),
        )
        return

    for cat in categories:
        products = db.get_active_products_by_category(cat["id"])
        emoji = cat["emoji"] or "🍴"
        lines = [f"{emoji} {cat['name']}\n"]
        if not products:
            lines.append("(در حال حاضر موردی موجود نیست)")
        for p in products:
            desc = f" - {p['description']}" if p["description"] else ""
            lines.append(f"• {p['name']}: {helpers.format_price(p['price'])}{desc}")
        await update.message.reply_text("\n".join(lines))

    await update.message.reply_text(
        "این بود منوی کامل کافه «نُوا» 📖\nبرای سفارش از «🍽 سفارش جدید» استفاده کن.",
        reply_markup=helpers.main_menu_keyboard(),
    )


# ---------- پیگیری سفارش ----------

async def track_order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if user is None:
        await update.message.reply_text("اطلاعات شما یافت نشد. لطفاً /start را بزن.")
        return

    active_orders = db.get_active_orders_for_user(user["id"])
    if not active_orders:
        recent = db.get_user_orders(user["id"], limit=1)
        if not recent:
            await update.message.reply_text(
                "هنوز سفارشی ثبت نکردی 🙂\nبرای شروع از «🍽 سفارش جدید» استفاده کن.",
                reply_markup=helpers.main_menu_keyboard(),
            )
            return
        order = recent[0]
        status_fa = config.STATUS_LABELS_FA.get(order["status"], order["status"])
        await update.message.reply_text(
            f"📦 آخرین سفارش شما: {order['display_number']}\n"
            f"وضعیت: {status_fa}",
            reply_markup=helpers.main_menu_keyboard(),
        )
        return

    lines = ["📦 سفارش‌های فعال شما:\n"]
    for order in active_orders:
        status_fa = config.STATUS_LABELS_FA.get(order["status"], order["status"])
        lines.append(
            f"• {order['display_number']} — وضعیت: {status_fa} — مبلغ: {helpers.format_price(order['total_amount'])}"
        )
        if order["status"] == "PENDING_PREP" and order["ready_estimate"]:
            lines.append(f"  ⏱ زمان تقریبی آماده‌سازی: حدود {order['ready_estimate']} دقیقه")

    await update.message.reply_text("\n".join(lines), reply_markup=helpers.main_menu_keyboard())


# ---------- ویرایش نام ----------

async def edit_name_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "لطفاً نام یا نام مستعار جدیدت رو بفرست:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return states.WAIT_NEW_NAME


async def edit_name_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    if not new_name:
        await update.message.reply_text("لطفاً یک نام معتبر وارد کن:")
        return states.WAIT_NEW_NAME

    telegram_id = update.effective_user.id
    db.update_user_info(telegram_id, name=new_name)

    await update.message.reply_text(
        f"✅ نام شما به «{new_name}» تغییر کرد.",
        reply_markup=helpers.main_menu_keyboard(),
    )
    return ConversationHandler.END


async def edit_name_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ویرایش نام لغو شد.", reply_markup=helpers.main_menu_keyboard()
    )
    return ConversationHandler.END
