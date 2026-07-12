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
    """نمایش مبلغ به هزار تومان (گرد شده)"""
    if amount == 0:
        return "رایگان"
    thousands = amount // 1000
    remainder = amount % 1000
    if remainder == 0:
        return f"{thousands:,} هزار تومن"
    else:
        # اگر رقم‌های زیر هزار داشت، با یک اعشار نشون بده
        return f"{amount/1000:,.1f} هزار تومن"


# ====== ساعت کاری کافه ======

def is_cafe_open():
    """بررسی اینکه آیا کافه الان باز است یا نه."""
    if db.get_setting("temp_closed", "0") == "1":
        return False
    from datetime import datetime
    open_str = db.get_setting("open_hour", "9:00")
    close_str = db.get_setting("close_hour", "23:00")
    try:
        now_t = datetime.now().time()
        oh, om = map(int, open_str.split(":"))
        ch, cm = map(int, close_str.split(":"))
        from datetime import time as dtime
        open_t = dtime(oh, om)
        close_t = dtime(ch, cm)
        if open_t <= close_t:
            # کار روزانه معمولی (مثل 9:00 تا 23:00)
            return open_t <= now_t <= close_t
        else:
            # شب‌کاری (مثل 22:00 تا 4:00)
            return now_t >= open_t or now_t <= close_t
    except Exception:
        return True  # در صورت خطا اجازه سفارش بده


def cafe_closed_text():
    open_str = db.get_setting("open_hour", "9:00")
    close_str = db.get_setting("close_hour", "23:00")
    if db.get_setting("temp_closed", "0") == "1":
        msg = db.get_setting("temp_closed_msg", "امروز تعطیلیم")
        return (
            f"🚫 {msg}\n\n"
            f"ساعت کاری ما از {open_str} تا {close_str} هست.\n"
            "بعداً برمی‌گردم ☕"
        )
    return (
        f"😴 نُوا الان استراحت می‌کنه!\n\n"
        f"ساعت کاری از {open_str} تا {close_str} هست.\n"
        "اون موقع برمی‌گردم ☕"
    )


def get_menu_photo():
    """آیدی عکس منوی چاپی ذخیره‌شده در settings."""
    return db.get_setting("menu_photo_file_id")


# ====== کیبورد اینلاین سبد خرید (با ویرایش آیتم‌ها) ======

def cart_inline_keyboard(items):
    """کیبورد سبد خرید با امکان ویرایش تعداد هر آیتم."""
    buttons = []
    for item in items:
        # ردیف نام آیتم (غیرقابل کلیک)
        buttons.append([
            InlineKeyboardButton(f"🔹 {item['name']}", callback_data="noop")
        ])
        # ردیف کم/زیاد/حذف
        buttons.append([
            InlineKeyboardButton("➖", callback_data=f"ce_dec_{item['product_id']}"),
            InlineKeyboardButton(str(item["quantity"]), callback_data="noop"),
            InlineKeyboardButton("➕", callback_data=f"ce_inc_{item['product_id']}"),
            InlineKeyboardButton("🗑", callback_data=f"ce_del_{item['product_id']}"),
        ])
    buttons.append([InlineKeyboardButton("─────────────", callback_data="noop")])
    buttons.append([
        InlineKeyboardButton(config.BTN_CHECKOUT, callback_data="cart_checkout"),
        InlineKeyboardButton(config.BTN_CART_DISCOUNT, callback_data="cart_discount"),
    ])
    buttons.append([
        InlineKeyboardButton(config.BTN_CONTINUE_SHOPPING, callback_data="cart_continue"),
        InlineKeyboardButton(config.BTN_CLEAR_CART, callback_data="cart_clear"),
    ])
    return InlineKeyboardMarkup(buttons)


def build_cart_text(user_id, discount_code=None):
    items = db.get_cart_items(user_id)
    if not items:
        return "🛒 سبد خریدت خالیه.", 0, 0, []

    lines = ["🛒 سبد خرید:\n"]
    total = 0
    for item in items:
        line_total = item["price"] * item["quantity"]
        total += line_total
        lines.append(f"• {item['name']} × {item['quantity']} ← {format_price(line_total)}")

    final_total = total
    if discount_code:
        code_row = db.get_discount_code(discount_code)
        if code_row and code_row["active"]:
            final_total = apply_discount(total, code_row["discount_percent"])
            lines.append(f"\n🎟 تخفیف {code_row['discount_percent']}٪ اعمال شد")
            lines.append(f"جمع کل: {format_price(final_total)} (به‌جای {format_price(total)})")
        else:
            lines.append(f"\nجمع کل: {format_price(total)}")
    else:
        lines.append(f"\nجمع کل: {format_price(total)}")

    return "\n".join(lines), total, final_total, items


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
    # آیتم پرطرفدار فقط برای دسته‌بندی‌هایی با ۵+ آیتم فعال
    popular_ids = set()
    if len(products) >= 5:
        popular_ids = db.get_popular_product_ids_in_category(category_id, limit=2)

    buttons = []
    row = []
    for p in products:
        star = "⭐" if p["id"] in popular_ids else ""
        label = f"{star}{p['name']}{star}" if star else p["name"]
        row.append(InlineKeyboardButton(label, callback_data=f"prod_{p['id']}"))
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


# ====== ارسال ایمن به گروه‌ها (با مدیریت migrate) ======

def get_orders_group_id():
    import database as _db, config as _config
    return int(_db.get_setting("orders_group_id_override", str(_config.ORDERS_GROUP_ID)))


def get_satisfaction_group_id():
    import database as _db, config as _config
    return int(_db.get_setting("satisfaction_group_id_override", str(_config.SATISFACTION_GROUP_ID)))


async def safe_send(bot, group_getter, *, text=None, photo=None, caption=None, reply_markup=None):
    """
    ارسال پیام به گروه با retry خودکار در صورت migrate شدن.
    group_getter: تابعی که chat_id رو برمی‌گردونه (get_orders_group_id یا get_satisfaction_group_id)
    """
    import database as _db
    from telegram.error import ChatMigrated

    group_id = group_getter()
    for _ in range(2):
        try:
            if photo:
                return await bot.send_photo(
                    chat_id=group_id, photo=photo, caption=caption, reply_markup=reply_markup
                )
            else:
                return await bot.send_message(
                    chat_id=group_id, text=text, reply_markup=reply_markup
                )
        except ChatMigrated as e:
            new_id = getattr(e, "new_chat_id", None) or getattr(e, "migrate_to_chat_id", None)
            if not new_id:
                raise
            # ذخیره آیدی جدید برای هر دو گروه (نمی‌دانیم کدام migrate شده)
            _db.set_setting("orders_group_id_override", str(new_id))
            _db.set_setting("satisfaction_group_id_override", str(new_id))
            group_id = new_id
    raise RuntimeError("ارسال به گروه ناموفق بود")
