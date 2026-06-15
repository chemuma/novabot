from telegram import Update
from telegram.ext import ContextTypes

import config
import database as db
from handlers import order_utils


async def order_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    telegram_id = update.effective_user.id

    if not (db.is_admin(telegram_id) or db.is_owner(telegram_id)):
        await query.answer("⛔️ شما دسترسی به این بخش را ندارید.", show_alert=True)
        return

    # callback_data: oa_{action}_{order_id}
    _, action, order_id_str = query.data.split("_", 2)
    order_id = int(order_id_str)

    order_row = db.get_order(order_id)
    if order_row is None:
        await query.answer("سفارش یافت نشد.", show_alert=True)
        return

    user = db.get_user_by_id(order_row["user_id"])
    customer_chat_id = user["telegram_id"] if user else None

    if action == "start":
        if order_row["status"] != config.STATUS_PENDING_PREP:
            await query.answer("این سفارش در وضعیت مناسب نیست.", show_alert=True)
            return
        db.update_order_status(order_id, config.STATUS_PREPARING)
        await query.answer("شروع آماده‌سازی ثبت شد ✅")
        await _refresh_group_message(query, order_id, config.STATUS_PREPARING)
        if customer_chat_id:
            await context.bot.send_message(
                chat_id=customer_chat_id,
                text="☕ سفارشت در حال آماده‌سازیه. چند لحظه دیگه حاضره",
            )

    elif action == "ready":
        if order_row["status"] != config.STATUS_PREPARING:
            await query.answer("این سفارش در وضعیت مناسب نیست.", show_alert=True)
            return
        db.update_order_status(order_id, config.STATUS_READY)
        await query.answer("آماده شدن سفارش ثبت شد ✅")
        await _refresh_group_message(query, order_id, config.STATUS_READY)
        if customer_chat_id:
            await context.bot.send_message(
                chat_id=customer_chat_id,
                text="☕ سفارشت آماده‌ست! می‌تونی برای تحویل به کافه مراجعه کنی",
            )

    elif action == "delivered":
        if order_row["status"] != config.STATUS_READY:
            await query.answer("این سفارش در وضعیت مناسب نیست.", show_alert=True)
            return
        db.update_order_status(order_id, config.STATUS_DELIVERED)
        await query.answer("تحویل سفارش ثبت شد ✅")
        await _refresh_group_message(query, order_id, config.STATUS_DELIVERED)
        if customer_chat_id:
            await context.bot.send_message(
                chat_id=customer_chat_id,
                text="🙏 ممنون که از کافه «نُوا» سفارش دادی! امیدواریم لذت ببری ☕",
            )
            from handlers import satisfaction
            await satisfaction.send_rating_request(context.bot, order_id, customer_chat_id)

    elif action == "cancel":
        if order_row["status"] in (config.STATUS_DELIVERED, config.STATUS_CANCELLED):
            await query.answer("این سفارش قابل لغو نیست.", show_alert=True)
            return

        receipt_rejected = bool(order_row["receipt_file_id"])
        db.update_order_status(order_id, config.STATUS_CANCELLED)
        await query.answer("سفارش لغو شد ❌")
        await _refresh_group_message(query, order_id, config.STATUS_CANCELLED)

        if customer_chat_id:
            if receipt_rejected:
                await context.bot.send_message(
                    chat_id=customer_chat_id,
                    text="رسید پرداخت شما تایید نشد. لطفاً با کافه تماس بگیرید 📞",
                )
            else:
                await context.bot.send_message(
                    chat_id=customer_chat_id,
                    text=f"❌ سفارش {order_row['display_number']} لغو شد. در صورت سوال با کافه تماس بگیر 📞",
                )

    else:
        await query.answer()


async def _refresh_group_message(query, order_id, new_status):
    """ویرایش پیام گروه سفارشات با وضعیت و کیبورد جدید."""
    order_row = db.get_order(order_id)
    user = db.get_user_by_id(order_row["user_id"])
    caption = order_utils.build_order_caption(order_row, user, deposit_note=bool(order_row["deposit_required"]))
    caption += f"\n\nوضعیت: {config.STATUS_LABELS_FA.get(new_status, new_status)}"
    kb = order_utils.state_machine_keyboard(new_status, order_id)

    try:
        if query.message.photo:
            await query.edit_message_caption(caption=caption, reply_markup=kb)
        else:
            await query.edit_message_text(text=caption, reply_markup=kb)
    except Exception:
        pass
