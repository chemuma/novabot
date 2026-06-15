from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
import config
import database as db


# ====== کیبوردها ======

def main_menu_keyboard():
    return ReplyKeyboardMarkup(config.MAIN_MENU_BUTTONS, resize_keyboard=True)


def owner_menu_keyboard():
    return ReplyKeyboardMarkup(config.OWNER_MENU_BUTTONS, resize_keyboard=True)


def contact_request_keyboard():
    from telegram import KeyboardButton
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 ارسال شماره تماس", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ====== اعتبارسنجی کد تخفیف (چک‌سام) ======
# فرمت: ۶ حرف انگلیسی بزرگ + ۱ رقم وسط (مجموع مقادیر حروف mod 10)
# مثال: ABC5XYZ

def validate_discount_checksum(code: str) -> bool:
    code = code.strip().upper()
    if len(code) != 7:
        return False
    letters = code[:3] + code[4:]  # ۶ حرف: ۳ قبل و ۳ بعد از رقم وسط
    digit = code[3]
    if not letters.isalpha() or not letters.isascii():
        return False
    if not digit.isdigit():
        return False
    total = sum(ord(ch) - ord("A") + 1 for ch in letters)
    return total % 10 == int(digit)


def is_discount_code_usable(code_row, cart_items_count) -> bool:
    """بررسی فعال بودن و انقضای کد (بدون بررسی ظرفیت دقیق - طبق منطق فاز ۸)"""
    if code_row is None:
        return False
    if not code_row["active"]:
        return False
    if code_row["expiry_date"]:
        from datetime import date
        try:
            expiry = date.fromisoformat(code_row["expiry_date"])
            if date.today() > expiry:
                return False
        except ValueError:
            pass
    if code_row["remaining_capacity"] <= 0:
        return False
    return True


def apply_discount(total_amount, discount_percent):
    discounted = total_amount - (total_amount * discount_percent // 100)
    return discounted


def generate_discount_code(percent, capacity, expiry_date=None):
    """ساخت کد تخفیف تصادفی با فرمت LLL#LLL و چک‌سام معتبر، ذخیره در دیتابیس و بازگرداندن متن کد."""
    import random
    import string

    while True:
        letters = "".join(random.choices(string.ascii_uppercase, k=6))
        total = sum(ord(ch) - ord("A") + 1 for ch in letters)
        digit = total % 10
        code = letters[:3] + str(digit) + letters[3:]
        if db.get_discount_code(code) is None:
            break

    db.add_discount_code(code, percent, capacity, expiry_date)
    return code


# ====== تخمین زمان آماده‌سازی ======
# فرمول: فاصله بین سفارش‌ها + max(زمان دسته‌بندی‌های سفارش) + میانگین زمان سایر دسته‌بندی‌های سفارش

QUEUE_GAP_MINUTES = 5  # فاصله فرضی بین سفارش‌ها (می‌تواند بعداً به settings منتقل شود)


def estimate_prep_time(category_ids):
    """category_ids: لیست category_id های موجود در سفارش (با تکرار مجاز، فقط مقادیر یکتا لازم است)"""
    unique_ids = list(set(category_ids))
    if not unique_ids:
        return 0

    times = []
    for cid in unique_ids:
        cat = db.get_category(cid)
        if cat:
            times.append(cat["prep_time_minutes"])

    if not times:
        return 0

    max_time = max(times)
    if len(times) > 1:
        others = [t for t in times if t != max_time] or times
        avg_others = sum(others) / len(others)
    else:
        avg_others = 0

    return int(QUEUE_GAP_MINUTES + max_time + avg_others)


# ====== فرمت قیمت ======

def format_price(amount):
    return f"{amount:,} تومان"


# ====== کیبورد اینلاین سبد خرید ======

def cart_inline_keyboard(has_discount=False):
    buttons = [
        [InlineKeyboardButton(config.BTN_CHECKOUT, callback_data="cart_checkout")],
        [InlineKeyboardButton(config.BTN_CART_DISCOUNT, callback_data="cart_discount")],
        [InlineKeyboardButton(config.BTN_CONTINUE_SHOPPING, callback_data="cart_continue")],
        [InlineKeyboardButton(config.BTN_CLEAR_CART, callback_data="cart_clear")],
    ]
    return InlineKeyboardMarkup(buttons)


def build_cart_text(user_id):
    items = db.get_cart_items(user_id)
    if not items:
        return "🛒 سبد خریدت خالیه.", 0

    lines = ["🛒 سبد خرید شما:\n"]
    total = 0
    for item in items:
        line_total = item["price"] * item["quantity"]
        total += line_total
        lines.append(f"• {item['name']} × {item['quantity']} → {format_price(line_total)}")

    lines.append(f"\nجمع کل: {format_price(total)}")
    return "\n".join(lines), total


# ====== کیبوردهای فلوی سفارش جدید ======

def categories_keyboard():
    categories = db.get_active_categories()
    buttons = []
    row = []
    for cat in categories:
        emoji = cat["emoji"] or "🍴"
        row.append(InlineKeyboardButton(f"{emoji} {cat['name']}", callback_data=f"cat_{cat['id']}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(config.BTN_CART, callback_data="nav_cart")])
    return InlineKeyboardMarkup(buttons)


def products_keyboard(category_id):
    products = db.get_active_products_by_category(category_id)
    buttons = []
    row = []
    for p in products:
        row.append(InlineKeyboardButton(p["name"], callback_data=f"prod_{p['id']}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([
        InlineKeyboardButton(config.BTN_BACK_CATEGORIES, callback_data="nav_categories"),
        InlineKeyboardButton(config.BTN_CART, callback_data="nav_cart"),
    ])
    return InlineKeyboardMarkup(buttons)


def product_detail_keyboard(product_id, qty):
    buttons = [
        [
            InlineKeyboardButton("➖", callback_data=f"pq_dec_{product_id}"),
            InlineKeyboardButton(str(qty), callback_data="noop"),
            InlineKeyboardButton("➕", callback_data=f"pq_inc_{product_id}"),
        ],
        [InlineKeyboardButton(config.BTN_ADD_TO_CART, callback_data=f"pq_add_{product_id}")],
        [InlineKeyboardButton(config.BTN_BACK, callback_data=f"pq_back_{product_id}")],
    ]
    return InlineKeyboardMarkup(buttons)


def product_caption(product):
    desc = f"\n{product['description']}" if product["description"] else ""
    return f"{product['name']}\n💰 {format_price(product['price'])}{desc}"


# ====== کیبورد اینلاین تأیید کد تخفیف ======

def discount_entry_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(config.BTN_BACK, callback_data="discount_back")]])
