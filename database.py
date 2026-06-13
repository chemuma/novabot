import sqlite3
from contextlib import contextmanager

DB_PATH = "nova.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_cursor(commit=False):
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()


def init_db():
    with db_cursor(commit=True) as cur:
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            name TEXT,
            phone TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS admins (
            telegram_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL CHECK(role IN ('admin','owner')),
            added_by INTEGER
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emoji TEXT,
            prep_time_minutes INTEGER DEFAULT 5,
            sort_order INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL REFERENCES categories(id),
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            photo_file_id TEXT,
            description TEXT,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS discount_codes (
            code TEXT PRIMARY KEY,
            discount_percent INTEGER NOT NULL,
            total_capacity INTEGER NOT NULL,
            remaining_capacity INTEGER NOT NULL,
            expiry_date TEXT,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_number TEXT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'PENDING_PREP',
            total_amount INTEGER NOT NULL,
            discount_code TEXT,
            deposit_required INTEGER DEFAULT 0,
            deposit_amount INTEGER DEFAULT 0,
            receipt_file_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            ready_estimate INTEGER,
            group_message_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL,
            price_at_order INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS satisfaction (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            rating INTEGER,
            comment TEXT,
            photo_file_id TEXT,
            liked_by_admin INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS counters (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cycle_start_date TEXT,
            month_in_cycle INTEGER DEFAULT 1,
            day_counter INTEGER DEFAULT 1,
            daily_order_counter INTEGER DEFAULT 0,
            last_order_date TEXT
        );
        """)

        # default settings
        defaults = {
            "open_hour": "9:00",
            "close_hour": "23:00",
            "big_order_threshold": "300000",
            "deposit_percent": "30",
            "card_number": "0000-0000-0000-0000",
            "cafe_phone": "021-00000000",
            "satisfaction_discount_percent": "5",
        }
        for k, v in defaults.items():
            cur.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
            )

        # init counters row
        cur.execute("SELECT * FROM counters WHERE id = 1")
        if cur.fetchone() is None:
            from datetime import date
            cur.execute(
                "INSERT INTO counters (id, cycle_start_date, month_in_cycle, day_counter, daily_order_counter, last_order_date) "
                "VALUES (1, ?, 1, 1, 0, NULL)",
                (date.today().isoformat(),),
            )


# ---------- Users ----------

def get_or_create_user(telegram_id):
    with db_cursor(commit=True) as cur:
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cur.fetchone()
        if row:
            return row
        cur.execute("INSERT INTO users (telegram_id) VALUES (?)", (telegram_id,))
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return cur.fetchone()


def get_user(telegram_id):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return cur.fetchone()


def update_user_info(telegram_id, name=None, phone=None):
    with db_cursor(commit=True) as cur:
        if name is not None:
            cur.execute("UPDATE users SET name = ? WHERE telegram_id = ?", (name, telegram_id))
        if phone is not None:
            cur.execute("UPDATE users SET phone = ? WHERE telegram_id = ?", (phone, telegram_id))


# ---------- Settings ----------

def get_setting(key, default=None):
    with db_cursor() as cur:
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


# ---------- Admins ----------

def is_admin(telegram_id):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM admins WHERE telegram_id = ?", (telegram_id,))
        return cur.fetchone() is not None


def is_owner(telegram_id):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM admins WHERE telegram_id = ? AND role = 'owner'", (telegram_id,))
        return cur.fetchone() is not None


def add_admin(telegram_id, role, added_by):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT OR REPLACE INTO admins (telegram_id, role, added_by) VALUES (?, ?, ?)",
            (telegram_id, role, added_by),
        )


def remove_admin(telegram_id):
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM admins WHERE telegram_id = ? AND role != 'owner'", (telegram_id,))


def list_admins():
    with db_cursor() as cur:
        cur.execute("SELECT * FROM admins")
        return cur.fetchall()


# ---------- Categories ----------

def get_active_categories():
    with db_cursor() as cur:
        cur.execute("SELECT * FROM categories WHERE active = 1 ORDER BY sort_order, id")
        return cur.fetchall()


def get_all_categories():
    with db_cursor() as cur:
        cur.execute("SELECT * FROM categories ORDER BY sort_order, id")
        return cur.fetchall()


def get_category(category_id):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        return cur.fetchone()


def add_category(name, emoji, prep_time_minutes=5, sort_order=0):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO categories (name, emoji, prep_time_minutes, sort_order, active) VALUES (?, ?, ?, ?, 1)",
            (name, emoji, prep_time_minutes, sort_order),
        )


def set_category_active(category_id, active):
    with db_cursor(commit=True) as cur:
        cur.execute("UPDATE categories SET active = ? WHERE id = ?", (1 if active else 0, category_id))


def delete_category(category_id):
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def update_category_prep_time(category_id, minutes):
    with db_cursor(commit=True) as cur:
        cur.execute("UPDATE categories SET prep_time_minutes = ? WHERE id = ?", (minutes, category_id))


# ---------- Products ----------

def get_active_products_by_category(category_id):
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM products WHERE category_id = ? AND active = 1 ORDER BY id", (category_id,)
        )
        return cur.fetchall()


def get_all_products_by_category(category_id):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM products WHERE category_id = ? ORDER BY id", (category_id,))
        return cur.fetchall()


def get_product(product_id):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        return cur.fetchone()


def add_product(category_id, name, price, photo_file_id=None, description=None):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO products (category_id, name, price, photo_file_id, description, active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (category_id, name, price, photo_file_id, description),
        )


def update_product(product_id, **fields):
    if not fields:
        return
    keys = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [product_id]
    with db_cursor(commit=True) as cur:
        cur.execute(f"UPDATE products SET {keys} WHERE id = ?", values)


def set_product_active(product_id, active):
    with db_cursor(commit=True) as cur:
        cur.execute("UPDATE products SET active = ? WHERE id = ?", (1 if active else 0, product_id))


def delete_product(product_id):
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM products WHERE id = ?", (product_id,))


# ---------- Cart ----------

def get_cart_items(user_id):
    with db_cursor() as cur:
        cur.execute(
            """SELECT cart_items.id as cart_id, products.id as product_id, products.name,
                      products.price, cart_items.quantity
               FROM cart_items
               JOIN products ON products.id = cart_items.product_id
               WHERE cart_items.user_id = ?""",
            (user_id,),
        )
        return cur.fetchall()


def add_to_cart(user_id, product_id, quantity):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "SELECT * FROM cart_items WHERE user_id = ? AND product_id = ?", (user_id, product_id)
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE cart_items SET quantity = quantity + ? WHERE id = ?", (quantity, row["id"])
            )
        else:
            cur.execute(
                "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)",
                (user_id, product_id, quantity),
            )


def clear_cart(user_id):
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))


def get_cart_total(user_id):
    items = get_cart_items(user_id)
    return sum(i["price"] * i["quantity"] for i in items)


# ---------- Discount codes ----------

def get_discount_code(code):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM discount_codes WHERE code = ?", (code,))
        return cur.fetchone()


def add_discount_code(code, percent, capacity, expiry_date):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO discount_codes (code, discount_percent, total_capacity, remaining_capacity, expiry_date, active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (code, percent, capacity, capacity, expiry_date),
        )


def list_discount_codes():
    with db_cursor() as cur:
        cur.execute("SELECT * FROM discount_codes ORDER BY active DESC, code")
        return cur.fetchall()


def deactivate_discount_code(code):
    with db_cursor(commit=True) as cur:
        cur.execute("UPDATE discount_codes SET active = 0 WHERE code = ?", (code,))


def consume_discount_code(code, items_count):
    """Subtract items_count from remaining_capacity; auto-deactivate at <= 0."""
    with db_cursor(commit=True) as cur:
        cur.execute("SELECT remaining_capacity FROM discount_codes WHERE code = ?", (code,))
        row = cur.fetchone()
        if not row:
            return
        new_remaining = row["remaining_capacity"] - items_count
        if new_remaining <= 0:
            cur.execute(
                "UPDATE discount_codes SET remaining_capacity = ?, active = 0 WHERE code = ?",
                (new_remaining, code),
            )
        else:
            cur.execute(
                "UPDATE discount_codes SET remaining_capacity = ? WHERE code = ?",
                (new_remaining, code),
            )


# ---------- Orders ----------

def generate_display_number():
    """Generate #MDDNN order number and update counters."""
    from datetime import date
    today = date.today().isoformat()
    with db_cursor(commit=True) as cur:
        cur.execute("SELECT * FROM counters WHERE id = 1")
        c = cur.fetchone()

        day_counter = c["day_counter"]
        daily_order_counter = c["daily_order_counter"]
        last_order_date = c["last_order_date"]

        if last_order_date != today:
            if last_order_date is not None:
                day_counter += 1
            daily_order_counter = 0
            last_order_date = today

        daily_order_counter += 1

        cur.execute(
            "UPDATE counters SET day_counter = ?, daily_order_counter = ?, last_order_date = ? WHERE id = 1",
            (day_counter, daily_order_counter, last_order_date),
        )

        month = c["month_in_cycle"]
        return f"#{month}{day_counter:02d}{daily_order_counter:02d}"


def create_order(user_id, total_amount, discount_code=None, deposit_required=0,
                  deposit_amount=0, status="PENDING_PREP", ready_estimate=None):
    display_number = generate_display_number()
    with db_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO orders (display_number, user_id, status, total_amount, discount_code,
                                    deposit_required, deposit_amount, ready_estimate)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (display_number, user_id, status, total_amount, discount_code,
             deposit_required, deposit_amount, ready_estimate),
        )
        order_id = cur.lastrowid
        return order_id, display_number


def add_order_item(order_id, product_id, quantity, price_at_order):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, price_at_order) VALUES (?, ?, ?, ?)",
            (order_id, product_id, quantity, price_at_order),
        )


