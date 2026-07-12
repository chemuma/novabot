from datetime import date, timedelta

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, ContextTypes

import config
import database as db
import helpers
import states


SATISFACTION_STARS = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]


def _owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not db.is_owner(update.effective_user.id):
            return
        return await func(update, context)
    return wrapper


# ====== 📊 آمار فروش ======

@_owner_only
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total, today = db.get_sales_stats()
    text = (
        "📊 آمار فروش کافه «نُوا»\n\n"
        f"امروز:\n  تعداد سفارش: {today['cnt']}\n  مجموع فروش: {helpers.format_price(today['total'])}\n\n"
        f"کل (از شروع چرخه فعلی):\n  تعداد سفارش: {total['cnt']}\n  مجموع فروش: {helpers.format_price(total['total'])}"
    )
    await update.message.reply_text(text, reply_markup=helpers.owner_menu_keyboard())


# ====== 🖼 باشگاه مشتریان ======

@_owner_only
async def club_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users_for_club()
    if not users:
        await update.message.reply_text(
            "باشگاه مشتریان خالیه.", reply_markup=helpers.owner_menu_keyboard()
        )
        return

    lines = ["🖼 باشگاه مشتریان (جدیدترین بالا):\n"]
    for u in users:
        name = u["name"] or "بدون نام"
        phone = u["phone"] or "—"
        lines.append(f"• {name} | {phone}")

    text = "\n".join(lines)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 ریست کامل باشگاه", callback_data="ownr_club_reset")]
    ])

    # تلگرام محدودیت طول پیام دارد؛ در صورت طولانی بودن، تقسیم می‌شود
    if len(text) > 3800:
        chunk = []
        size = 0
        for line in lines:
            if size + len(line) > 3800:
                await update.message.reply_text("\n".join(chunk))
                chunk, size = [], 0
            chunk.append(line)
            size += len(line)
        if chunk:
            await update.message.reply_text("\n".join(chunk), reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)


async def club_reset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not db.is_owner(update.effective_user.id):
        await query.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ بله، ریست کن", callback_data="ownr_club_reset_yes"),
            InlineKeyboardButton("🔙 انصراف", callback_data="ownr_club_reset_no"),
        ]
    ])
    await query.edit_message_reply_markup(reply_markup=kb)
    await query.answer()


async def club_reset_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not db.is_owner(update.effective_user.id):
        await query.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return

    if query.data == "ownr_club_reset_yes":
        db.reset_customer_club()
        await query.edit_message_text("✅ باشگاه مشتریان به‌طور کامل ریست شد.")
    else:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 ریست کامل باشگاه", callback_data="ownr_club_reset")]
            ])
        )
    await query.answer()


# ====== ⭐ مشاهده رضایت مشتریان ======

@_owner_only
async def satisfaction_view_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.get_recent_satisfaction(limit=15)
    if not rows:
        await update.message.reply_text(
            "هنوز رضایتی ثبت نشده.", reply_markup=helpers.owner_menu_keyboard()
        )
        return

    lines = ["⭐ آخرین رضایت‌های ثبت‌شده:\n"]
    for r in rows:
        stars = SATISFACTION_STARS[r["rating"] - 1] if r["rating"] else "—"
        line = f"• {r['display_number']} | {r['user_name']} | {stars}"
        if r["comment"]:
            comment = r["comment"][:80]
            line += f"\n  📝 {comment}"
        if r["photo_file_id"]:
            line += "\n  📷 (عکس ضمیمه شده)"
        if r["liked_by_admin"]:
            line += "\n  🎁 تخفیف ارسال شده"
        lines.append(line)

    await update.message.reply_text("\n\n".join(lines), reply_markup=helpers.owner_menu_keyboard())


# ====== بازگشت به منوی اصلی ======

async def back_to_main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_owner(update.effective_user.id):
        return
    await update.message.reply_text(
        "بازگشت به منوی اصلی.", reply_markup=helpers.main_menu_keyboard()
    )


# ====== 📂 مدیریت دسته‌بندی‌ها ======

def _categories_management_keyboard():
    categories = db.get_all_categories()
    buttons = []
    for cat in categories:
        status = "✅" if cat["active"] else "🚫"
        emoji = cat["emoji"] or "🍴"
        label = f"{status} {emoji} {cat['name']} ({cat['prep_time_minutes']} دقیقه)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"ownr_cat_toggle_{cat['id']}")])
        buttons.append([
            InlineKeyboardButton("⏱ زمان آماده‌سازی", callback_data=f"ownr_cat_prep_{cat['id']}"),
            InlineKeyboardButton("❌ حذف", callback_data=f"ownr_cat_del_{cat['id']}"),
        ])
    buttons.append([InlineKeyboardButton("➕ افزودن دسته‌بندی", callback_data="ownr_cat_add")])
    return InlineKeyboardMarkup(buttons)


@_owner_only
async def categories_management_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categories = db.get_all_categories()
    if not categories:
        text = "هنوز دسته‌بندی‌ای ثبت نشده. یکی اضافه کن 👇"
    else:
        text = (
            "📂 مدیریت دسته‌بندی‌ها\n\n"
            "روی نام هر دسته بزن تا فعال/غیرفعال شود؛ "
            "✅ = فعال، 🚫 = غیرفعال."
        )
    await update.message.reply_text(text, reply_markup=_categories_management_keyboard())


