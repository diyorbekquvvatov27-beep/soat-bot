import sqlite3
from contextlib import contextmanager
from config import DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                brand TEXT NOT NULL,
                price INTEGER NOT NULL,
                photo_file_id TEXT NOT NULL,
                description TEXT DEFAULT '',
                in_stock INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                buyer_name TEXT,
                buyer_phone TEXT,
                buyer_username TEXT,
                buyer_chat_id INTEGER,
                status TEXT DEFAULT 'kutilmoqda',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Eski (status ustunisiz) bazalar uchun migratsiya
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(orders)").fetchall()]
        if "status" not in cols:
            conn.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'kutilmoqda'")


def add_product(name, category, brand, price, photo_file_id, description=""):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO products (name, category, brand, price, photo_file_id, description)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, category, brand, price, photo_file_id, description),
        )
        return cur.lastrowid


def get_brands(category):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT brand FROM products WHERE category = ? AND in_stock = 1 ORDER BY brand",
            (category,),
        ).fetchall()
        return [r["brand"] for r in rows]


def get_all_brands():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT brand FROM products WHERE in_stock = 1 ORDER BY brand"
        ).fetchall()
        return [r["brand"] for r in rows]


def get_products_by_brand(brand):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM products WHERE brand = ? AND in_stock = 1 ORDER BY id",
            (brand,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_products(category, brand=None):
    with get_conn() as conn:
        if brand:
            rows = conn.execute(
                "SELECT * FROM products WHERE category = ? AND brand = ? AND in_stock = 1 ORDER BY id",
                (category, brand),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM products WHERE category = ? AND in_stock = 1 ORDER BY id",
                (category,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_product(product_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return dict(row) if row else None


def delete_product(product_id):
    with get_conn() as conn:
        conn.execute("UPDATE products SET in_stock = 0 WHERE id = ?", (product_id,))


def list_all_products():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM products WHERE in_stock = 1 ORDER BY category, brand, id"
        ).fetchall()
        return [dict(r) for r in rows]


def count_products():
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM products WHERE in_stock = 1").fetchone()
        return row["c"]


def save_order(product_id, buyer_name, buyer_phone, buyer_username, buyer_chat_id):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO orders (product_id, buyer_name, buyer_phone, buyer_username, buyer_chat_id, status)
               VALUES (?, ?, ?, ?, ?, 'kutilmoqda')""",
            (product_id, buyer_name, buyer_phone, buyer_username, buyer_chat_id),
        )
        return cur.lastrowid


_ORDER_SELECT = """
    SELECT o.*, p.name AS product_name, p.price AS product_price
    FROM orders o
    LEFT JOIN products p ON o.product_id = p.id
"""


def get_order(order_id):
    with get_conn() as conn:
        row = conn.execute(_ORDER_SELECT + " WHERE o.id = ?", (order_id,)).fetchone()
        return dict(row) if row else None


def get_orders_by_buyer(buyer_chat_id):
    with get_conn() as conn:
        rows = conn.execute(
            _ORDER_SELECT + " WHERE o.buyer_chat_id = ? ORDER BY o.id DESC",
            (buyer_chat_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_recent_orders(limit=20):
    with get_conn() as conn:
        rows = conn.execute(
            _ORDER_SELECT + " ORDER BY o.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_order_status(order_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
