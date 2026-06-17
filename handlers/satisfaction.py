from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, ContextTypes

import config
import database as db
import helpers
import states


STARS = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]


def _rating_keyboard(satisfaction_id):
    row = [
        InlineKeyboardButton(str(i), callback_data=f"sat_rate_{satisfaction_id}_{i}")
        for i in range(1, 6)
    ]
    return InlineKeyboardMarkup([row])


def _followup_keyboard(satisfaction_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📷/📝 ارسال", callback_data=f"sat_send_{satisfaction_id}"),
            InlineKeyboardButton("⏭ رد کردن", callback_data=f"sat_skip_{satisfaction_id}"),
        ]
    ])


# ====== شروع فلو بعد از تحویل سفارش ======

async def send_rating_request(bot, order_id, customer_chat_id):
    existing = db.get_satisfaction_by_order(order_id)
    if existing is None:
        satisfaction_id = db.create_satisfaction_entry(order_id, db.get_order(order_id)["user_id"])
    else:
        satisfaction_id = existing["id"]

    await bot.send_message(
        chat_id=customer_chat_id,
        text="لطفاً به سفارشت امتیاز بده ⭐ تا ⭐⭐⭐⭐⭐",
        reply_markup=_rating_keyboard(satisfaction_id),
    )


# ====== منوی «⭐ ثبت رضایت» ======

async def satisfaction_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if user is None:
        await update.message.reply_text("اطلاعات شما یافت نشد. لطفاً /start را بزن.")
        return

    unrated = db.get_unrated_orders(user["id"])
    if not unrated:
        await update.message.reply_text(
            "سفارشی برای ثبت رضایت نداری 🙂", reply_markup=helpers.main_menu_keyboard()
        )
        return

    buttons = []
    for order in unrated:
        sat = db.get_satisfaction_by_order(order["id"])
        if sat is None:
            sat_id = db.create_satisfaction_entry(order["id"], user["id"])
        else:
            sat_id = sat["id"]
        buttons.append([
            InlineKeyboardButton(
                f"⭐ ثبت امتیاز برای سفارش {order['display_number']}",
                callback_data=f"sat_open_{sat_id}",
            )
        ])

    await update.message.reply_text(
        "برای کدوم سفارش می‌خوای رضایتت رو ثبت کنی؟",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def open_satisfaction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    satisfaction_id = int(query.data.split("_")[-1])
    await query.answer()
    await query.message.reply_text(
        "لطفاً به سفارشت امتیاز بده ⭐ تا ⭐⭐⭐⭐⭐",
        reply_markup=_rating_keyboard(satisfaction_id),
    )


# ====== ثبت امتیاز ======

async def rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    satisfaction_id = int(parts[2])
    rating = int(parts[3])

    db.update_satisfaction_rating(satisfaction_id, rating)
    await query.answer("ممنون از نظرت! 🙏")

    await query.edit_message_text(
        f"امتیاز ثبت شد: {STARS[rating - 1]}\n\n"
        "مایل هستی متن یا عکس سفارشت رو ارسال کنی؟ (تخفیف داره!)",
        reply_markup=_followup_keyboard(satisfaction_id),
    )


# ====== ادامه با متن/عکس یا رد کردن ======

async def content_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("ممنون از وقتت 🙏 منتظر سفارش بعدیت هستیم ☕")


async def content_send_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    satisfaction_id = int(query.data.split("_")[-1])
    context.user_data["satisfaction_id"] = satisfaction_id

    await query.answer()
    await query.edit_message_text(
        "📷 یک عکس یا 📝 یک متن از تجربه‌ت با کافه نُوا برامون بفرست:"
    )
    return states.WAIT_SATISFACTION_CONTENT


async def receive_satisfaction_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    satisfaction_id = context.user_data.get("satisfaction_id")
    if satisfaction_id is None:
        return ConversationHandler.END

    sat = db.get_satisfaction_by_id(satisfaction_id)
    order = db.get_order(sat["order_id"])
    user = db.get_user_by_id(sat["user_id"])

    photo_file_id = None
    comment = None

    if update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
        comment = update.message.caption
    elif update.message.text:
        comment = update.message.text.strip()
    else:
        await update.message.reply_text("لطفاً یک متن یا عکس ارسال کن، یا /cancel برای انصراف:")
        return states.WAIT_SATISFACTION_CONTENT

    db.update_satisfaction_content(satisfaction_id, comment=comment, photo_file_id=photo_file_id)

    # ── ارسال به گروه رضایت مشتری ──
    rating = sat["rating"] or 0
    stars = STARS[rating - 1] if 1 <= rating <= 5 else "—"
    group_text = (
        f"⭐ نظر جدید\n"
        f"👤 {user['name']}\n"
        f"امتیاز: {stars}\n"
        f"سفارش: {order['display_number']}"
    )
    if comment:
        group_text += f"\n\n📝 {comment}"

    like_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👍 پسند — تخفیف بده", callback_data=f"sat_like_{satisfaction_id}")]
    ])

    try:
        msg = await helpers.safe_send(
            context.bot,
            helpers.get_satisfaction_group_id,
            photo=photo_file_id if photo_file_id else None,
            text=group_text if not photo_file_id else None,
            caption=group_text if photo_file_id else None,
            reply_markup=like_kb if photo_file_id else None,
        )
        db.set_satisfaction_group_message(satisfaction_id, msg.message_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"خطا در ارسال رضایت به گروه: {e}")

    await update.message.reply_text(
        "ممنون از وقتت! نظرت برامون خیلی ارزشمنده 🙏", reply_markup=helpers.main_menu_keyboard()
    )
    context.user_data.pop("satisfaction_id", None)
    return ConversationHandler.END