async def category_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not db.is_owner(update.effective_user.id):
        await query.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return ConversationHandler.END

    data = query.data

    if data == "ownr_cat_add":
        context.user_data["owner_flow"] = {"type": "cat_add", "step": 0, "data": {}}
        await query.answer()
        await query.message.reply_text("نام دسته‌بندی جدید رو بفرست:")
        return states.OWNER_WAIT_INPUT

    if data.startswith("ownr_cat_toggle_"):
        cat_id = int(data.rsplit("_", 1)[1])
        cat = db.get_category(cat_id)
        if cat is None:
            await query.answer("یافت نشد.", show_alert=True)
            return ConversationHandler.END
        db.set_category_active(cat_id, not cat["active"])
        await query.answer("وضعیت تغییر کرد ✅")
        await query.edit_message_reply_markup(reply_markup=_categories_management_keyboard())
        return ConversationHandler.END

    if data.startswith("ownr_cat_del_"):
        cat_id = int(data.rsplit("_", 1)[1])
        products = db.get_all_products_by_category(cat_id)
        if products:
            await query.answer(
                "⛔️ این دسته دارای محصول است؛ ابتدا محصولاتش را حذف یا غیرفعال کن.", show_alert=True
            )
            return ConversationHandler.END
        try:
            db.delete_category(cat_id)
            await query.answer("✅ دسته‌بندی حذف شد")
        except Exception:
            await query.answer("⛔️ حذف ممکن نیست.", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=_categories_management_keyboard())
        return ConversationHandler.END

    if data.startswith("ownr_cat_prep_"):
        cat_id = int(data.rsplit("_", 1)[1])
        context.user_data["owner_flow"] = {"type": "cat_prep", "step": 0, "data": {"category_id": cat_id}}
        await query.answer()
        await query.message.reply_text("زمان آماده‌سازی جدید این دسته رو به دقیقه (فقط عدد) بفرست:")
        return states.OWNER_WAIT_INPUT

    await query.answer()
    return ConversationHandler.END


# ====== 🍽 مدیریت محصولات ======

def _products_categories_keyboard():
    categories = db.get_all_categories()
    buttons = []
    for cat in categories:
        emoji = cat["emoji"] or "🍴"
        status = "✅" if cat["active"] else "🚫"
        buttons.append(
            [InlineKeyboardButton(f"{status} {emoji} {cat['name']}", callback_data=f"ownr_prod_cat_{cat['id']}")]
        )
    if not buttons:
        buttons.append([InlineKeyboardButton("ابتدا یک دسته‌بندی بساز", callback_data="ownr_noop")])
    return InlineKeyboardMarkup(buttons)


@_owner_only
async def products_management_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🍽 مدیریت محصولات\n\nابتدا دسته‌بندی رو انتخاب کن:",
        reply_markup=_products_categories_keyboard(),
    )


def _products_list_keyboard(category_id):
    products = db.get_all_products_by_category(category_id)
    buttons = []
    for p in products:
        status = "✅" if p["active"] else "🚫"
        buttons.append(
            [InlineKeyboardButton(f"{status} {p['name']} | {p['price']:,}", callback_data=f"ownr_prod_edit_{p['id']}")]
        )
    buttons.append([InlineKeyboardButton("➕ افزودن محصول", callback_data=f"ownr_prod_add_{category_id}")])
    buttons.append([InlineKeyboardButton(config.BTN_BACK_CATEGORIES, callback_data="ownr_prod_catlist")])
    return InlineKeyboardMarkup(buttons)


def _product_edit_keyboard(product_id):
    p = db.get_product(product_id)
    status_label = "🚫 غیرفعال کن" if p["active"] else "✅ فعال کن"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ نام", callback_data=f"ownr_prodf_name_{product_id}")],
        [InlineKeyboardButton("✏️ قیمت", callback_data=f"ownr_prodf_price_{product_id}")],
        [InlineKeyboardButton("✏️ توضیح", callback_data=f"ownr_prodf_desc_{product_id}")],
        [InlineKeyboardButton("✏️ عکس", callback_data=f"ownr_prodf_photo_{product_id}")],
        [InlineKeyboardButton(status_label, callback_data=f"ownr_prod_toggle_{product_id}")],
        [InlineKeyboardButton("❌ حذف محصول", callback_data=f"ownr_prod_del_{product_id}")],
        [InlineKeyboardButton(config.BTN_BACK, callback_data=f"ownr_prod_cat_{p['category_id']}")],
    ])


def _product_edit_text(product_id):
    p = db.get_product(product_id)
    status = "فعال ✅" if p["active"] else "غیرفعال 🚫"
    desc = p["description"] or "—"
    return (
        f"ویرایش محصول «{p['name']}»\n"
        f"قیمت: {p['price']:,} تومان\n"
        f"توضیح: {desc}\n"
        f"وضعیت: {status}"
    )


