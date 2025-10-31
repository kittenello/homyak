import aiosqlite
from pathlib import Path
from ..config import RARITY_DB_PATH, HOMYAK_FILES_DIR

RARITY_NAMES = {
    1: "Обычная",
    2: "Редкая",
    3: "Мифическая",
    4: "Легендарная",
    5: "Секретная"
}

RARITY_POINTS = {
    1: 1000,
    2: 2000,
    3: 3000,
    4: 5000,
    5: 10000,
}

async def init_db():
    db_path = str(RARITY_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS homyak_rarity (
                filename TEXT PRIMARY KEY,
                rarity INTEGER NOT NULL
            )
        """)
        await db.commit()

async def get_rarity(filename: str) -> int:
    async with aiosqlite.connect(str(RARITY_DB_PATH)) as db:
        cursor = await db.execute("SELECT rarity FROM homyak_rarity WHERE filename = ?", (filename,))
        row = await cursor.fetchone()
        return row[0] if row else 1

async def set_rarity(filename: str, rarity: int):
    async with aiosqlite.connect(str(RARITY_DB_PATH)) as db:
        await db.execute("""
            INSERT INTO homyak_rarity (filename, rarity)
            VALUES (?, ?)
            ON CONFLICT(filename) DO UPDATE SET rarity = excluded.rarity
        """, (filename, rarity))
        await db.commit()

async def get_rarity_stats() -> dict[int, int]:
    db_path = str(RARITY_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("""
            SELECT rarity, COUNT(*) 
            FROM homyak_rarity 
            GROUP BY rarity
        """)
        rows = await cursor.fetchall()
        stats = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for rarity, count in rows:
            if rarity in stats:
                stats[rarity] = count
        return stats
    

async def remove_rarity(filename: str):
    db_path = str(RARITY_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM homyak_rarity WHERE filename = ?", (filename,))
        await db.commit()