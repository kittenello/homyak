import aiosqlite
from ..config import FAVORITES_DB_PATH

async def init_db():
    db_path = str(FAVORITES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER PRIMARY KEY,
                filename TEXT NOT NULL
            )
        """)
        await db.commit()

async def set_favorite(user_id: int, filename: str):
    db_path = str(FAVORITES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO favorites (user_id, filename)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET filename = excluded.filename
        """, (user_id, filename))
        await db.commit()

async def get_favorite(user_id: int) -> str | None:
    db_path = str(FAVORITES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT filename FROM favorites WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None