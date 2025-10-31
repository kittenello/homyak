import aiosqlite
from pathlib import Path
from ..config import CARDS_DB_PATH, HOMYAK_FILES_DIR

async def init_db():
    db_path = str(CARDS_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_cards (
                user_id INTEGER,
                filename TEXT,
                first_opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, filename)
            )
        """)
        await db.commit()

async def rename_homyak_in_cards(old_filename: str, new_filename: str):
    db_path = str(CARDS_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            UPDATE user_cards
            SET filename = ?
            WHERE filename = ?
        """, (new_filename, old_filename))
        await db.commit()

async def add_card(user_id: int, filename: str):
    db_path = str(CARDS_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT OR IGNORE INTO user_cards (user_id, filename)
            VALUES (?, ?)
        """, (user_id, filename))
        await db.commit()

async def get_user_cards(user_id: int) -> set[str]:
    db_path = str(CARDS_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT filename FROM user_cards WHERE user_id = ?", (user_id,))
        rows = await cursor.fetchall()
        return {row[0] for row in rows}

async def get_total_cards_count() -> int:
    files = [
        f.name for f in HOMYAK_FILES_DIR.glob("*.png")
        if f.name.lower() != "welcome.png"
    ]
    return len(files)

async def remove_homyak_from_all_users(filename: str):
    db_path = str(CARDS_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM user_cards WHERE filename = ?", (filename,))
        await db.commit()

async def get_top_cards_in_chat(chat_id: int, limit: int = 10):
    db_path = str(CARDS_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("""
            SELECT user_id, COUNT(*) as card_count
            FROM user_cards
            GROUP BY user_id
            ORDER BY card_count DESC
            LIMIT ?
        """, (limit,))
        card_rows = await cursor.fetchall()

    if not card_rows:
        return []

    from bot.main import bot
    top_list = []
    for user_id, card_count in card_rows:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status not in ["left", "kicked"]:
                user = member.user
                first_name = user.first_name or ""
                username = user.username
                top_list.append((user_id, card_count, first_name, username))
                if len(top_list) >= limit:
                    break
        except:
            continue

    return top_list

async def get_all_cards_in_chat(chat_id: int):
    """Возвращает всех участников чата с количеством их карт (даже если 0)."""
    from bot.main import bot
    try:
        members = []
        offset = 0
        while True:
            chunk = await bot.get_chat_administrators(chat_id) if offset == 0 else []
            break

        db_path = str(CARDS_DB_PATH)
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("""
                SELECT user_id, COUNT(*) as card_count
                FROM user_cards
                GROUP BY user_id
            """)
            db_users = {row[0]: row[1] for row in await cursor.fetchall()}


        from .scores import get_all_user_ids_with_scores
        score_users = await get_all_user_ids_with_scores()
        
        all_user_ids = set(db_users.keys()) | set(score_users)

        valid_users = []
        for user_id in all_user_ids:
            try:
                member = await bot.get_chat_member(chat_id, user_id)
                if member.status not in ["left", "kicked", "banned"]:
                    card_count = db_users.get(user_id, 0)
                    valid_users.append((user_id, card_count))
            except:
                continue

        return valid_users

    except Exception as e:
        print(f"Ошибка получения участников: {e}")
        return []
    
async def reset_user_cards(user_id: int):
    """Сбрасывает коллекцию пользователя"""
    db_path = str(CARDS_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM user_cards WHERE user_id = ?", (user_id,))
        await db.commit()