async def product_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not db.is_owner(update.effective_user.id):
        await query.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return ConversationHandler.END

    data = query.data

    if data == "ownr_prod_catlist":
        await query.answer()
        try:
            await query.edit_message_text(
                "🍽 مدیریت محصولات\n\nابتدا دسته‌بندی رو انتخاب کن:",
                reply_markup=_products_categories_keyboard(),
            )
        except Exception:
            await query.message.reply_text(
                "🍽 مدیریت محصولات\n\nابتدا دسته‌بندی رو انتخاب کن:",
                reply_markup=_products_categories_keyboard(),
            )
        return ConversationHandler.END

    if data.startswith("ownr_prod_cat_"):
        cat_id = int(data.rsplit("_", 1)[1])
        cat = db.get_category(cat_id)
        await query.answer()
        text = f"محصولات دسته «{cat['name']}»:" if cat else "محصولات این دسته:"
        try:
            await query.edit_message_text(text, reply_markup=_products_list_keyboard(cat_id))
        except Exception:
            await query.message.reply_text(text, reply_markup=_products_list_keyboard(cat_id))
        return ConversationHandler.END

    if data.startswith("ownr_prod_add_"):
        cat_id = int(data.rsplit("_", 1)[1])
        context.user_data["owner_flow"] = {"type": "prod_add", "step": 0, "data": {"category_id": cat_id}}
        await query.answer()
        await query.message.reply_text("نام محصول جدید رو بفرست:")
        return states.OWNER_WAIT_INPUT

    if data.startswith("ownr_prod_edit_"):
        product_id = int(data.rsplit("_", 1)[1])
        p = db.get_product(product_id)
        if p is None:
            await query.answer("یافت نشد.", show_alert=True)
            return ConversationHandler.END
        await query.answer()
        text = _product_edit_text(product_id)
        try:
            await query.edit_message_text(text, reply_markup=_product_edit_keyboard(product_id))
        except Exception:
            await query.message.reply_text(text, reply_markup=_product_edit_keyboard(product_id))
        return ConversationHandler.END

    if data.startswith("ownr_prod_toggle_"):
        product_id = int(data.rsplit("_", 1)[1])
        p = db.get_product(product_id)
        if p is None:
            await query.answer("یافت نشد.", show_alert=True)
            return ConversationHandler.END
        db.set_product_active(product_id, not p["active"])
        await query.answer("وضعیت تغییر کرد ✅")
        await query.edit_message_text(_product_edit_text(product_id), reply_markup=_product_edit_keyboard(product_id))
        return ConversationHandler.END

    if data.startswith("ownr_prod_del_"):
        product_id = int(data.rsplit("_", 1)[1])
        p = db.get_product(product_id)
        if p is None:
            await query.answer("یافت نشد.", show_alert=True)
            return ConversationHandler.END
        category_id = p["category_id"]
        try:
            db.delete_product(product_id)
            await query.answer("✅ محصول حذف شد")
        except Exception:
            db.set_product_active(product_id, False)
            await query.answer(
                "⚠️ این محصول در سفارش‌های قبلی استفاده شده؛ به‌جای حذف، غیرفعال شد.", show_alert=True
            )
        await query.edit_message_text("محصولات این دسته:", reply_markup=_products_list_keyboard(category_id))
        return ConversationHandler.END

    if data.startswith("ownr_prodf_"):
        # ownr_prodf_{field}_{product_id}
        _, _, field, product_id_str = data.split("_", 3)
        product_id = int(product_id_str)
        context.user_data["owner_flow"] = {"type": "prod_field", "field": field, "data": {"product_id": product_id}}
        await query.answer()
        prompts = {
            "name": "نام جدید محصول رو بفرست:",
            "price": "قیمت جدید محصول رو بفرست (فقط عدد، تومان):",
            "desc": "توضیح جدید محصول رو بفرست (یا بنویس: ندارد):",
            "photo": "عکس جدید محصول رو بفرست (یا بنویس: ندارد):",
        }
        await query.message.reply_text(prompts.get(field, "مقدار جدید رو بفرست:"))
        return states.OWNER_WAIT_INPUT

    await query.answer()
    return ConversationHandler.END


# ====== 🎟 مدیریت کدهای تخفیف ======

def _discount_list_text_and_kb():
    codes = db.list_discount_codes()
    if not codes:
        text = "🎟 هنوز کد تخفیفی ساخته نشده."
    else:
        lines = ["🎟 کدهای تخفیف:\n"]
        for c in codes:
            status = "✅" if c["active"] else "🚫"
            expiry = c["expiry_date"] or "بدون انقضا"
            lines.append(
                f"{status} {c['code']} | {c['discount_percent']}٪ | "
                f"باقی‌مانده {c['remaining_capacity']}/{c['total_capacity']} | انقضا: {expiry}"
            )
        text = "\n".join(lines)

    kb_buttons = [[InlineKeyboardButton("➕ ساخت کد جدید", callback_data="ownr_disc_add")]]
    if any(c["active"] for c in codes):
        kb_buttons.append([InlineKeyboardButton("❌ غیرفعال کردن یک کد", callback_data="ownr_disc_deactlist")])
    return text, InlineKeyboardMarkup(kb_buttons)


