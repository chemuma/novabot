from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes

import config
import database as db
import helpers


# ---------- ورود به فلوی سفارش جدید ----------

async def new_order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # بررسی ساعت کاری
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
            "فعلاً دسته‌بندی فعالی ندارم که نشونت بدم — بزودی اضافه می‌شه 🙏",
            reply_markup=helpers.main_menu_keyboard(),
        )
        return

    text = "🍽 از کجا شروع کنیم؟ یه دسته‌بندی انتخاب کن:"
    menu_photo = helpers.get_menu_photo()
    if menu_photo:
        await update.message.reply_photo(
            photo=menu_photo,
            caption=text,
            reply_markup=helpers.categories_keyboard(),
        )
    else:
        await update.message.reply_text(text, reply_markup=helpers.categories_keyboard())


# ---------- انتخاب دسته‌بندی → نمایش محصولات ----------

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category_id = int(query.data.split("_", 1)[1])
    category = db.get_category(category_id)
    if category is None:
        await query.answer("این دسته‌بندی پیدا نشد.", show_alert=True)
        return

    products = db.get_active_products_by_category(category_id)
    emoji = category["emoji"] or "🍴"
    if products:
        text = f"{emoji} {category['name']}\n\nکدوم رو می‌خوای؟"
    else:
        text = f"{emoji} {category['name']}\n\nفعلاً چیزی توی این دسته نداریم."

    keyboard = helpers.products_keyboard(category_id)
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=text, reply_markup=keyboard)
        else:
            await query.edit_message_text(text, reply_markup=keyboard)
    except Exception:
        await query.message.reply_text(text, reply_markup=keyboard)


# ---------- نمایش جزئیات یک محصول ----------

async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split("_", 1)[1])
    product = db.get_product(product_id)
    if product is None or not product["active"]:
        await query.answer("این محصول فعلاً موجود نیست.", show_alert=True)
        return

    temp_qty = context.user_data.setdefault("temp_qty", {})
    temp_qty[product_id] = 1

    caption = helpers.product_caption(product)
    keyboard = helpers.product_detail_keyboard(product_id, 1)

    if product["photo_file_id"]:
        await query.message.reply_photo(product["photo_file_id"], caption=caption, reply_markup=keyboard)
    else:
        await query.message.reply_text(caption, reply_markup=keyboard)


# ---------- تغییر تعداد / افزودن به سبد / بازگشت ----------

async def product_quantity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    action, product_id = query.data.rsplit("_", 1)
    product_id = int(product_id)
    product = db.get_product(product_id)
    if product is None:
        await query.answer("این محصول پیدا نشد.", show_alert=True)
        return

    temp_qty = context.user_data.setdefault("temp_qty", {})
    qty = temp_qty.get(product_id, 1)

    if action == "pq_inc":
        qty = min(qty + 1, 20)
        temp_qty[product_id] = qty
        await query.edit_message_reply_markup(reply_markup=helpers.product_detail_keyboard(product_id, qty))
        await query.answer()

    elif action == "pq_dec":
        qty = max(qty - 1, 1)
        temp_qty[product_id] = qty
        await query.edit_message_reply_markup(reply_markup=helpers.product_detail_keyboard(product_id, qty))
        await query.answer()

    elif action == "pq_add":
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)
        db.add_to_cart(user["id"], product_id, qty)
        temp_qty.pop(product_id, None)
        await query.answer(f"✅ {qty} تا «{product['name']}» به سبد اضافه شد", show_alert=False)
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


# ---------- ناوبری بین دسته‌بندی‌ها / سبد خرید ----------

async def nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "noop":
        return

    if query.data == "nav_categories":
        categories = db.get_active_categories()
        text = "🍽 از کجا شروع کنیم؟ یه دسته‌بندی انتخاب کن:"
        keyboard = helpers.categories_keyboard()
        if not categories:
            text = "فعلاً دسته‌بندی فعالی نداریم."
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=text, reply_markup=keyboard)
            else:
                await query.edit_message_text(text, reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(text, reply_markup=keyboard)

    elif query.data == "nav_cart":
        telegram_id = update.effective_user.id
        user = db.get_or_create_user(telegram_id)
        await send_cart(query.message, user["id"], context, as_new_message=True)


# ---------- نمایش سبد خرید ----------

async def cart_view_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_or_create_user(telegram_id)
    await send_cart(update.message, user["id"], context, as_new_message=True)


async def send_cart(message, user_id, context, as_new_message=False, edit_query=None):
    text, total = helpers.build_cart_text(user_id)

    discount_code = context.user_data.get("cart_discount")
    if discount_code and total > 0:
        code_row = db.get_discount_code(discount_code)
        if code_row and helpers.is_discount_code_usable(code_row, sum_cart_items(user_id)):
            discounted_total = helpers.apply_discount(total, code_row["discount_percent"])
            text += (
                f"\n\n🎟 کد تخفیف «{discount_code}» ({code_row['discount_percent']}٪) اعمال شده.\n"
                f"جمع کل با تخفیف: {helpers.format_price(discounted_total)}"
            )
        else:
            context.user_data.pop("cart_discount", None)

    keyboard = helpers.cart_inline_keyboard()

    if edit_query is not None:
        try:
            await edit_query.edit_message_text(text, reply_markup=keyboard)
            return
        except Exception:
            pass

    await message.reply_text(text, reply_markup=keyboard)


def sum_cart_items(user_id):
    items = db.get_cart_items(user_id)
    return sum(i["quantity"] for i in items)


# ---------- اکشن‌های اینلاین سبد خرید ----------

async def cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    telegram_id = update.effective_user.id
    user = db.get_or_create_user(telegram_id)

    if query.data == "cart_continue":
        await query.answer()
        # بررسی ساعت کاری حتی در ادامه خرید
        if not helpers.is_cafe_open():
            await query.message.reply_text(helpers.cafe_closed_text())
            return
        categories = db.get_active_categories()
        text = "🍽 از کجا شروع کنیم؟ یه دسته‌بندی انتخاب کن:"
        if not categories:
            text = "فعلاً دسته‌بندی فعالی نداریم."
        menu_photo = helpers.get_menu_photo()
        if menu_photo:
            await query.message.reply_photo(photo=menu_photo, caption=text, reply_markup=helpers.categories_keyboard())
        else:
            await query.message.reply_text(text, reply_markup=helpers.categories_keyboard())

    elif query.data == "cart_clear":
        db.clear_cart(user["id"])
        context.user_data.pop("cart_discount", None)
        await query.answer("🗑 سبد خرید پاک شد")
        await send_cart(query.message, user["id"], context, edit_query=query)

    elif query.data == "cart_discount":
        await query.answer()
        items = db.get_cart_items(user["id"])
        if not items:
            await query.message.reply_text("سبد خریدت خالیه؛ اول یه چیزی اضافه کن 🙂")
            return
        await query.message.reply_text(
            "🎟 کد تخفیفت رو بفرست (مثل ABC5XYZ):",
            reply_markup=helpers.discount_entry_keyboard(),
        )
        context.user_data["awaiting_discount_code"] = True

    elif query.data == "cart_checkout":
        # بررسی ساعت کاری قبل از ثبت نهایی
        if not helpers.is_cafe_open():
            await query.answer()
            await query.message.reply_text(
                helpers.cafe_closed_text(),
                reply_markup=helpers.main_menu_keyboard(),
            )
            return ConversationHandler.END
        await query.answer()
        from telegram.ext import ConversationHandler
        from handlers import checkout
        return await checkout.start_checkout(update, context, user)
