"""
APScheduler jobs:
1. لغو خودکار بیعانه‌های منقضی (هر ۵ دقیقه)
2. داشبورد روزانه ساعت ۱۲ شب به گروه سفارشات
3. بکاپ هفتگی JSON برای Owner
"""
import logging
from datetime import datetime, timedelta
from io import BytesIO

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import database as db
import helpers

logger = logging.getLogger(__name__)




# ======== ۱. لغو خودکار بیعانه منقضی ========

async def cancel_expired_deposits(bot):
    try:
        orders = db.get_pending_cancel_candidates()
        cutoff = datetime.utcnow() - timedelta(minutes=config.DEPOSIT_RECEIPT_TIMEOUT_MINUTES)

        for order in orders:
            try:
                created_at = datetime.fromisoformat(order["created_at"])
            except ValueError:
                continue

            if created_at < cutoff:
                db.update_order_status(order["id"], config.STATUS_CANCELLED)

                if order["group_message_id"]:
                    try:
                        await bot.delete_message(
                            chat_id=helpers.get_orders_group_id(),
                            message_id=order["group_message_id"],
                        )
                    except Exception:
                        pass

                user = db.get_user_by_id(order["user_id"])
                if user:
                    try:
                        await bot.send_message(
                            chat_id=user["telegram_id"],
                            text=(
                                f"⏳ سفارش {order['display_number']} به‌دلیل عدم ارسال رسید "
                                f"ظرف {config.DEPOSIT_RECEIPT_TIMEOUT_MINUTES} دقیقه لغو شد.\n"
                                "در صورت سوال با کافه تماس بگیر 📞"
                            ),
                        )
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"خطا در job لغو بیعانه: {e}")


# ======== ۲. داشبورد روزانه (ساعت ۲۴:۰۰) ========

async def send_daily_report(bot):
    try:
        day, top_items = db.get_daily_report()

        if day["cnt"] == 0:
            text = "📊 گزارش امروز\n\nامروز سفارشی ثبت نشد."
        else:
            from helpers import format_price
            lines = [
                "📊 گزارش امروز نُوا\n",
                f"🧾 تعداد سفارش: {day['cnt']}",
                f"💰 درآمد: {format_price(day['revenue'])}",
            ]
            if top_items:
                lines.append("\n🏆 پرفروش‌ترین‌های امروز:")
                medals = ["🥇", "🥈", "🥉"]
                for i, item in enumerate(top_items):
                    medal = medals[i] if i < len(medals) else "•"
                    lines.append(f"  {medal} {item['name']} ({item['sold']} عدد)")
            text = "\n".join(lines)

        await bot.send_message(chat_id=helpers.get_orders_group_id(), text=text)
    except Exception as e:
        logger.error(f"خطا در گزارش روزانه: {e}")


# ======== ۳. بکاپ هفتگی JSON ========

async def send_weekly_backup(bot):
    try:
        from handlers.owner_panel import _export_backup
        import json

        data = _export_backup()
        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        buf = BytesIO(json_bytes)
        filename = f"nova_backup_{datetime.now().strftime('%Y%m%d')}.json"
        buf.name = filename

        for owner_id in config.OWNER_IDS:
            try:
                await bot.send_document(
                    chat_id=owner_id,
                    document=buf,
                    filename=filename,
                    caption=(
                        f"💾 بکاپ هفتگی نُوا — {datetime.now().strftime('%Y/%m/%d')}\n"
                        "شامل: تنظیمات، محصولات، دسته‌بندی‌ها، کدهای تخفیف، آمار کلی\n\n"
                        "برای بازیابی از پنل مدیر → «بکاپ و بازیابی» استفاده کن."
                    ),
                )
                buf.seek(0)
            except Exception as ex:
                logger.error(f"خطا در ارسال بکاپ به owner {owner_id}: {ex}")
    except Exception as e:
        logger.error(f"خطا در job بکاپ هفتگی: {e}")


# ======== راه‌اندازی scheduler ========

def start_scheduler(bot):
    scheduler = AsyncIOScheduler(timezone="Asia/Tehran")

    # هر ۵ دقیقه: لغو بیعانه‌های منقضی
    scheduler.add_job(
        cancel_expired_deposits,
        "interval",
        minutes=5,
        args=[bot],
        id="cancel_expired_deposits",
        replace_existing=True,
    )

    # هر شب ساعت ۲۴:۰۰: گزارش روزانه
    scheduler.add_job(
        send_daily_report,
        "cron",
        hour=0,
        minute=0,
        args=[bot],
        id="daily_report",
        replace_existing=True,
    )

    # هر دوشنبه ساعت ۹ صبح: بکاپ هفتگی
    scheduler.add_job(
        send_weekly_backup,
        "cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        args=[bot],
        id="weekly_backup",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler فعال شد (۳ job: بیعانه، گزارش روزانه، بکاپ هفتگی)")
    return scheduler