@_owner_only
async def discounts_management_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, kb = _discount_list_text_and_kb()
    await update.message.reply_text(text, reply_markup=kb)


def _discount_deactivate_keyboard():
    codes = [c for c in db.list_discount_codes() if c["active"]]
    buttons = [[InlineKeyboardButton(c["code"], callback_data=f"ownr_disc_deact_{c['code']}")] for c in codes]
    buttons.append([InlineKeyboardButton(config.BTN_BACK, callback_data="ownr_disc_list")])
    return InlineKeyboardMarkup(buttons)


async def discount_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not db.is_owner(update.effective_user.id):
        await query.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return ConversationHandler.END

    data = query.data

    if data == "ownr_disc_list":
        text, kb = _discount_list_text_and_kb()
        await query.answer()
        await query.edit_message_text(text, reply_markup=kb)
        return ConversationHandler.END

    if data == "ownr_disc_add":
        context.user_data["owner_flow"] = {"type": "disc_add", "step": 0, "data": {}}
        await query.answer()
        await query.message.reply_text("درصد تخفیف رو بفرست (عددی بین ۱ تا ۱۰۰):")
        return states.OWNER_WAIT_INPUT

    if data == "ownr_disc_deactlist":
        await query.answer()
        await query.edit_message_text(
            "کدی که می‌خوای غیرفعال کنی رو انتخاب کن:", reply_markup=_discount_deactivate_keyboard()
        )
        return ConversationHandler.END

    if data.startswith("ownr_disc_deact_"):
        code = data[len("ownr_disc_deact_"):]
        db.deactivate_discount_code(code)
        await query.answer(f"کد {code} غیرفعال شد ✅")
        text, kb = _discount_list_text_and_kb()
        await query.edit_message_text(text, reply_markup=kb)
        return ConversationHandler.END

    await query.answer()
    return ConversationHandler.END


# ====== 👥 مدیریت ادمین‌ها ======

def _admins_list_text_and_kb():
    admins = db.list_admins()
    lines = ["👥 لیست ادمین‌ها:\n"]
    buttons = []
    for a in admins:
        role_fa = "مدیر اصلی 👑" if a["role"] == "owner" else "ادمین"
        lines.append(f"• {a['telegram_id']} — {role_fa}")
        if a["role"] != "owner":
            buttons.append(
                [InlineKeyboardButton(f"❌ حذف {a['telegram_id']}", callback_data=f"ownr_adm_del_{a['telegram_id']}")]
            )
    buttons.append([InlineKeyboardButton("➕ افزودن ادمین", callback_data="ownr_adm_add")])
    return "\n".join(lines), InlineKeyboardMarkup(buttons)


@_owner_only
async def admins_management_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, kb = _admins_list_text_and_kb()
    await update.message.reply_text(text, reply_markup=kb)


async def admin_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not db.is_owner(update.effective_user.id):
        await query.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return ConversationHandler.END

    data = query.data

    if data == "ownr_adm_add":
        context.user_data["owner_flow"] = {"type": "adm_add", "step": 0, "data": {}}
        await query.answer()
        await query.message.reply_text("آیدی عددی تلگرام ادمین جدید رو بفرست:")
        return states.OWNER_WAIT_INPUT

    if data.startswith("ownr_adm_del_"):
        telegram_id = int(data.rsplit("_", 1)[1])
        db.remove_admin(telegram_id)
        await query.answer("✅ ادمین حذف شد")
        text, kb = _admins_list_text_and_kb()
        await query.edit_message_text(text, reply_markup=kb)
        return ConversationHandler.END

    await query.answer()
    return ConversationHandler.END


# ====== ⚙️ تنظیمات ======

SETTINGS_FIELDS = {
    "open_hour": ("ساعت شروع کار (مثل 9:00)", "text"),
    "close_hour": ("ساعت پایان کار (مثل 23:00)", "text"),
    "big_order_threshold": ("آستانه سفارش بزرگ (تومان)", "int"),
    "deposit_percent": ("درصد بیعانه", "int"),
    "card_number": ("شماره کارت", "text"),
    "cafe_phone": ("شماره تماس کافه", "text"),
    "satisfaction_discount_percent": ("درصد تخفیف رضایت مشتری", "int"),
    "temp_closed_msg": ("پیام تعطیلی موقت", "text"),
    "menu_photo_file_id": ("عکس منوی چاپی (file_id)", "photo"),
}


def _settings_text_and_kb():
    lines = ["⚙️ تنظیمات فعلی:\n"]
    buttons = []
    for key, (label, _) in SETTINGS_FIELDS.items():
        value = db.get_setting(key, "—")
        lines.append(f"• {label}: {value}")
        buttons.append([InlineKeyboardButton(f"✏️ {label}", callback_data=f"ownr_set_edit_{key}")])
    return "\n".join(lines), InlineKeyboardMarkup(buttons)


@_owner_only
async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, kb = _settings_text_and_kb()
    await update.message.reply_text(text, reply_markup=kb)


