import aiosqlite
import time
from ..config import ELIXIR_DB_PATH

async def init_db():
    async with aiosqlite.connect(ELIXIR_DB_PATH) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS elixirs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, type TEXT NOT NULL, created_at INTEGER NOT NULL, uses INTEGER NOT NULL DEFAULT 1, expires_at INTEGER)"
        )
        await db.commit()

async def add_elixir(user_id: int, typ: str, uses: int = 1, expires_at: int | None = None):
    now = int(time.time())
    async with aiosqlite.connect(ELIXIR_DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO elixirs(user_id, type, created_at, uses, expires_at) VALUES(?,?,?,?,?)",
            (user_id, typ, now, uses, expires_at),
        )
        await db.commit()
        return cur.lastrowid

async def get_user_elixirs(user_id: int):
    now = int(time.time())
    async with aiosqlite.connect(ELIXIR_DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, type, created_at, uses, expires_at FROM elixirs WHERE user_id = ?",
            (user_id,),
        )
        rows = await cur.fetchall()
        result = []
        for r in rows:
            if r[4] is not None and r[4] < now:
                await db.execute("DELETE FROM elixirs WHERE id = ?", (r[0],))
                continue
            result.append({"id": r[0], "type": r[1], "created_at": r[2], "uses": r[3], "expires_at": r[4]})
        await db.commit()
        return result

async def has_elixir(user_id: int, typ: str) -> bool:
    now = int(time.time())
    async with aiosqlite.connect(ELIXIR_DB_PATH) as db:
        cur = await db.execute(
            "SELECT id FROM elixirs WHERE user_id = ? AND type = ? AND (expires_at IS NULL OR expires_at > ?) LIMIT 1",
            (user_id, typ, now),
        )
        r = await cur.fetchone()
        return bool(r)

async def consume_elixir_by_id(user_id: int, elixir_id: int) -> bool:
    async with aiosqlite.connect(ELIXIR_DB_PATH) as db:
        cur = await db.execute("SELECT uses FROM elixirs WHERE id = ? AND user_id = ?", (elixir_id, user_id))
        r = await cur.fetchone()
        if not r:
            return False
        uses = r[0]
        if uses <= 1:
            await db.execute("DELETE FROM elixirs WHERE id = ?", (elixir_id,))
        else:
            await db.execute("UPDATE elixirs SET uses = uses - 1 WHERE id = ?", (elixir_id,))
        await db.commit()
        return True

async def consume_first_of_type(user_id: int, typ: str) -> bool:
    async with aiosqlite.connect(ELIXIR_DB_PATH) as db:
        cur = await db.execute(
            "SELECT id FROM elixirs WHERE user_id = ? AND type = ? ORDER BY created_at LIMIT 1",
            (user_id, typ),
        )
        r = await cur.fetchone()
        if not r:
            return False
        elixir_id = r[0]
        await db.execute("DELETE FROM elixirs WHERE id = ? AND (SELECT uses FROM elixirs WHERE id=?)<=1", (elixir_id, elixir_id))
        await db.execute("UPDATE elixirs SET uses = uses - 1 WHERE id = ? AND (SELECT uses FROM elixirs WHERE id=?)>1", (elixir_id, elixir_id))
        await db.commit()
        return True