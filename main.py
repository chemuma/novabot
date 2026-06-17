"""
نقطه ورود ربات نُوا
"""
import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
import database as db
import states
from scheduler import start_scheduler
from handlers import (
    start,
    customer_menu,
    order,
    discount,
    checkout,
    satisfaction,
    owner_panel,
    order_actions,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.WARNING,
)
logging.getLogger("__main__").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def error_handler(update, context):
    from telegram.error import ChatMigrated
    err = context.error
    if isinstance(err, ChatMigrated):
        # در نسخه‌های مختلف کتابخانه، attribute نام متفاوتی دارد
        new_id = getattr(err, "new_chat_id", None) or getattr(err, "migrate_to_chat_id", None)
        if new_id:
            # نمی‌دانیم کدام گروه migrate شده، هر دو رو آپدیت می‌کنیم
            db.set_setting("orders_group_id_override", str(new_id))
            db.set_setting("satisfaction_group_id_override", str(new_id))
            logger.warning(f"گروه migrate شد → آیدی جدید {new_id} ذخیره شد")
        return
    logger.error(f"خطا: {type(err).__name__}: {err}")


def build_app() -> Application:
    db.init_db()
    db.seed_owners(config.OWNER_IDS)

    app = Application.builder().token(config.BOT_TOKEN).build()

    # ── ۱. ثبت‌نام ──
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

    # ── ۲. ویرایش نام ──
    edit_name_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{config.BTN_EDIT_NAME}$"), customer_menu.edit_name_start)],
        states={
            states.WAIT_NEW_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, customer_menu.edit_name_receive)],
        },
        fallbacks=[CommandHandler("cancel", customer_menu.edit_name_cancel)],
    )
    app.add_handler(edit_name_conv)

    # ── ۳. سبد خرید + بیعانه ──
    cart_checkout_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(order.cart_callback, pattern="^cart_checkout$")],
        states={
            states.WAIT_RECEIPT_PHOTO: [
                MessageHandler(filters.PHOTO, checkout.receive_receipt_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, checkout.receive_receipt_wrong_type),
            ],
        },
        fallbacks=[CommandHandler("cancel", checkout.cancel_checkout)],
        per_user=True, per_chat=True,
    )
    app.add_handler(cart_checkout_conv)

    # ── ۴. رضایت مشتری ──
    satisfaction_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(satisfaction.content_send_callback, pattern="^sat_send_")],
        states={
            states.WAIT_SATISFACTION_CONTENT: [
                MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), satisfaction.receive_satisfaction_content)
            ],
        },
        fallbacks=[CommandHandler("cancel", satisfaction.cancel_satisfaction_content)],
        per_user=True, per_chat=True,
    )
    app.add_handler(satisfaction_conv)

    # ── ۵. Owner Panel ──
    owner_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(owner_panel.owner_callback_entry, pattern="^ownr_")],
        states={
            states.OWNER_WAIT_INPUT: [
                MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL, owner_panel.owner_input_handler),
                CallbackQueryHandler(owner_panel.owner_callback_entry, pattern="^ownr_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", owner_panel.owner_cancel)],
        per_user=True, per_chat=True,
    )
    app.add_handler(owner_conv)

    # ── ۶. کال‌بک‌های سفارش ──
    app.add_handler(CallbackQueryHandler(order.category_callback, pattern=r"^cat_\d+$"))
    app.add_handler(CallbackQueryHandler(order.product_callback, pattern=r"^prod_\d+$"))
    app.add_handler(CallbackQueryHandler(order.product_quantity_callback, pattern=r"^pq_(inc|dec|add|back)_\d+$"))
    app.add_handler(CallbackQueryHandler(order.nav_callback, pattern=r"^(nav_categories|nav_cart|noop)$"))
    app.add_handler(CallbackQueryHandler(order.cart_callback, pattern=r"^cart_(continue|clear|discount)$"))
    app.add_handler(CallbackQueryHandler(discount.discount_back_callback, pattern="^discount_back$"))

    # ── ۷. State Machine ادمین گروه ──
    app.add_handler(CallbackQueryHandler(order_actions.order_action_callback, pattern=r"^oa_(start|ready|delivered|cancel)_\d+$"))

    # ── ۸. رضایت مشتری ──
    app.add_handler(CallbackQueryHandler(satisfaction.open_satisfaction_callback, pattern=r"^sat_open_\d+$"))
    app.add_handler(CallbackQueryHandler(satisfaction.rating_callback, pattern=r"^sat_rate_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(satisfaction.content_skip_callback, pattern=r"^sat_skip_\d+$"))
    app.add_handler(CallbackQueryHandler(satisfaction.admin_like_callback, pattern=r"^sat_like_\d+$"))

    # ── ۹. تعطیلی موقت + بکاپ ──
    app.add_handler(CallbackQueryHandler(owner_panel.toggle_closed_callback, pattern=r"^ownr_close_(yes|no)$"))
    app.add_handler(CallbackQueryHandler(owner_panel.backup_callback_router, pattern=r"^ownr_backup_(send|restore)$"))

    # ── ۱۰. دکمه‌های منوی مشتری ──
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_NEW_ORDER}$"), order.new_order_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_CART}$"), order.cart_view_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_SATISFACTION}$"), satisfaction.satisfaction_menu_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_TRACK_ORDER}$"), customer_menu.track_order_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_HELP}$"), customer_menu.help_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_CONTACT}$"), customer_menu.contact_cafe_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_MENU_GUIDE}$"), customer_menu.menu_guide_handler))

    # ── ۱۱. دکمه‌های منوی Owner ──
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_OWNER_PRODUCTS}$"), owner_panel.products_management_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_OWNER_CATEGORIES}$"), owner_panel.categories_management_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_OWNER_DISCOUNTS}$"), owner_panel.discounts_management_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_OWNER_ADMINS}$"), owner_panel.admins_management_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_OWNER_SETTINGS}$"), owner_panel.settings_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_OWNER_STATS}$"), owner_panel.stats_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_OWNER_CLUB}$"), owner_panel.club_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_OWNER_SATISFACTION}$"), owner_panel.satisfaction_view_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_OWNER_TOGGLE_CLOSED}$"), owner_panel.toggle_closed_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_OWNER_BACKUP}$"), owner_panel.backup_handler))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_OWNER_BACK_MAIN}$"), owner_panel.back_to_main_handler))

    # ── ۱۲. کد تخفیف + بازیابی بکاپ (fallback text/file handler) ──
    app.add_handler(MessageHandler(filters.Document.ALL, _doc_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, discount.discount_text_handler))

    app.add_error_handler(error_handler)
    return app


async def _doc_router(update: Update, context):
    """مسیریابی فایل‌های دریافتی — فعلاً فقط بکاپ restore."""
    flow = context.user_data.get("owner_flow", {})
    if flow.get("type") == "backup_restore" and db.is_owner(update.effective_user.id):
        await owner_panel.handle_backup_restore_file(update, context)


if __name__ == "__main__":
    application = build_app()

    async def post_init(app):
        start_scheduler(app.bot)

    application.post_init = post_init

    # Railway: اگر WEBHOOK_URL تنظیم شده، از webhook استفاده کن وگرنه polling
    webhook_url = os.environ.get("WEBHOOK_URL")
    port = int(os.environ.get("PORT", 8443))

    if webhook_url:
        logger.info(f"🚀 نُوا با webhook شروع به کار کرد: {webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        logger.info("🚀 نُوا با polling شروع به کار کرد")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
