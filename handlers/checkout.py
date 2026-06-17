from telegram.ext import ContextTypes, ConversationHandler

import config
import database as db
import helpers
import states
from handlers import order, order_utils


async def start_checkout(update, context: ContextTypes.DEFAULT_TYPE, user):
    query = update.callback_query
    items = db.get_cart_items(user["id"])

    if not items:
        await query.message.reply_text("سبد خریدت خالیه؛ اول یه چیزی اضافه کن 🙂")
        return ConversationHandler.END

    subtotal = sum(i["price"] * i["quantity"] for i in items)
    final_total = subtotal
    discount_code = context.user_data.get("cart_discount")

    if discount_code:
        code_row = db.get_discount_code(discount_code)
        if helpers.is_discount_code_usable(code_row, order.sum_cart_items(user["id"])):
            final_total = helpers.apply_discount(subtotal, code_row["discount_percent"])
        else:
            discount_code = None
            context.user_data.pop("cart_discount", None)

    threshold = int(db.get_setting("big_order_threshold", "300000"))
    category_ids = order_utils.get_cart_category_ids(user["id"])
    estimate = helpers.estimate_prep_time(category_ids)

    # ──── سفارش زیر آستانه: مستقیم ثبت ────
    if final_total < threshold:
        order_id, display_number = db.create_order(
            user_id=user["id"], total_amount=final_total, discount_code=discount_code,
            status=config.STATUS_PENDING_PREP,
        )
        for item in items:
            db.add_order_item(order_id, item["product_id"], item["quantity"], item["price"])

        if discount_code:
            db.consume_discount_code(discount_code, order.sum_cart_items(user["id"]))

        db.set_order_ready_estimate(order_id, estimate)
        db.clear_cart(user["id"])
        context.user_data.pop("cart_discount", None)

        order_row = db.get_order(order_id)
        caption = order_utils.build_order_caption(order_row, user)
        kb = order_utils.state_machine_keyboard(config.STATUS_PENDING_PREP, order_id)

        try:
            msg = await helpers.safe_send(
                context.bot, helpers.get_orders_group_id,
                text=caption, reply_markup=kb
            )
            db.set_order_group_message(order_id, msg.message_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"خطا در ارسال به گروه: {e}")

        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        await query.message.reply_text(
            f"✅ سفارشت ثبت شد! شماره سفارش: {display_number}\n"
            f"💰 جمع کل: {helpers.format_price(final_total)}\n"
            f"⏱ تقریباً {estimate} دقیقه دیگه آماده‌ست\n\n"
            "از «📦 پیگیری سفارش» می‌تونی وضعیتش رو ببینی 🙂",
            reply_markup=helpers.main_menu_keyboard(),
        )
        return ConversationHandler.END

    # ──── سفارش بالای آستانه: نیاز به بیعانه ────
    else:
        deposit_percent = int(db.get_setting("deposit_percent", "30"))
        deposit_amount = final_total * deposit_percent // 100
        card_number = db.get_setting("card_number", "----")

        order_id, display_number = db.create_order(
            user_id=user["id"], total_amount=final_total, discount_code=discount_code,
            deposit_required=1, deposit_amount=deposit_amount,
            status=config.STATUS_AWAITING_DEPOSIT,
        )
        for item in items:
            db.add_order_item(order_id, item["product_id"], item["quantity"], item["price"])

        if discount_code:
            db.consume_discount_code(discount_code, order.sum_cart_items(user["id"]))

        db.set_order_ready_estimate(order_id, estimate)
        db.clear_cart(user["id"])
        context.user_data.pop("cart_discount", None)
        context.user_data["pending_deposit_order_id"] = order_id

        order_row = db.get_order(order_id)
        alert_text = order_utils.build_big_order_alert(order_row, user)

        try:
            msg = await helpers.safe_send(
                context.bot, helpers.get_orders_group_id,
                text=alert_text
            )
            db.set_order_group_message(order_id, msg.message_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"خطا در ارسال آلرت گروه: {e}")

        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        await query.message.reply_text(
            f"💳 جمع کل سفارشت: {helpers.format_price(final_total)}\n\n"
            f"چون سفارش بزرگیه، نیاز دارم {deposit_percent}٪ بیعانه یعنی "
            f"{helpers.format_price(deposit_amount)} رو از قبل دریافت کنم.\n\n"
            f"💳 شماره کارت: {card_number}\n\n"
            "بعد از واریز، عکس رسیدت رو همینجا بفرست 📸\n\n"
            "⏳ ۳۰ دقیقه وقت داری — بعدش سفارش خودکار لغو می‌شه.",
        )
        return states.WAIT_RECEIPT_PHOTO


async def receive_receipt_photo(update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get("pending_deposit_order_id")
    if order_id is None:
        return ConversationHandler.END

    order_row = db.get_order(order_id)
    if order_row is None or order_row["status"] != config.STATUS_AWAITING_DEPOSIT:
        await update.message.reply_text(
            "این سفارش دیگه معتبر نیست — احتمالاً مهلتش تموم شده. دوباره سفارش بده 🙏",
            reply_markup=helpers.main_menu_keyboard(),
        )
        context.user_data.pop("pending_deposit_order_id", None)
        return ConversationHandler.END

    photo_file_id = update.message.photo[-1].file_id
    db.set_order_receipt(order_id, photo_file_id)

    # حذف پیام آماده‌باش از گروه
    if order_row["group_message_id"]:
        group_id = helpers.get_orders_group_id()
        try:
            await context.bot.delete_message(chat_id=group_id, message_id=order_row["group_message_id"])
        except Exception:
            pass

    db.update_order_status(order_id, config.STATUS_PENDING_PREP)
    order_row = db.get_order(order_id)
    user = db.get_user_by_id(order_row["user_id"])

    caption = order_utils.build_order_caption(order_row, user, deposit_note=True)
    kb = order_utils.state_machine_keyboard(config.STATUS_PENDING_PREP, order_id)

    try:
        msg = await helpers.safe_send(
            context.bot, helpers.get_orders_group_id,
            photo=photo_file_id, caption=caption, reply_markup=kb
        )
        db.set_order_group_message(order_id, msg.message_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"خطا در ارسال رسید به گروه: {e}")

    await update.message.reply_text(
        f"✅ رسید دریافت شد! سفارش {order_row['display_number']} ثبت شد.\n"
        f"⏱ تقریباً {order_row['ready_estimate']} دقیقه دیگه آماده‌ست ☕",
        reply_markup=helpers.main_menu_keyboard(),
    )

    context.user_data.pop("pending_deposit_order_id", None)
    return ConversationHandler.END


async def receive_receipt_wrong_type(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لطفاً عکس رسید پرداختت رو بفرست 📸")
    return states.WAIT_RECEIPT_PHOTO


async def cancel_checkout(update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get("pending_deposit_order_id")
    if order_id:
        order_row = db.get_order(order_id)
        if order_row and order_row["status"] == config.STATUS_AWAITING_DEPOSIT:
            db.update_order_status(order_id, config.STATUS_CANCELLED)
            group_id = helpers.get_orders_group_id()
            if order_row["group_message_id"]:
                try:
                    await context.bot.delete_message(
                        chat_id=group_id, message_id=order_row["group_message_id"]
                    )
                except Exception:
                    pass
        context.user_data.pop("pending_deposit_order_id", None)

    await update.message.reply_text("سفارش لغو شد.", reply_markup=helpers.main_menu_keyboard())
    return ConversationHandler.END
