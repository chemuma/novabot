import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
import database as db
import states
from handlers import start, customer_menu


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def build_app():
    db.init_db()

    app = Application.builder().token(config.BOT_TOKEN).build()

    # ---------- /start و ثبت‌نام ----------
    onboarding_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start.start)],
        states={
            states.ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, start.receive_name)],
            states.ASK_PHONE: [
                MessageHandler(filters.CONTACT, start.receive_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, start.receive_phone),
            ],
        },
        fallbacks=[CommandHandler("cancel", start.cancel_onboarding)],
    )
    app.add_handler(onboarding_conv)

    # ---------- ویرایش نام ----------
    edit_name_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{config.BTN_EDIT_NAME}$"), customer_menu.edit_name_start)],
        states={
            states.WAIT_NEW_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, customer_menu.edit_name_receive)
            ],
        },
        fallbacks=[CommandHandler("cancel", customer_menu.edit_name_cancel)],
    )
    app.add_handler(edit_name_conv)

    # ---------- دکمه‌های ثابت منوی اصلی ----------
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_HELP}$"), customer_menu.help_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_CONTACT}$"), customer_menu.contact_cafe_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_MENU_GUIDE}$"), customer_menu.menu_guide_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_TRACK_ORDER}$"), customer_menu.track_order_handler))

    return app


if __name__ == "__main__":
    application = build_app()
    logger.info("ربات کافه نُوا (فاز ۱) در حال اجراست...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