def get_order(order_id):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return cur.fetchone()


def get_order_items(order_id):
    with db_cursor() as cur:
        cur.execute(
            """SELECT order_items.*, products.name as product_name
               FROM order_items JOIN products ON products.id = order_items.product_id
               WHERE order_id = ?""",
            (order_id,),
        )
        return cur.fetchall()


def update_order_status(order_id, status):
    with db_cursor(commit=True) as cur:
        cur.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))


def set_order_receipt(order_id, file_id):
    with db_cursor(commit=True) as cur:
        cur.execute("UPDATE orders SET receipt_file_id = ? WHERE id = ?", (file_id, order_id))


def set_order_group_message(order_id, message_id):
    with db_cursor(commit=True) as cur:
        cur.execute("UPDATE orders SET group_message_id = ? WHERE id = ?", (message_id, order_id))


def get_user_orders(user_id, limit=10):
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        )
        return cur.fetchall()


def get_active_orders_for_user(user_id):
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM orders WHERE user_id = ? AND status IN "
            "('PENDING_PREP','AWAITING_DEPOSIT','PREPARING','READY') ORDER BY id DESC",
            (user_id,),
        )
        return cur.fetchall()


def get_pending_cancel_candidates():
    """Orders awaiting deposit receipt for timeout check."""
    with db_cursor() as cur:
        cur.execute("SELECT * FROM orders WHERE status = 'AWAITING_DEPOSIT'")
        return cur.fetchall()


