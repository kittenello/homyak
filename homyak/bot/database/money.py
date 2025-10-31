import aiosqlite
from ..config import MONEY_DB_PATH

async def init_db():
    db_path = str(MONEY_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS money(user_id INTEGER PRIMARY KEY, coins INTEGER NOT NULL DEFAULT 0)"
        )
        await db.commit()

async def get_money(user_id: int) -> int:
    db_path = str(MONEY_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("SELECT coins FROM money WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else 0

async def set_money(user_id: int, amount: int):
    db_path = str(MONEY_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO money(user_id, coins) VALUES(?, ?) ON CONFLICT(user_id) DO UPDATE SET coins = excluded.coins",
            (user_id, amount),
        )
        await db.commit()

async def add_money(user_id: int, amount: int):
    current = await get_money(user_id)
    new = current + amount
    if new < 0:
        new = 0
    await set_money(user_id, new)
    return new

async def get_top_money_in_chat(bot, chat_id: int, limit: int = 10) -> list[tuple[int, int, str, str]]:
    """Возвращает топ по монетам. Принимает bot первым аргументом."""
    db_path = str(MONEY_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT user_id, coins FROM money ORDER BY coins DESC LIMIT ?",
            (max(limit * 5, limit),),
        )
        rows = await cursor.fetchall()

    if not rows:
        return []

    result = []
    for user_id, coins in rows:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member and getattr(member, "status", None) not in ("left", "kicked") and not getattr(member.user, "is_bot", False):
                user = member.user
                first_name = user.first_name or ""
                username = user.username
                result.append((user_id, coins, first_name, username))
                if len(result) >= limit:
                    break
        except Exception:
            continue

    return result

async def subtract_money(user_id: int, amount: int):
    db_path = str(DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE users SET money = money - ? WHERE user_id = ?", (amount, user_id))
        await db.commit()