async def settings_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not db.is_owner(update.effective_user.id):
        await query.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return ConversationHandler.END

    data = query.data
    if data.startswith("ownr_set_edit_"):
        key = data[len("ownr_set_edit_"):]
        if key not in SETTINGS_FIELDS:
            await query.answer("یافت نشد.", show_alert=True)
            return ConversationHandler.END
        label, value_type = SETTINGS_FIELDS[key]
        context.user_data["owner_flow"] = {"type": "set_edit", "step": 0, "data": {"key": key}}
        await query.answer()
        current = db.get_setting(key, "—")
        if value_type == "photo":
            cur_display = "تنظیم شده ✅" if current else "تنظیم نشده"
            await query.message.reply_text(
                f"عکس جدید منوی چاپی رو بفرست تا جایگزین بشه.\n(وضعیت فعلی: {cur_display})\n"
                "یا بنویس: ندارد تا عکس حذف بشه."
            )
        else:
            await query.message.reply_text(
                f"مقدار جدید برای «{label}» رو بفرست (مقدار فعلی: {current}):"
            )
        return states.OWNER_WAIT_INPUT

    await query.answer()
    return ConversationHandler.END


# ====== مسیریاب کلی کال‌بک‌های Owner Panel ======

async def owner_callback_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "ownr_noop":
        await query.answer()
        return ConversationHandler.END

    if data.startswith("ownr_club_reset"):
        if data == "ownr_club_reset":
            await club_reset_callback(update, context)
        else:
            await club_reset_confirm_callback(update, context)
        return ConversationHandler.END

    if data.startswith("ownr_cat_"):
        return await category_callback_router(update, context)
    if data.startswith("ownr_prod"):
        return await product_callback_router(update, context)
    if data.startswith("ownr_disc_"):
        return await discount_callback_router(update, context)
    if data.startswith("ownr_adm_"):
        return await admin_callback_router(update, context)
    if data.startswith("ownr_set_"):
        return await settings_callback_router(update, context)

    await query.answer()
    return ConversationHandler.END


# ====== ورودی متن/عکس برای فلوهای چندمرحله‌ای ======

async def owner_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_owner(update.effective_user.id):
        return ConversationHandler.END

    flow = context.user_data.get("owner_flow")
    if flow is None:
        return ConversationHandler.END

    flow_type = flow["type"]

    if flow_type == "cat_add":
        return await _handle_cat_add(update, context, flow)
    if flow_type == "cat_prep":
        return await _handle_cat_prep(update, context, flow)
    if flow_type == "prod_add":
        return await _handle_prod_add(update, context, flow)
    if flow_type == "prod_field":
        return await _handle_prod_field(update, context, flow)
    if flow_type == "disc_add":
        return await _handle_disc_add(update, context, flow)
    if flow_type == "adm_add":
        return await _handle_adm_add(update, context, flow)
    if flow_type == "set_edit":
        return await _handle_set_edit(update, context, flow)

    context.user_data.pop("owner_flow", None)
    return ConversationHandler.END


async def _handle_cat_add(update, context, flow):
    text = (update.message.text or "").strip() if update.message.text else ""
    step = flow["step"]

    if step == 0:
        if not text:
            await update.message.reply_text("لطفاً یک نام معتبر بفرست:")
            return states.OWNER_WAIT_INPUT
        flow["data"]["name"] = text
        flow["step"] = 1
        await update.message.reply_text("ایموجی این دسته رو بفرست (یا بنویس: ندارد):")
        return states.OWNER_WAIT_INPUT

    if step == 1:
        emoji = None if text in ("ندارد", "-", "") else text
        flow["data"]["emoji"] = emoji
        flow["step"] = 2
        await update.message.reply_text("زمان آماده‌سازی این دسته به دقیقه (فقط عدد) رو بفرست:")
        return states.OWNER_WAIT_INPUT

    if step == 2:
        if not text.isdigit():
            await update.message.reply_text("لطفاً فقط عدد بفرست:")
            return states.OWNER_WAIT_INPUT
        prep_time = int(text)
        db.add_category(flow["data"]["name"], flow["data"]["emoji"], prep_time_minutes=prep_time)
        name = flow["data"]["name"]
        context.user_data.pop("owner_flow", None)
        await update.message.reply_text(
            f"✅ دسته‌بندی «{name}» اضافه شد.",
            reply_markup=_categories_management_keyboard(),
        )
        return ConversationHandler.END


async def _handle_cat_prep(update, context, flow):
    text = (update.message.text or "").strip() if update.message.text else ""
    if not text.isdigit():
        await update.message.reply_text("لطفاً فقط عدد (دقیقه) بفرست:")
        return states.OWNER_WAIT_INPUT

    category_id = flow["data"]["category_id"]
    db.update_category_prep_time(category_id, int(text))
    context.user_data.pop("owner_flow", None)
    await update.message.reply_text("✅ زمان آماده‌سازی به‌روزرسانی شد.", reply_markup=_categories_management_keyboard())
    return ConversationHandler.END


