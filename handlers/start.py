from telegram import ReplyKeyboardRemove, Update
from telegram.ext import ConversationHandler, ContextTypes

import config
import database as db
import helpers
import states


WELCOME_NEW_USER = (
    "👋 سلام! به کافه «نُوا» خوش اومدی ☕\n\n"
    "از اینجا می‌تونی سفارشت رو ثبت کنی، از تخفیف‌ها استفاده کنی و عضو باشگاه مشتریان نُوا بشی.\n\n"
    "برای اینکه بتونیم سفارش‌هات رو پیگیری کنیم و در صورت نیاز باهات تماس بگیریم، "
    "لازمه اسم و شماره تماستو داشته باشیم. این اطلاعات فقط برای اطلاع‌رسانی سفارش استفاده می‌شه.\n\n"
    "اول بگو چی صدات کنیم؟ (اسم یا اسم مستعار، هر چی دوست داری 🙂)"
)

WELCOME_OWNER = (
    "👑 سلام مدیر عزیز!\n"
    "به پنل مدیریت کافه «نُوا» خوش اومدید.\n"
    "از منوی پایین می‌تونید همه چیز رو مدیریت کنید."
)

WELCOME_BACK = "👋 سلام مجدد! خوش برگشتی به کافه «نُوا» ☕"


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
        f"خیلی خوب، {name}! حالا لطفاً با دکمه زیر شماره تماستو برای ما ارسال کن 📱",
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
        f"عالی شد {user['name']} جان! ثبت‌نام شما با موفقیت انجام شد ✅\n"
        "حالا می‌تونی از منوی پایین استفاده کنی.",
        reply_markup=helpers.main_menu_keyboard(),
    )
    return ConversationHandler.END


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ثبت‌نام لغو شد. هر وقت خواستی دوباره با /start شروع کن.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END
