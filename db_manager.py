import sqlite3
from datetime import datetime, timedelta

from config import DISCOUNT_TIERS

STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"

STATUS_LABELS = {
    STATUS_PROCESSING: "⏳ В обработке",
    STATUS_COMPLETED: "✅ Завершён",
    STATUS_CANCELLED: "❌ Отменён",
}


class Database:
    def __init__(self, db_name="shop.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.create_tables()
        self._migrate()
        self._normalize_order_statuses()

    def create_tables(self):
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            specs TEXT,
            stock INTEGER DEFAULT 0,
            article TEXT,
            brand TEXT,
            image_file_id TEXT,
            is_emergency INTEGER DEFAULT 0)"""
        )
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'client')"""
        )
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            items_text TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'processing',
            delivery_type TEXT,
            phone TEXT,
            address TEXT,
            discount REAL DEFAULT 0)"""
        )
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            phone TEXT,
            city TEXT)"""
        )
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS cart_items (
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (user_id, product_id),
            FOREIGN KEY (product_id) REFERENCES products(id))"""
        )
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, product_id),
            FOREIGN KEY (product_id) REFERENCES products(id))"""
        )
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS bot_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            user_id INTEGER,
            created_at TEXT NOT NULL)"""
        )
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS faq_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1)"""
        )
        self.conn.commit()

    def _migrate(self):
        product_cols = {
            "stock": "INTEGER DEFAULT 0",
            "article": "TEXT",
            "brand": "TEXT",
            "image_file_id": "TEXT",
            "is_emergency": "INTEGER DEFAULT 0",
        }
        self.cursor.execute("PRAGMA table_info(products)")
        existing = {row[1] for row in self.cursor.fetchall()}
        for col, typedef in product_cols.items():
            if col not in existing:
                self.cursor.execute(f"ALTER TABLE products ADD COLUMN {col} {typedef}")

        order_cols = {
            "delivery_type": "TEXT",
            "phone": "TEXT",
            "address": "TEXT",
            "discount": "REAL DEFAULT 0",
        }
        self.cursor.execute("PRAGMA table_info(orders)")
        existing = {row[1] for row in self.cursor.fetchall()}
        for col, typedef in order_cols.items():
            if col not in existing:
                self.cursor.execute(f"ALTER TABLE orders ADD COLUMN {col} {typedef}")

        user_cols = {
            "username": "TEXT",
            "first_name": "TEXT",
            "first_seen": "TEXT",
            "last_seen": "TEXT",
        }
        self.cursor.execute("PRAGMA table_info(users)")
        existing = {row[1] for row in self.cursor.fetchall()}
        for col, typedef in user_cols.items():
            if col not in existing:
                self.cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")
        self.conn.commit()

    def _normalize_order_statuses(self):
        mapping = {
            "В обработке": STATUS_PROCESSING,
            "completed": STATUS_COMPLETED,
            "✅ Завершен": STATUS_COMPLETED,
            "cancelled": STATUS_CANCELLED,
            "❌ Отменен": STATUS_CANCELLED,
        }
        for old, new in mapping.items():
            self.cursor.execute("UPDATE orders SET status = ? WHERE status = ?", (new, old))
        self.conn.commit()

    # --- PRODUCTS ---
    def add_product(self, name, price, category, specs, stock=0, article="", brand="", image_file_id=None, is_emergency=0):
        self.cursor.execute(
            """INSERT INTO products (name, price, category, specs, stock, article, brand, image_file_id, is_emergency)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, price, category.lower(), specs, stock, article, brand, image_file_id, is_emergency),
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def get_product_by_id(self, pid):
        self.cursor.execute("SELECT * FROM products WHERE id = ?", (pid,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def update_product(self, pid, name, price, specs, stock=None):
        if stock is not None:
            self.cursor.execute(
                "UPDATE products SET name = ?, price = ?, specs = ?, stock = ? WHERE id = ?",
                (name, price, specs, stock, pid),
            )
        else:
            self.cursor.execute(
                "UPDATE products SET name = ?, price = ?, specs = ? WHERE id = ?",
                (name, price, specs, pid),
            )
        self.conn.commit()

    def update_product_field(self, pid, field, value):
        allowed = {
            "name", "price", "specs", "stock", "category", "article",
            "brand", "image_file_id", "is_emergency",
        }
        if field not in allowed:
            return
        self.cursor.execute(f"UPDATE products SET {field} = ? WHERE id = ?", (value, pid))
        self.conn.commit()

    def update_product_image(self, pid, file_id):
        self.update_product_field(pid, "image_file_id", file_id)

    def rename_category(self, old_name, new_name):
        self.cursor.execute(
            "UPDATE products SET category = ? WHERE category = ?",
            (new_name.lower(), old_name.lower()),
        )
        self.conn.commit()

    def get_category_stats(self):
        self.cursor.execute(
            """SELECT category, COUNT(*) as cnt FROM products
               GROUP BY category ORDER BY category"""
        )
        return [dict(r) for r in self.cursor.fetchall()]

    def delete_product(self, pid):
        self.cursor.execute("DELETE FROM cart_items WHERE product_id = ?", (pid,))
        self.cursor.execute("DELETE FROM favorites WHERE product_id = ?", (pid,))
        self.cursor.execute("DELETE FROM products WHERE id = ?", (pid,))
        self.conn.commit()

    def get_categories(self):
        self.cursor.execute("SELECT DISTINCT category FROM products ORDER BY category")
        return [r[0] for r in self.cursor.fetchall()]

    def get_products(self, category):
        self.cursor.execute(
            "SELECT * FROM products WHERE category = ? ORDER BY name",
            (category.lower(),),
        )
        return [dict(r) for r in self.cursor.fetchall()]

    def get_emergency_products(self):
        self.cursor.execute(
            "SELECT * FROM products WHERE is_emergency = 1 ORDER BY name LIMIT 12"
        )
        return [dict(r) for r in self.cursor.fetchall()]

    def search_products(self, query, limit=10):
        q = f"%{query.strip()}%"
        self.cursor.execute(
            """SELECT * FROM products
               WHERE name LIKE ? OR article LIKE ? OR specs LIKE ? OR brand LIKE ?
               ORDER BY name LIMIT ?""",
            (q, q, q, q, limit),
        )
        return [dict(r) for r in self.cursor.fetchall()]

    def decrease_stock(self, product_id, qty):
        self.cursor.execute(
            """UPDATE products SET stock = CASE
               WHEN stock - ? < 0 THEN 0 ELSE stock - ? END WHERE id = ?""",
            (qty, qty, product_id),
        )
        self.conn.commit()

    # --- CART ---
    def get_cart_count(self, user_id):
        self.cursor.execute(
            "SELECT COALESCE(SUM(qty), 0) FROM cart_items WHERE user_id = ?",
            (user_id,),
        )
        return self.cursor.fetchone()[0]

    def get_cart_items(self, user_id):
        self.cursor.execute(
            """SELECT c.product_id, c.qty, p.name, p.price, p.stock
               FROM cart_items c
               JOIN products p ON p.id = c.product_id
               WHERE c.user_id = ?""",
            (user_id,),
        )
        return [dict(r) for r in self.cursor.fetchall()]

    def add_to_cart(self, user_id, product_id, qty=1):
        product = self.get_product_by_id(product_id)
        if not product:
            return False, "Товар не найден"
        if product["stock"] <= 0:
            return False, "Нет в наличии"
        self.cursor.execute(
            "SELECT qty FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        row = self.cursor.fetchone()
        new_qty = (row[0] if row else 0) + qty
        if new_qty > product["stock"]:
            return False, f"Доступно только {product['stock']} шт."
        if row:
            self.cursor.execute(
                "UPDATE cart_items SET qty = ? WHERE user_id = ? AND product_id = ?",
                (new_qty, user_id, product_id),
            )
        else:
            self.cursor.execute(
                "INSERT INTO cart_items (user_id, product_id, qty) VALUES (?, ?, ?)",
                (user_id, product_id, qty),
            )
        self.conn.commit()
        return True, None

    def change_cart_qty(self, user_id, product_id, delta):
        self.cursor.execute(
            "SELECT qty FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        row = self.cursor.fetchone()
        if not row:
            return False
        new_qty = row[0] + delta
        if new_qty <= 0:
            self.remove_from_cart(user_id, product_id)
            return True
        product = self.get_product_by_id(product_id)
        if product and new_qty > product["stock"]:
            return False
        self.cursor.execute(
            "UPDATE cart_items SET qty = ? WHERE user_id = ? AND product_id = ?",
            (new_qty, user_id, product_id),
        )
        self.conn.commit()
        return True

    def remove_from_cart(self, user_id, product_id):
        self.cursor.execute(
            "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        self.conn.commit()

    def clear_cart(self, user_id):
        self.cursor.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def calc_cart_total(self, user_id):
        items = self.get_cart_items(user_id)
        subtotal = sum(i["price"] * i["qty"] for i in items)
        discount_rate = self.get_discount_rate(subtotal)
        discount = subtotal * discount_rate
        return subtotal, discount, subtotal - discount, discount_rate

    @staticmethod
    def get_discount_rate(subtotal):
        rate = 0.0
        for threshold, disc in DISCOUNT_TIERS:
            if subtotal >= threshold:
                rate = disc
        return rate

    def format_cart_text(self, user_id):
        items = self.get_cart_items(user_id)
        if not items:
            return None, 0, 0, 0, 0
        lines = []
        for i in items:
            line_total = i["price"] * i["qty"]
            lines.append(f"• {i['name']} × {i['qty']} — {int(line_total):,} ₽")
        subtotal, discount, total, rate = self.calc_cart_total(user_id)
        text = "📦 **Ваша корзина:**\n\n" + "\n".join(lines)
        text += f"\n\nСумма: {int(subtotal):,} ₽"
        if rate > 0:
            text += f"\nСкидка {int(rate * 100)}%: −{int(discount):,} ₽"
        text += f"\n**ИТОГО: {int(total):,} ₽**"
        return text, subtotal, discount, total, rate

    # --- FAVORITES ---
    def toggle_favorite(self, user_id, product_id):
        self.cursor.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        if self.cursor.fetchone():
            self.cursor.execute(
                "DELETE FROM favorites WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            )
            self.conn.commit()
            return False
        self.cursor.execute(
            "INSERT INTO favorites (user_id, product_id) VALUES (?, ?)",
            (user_id, product_id),
        )
        self.conn.commit()
        return True

    def get_favorites(self, user_id):
        self.cursor.execute(
            """SELECT p.* FROM favorites f
               JOIN products p ON p.id = f.product_id
               WHERE f.user_id = ?""",
            (user_id,),
        )
        return [dict(r) for r in self.cursor.fetchall()]

    # --- PROFILE ---
    def save_profile(self, user_id, name, phone, city):
        self.cursor.execute(
            "INSERT OR REPLACE INTO user_profiles VALUES (?, ?, ?, ?)",
            (user_id, name, phone, city),
        )
        self.conn.commit()

    def get_profile(self, user_id):
        self.cursor.execute(
            "SELECT full_name, phone, city FROM user_profiles WHERE user_id = ?",
            (user_id,),
        )
        return self.cursor.fetchone()

    def ensure_user(self, user_id, role="client"):
        self.cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        if not self.cursor.fetchone():
            now = datetime.utcnow().isoformat()
            self.cursor.execute(
                """INSERT INTO users (user_id, role, first_seen, last_seen)
                   VALUES (?, ?, ?, ?)""",
                (user_id, role, now, now),
            )
            self.conn.commit()

    def touch_user(self, user_id, username=None, first_name=None):
        now = datetime.utcnow().isoformat()
        self.cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if self.cursor.fetchone():
            self.cursor.execute(
                """UPDATE users SET last_seen = ?, username = COALESCE(?, username),
                   first_name = COALESCE(?, first_name) WHERE user_id = ?""",
                (now, username, first_name, user_id),
            )
        else:
            self.cursor.execute(
                """INSERT INTO users (user_id, role, username, first_name, first_seen, last_seen)
                   VALUES (?, 'client', ?, ?, ?, ?)""",
                (user_id, username, first_name, now, now),
            )
        self.conn.commit()

    def record_event(self, event_type, user_id):
        self.cursor.execute(
            "INSERT INTO bot_events (event_type, user_id, created_at) VALUES (?, ?, ?)",
            (event_type, user_id, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def _count_events_since(self, hours):
        since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        self.cursor.execute(
            "SELECT COUNT(*) FROM bot_events WHERE created_at >= ?",
            (since,),
        )
        return self.cursor.fetchone()[0]

    def get_metrics_summary(self):
        since_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        since_1h = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        today = datetime.utcnow().strftime("%Y-%m-%d")

        self.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.cursor.fetchone()[0]

        self.cursor.execute(
            "SELECT COUNT(DISTINCT user_id) FROM bot_events WHERE created_at >= ?",
            (since_24h,),
        )
        active_24h = self.cursor.fetchone()[0]

        self.cursor.execute(
            "SELECT COUNT(*) FROM users WHERE first_seen LIKE ?",
            (f"{today}%",),
        )
        new_today = self.cursor.fetchone()[0]

        self.cursor.execute(
            "SELECT COUNT(*) FROM bot_events WHERE created_at >= ?",
            (since_1h,),
        )
        events_1h = self.cursor.fetchone()[0]

        self.cursor.execute(
            "SELECT COUNT(*) FROM orders WHERE status = ?",
            (STATUS_PROCESSING,),
        )
        pending_orders = self.cursor.fetchone()[0]

        self.cursor.execute(
            "SELECT COUNT(DISTINCT user_id) FROM cart_items"
        )
        carts_with_items = self.cursor.fetchone()[0]

        return {
            "total_users": total_users,
            "active_24h": active_24h,
            "new_today": new_today,
            "events_1h": events_1h,
            "pending_orders": pending_orders,
            "carts_with_items": carts_with_items,
            "total_sales": self.get_total_sales(),
        }

    def get_users_paginated(self, page=0, per_page=10):
        offset = page * per_page
        self.cursor.execute(
            """SELECT u.user_id, u.username, u.first_name, u.last_seen, u.first_seen,
                      p.full_name,
                      (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.user_id) as orders_count
               FROM users u
               LEFT JOIN user_profiles p ON p.user_id = u.user_id
               ORDER BY u.last_seen DESC
               LIMIT ? OFFSET ?""",
            (per_page + 1, offset),
        )
        rows = [dict(r) for r in self.cursor.fetchall()]
        has_next = len(rows) > per_page
        return rows[:per_page], has_next

    def get_role(self, user_id):
        self.cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
        res = self.cursor.fetchone()
        return res[0] if res else "client"

    def set_role(self, user_id, role):
        self.touch_user(user_id)
        self.cursor.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))
        self.conn.commit()

    # --- ORDERS ---
    def add_order(self, user_id, items_text, total, delivery_type, phone, address, discount=0):
        self.cursor.execute(
            """INSERT INTO orders (user_id, items_text, total, status, delivery_type, phone, address, discount)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, items_text, total, STATUS_PROCESSING, delivery_type, phone, address, discount),
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def get_orders_by_status(self, status):
        self.cursor.execute(
            "SELECT * FROM orders WHERE status = ? ORDER BY id DESC",
            (status,),
        )
        return [dict(r) for r in self.cursor.fetchall()]

    def get_all_orders(self, limit=20):
        self.cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in self.cursor.fetchall()]

    def get_user_orders(self, user_id, status):
        self.cursor.execute(
            "SELECT id, items_text, total, status FROM orders WHERE user_id = ? AND status = ? ORDER BY id DESC",
            (user_id, status),
        )
        return [dict(r) for r in self.cursor.fetchall()]

    def get_last_completed_order(self, user_id):
        self.cursor.execute(
            """SELECT * FROM orders WHERE user_id = ? AND status = ?
               ORDER BY id DESC LIMIT 1""",
            (user_id, STATUS_COMPLETED),
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def update_order_status(self, order_id, new_status):
        self.cursor.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (new_status, order_id),
        )
        self.conn.commit()

    def get_order_by_id(self, oid):
        self.cursor.execute("SELECT * FROM orders WHERE id = ?", (oid,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def get_total_sales(self):
        self.cursor.execute(
            "SELECT COALESCE(SUM(total), 0) FROM orders WHERE status = ?",
            (STATUS_COMPLETED,),
        )
        return self.cursor.fetchone()[0] or 0

    # --- FAQ ---
    def get_faq_items(self, active_only=True):
        if active_only:
            self.cursor.execute(
                "SELECT * FROM faq_items WHERE is_active = 1 ORDER BY sort_order, id"
            )
        else:
            self.cursor.execute("SELECT * FROM faq_items ORDER BY sort_order, id")
        return [dict(r) for r in self.cursor.fetchall()]

    def get_faq_by_id(self, faq_id):
        self.cursor.execute("SELECT * FROM faq_items WHERE id = ?", (faq_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def add_faq(self, title, content, sort_order=0):
        self.cursor.execute(
            "INSERT INTO faq_items (title, content, sort_order) VALUES (?, ?, ?)",
            (title, content, sort_order),
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def update_faq(self, faq_id, title=None, content=None, is_active=None):
        item = self.get_faq_by_id(faq_id)
        if not item:
            return
        title = title if title is not None else item["title"]
        content = content if content is not None else item["content"]
        active = is_active if is_active is not None else item["is_active"]
        self.cursor.execute(
            "UPDATE faq_items SET title = ?, content = ?, is_active = ? WHERE id = ?",
            (title, content, active, faq_id),
        )
        self.conn.commit()

    def delete_faq(self, faq_id):
        self.cursor.execute("DELETE FROM faq_items WHERE id = ?", (faq_id,))
        self.conn.commit()

    def faq_count(self):
        self.cursor.execute("SELECT COUNT(*) FROM faq_items")
        return self.cursor.fetchone()[0]


db = Database()