async def _handle_prod_add(update, context, flow):
    step = flow["step"]
    text = update.message.text.strip() if update.message.text else None

    if step == 0:
        if not text:
            await update.message.reply_text("لطفاً نام معتبر بفرست:")
            return states.OWNER_WAIT_INPUT
        flow["data"]["name"] = text
        flow["step"] = 1
        await update.message.reply_text("قیمت محصول رو بفرست (فقط عدد، تومان):")
        return states.OWNER_WAIT_INPUT

    if step == 1:
        if not text or not text.isdigit():
            await update.message.reply_text("لطفاً فقط عدد بفرست:")
            return states.OWNER_WAIT_INPUT
        flow["data"]["price"] = int(text)
        flow["step"] = 2
        await update.message.reply_text("توضیح کوتاه محصول رو بفرست (یا بنویس: ندارد):")
        return states.OWNER_WAIT_INPUT

    if step == 2:
        desc = None if (text is None or text in ("ندارد", "-", "")) else text
        flow["data"]["description"] = desc
        flow["step"] = 3
        await update.message.reply_text("عکس محصول رو بفرست، یا بنویس: ندارد")
        return states.OWNER_WAIT_INPUT

    if step == 3:
        photo_file_id = None
        if update.message.photo:
            photo_file_id = update.message.photo[-1].file_id
        elif text and text not in ("ندارد", "-", ""):
            await update.message.reply_text("لطفاً عکس بفرست یا بنویس: ندارد")
            return states.OWNER_WAIT_INPUT
        elif not update.message.photo and text is None:
            await update.message.reply_text("لطفاً عکس بفرست یا بنویس: ندارد")
            return states.OWNER_WAIT_INPUT

        d = flow["data"]
        db.add_product(d["category_id"], d["name"], d["price"], photo_file_id=photo_file_id, description=d["description"])
        category_id = d["category_id"]
        name = d["name"]
        context.user_data.pop("owner_flow", None)
        await update.message.reply_text(
            f"✅ محصول «{name}» اضافه شد.",
            reply_markup=_products_list_keyboard(category_id),
        )
        return ConversationHandler.END


async def _handle_prod_field(update, context, flow):
    field = flow["field"]
    product_id = flow["data"]["product_id"]
    text = update.message.text.strip() if update.message.text else None

    p = db.get_product(product_id)
    if p is None:
        context.user_data.pop("owner_flow", None)
        await update.message.reply_text("این محصول دیگر موجود نیست.")
        return ConversationHandler.END

    if field == "name":
        if not text:
            await update.message.reply_text("لطفاً نام معتبر بفرست:")
            return states.OWNER_WAIT_INPUT
        db.update_product(product_id, name=text)

    elif field == "price":
        if not text or not text.isdigit():
            await update.message.reply_text("لطفاً فقط عدد بفرست:")
            return states.OWNER_WAIT_INPUT
        db.update_product(product_id, price=int(text))

    elif field == "desc":
        desc = None if (text is None or text in ("ندارد", "-", "")) else text
        db.update_product(product_id, description=desc)

    elif field == "photo":
        if update.message.photo:
            db.update_product(product_id, photo_file_id=update.message.photo[-1].file_id)
        elif text in ("ندارد", "-"):
            db.update_product(product_id, photo_file_id=None)
        else:
            await update.message.reply_text("لطفاً عکس بفرست یا بنویس: ندارد")
            return states.OWNER_WAIT_INPUT

    context.user_data.pop("owner_flow", None)
    await update.message.reply_text(
        f"✅ محصول «{db.get_product(product_id)['name']}» به‌روزرسانی شد.",
        reply_markup=_product_edit_keyboard(product_id),
    )
    return ConversationHandler.END


async def _handle_disc_add(update, context, flow):
    text = (update.message.text or "").strip() if update.message.text else ""
    step = flow["step"]

    if step == 0:
        if not text.isdigit() or not (1 <= int(text) <= 100):
            await update.message.reply_text("لطفاً عددی بین ۱ تا ۱۰۰ بفرست:")
            return states.OWNER_WAIT_INPUT
        flow["data"]["percent"] = int(text)
        flow["step"] = 1
        await update.message.reply_text("ظرفیت کل کد (تعداد آیتم قابل استفاده) رو بفرست:")
        return states.OWNER_WAIT_INPUT

    if step == 1:
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("لطفاً یک عدد مثبت بفرست:")
            return states.OWNER_WAIT_INPUT
        flow["data"]["capacity"] = int(text)
        flow["step"] = 2
        await update.message.reply_text("کد تا چند روز دیگه منقضی شود؟ (برای بدون انقضا عدد ۰ بفرست):")
        return states.OWNER_WAIT_INPUT

    if step == 2:
        if not text.isdigit():
            await update.message.reply_text("لطفاً فقط عدد بفرست:")
            return states.OWNER_WAIT_INPUT
        days = int(text)
        expiry_date = None
        if days > 0:
            expiry_date = (date.today() + timedelta(days=days)).isoformat()

        percent = flow["data"]["percent"]
        capacity = flow["data"]["capacity"]
        code = helpers.generate_discount_code(percent, capacity, expiry_date)
        context.user_data.pop("owner_flow", None)

        expiry_text = expiry_date or "بدون انقضا"
        await update.message.reply_text(
            f"✅ کد تخفیف ساخته شد:\n\n"
            f"`{code}`\n\n"
            f"درصد: {percent}٪ | ظرفیت: {capacity} | انقضا: {expiry_text}\n\n"
            "_روی کد بالا ضربه بزن تا کپی بشه 👆_",
            parse_mode="Markdown",
        )
        text2, kb = _discount_list_text_and_kb()
        await update.message.reply_text(text2, reply_markup=kb)
        return ConversationHandler.END


