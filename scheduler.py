"""
APScheduler job برای لغو خودکار سفارش‌هایی که ظرف ۳۰ دقیقه رسید بیعانه ارسال نکرده‌اند.
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import database as db

logger = logging.getLogger(__name__)


async def cancel_expired_deposits(bot):
    """هر ۵ دقیقه یکبار اجرا می‌شود."""
    try:
        orders = db.get_pending_cancel_candidates()
        cutoff = datetime.utcnow() - timedelta(minutes=config.DEPOSIT_RECEIPT_TIMEOUT_MINUTES)

        for order in orders:
            created_str = order["created_at"]
            try:
                created_at = datetime.fromisoformat(created_str)
            except ValueError:
                continue

            if created_at < cutoff:
                db.update_order_status(order["id"], config.STATUS_CANCELLED)
                logger.info(f"سفارش {order['display_number']} به‌دلیل عدم ارسال رسید لغو شد.")

                # حذف پیام آماده‌باش از گروه سفارشات
                if order["group_message_id"]:
                    group_id = int(db.get_setting("orders_group_id_override", str(config.ORDERS_GROUP_ID)))
                    try:
                        await bot.delete_message(
                            chat_id=group_id,
                            message_id=order["group_message_id"],
                        )
                    except Exception:
                        pass

                # اطلاع به مشتری
                user = db.get_user_by_id(order["user_id"])
                if user:
                    try:
                        await bot.send_message(
                            chat_id=user["telegram_id"],
                            text=(
                                f"⏳ سفارش {order['display_number']} به‌دلیل عدم ارسال رسید بیعانه "
                                f"ظرف {config.DEPOSIT_RECEIPT_TIMEOUT_MINUTES} دقیقه، "
                                "به‌صورت خودکار لغو شد.\n"
                                "در صورت سوال با کافه تماس بگیر 📞"
                            ),
                        )
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"خطا در job لغو بیعانه: {e}")


def start_scheduler(bot):
    scheduler = AsyncIOScheduler(timezone="Asia/Tehran")
    scheduler.add_job(
        cancel_expired_deposits,
        "interval",
        minutes=5,
        args=[bot],
        id="cancel_expired_deposits",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler شروع به کار کرد.")
    return scheduler
