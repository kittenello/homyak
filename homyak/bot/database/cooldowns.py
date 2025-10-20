import aiosqlite
from datetime import datetime
from ..config import COOLDOWN_DB_PATH

async def init_db():
    db_path = str(COOLDOWN_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id INTEGER PRIMARY KEY,
                last_used TEXT NOT NULL,
                is_infinite INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.commit()

async def get_last_used(user_id: int) -> datetime | None:
    db_path = str(COOLDOWN_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT last_used FROM cooldowns WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return datetime.fromisoformat(row[0])
        return None

async def set_last_used(user_id: int):
    now = datetime.now().isoformat()
    db_path = str(COOLDOWN_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO cooldowns (user_id, last_used, is_infinite)
            VALUES (?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET last_used = excluded.last_used, is_infinite = excluded.is_infinite
        """, (user_id, now))
        await db.commit()

async def set_infinite_mode(user_id: int, enable: bool):
    db_path = str(COOLDOWN_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO cooldowns (user_id, last_used, is_infinite)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET is_infinite = excluded.is_infinite
        """, (user_id, datetime.now().isoformat(), 1 if enable else 0))
        await db.commit()

async def is_infinite(user_id: int) -> bool:
    db_path = str(COOLDOWN_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT is_infinite FROM cooldowns WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row is not None and row[0] == 1
    
async def reset_cooldown(user_id: int):
    """Сбросить КД для одного пользователя"""
    db_path = str(COOLDOWN_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM cooldowns WHERE user_id = ?", (user_id,))
        await db.commit()

async def reset_all_cooldowns():
    """Сбросить КД для всех"""
    db_path = str(COOLDOWN_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM cooldowns")
        await db.commit()

async def reset_user_cooldown(user_id: int):
    """Сбрасывает кулдаун пользователя"""
    db_path = str(COOLDOWN_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM cooldowns WHERE user_id = ?", (user_id,))
        await db.commit()