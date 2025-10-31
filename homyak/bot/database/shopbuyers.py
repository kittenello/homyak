import aiosqlite
from pathlib import Path
from ..config import SHOPBUYERS_DB_PATH
from datetime import datetime

DB_PATH = SHOPBUYERS_DB_PATH

async def init_db():
    db_path = str(DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_id INTEGER,
            homyak_filename TEXT,
            created_at TEXT
        )
        """)
        await db.commit()

async def has_bought(user_id: int, item_id: int) -> bool:
    db_path = str(DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT 1 FROM purchases WHERE user_id = ? AND item_id = ? LIMIT 1", (user_id, item_id))
        r = await cursor.fetchone()
        return bool(r)

async def record_purchase(user_id: int, item_id: int, homyak_filename: str):
    db_path = str(DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO purchases (user_id, item_id, homyak_filename, created_at) VALUES (?, ?, ?, ?)",
            (user_id, item_id, homyak_filename, datetime.utcnow().isoformat())
        )
        await db.commit()