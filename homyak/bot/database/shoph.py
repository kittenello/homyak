import aiosqlite
from pathlib import Path
from ..config import SHOPH_DB_PATH

DB_PATH = SHOPH_DB_PATH

async def init_db():
    db_path = str(DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE,
            name TEXT,
            price_coins INTEGER DEFAULT 0,
            price_stars INTEGER DEFAULT 0,
            stock INTEGER DEFAULT 0
        )
        """)
        await db.commit()

async def add_item(filename: str, name: str, price_coins: int, price_stars: int, stock: int = 0):
    db_path = str(DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT OR REPLACE INTO shop_items (filename, name, price_coins, price_stars, stock)
            VALUES (?, ?, ?, ?, ?)
        """, (filename, name, price_coins, price_stars, stock))
        await db.commit()

async def list_items() -> list[dict]:
    db_path = str(DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT id, filename, name, price_coins, price_stars, stock FROM shop_items")
        rows = await cursor.fetchall()
        return [
            {"id": r[0], "filename": r[1], "name": r[2], "price_coins": r[3], "price_stars": r[4], "stock": r[5]}
            for r in rows
        ]

async def get_item(item_id: int) -> dict | None:
    db_path = str(DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT id, filename, name, price_coins, price_stars, stock FROM shop_items WHERE id = ?", (item_id,))
        r = await cursor.fetchone()
        if not r:
            return None
        return {"id": r[0], "filename": r[1], "name": r[2], "price_coins": r[3], "price_stars": r[4], "stock": r[5]}

async def reduce_stock(item_id: int) -> bool:
    db_path = str(DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT stock FROM shop_items WHERE id = ?", (item_id,))
        r = await cursor.fetchone()
        if not r:
            return False
        stock = r[0]
        if stock == 0:
            return True
        if stock > 0:
            new_stock = stock - 1
            await db.execute("UPDATE shop_items SET stock = ? WHERE id = ?", (new_stock, item_id))
            await db.commit()
            return True
        return False

async def delete_item(item_id: int) -> bool:
    """Удаляет товар по id. Возвращает True если удалено."""
    db_path = str(DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT 1 FROM shop_items WHERE id = ?", (item_id,))
        r = await cursor.fetchone()
        if not r:
            return False
        await db.execute("DELETE FROM shop_items WHERE id = ?", (item_id,))
        await db.commit()
        return True