from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import config
import database as db
import helpers
import states
from handlers import discount


# ═══════════════════════════════════════
# ۱. سفارش جدید
# ═══════════════════════════════════════

async def new_order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not helpers.is_cafe_open():
        await update.message.reply_text(
            helpers.cafe_closed_text(),
            reply_markup=helpers.main_menu_keyboard(),
        )
        return

    context.user_data.pop("temp_qty", None)
    categories = db.get_active_categories()
    if not categories:
        await update.message.reply_text(
            "فعلاً دسته‌بندی فعالی ندارم — بزودی اضافه می‌شه 🙏",
            reply_markup=helpers.main_menu_keyboard(),
        )
        return

    text = "🍽 از کجا شروع کنیم؟ یه دسته‌بندی انتخاب کن:"
    menu_photo = helpers.get_menu_photo()
    if menu_photo:
        await update.message.reply_photo(
            photo=menu_photo, caption=text, reply_markup=helpers.categories_keyboard()
        )
    else:
        await update.message.reply_text(text, reply_markup=helpers.categories_keyboard())


# ═══════════════════════════════════════
# ۲. ناوبری دسته‌بندی‌ها
# ═══════════════════════════════════════

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category_id = int(query.data.split("_", 1)[1])
    category = db.get_category(category_id)
    if category is None:
        return

    emoji = category["emoji"] or "🍴"
    text = f"{emoji} {category['name']}\n\nکدوم رو می‌خوای؟"
    keyboard = helpers.products_keyboard(category_id)
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=text, reply_markup=keyboard)
        else:
            await query.edit_message_text(text, reply_markup=keyboard)
    except Exception:
        await query.message.reply_text(text, reply_markup=keyboard)


# ═══════════════════════════════════════
# ۳. جزئیات محصول + تعداد
# ═══════════════════════════════════════

async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split("_", 1)[1])
    product = db.get_product(product_id)
    if product is None or not product["active"]:
        await query.answer("این محصول فعلاً موجود نیست.", show_alert=True)
        return

    context.user_data.setdefault("temp_qty", {})[product_id] = 1
    caption = helpers.product_caption(product)
    keyboard = helpers.product_detail_keyboard(product_id, 1)

    if product["photo_file_id"]:
        await query.message.reply_photo(product["photo_file_id"], caption=caption, reply_markup=keyboard)
    else:
        await query.message.reply_text(caption, reply_markup=keyboard)


async def product_quantity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, product_id = query.data.rsplit("_", 1)
    product_id = int(product_id)
    product = db.get_product(product_id)
    if product is None:
        await query.answer()
        return

    temp_qty = context.user_data.setdefault("temp_qty", {})
    qty = temp_qty.get(product_id, 1)

    if action == "pq_inc":
        qty = min(qty + 1, 20)
        temp_qty[product_id] = qty
        try:
            await query.edit_message_reply_markup(reply_markup=helpers.product_detail_keyboard(product_id, qty))
        except Exception:
            pass
        await query.answer()

    elif action == "pq_dec":
        qty = max(qty - 1, 1)
        temp_qty[product_id] = qty
        try:
            await query.edit_message_reply_markup(reply_markup=helpers.product_detail_keyboard(product_id, qty))
        except Exception:
            pass
        await query.answer()

    elif action == "pq_add":
        user = db.get_or_create_user(update.effective_user.id)
        db.add_to_cart(user["id"], product_id, qty)
        temp_qty.pop(product_id, None)
        await query.answer(f"✅ {qty}× {product['name']} به سبد اضافه شد")
        # حذف پیام جزئیات محصول
        try:
            await query.message.delete()
        except Exception:
            pass

    elif action == "pq_back":
        temp_qty.pop(product_id, None)
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass


# ═══════════════════════════════════════
# ۴. ناوبری کلی
# ═══════════════════════════════════════