async def _handle_adm_add(update, context, flow):
    text = (update.message.text or "").strip() if update.message.text else ""
    if not text.lstrip("-").isdigit():
        await update.message.reply_text("لطفاً فقط آیدی عددی تلگرام رو بفرست:")
        return states.OWNER_WAIT_INPUT

    telegram_id = int(text)
    db.add_admin(telegram_id, "admin", update.effective_user.id)
    context.user_data.pop("owner_flow", None)

    await update.message.reply_text(f"✅ کاربر {telegram_id} به‌عنوان ادمین اضافه شد.")
    text2, kb = _admins_list_text_and_kb()
    await update.message.reply_text(text2, reply_markup=kb)
    return ConversationHandler.END


async def _handle_set_edit(update, context, flow):
    text = (update.message.text or "").strip() if update.message.text else ""
    key = flow["data"]["key"]
    label, value_type = SETTINGS_FIELDS[key]

    if value_type == "photo":
        if update.message.photo:
            value = update.message.photo[-1].file_id
        elif text in ("ندارد", "-", ""):
            value = ""
        else:
            await update.message.reply_text("لطفاً عکس منو رو مستقیم بفرست (یا بنویس: ندارد):")
            return states.OWNER_WAIT_INPUT
    elif value_type == "int":
        if not text.isdigit():
            await update.message.reply_text("لطفاً فقط عدد بفرست:")
            return states.OWNER_WAIT_INPUT
        value = text
    else:
        if not text:
            await update.message.reply_text("لطفاً یک مقدار معتبر بفرست:")
            return states.OWNER_WAIT_INPUT
        value = text

    db.set_setting(key, value)
    context.user_data.pop("owner_flow", None)

    await update.message.reply_text(f"✅ «{label}» به‌روزرسانی شد.")
    text2, kb = _settings_text_and_kb()
    await update.message.reply_text(text2, reply_markup=kb)
    return ConversationHandler.END


async def owner_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("owner_flow", None)
    await update.message.reply_text("عملیات لغو شد.", reply_markup=helpers.owner_menu_keyboard())
    return ConversationHandler.END


# ====== 🚫 تعطیل موقت ======

@_owner_only
async def toggle_closed_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current = db.get_setting("temp_closed", "0")
    if current == "1":
        db.set_setting("temp_closed", "0")
        await update.message.reply_text(
            "✅ کافه دوباره باز شد! مشتریا می‌تونن سفارش بدن.",
            reply_markup=helpers.owner_menu_keyboard(),
        )
    else:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ بله، تعطیل کن", callback_data="ownr_close_yes"),
                InlineKeyboardButton("🔙 انصراف", callback_data="ownr_close_no"),
            ]
        ])
        msg_text = db.get_setting("temp_closed_msg", "امروز تعطیلیم! فردا منتظرتونم ☕")
        await update.message.reply_text(
            f"آیا می‌خوای کافه رو موقتاً تعطیل کنی؟\n\n"
            f"پیام فعلی به مشتریان:\n«{msg_text}»\n\n"
            "برای تغییر پیام، از تنظیمات → «پیام تعطیلی» عوضش کن.",
            reply_markup=kb,
        )


async def toggle_closed_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not db.is_owner(update.effective_user.id):
        await query.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return

    if query.data == "ownr_close_yes":
        db.set_setting("temp_closed", "1")
        await query.edit_message_text("🚫 کافه تعطیل شد. مشتریا پیام تعطیلی می‌بینن.")
        await query.answer("تعطیل شد ✅")
    else:
        await query.edit_message_text("لغو شد — کافه همچنان بازه.")
        await query.answer()


# ====== 💾 بکاپ و بازیابی ======

@_owner_only
async def backup_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 دریافت بکاپ", callback_data="ownr_backup_send")],
        [InlineKeyboardButton("📥 بازیابی از فایل", callback_data="ownr_backup_restore")],
    ])
    await update.message.reply_text(
        "💾 بکاپ و بازیابی\n\n"
        "• «دریافت بکاپ»: یک فایل JSON شامل تنظیمات، محصولات، دسته‌بندی‌ها، "
        "آمار فروش و کدهای تخفیف برات می‌فرسته.\n"
        "• «بازیابی از فایل»: فایل JSON بکاپ رو آپلود کن تا اطلاعات بازگردونه بشه.",
        reply_markup=kb,
    )


