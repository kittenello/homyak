import aiosqlite
from ..config import CASINO_DB_PATH

DB_PATH = CASINO_DB_PATH

async def init_db():
    """Инициализация БД казино"""
    db_path = str(DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS casino_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bet_amount INTEGER NOT NULL,
                dice_value INTEGER NOT NULL,
                win_amount INTEGER NOT NULL DEFAULT 0,
                multiplier INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def record_game(user_id: int, bet: int, dice_value: int, win_amount: int, multiplier: int):
    """Записывает игру в историю"""
    db_path = str(DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO casino_history (user_id, bet_amount, dice_value, win_amount, multiplier)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, bet, dice_value, win_amount, multiplier))
        await db.commit()