import aiosqlite
from datetime import datetime, timedelta
from ..config import COOLDOWN_DB_PATH
from ..database.premium import is_premium_active
from ..database.bonus import get_bonus
from ..database.elixir import consume_first_of_type

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
    db_path = str(COOLDOWN_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM cooldowns WHERE user_id = ?", (user_id,))
        await db.commit()

async def reset_all_cooldowns():
    db_path = str(COOLDOWN_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM cooldowns")
        await db.commit()

async def reset_user_cooldown(user_id: int):
    db_path = str(COOLDOWN_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM cooldowns WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_cooldown_time(user_id: int) -> int:
    is_premium = await is_premium_active(user_id)
    bonus_info = await get_bonus(user_id)
    has_bonus = bonus_info and bonus_info["is_active"]
    has_time_boost = await consume_first_of_type(user_id, "time")

    if is_premium:
        if has_bonus:
            cooldown = 4 * 3600
        else:
            cooldown = 5 * 3600
    else:
        if has_bonus:
            cooldown = 6 * 3600
        else:
            cooldown = 7 * 3600
            
    if has_time_boost:
        cooldown = max(cooldown - 3600, 0)

    return cooldown

async def get_remaining_time(user_id: int) -> int:
    last_used = await get_last_used(user_id)
    if not last_used:
        return 0

    cooldown = await get_cooldown_time(user_id)
    now = datetime.now()
    next_available = last_used + timedelta(seconds=cooldown)

    if now >= next_available:
        return 0

    return int((next_available - now).total_seconds())

async def reduce_cooldown(user_id: int, seconds: int):
    db_path = str(COOLDOWN_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT last_used FROM cooldowns WHERE user_id = ?",
            (user_id,)
        )
        result = await cursor.fetchone()
        
        if result:
            last_used = datetime.fromisoformat(result[0])
            new_last_used = last_used - timedelta(seconds=seconds)
            
            await db.execute(
                "UPDATE cooldowns SET last_used = ? WHERE user_id = ?",
                (new_last_used.isoformat(), user_id)
            )
            await db.commit()