async def backup_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not db.is_owner(update.effective_user.id):
        await query.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return ConversationHandler.END

    if query.data == "ownr_backup_send":
        await query.answer("در حال ساخت بکاپ...")
        await query.edit_message_text("⏳ در حال ساخت فایل بکاپ...")

        import json
        from datetime import datetime

        data = _export_backup()
        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

        filename = f"nova_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        from io import BytesIO
        buf = BytesIO(json_bytes)
        buf.name = filename

        await query.message.reply_document(
            document=buf,
            filename=filename,
            caption=(
                f"💾 بکاپ نُوا — {datetime.now().strftime('%Y/%m/%d %H:%M')}\n"
                f"شامل: تنظیمات، محصولات، دسته‌بندی‌ها، کدهای تخفیف، آمار فروش\n\n"
                "⚠️ برای بازیابی این فایل رو از منوی «بکاپ و بازیابی» آپلود کن."
            ),
        )
        return ConversationHandler.END

    if query.data == "ownr_backup_restore":
        context.user_data["owner_flow"] = {"type": "backup_restore", "step": 0, "data": {}}
        await query.answer()
        await query.edit_message_text(
            "📥 فایل JSON بکاپ رو همینجا آپلود کن.\n\n"
            "⚠️ این عملیات تنظیمات، محصولات و دسته‌بندی‌های فعلی رو با داده‌های بکاپ جایگزین می‌کنه.\n"
            "کاربران و سفارش‌های قبلی دست‌نخورده می‌مونن."
        )
        return states.OWNER_WAIT_INPUT

    await query.answer()
    return ConversationHandler.END


def _export_backup():
    """استخراج داده‌های ضروری برای بکاپ (بدون اطلاعات شخصی کاربران)."""
    from datetime import datetime

    # تنظیمات
    settings_rows = db.get_all_settings()
    settings = {r["key"]: r["value"] for r in settings_rows}

    # دسته‌بندی‌ها
    categories = [dict(r) for r in db.get_all_categories()]

    # محصولات
    products = []
    for cat in categories:
        prods = db.get_all_products_by_category(cat["id"])
        for p in prods:
            products.append(dict(p))

    # کدهای تخفیف
    discount_codes = [dict(r) for r in db.list_discount_codes()]

    # آمار فروش خلاصه (بدون جزئیات سفارش)
    total_stats, today_stats = db.get_sales_stats()

    return {
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        "settings": settings,
        "categories": categories,
        "products": products,
        "discount_codes": discount_codes,
        "stats_summary": {
            "total_orders": total_stats["cnt"],
            "total_revenue": total_stats["total"],
        },
    }


async def handle_backup_restore_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت فایل JSON و بازیابی داده‌ها."""
    if not db.is_owner(update.effective_user.id):
        return ConversationHandler.END

    flow = context.user_data.get("owner_flow", {})
    if flow.get("type") != "backup_restore":
        return ConversationHandler.END

    if not update.message.document:
        await update.message.reply_text("لطفاً فایل JSON بکاپ رو آپلود کن:")
        return states.OWNER_WAIT_INPUT

    doc = update.message.document
    if not doc.file_name.endswith(".json"):
        await update.message.reply_text("فایل باید با پسوند .json باشه:")
        return states.OWNER_WAIT_INPUT

    try:
        file = await context.bot.get_file(doc.file_id)
        from io import BytesIO
        buf = BytesIO()
        await file.download_to_memory(buf)
        buf.seek(0)
        import json
        data = json.loads(buf.read().decode("utf-8"))
    except Exception as e:
        await update.message.reply_text(f"⛔️ خطا در خواندن فایل: {e}")
        context.user_data.pop("owner_flow", None)
        return ConversationHandler.END

    if data.get("version") != 1:
        await update.message.reply_text("⛔️ فرمت بکاپ معتبر نیست.")
        context.user_data.pop("owner_flow", None)
        return ConversationHandler.END

    # بازیابی تنظیمات
    for k, v in data.get("settings", {}).items():
        db.set_setting(k, v)

    # بازیابی دسته‌بندی‌ها
    import database as _db
    with _db.db_cursor(commit=True) as cur:
        for cat in data.get("categories", []):
            cur.execute(
                "INSERT OR REPLACE INTO categories (id, name, emoji, prep_time_minutes, sort_order, active) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (cat["id"], cat["name"], cat.get("emoji"), cat.get("prep_time_minutes", 5),
                 cat.get("sort_order", 0), cat.get("active", 1)),
            )

        # بازیابی محصولات
        for p in data.get("products", []):
            cur.execute(
                "INSERT OR REPLACE INTO products (id, category_id, name, price, photo_file_id, description, active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (p["id"], p["category_id"], p["name"], p["price"],
                 p.get("photo_file_id"), p.get("description"), p.get("active", 1)),
            )

        # بازیابی کدهای تخفیف
        for c in data.get("discount_codes", []):
            cur.execute(
                "INSERT OR REPLACE INTO discount_codes "
                "(code, discount_percent, total_capacity, remaining_capacity, expiry_date, active) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (c["code"], c["discount_percent"], c["total_capacity"],
                 c["remaining_capacity"], c.get("expiry_date"), c.get("active", 1)),
            )

    context.user_data.pop("owner_flow", None)
    await update.message.reply_text(
        "✅ بازیابی با موفقیت انجام شد!\n"
        "تنظیمات، محصولات، دسته‌بندی‌ها و کدهای تخفیف بازگردونده شدن.",
        reply_markup=helpers.owner_menu_keyboard(),
    )
    return ConversationHandler.END
