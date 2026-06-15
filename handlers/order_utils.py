from telegram import InlineKeyboardMarkup, InlineKeyboardButton

import config
import database as db
import helpers


def get_cart_category_ids(user_id):
    items = db.get_cart_items(user_id)
    category_ids = []
    for item in items:
        product = db.get_product(item["product_id"])
        if product:
            category_ids.append(product["category_id"])
    return category_ids


def build_items_lines(order_id):
    items = db.get_order_items(order_id)
    lines = []
    for it in items:
        line_total = it["price_at_order"] * it["quantity"]
        lines.append(f"• {it['product_name']} × {it['quantity']} → {helpers.format_price(line_total)}")
    return lines


def build_order_caption(order, user, deposit_note=False):
    """متن کامل سفارش برای ارسال به گروه سفارشات"""
    lines = [
        f"🆕 سفارش جدید {order['display_number']}",
        f"👤 نام: {user['name']}",
        f"📱 شماره: {user['phone']}",
        "",
        "🧾 اقلام:",
    ]
    lines.extend(build_items_lines(order["id"]))
    lines.append("")

    if order["discount_code"]:
        lines.append(f"🎟 کد تخفیف: {order['discount_code']}")

    if deposit_note and order["deposit_required"]:
        remaining = order["total_amount"] - order["deposit_amount"]
        lines.append(f"بیعانه دریافت‌شده: {helpers.format_price(order['deposit_amount'])}")
        lines.append(f"مبلغ باقی‌مانده (نقدی): {helpers.format_price(remaining)}")
    else:
        lines.append(f"💰 جمع کل: {helpers.format_price(order['total_amount'])}")

    if order["ready_estimate"]:
        lines.append(f"⏱ زمان تقریبی آماده‌سازی: حدود {order['ready_estimate']} دقیقه")

    return "\n".join(lines)


def build_big_order_alert(order, user):
    return (
        f"🔔 سفارش بزرگ — در انتظار رسید بیعانه\n\n"
        f"شماره سفارش: {order['display_number']}\n"
        f"👤 نام: {user['name']}\n"
        f"📱 شماره: {user['phone']}\n"
        f"💰 جمع کل: {helpers.format_price(order['total_amount'])}\n"
        f"بیعانه مورد انتظار: {helpers.format_price(order['deposit_amount'])}\n\n"
        f"⏳ آماده‌باش؛ منتظر تایید رسید پرداخت هستیم."
    )


def state_machine_keyboard(status, order_id):
    if status == config.STATUS_PENDING_PREP:
        buttons = [
            [InlineKeyboardButton(config.BTN_START_PREP, callback_data=f"oa_start_{order_id}")],
            [InlineKeyboardButton(config.BTN_CANCEL_ORDER, callback_data=f"oa_cancel_{order_id}")],
        ]
    elif status == config.STATUS_PREPARING:
        buttons = [
            [InlineKeyboardButton(config.BTN_DONE_PREP, callback_data=f"oa_ready_{order_id}")],
            [InlineKeyboardButton(config.BTN_CANCEL_ORDER, callback_data=f"oa_cancel_{order_id}")],
        ]
    elif status == config.STATUS_READY:
        buttons = [
            [InlineKeyboardButton(config.BTN_DELIVERED, callback_data=f"oa_delivered_{order_id}")],
        ]
    else:
        return None

    return InlineKeyboardMarkup(buttons)
