# State های مشترک ConversationHandler ها برای جلوگیری از تداخل بین فازها

# فاز ۱: ورود کاربر جدید (/start)
ASK_NAME = 1
ASK_PHONE = 2

# فاز ۲: سفارش جدید و سبد خرید
WAIT_QUANTITY = 10
WAIT_DISCOUNT_CODE_CART = 11
WAIT_RECEIPT_PHOTO = 12

# فاز ۲: ویرایش نام
WAIT_NEW_NAME = 20

# فاز ۳: رضایت مشتری
WAIT_RATING_FOLLOWUP = 30
WAIT_SATISFACTION_CONTENT = 31

# فاز ۴ (Owner Panel)
OWNER_WAIT_INPUT = 40

# زیرفلوهای Owner Panel (با user_data["owner_step"] ترکیب می‌شوند)
OWNER_CAT_ADD = 41
OWNER_PROD_ADD = 42
OWNER_PROD_EDIT = 43
OWNER_DISCOUNT_ADD = 44
OWNER_ADMIN_ADD = 45
OWNER_SETTING_EDIT = 46
OWNER_CAT_PREPTIME_EDIT = 47