async def cancel_satisfaction_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("satisfaction_id", None)
    await update.message.reply_text("ارسال نظر لغو شد.", reply_markup=helpers.main_menu_keyboard())
    return ConversationHandler.END


# ====== لایک ادمین در گروه رضایت → تخفیف خودکار ======

async def admin_like_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    telegram_id = update.effective_user.id

    if not (db.is_admin(telegram_id) or db.is_owner(telegram_id)):
        await query.answer("⛔️ شما دسترسی به این بخش را ندارید.", show_alert=True)
        return

    satisfaction_id = int(query.data.split("_")[-1])
    sat = db.get_satisfaction_by_id(satisfaction_id)

    if sat is None:
        await query.answer("یافت نشد.", show_alert=True)
        return

    if sat["liked_by_admin"]:
        await query.answer("قبلاً تخفیف برای این مشتری ارسال شده ✅", show_alert=True)
        return

    user = db.get_user_by_id(sat["user_id"])
    percent = int(db.get_setting("satisfaction_discount_percent", "5"))

    code = helpers.generate_discount_code(percent=percent, capacity=1, expiry_date=None)
    db.mark_satisfaction_liked(satisfaction_id)

    await query.answer("✅ کد تخفیف ساخته و برای مشتری ارسال شد")

    try:
        if query.message.photo:
            new_caption = (query.message.caption or "") + "\n\n🎁 تخفیف ویژه برای این مشتری ارسال شد ✅"
            await query.edit_message_caption(caption=new_caption, reply_markup=None)
        else:
            new_text = (query.message.text or "") + "\n\n🎁 تخفیف ویژه برای این مشتری ارسال شد ✅"
            await query.edit_message_text(text=new_text, reply_markup=None)
    except Exception:
        pass

    if user:
        await context.bot.send_message(
            chat_id=user["telegram_id"],
            text=(
                f"🎉 مدیر کافه نُوا از عکس/نظرت خوشش اومد!\n"
                f"یک کد تخفیف {percent}٪ ویژه برات داریم:\n\n"
                f"🎟 {code}\n\n"
                "این کد رو موقع ثبت سفارش بعدی در سبد خریدت وارد کن."
            ),
        )
