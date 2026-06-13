import os

# ====== توکن و آیدی‌های ثابت ======
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8625065863:AAHzbowo8EgpTZiJ7eNheuBQl5_Uhd4Jgjk")

# آیدی عددی تلگرام دو مدیر اصلی (Owner) - باید قبل از اجرا پر شود
OWNER_IDS = [
    71961138,  # owner 1 - جای این را با آیدی واقعی عوض کنید
    158893761,  # owner 2 - جای این را با آیدی واقعی عوض کنید
]

# آیدی عددی گروه سفارشات و گروه رضایت مشتری (با فوروارد یک پیام از گروه به @JsonDumpBot یا مشابه پیدا می‌شود)
ORDERS_GROUP_ID = -5501484701   # جای این را با آیدی واقعی گروه سفارشات عوض کنید
SATISFACTION_GROUP_ID = -5351335799  # جای این را با آیدی واقعی گروه رضایت عوض کنید


# ====== متن دکمه‌های منوی اصلی مشتری ======
BTN_NEW_ORDER = "🍽 سفارش جدید"
BTN_CART = "🛒 سبد خرید"
BTN_DISCOUNT = "🎟 کد تخفیف"
BTN_MENU_GUIDE = "📖 راهنمای منو"
BTN_SATISFACTION = "⭐ ثبت رضایت"
BTN_TRACK_ORDER = "📦 پیگیری سفارش"
BTN_CONTACT = "📞 تماس با کافه"
BTN_HELP = "ℹ️ راهنمای ربات"
BTN_EDIT_NAME = "✏️ ویرایش نام"

MAIN_MENU_BUTTONS = [
    [BTN_NEW_ORDER, BTN_CART],
    [BTN_DISCOUNT, BTN_MENU_GUIDE],
    [BTN_SATISFACTION, BTN_TRACK_ORDER],
    [BTN_CONTACT, BTN_HELP],
    [BTN_EDIT_NAME],
]

# ====== دکمه‌های سبد خرید ======
BTN_CHECKOUT = "🧾 ثبت سفارش"
BTN_CART_DISCOUNT = "🎟 کد تخفیف"
BTN_CONTINUE_SHOPPING = "🍽 ادامه خرید"
BTN_CLEAR_CART = "🗑 پاک کردن سبد"

# ====== ناوبری محصولات ======
BTN_BACK_CATEGORIES = "🔙 دسته‌بندی‌ها"
BTN_BACK = "🔙 بازگشت"
BTN_ADD_TO_CART = "🛒 ثبت"

# ====== Owner Panel ======
BTN_OWNER_PRODUCTS = "🍽 مدیریت محصولات"
BTN_OWNER_CATEGORIES = "📂 مدیریت دسته‌بندی‌ها"
BTN_OWNER_DISCOUNTS = "🎟 مدیریت کدهای تخفیف"
BTN_OWNER_ADMINS = "👥 مدیریت ادمین‌ها"
BTN_OWNER_SETTINGS = "⚙️ تنظیمات"
BTN_OWNER_STATS = "📊 آمار فروش"
BTN_OWNER_CLUB = "🖼 باشگاه مشتریان"
BTN_OWNER_SATISFACTION = "⭐ مشاهده رضایت مشتریان"
BTN_OWNER_BACK_MAIN = "🔙 منوی اصلی"

OWNER_MENU_BUTTONS = [
    [BTN_OWNER_PRODUCTS, BTN_OWNER_CATEGORIES],
    [BTN_OWNER_DISCOUNTS, BTN_OWNER_ADMINS],
    [BTN_OWNER_SETTINGS, BTN_OWNER_STATS],
    [BTN_OWNER_CLUB, BTN_OWNER_SATISFACTION],
    [BTN_OWNER_BACK_MAIN],
]

# ====== State machine سفارش ======
STATUS_AWAITING_DEPOSIT = "AWAITING_DEPOSIT"
STATUS_PENDING_PREP = "PENDING_PREP"
STATUS_PREPARING = "PREPARING"
STATUS_READY = "READY"
STATUS_DELIVERED = "DELIVERED"
STATUS_CANCELLED = "CANCELLED"

STATUS_LABELS_FA = {
    STATUS_AWAITING_DEPOSIT: "در انتظار رسید بیعانه",
    STATUS_PENDING_PREP: "در انتظار آماده‌سازی",
    STATUS_PREPARING: "در حال آماده‌سازی",
    STATUS_READY: "آماده تحویل",
    STATUS_DELIVERED: "تحویل شده",
    STATUS_CANCELLED: "لغو شده",
}

# مهلت ارسال رسید بیعانه (دقیقه)
DEPOSIT_RECEIPT_TIMEOUT_MINUTES = 30
