import aiosqlite
from ..config import BONUS_DB_PATH

async def init_db():
    db_path = str(BONUS_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bonuses (
                user_id INTEGER PRIMARY KEY,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_premium_at_activation INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.commit()

async def set_bonus(user_id: int, is_premium: bool = False):
    db_path = str(BONUS_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO bonuses (user_id, is_active, is_premium_at_activation)
            VALUES (?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                is_active = 1,
                is_premium_at_activation = excluded.is_premium_at_activation
        """, (user_id, 1 if is_premium else 0))
        await db.commit()

async def get_bonus(user_id: int) -> dict | None:
    db_path = str(BONUS_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT is_active, is_premium_at_activation FROM bonuses WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return {
                "is_active": row[0] == 1,
                "is_premium_at_activation": row[1] == 1
            }
        return None
    
async def remove_bonus(user_id: int):
    db_path = str(BONUS_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM bonuses WHERE user_id = ?", (user_id,))
        await db.commit()