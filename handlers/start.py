from telegram import ReplyKeyboardRemove, Update
from telegram.ext import ConversationHandler, ContextTypes

import config
import database as db
import helpers
import states


WELCOME_NEW_USER = (
    "👋 سلام! من نُوام — دستیار سفارش کافه نُوا ☕\n\n"
    "اینجام تا سفارش گرفتن رو برات راحت کنم، تخفیف اعمال کنم و "
    "وضعیت سفارشت رو بهت اطلاع بدم.\n\n"
    "برای اینکه بتونم سفارشت رو دقیق ثبت کنم، به اسم و شمارت نیاز دارم "
    "— فقط برای همین استفاده می‌شه، قول می‌دم 🙂\n\n"
    "اول بگو چی صدات کنم؟ (اسم یا هر اسم مستعاری قبوله)"
)

WELCOME_OWNER = (
    "👑 سلام مدیر!\n"
    "به پنل مدیریت نُوا خوش اومدی.\n"
    "از منوی پایین می‌تونی همه چیز رو مدیریت کنی."
)

WELCOME_BACK = "👋 سلام! خوش برگشتی ☕ چی می‌خوری؟"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)

    if user is None or user["name"] is None or user["phone"] is None:
        db.get_or_create_user(telegram_id)
        await update.message.reply_text(WELCOME_NEW_USER, reply_markup=ReplyKeyboardRemove())
        return states.ASK_NAME

    if db.is_owner(telegram_id):
        await update.message.reply_text(WELCOME_OWNER, reply_markup=helpers.owner_menu_keyboard())
        return ConversationHandler.END

    await update.message.reply_text(WELCOME_BACK, reply_markup=helpers.main_menu_keyboard())
    return ConversationHandler.END


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("لطفاً یک نام معتبر وارد کن:")
        return states.ASK_NAME

    telegram_id = update.effective_user.id
    db.update_user_info(telegram_id, name=name)

    await update.message.reply_text(
        f"خوشحالم {name}! حالا شمارت رو با دکمه زیر برام بفرست 📱\n"
        "(این شماره فقط موقع تحویل سفارش استفاده می‌شه)",
        reply_markup=helpers.contact_request_keyboard(),
    )
    return states.ASK_PHONE


async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    if update.message.contact is None:
        await update.message.reply_text(
            "لطفاً از دکمه «📱 ارسال شماره تماس» استفاده کن:",
            reply_markup=helpers.contact_request_keyboard(),
        )
        return states.ASK_PHONE

    phone = update.message.contact.phone_number
    db.update_user_info(telegram_id, phone=phone)

    if db.is_owner(telegram_id):
        await update.message.reply_text(WELCOME_OWNER, reply_markup=helpers.owner_menu_keyboard())
        return ConversationHandler.END

    user = db.get_user(telegram_id)
    await update.message.reply_text(
        f"آماده‌ام {user['name']} جان! ✅\n"
        "هر وقت خواستی سفارش بده، منم اینجام ☕",
        reply_markup=helpers.main_menu_keyboard(),
    )
    return ConversationHandler.END


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ثبت‌نام لغو شد. هر وقت خواستی دوباره با /start شروع کن.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END
