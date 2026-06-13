from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

import database as db
import helpers
from handlers import order


async def discount_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اگر کاربر در حال وارد کردن کد تخفیف برای سبد خریده، این پیام رو پردازش کن."""
    if not context.user_data.get("awaiting_discount_code"):
        return

    code = update.message.text.strip().upper()
    context.user_data["awaiting_discount_code"] = False

    telegram_id = update.effective_user.id
    user = db.get_or_create_user(telegram_id)

    if not helpers.validate_discount_checksum(code):
        await update.message.reply_text("❌ کد تخفیف نامعتبر یا منقضی شده است")
        raise ApplicationHandlerStop

    code_row = db.get_discount_code(code)
    cart_items_count = order.sum_cart_items(user["id"])

    if not helpers.is_discount_code_usable(code_row, cart_items_count):
        await update.message.reply_text("❌ کد تخفیف نامعتبر یا منقضی شده است")
        raise ApplicationHandlerStop

    context.user_data["cart_discount"] = code
    await update.message.reply_text(f"✅ کد تخفیف {code_row['discount_percent']}٪ با موفقیت اعمال شد")
    await order.send_cart(update.message, user["id"], context)
    raise ApplicationHandlerStop


async def discount_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data["awaiting_discount_code"] = False
    await query.answer("لغو شد")
    try:
        await query.message.delete()
    except Exception:
        pass