# ---------- Satisfaction ----------

def create_satisfaction_entry(order_id, user_id):
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO satisfaction (order_id, user_id) VALUES (?, ?)", (order_id, user_id)
        )
        return cur.lastrowid


def get_satisfaction_by_order(order_id):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM satisfaction WHERE order_id = ?", (order_id,))
        return cur.fetchone()


def update_satisfaction_rating(satisfaction_id, rating):
    with db_cursor(commit=True) as cur:
        cur.execute("UPDATE satisfaction SET rating = ? WHERE id = ?", (rating, satisfaction_id))


def update_satisfaction_content(satisfaction_id, comment=None, photo_file_id=None):
    with db_cursor(commit=True) as cur:
        if comment is not None:
            cur.execute("UPDATE satisfaction SET comment = ? WHERE id = ?", (comment, satisfaction_id))
        if photo_file_id is not None:
            cur.execute("UPDATE satisfaction SET photo_file_id = ? WHERE id = ?", (photo_file_id, satisfaction_id))


def get_unrated_orders(user_id):
    with db_cursor() as cur:
        cur.execute(
            """SELECT orders.* FROM orders
               LEFT JOIN satisfaction ON satisfaction.order_id = orders.id
               WHERE orders.user_id = ? AND orders.status = 'DELIVERED'
                 AND (satisfaction.id IS NULL OR satisfaction.rating IS NULL)""",
            (user_id,),
        )
        return cur.fetchall()


def get_satisfaction_by_id(satisfaction_id):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM satisfaction WHERE id = ?", (satisfaction_id,))
        return cur.fetchone()


def mark_satisfaction_liked(satisfaction_id):
    with db_cursor(commit=True) as cur:
        cur.execute("UPDATE satisfaction SET liked_by_admin = 1 WHERE id = ?", (satisfaction_id,))


# ---------- Customer club & stats ----------

def get_all_users_for_club():
    with db_cursor() as cur:
        cur.execute("SELECT name, phone, created_at FROM users ORDER BY created_at DESC")
        return cur.fetchall()


def reset_customer_club():
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM users")


def get_sales_stats():
    with db_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(total_amount),0) as total FROM orders "
            "WHERE status != 'CANCELLED'"
        )
        total = cur.fetchone()
        cur.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(total_amount),0) as total FROM orders "
            "WHERE status != 'CANCELLED' AND date(created_at) = date('now')"
        )
        today = cur.fetchone()
        return total, today
