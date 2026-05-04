import sqlite3

class Database:
    def __init__(self, db_name="shop.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Таблица товаров
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS products 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL, category TEXT, specs TEXT)''')
        # Таблица пользователей и ролей
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS users 
            (user_id INTEGER PRIMARY KEY, role TEXT DEFAULT 'client')''')
        # Таблица заказов
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS orders 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, items_text TEXT, total REAL, status TEXT DEFAULT 'В обработке')''')
        # Таблица профилей
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS user_profiles 
            (user_id INTEGER PRIMARY KEY, full_name TEXT, phone TEXT, city TEXT)''')
        self.conn.commit()

    # --- ТОВАРЫ ---
    def add_product(self, name, price, category, specs):
        self.cursor.execute("INSERT INTO products (name, price, category, specs) VALUES (?, ?, ?, ?)", (name, price, category, specs))
        self.conn.commit()

    def get_total_sales(self):
        # Используем технический статус 'completed' для расчетов
        self.cursor.execute(
            "SELECT SUM(total) FROM orders WHERE status = 'completed'"
        )
        res = self.cursor.fetchone()
        return res[0] if res[0] else 0

    def get_categories(self):
        self.cursor.execute("SELECT DISTINCT category FROM products")
        return [res[0] for res in self.cursor.fetchall()]

    def get_products(self, cat):
        self.cursor.execute("SELECT id, name, price, category, specs FROM products WHERE category = ?", (cat,))
        return self.cursor.fetchall()

    def get_product_by_id(self, pid):
        self.cursor.execute("SELECT id, name, price, category, specs FROM products WHERE id = ?", (pid,))
        return self.cursor.fetchone()

    # --- ПРОФИЛЬ ---
    def save_profile(self, user_id, name, phone, city):
        self.cursor.execute("INSERT OR REPLACE INTO user_profiles VALUES (?, ?, ?, ?)", (user_id, name, phone, city))
        self.conn.commit()

    def get_profile(self, user_id):
        self.cursor.execute("SELECT full_name, phone, city FROM user_profiles WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()

    # --- ЗАКАЗЫ И РОЛИ ---
    def get_role(self, user_id):
        self.cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
        res = self.cursor.fetchone()
        return res[0] if res else 'client'

    def set_role(self, user_id, role):
        self.cursor.execute("INSERT OR REPLACE INTO users (user_id, role) VALUES (?, ?)", (user_id, role))
        self.conn.commit()

    def add_order(self, user_id, items_text, total):
        self.cursor.execute("INSERT INTO orders (user_id, items_text, total) VALUES (?, ?, ?)", (user_id, items_text, total))
        self.conn.commit()

    def get_orders_by_status(self, status):
        self.cursor.execute("SELECT * FROM orders WHERE status = ? ORDER BY id DESC", (status,))
        return self.cursor.fetchall()

    def get_user_orders(self, user_id, status):
        self.cursor.execute("SELECT id, items_text, total FROM orders WHERE user_id = ? AND status = ? ORDER BY id DESC", (user_id, status))
        return self.cursor.fetchall()

    def update_order_status(self, order_id, new_status):
        # Принимает 'completed', 'cancelled' или 'В обработке'
        self.cursor.execute(
            "UPDATE orders SET status = ? WHERE id = ?", 
            (new_status, order_id)
        )
        self.conn.commit()

    def update_product(self, pid, name, price, specs):
        self.cursor.execute(
            "UPDATE products SET name = ?, price = ?, specs = ? WHERE id = ?",
            (name, price, specs, pid)
        )
        self.conn.commit()

    def get_order_by_id(self, oid):
        """Получает всю информацию о заказе по его ID"""
        self.cursor.execute("SELECT * FROM orders WHERE id = ?", (oid,))
        return self.cursor.fetchone()

    def get_total_sales(self):
        # Считаем и новые 'completed', и старые '✅ Завершен'
        # Используем кортеж для фильтрации нескольких значений
        query = "SELECT SUM(total) FROM orders WHERE status IN ('completed', '✅ Завершен')"
        self.cursor.execute(query)
        res = self.cursor.fetchone()
        return res[0] if res[0] else 0

db = Database()