async def nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "noop":
        return

    if query.data == "nav_categories":
        text = "🍽 از کجا شروع کنیم؟ یه دسته‌بندی انتخاب کن:"
        keyboard = helpers.categories_keyboard()
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=keyboard)
            else:
                await query.edit_message_text(text, reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(text, reply_markup=keyboard)

    elif query.data == "nav_cart":
        user = db.get_or_create_user(update.effective_user.id)
        await _show_cart(query.message, user["id"], context, as_reply=True)


# ═══════════════════════════════════════
# ۵. سبد خرید
# ═══════════════════════════════════════

async def cart_view_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_or_create_user(update.effective_user.id)
    await _show_cart(update.message, user["id"], context, as_reply=True)


async def _show_cart(message, user_id, context, as_reply=False, edit_query=None):
    discount_code = context.user_data.get("cart_discount")
    text, total, final_total, items = helpers.build_cart_text(user_id, discount_code)
    keyboard = helpers.cart_inline_keyboard(items) if items else None

    if edit_query is not None:
        try:
            await edit_query.edit_message_text(text, reply_markup=keyboard)
            return
        except Exception:
            pass

    await message.reply_text(text, reply_markup=keyboard)


def sum_cart_items(user_id):
    return sum(i["quantity"] for i in db.get_cart_items(user_id))


# ═══════════════════════════════════════
# ۶. ویرایش آیتم‌های سبد (ce_*)
# ═══════════════════════════════════════

async def cart_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = db.get_or_create_user(update.effective_user.id)

    action, product_id = query.data.rsplit("_", 1)
    product_id = int(product_id)

    if action == "ce_inc":
        db.update_cart_item_qty(user["id"], product_id, +1)
        await query.answer("➕")
    elif action == "ce_dec":
        db.update_cart_item_qty(user["id"], product_id, -1)
        await query.answer("➖")
    elif action == "ce_del":
        db.remove_cart_item(user["id"], product_id)
        await query.answer("🗑 حذف شد")

    # بازنمایی سبد در همان پیام
    discount_code = context.user_data.get("cart_discount")
    text, total, final_total, items = helpers.build_cart_text(user["id"], discount_code)
    keyboard = helpers.cart_inline_keyboard(items) if items else None

    try:
        await query.edit_message_text(text, reply_markup=keyboard)
    except Exception:
        pass


# ═══════════════════════════════════════
# ۷. اکشن‌های سبد خرید (cart_*)
# ═══════════════════════════════════════

async def cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = db.get_or_create_user(update.effective_user.id)

    if query.data == "cart_continue":
        await query.answer()
        if not helpers.is_cafe_open():
            await query.message.reply_text(helpers.cafe_closed_text())
            return
        text = "🍽 از کجا شروع کنیم؟ یه دسته‌بندی انتخاب کن:"
        menu_photo = helpers.get_menu_photo()
        if menu_photo:
            await query.message.reply_photo(
                photo=menu_photo, caption=text, reply_markup=helpers.categories_keyboard()
            )
        else:
            await query.message.reply_text(text, reply_markup=helpers.categories_keyboard())

    elif query.data == "cart_clear":
        db.clear_cart(user["id"])
        context.user_data.pop("cart_discount", None)
        await query.answer("🗑 سبد پاک شد")
        try:
            await query.edit_message_text("🛒 سبد خریدت خالیه.", reply_markup=None)
        except Exception:
            pass

    elif query.data == "cart_discount":
        await query.answer()
        items = db.get_cart_items(user["id"])
        if not items:
            await query.message.reply_text("سبد خریدت خالیه؛ اول یه چیزی اضافه کن 🙂")
            return
        await query.message.reply_text(
            "🎟 کد تخفیفت رو بفرست:",
            reply_markup=helpers.discount_entry_keyboard(),
        )
        context.user_data["awaiting_discount_code"] = True

    elif query.data == "cart_checkout":
        if not helpers.is_cafe_open():
            await query.answer()
            await query.message.reply_text(
                helpers.cafe_closed_text(), reply_markup=helpers.main_menu_keyboard()
            )
            return ConversationHandler.END
        await query.answer()
        from handlers import checkout
        return await checkout.start_checkout(update, context, user)
