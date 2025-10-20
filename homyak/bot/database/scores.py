import aiosqlite
from aiogram import Bot
from ..config import SCORES_DB_PATH, CARDS_DB_PATH


async def init_db():
    db_path = str(SCORES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        # Глобальные очки пользователя
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_scores (
                user_id INTEGER PRIMARY KEY,
                total_score INTEGER NOT NULL DEFAULT 0,
                last_homyak TEXT
            )
        """)

        # Гарантируем наличие last_homyak
        cursor = await db.execute("PRAGMA table_info(user_scores)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        if "last_homyak" not in column_names:
            await db.execute("ALTER TABLE user_scores ADD COLUMN last_homyak TEXT")

        # Пер-чатовая таблица (оставляем для совместимости; топ по очкам берёт глобальные user_scores)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_user_scores (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                total_score INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        """)

        await db.commit()


async def add_score(user_id: int, points: int, homyak_name: str = None, chat_id: int | None = None):
    """
    Начисляет очки:
      • Всегда обновляет user_scores (глобальные очки пользователя).
      • Если передан chat_id — дополнительно обновляет chat_user_scores (для совместимости с другим кодом).
    """
    db_path = str(SCORES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        if homyak_name:
            await db.execute("""
                INSERT INTO user_scores (user_id, total_score, last_homyak)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET 
                    total_score = total_score + excluded.total_score,
                    last_homyak = excluded.last_homyak
            """, (user_id, points, homyak_name))
        else:
            await db.execute("""
                INSERT INTO user_scores (user_id, total_score)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET total_score = total_score + excluded.total_score
            """, (user_id, points))

        if chat_id is not None:
            await db.execute("""
                INSERT INTO chat_user_scores (chat_id, user_id, total_score)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    total_score = total_score + excluded.total_score
            """, (chat_id, user_id, points))

        await db.commit()


async def get_score(user_id: int) -> tuple[int, str | None]:
    """
    Возвращает (total_score, last_homyak) из user_scores.
    """
    db_path = str(SCORES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT total_score, last_homyak FROM user_scores WHERE user_id = ?", 
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return row[0], row[1]
        return 0, None


async def get_top_scores_in_chat(bot: Bot, chat_id: int, limit: int = 10):
    """
    Топ по ГЛОБАЛЬНЫМ очкам пользователей (user_scores), отфильтрованный по фактическому членству в chat_id.
    Т.е. берём самые большие total_score из user_scores и показываем только тех, кто сейчас в этом чате.
    """
    db_path = str(SCORES_DB_PATH)

    # Берём "с запасом", чтобы после фильтрации по членству набрать limit.
    oversample = max(limit * 5, 100)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("""
            SELECT user_id, total_score
            FROM user_scores
            ORDER BY total_score DESC
            LIMIT ?
        """, (oversample,))
        score_rows = await cursor.fetchall()

    if not score_rows:
        return []

    top_list = []
    for user_id, score in score_rows:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status not in ["left", "kicked"]:
                u = member.user
                first_name = u.first_name or ""
                username = u.username
                top_list.append((user_id, score, first_name, username))
                if len(top_list) >= limit:
                    break
        except Exception:
            continue

    return top_list


async def get_top_cards_in_chat(bot: Bot, chat_id: int, limit: int = 10):
    """
    Топ по количеству открытых карточек (таблица user_cards, глобальный счётчик),
    отфильтрованный по фактическому членству в chat_id.
    """
    db_path = str(CARDS_DB_PATH)

    # Аналогично — берём с запасом, затем фильтруем по членству.
    oversample = max(limit * 5, 100)

    async with aiosqlite.connect(db_path) as db:
        # user_cards: ожидается, что там записи вида (user_id, ...), по ним считаем COUNT(*)
        cursor = await db.execute("""
            SELECT user_id, COUNT(*) AS card_count
            FROM user_cards
            GROUP BY user_id
            ORDER BY card_count DESC
            LIMIT ?
        """, (oversample,))
        rows = await cursor.fetchall()

    if not rows:
        return []

    top_list = []
    for user_id, count in rows:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status not in ["left", "kicked"]:
                u = member.user
                first_name = u.first_name or ""
                username = u.username
                top_list.append((user_id, count, first_name, username))
                if len(top_list) >= limit:
                    break
        except Exception:
            continue

    return top_list


async def get_all_cards_in_chat(chat_id: int):
    """
    Вспомогательная функция для других частей бота; к кнопкам не требуется.
    """
    from bot.main import bot
    db_path = str(CARDS_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("""
            SELECT user_id, COUNT(*) as card_count
            FROM user_cards
            GROUP BY user_id
        """)
        rows = await cursor.fetchall()
    
    valid_users = []
    for user_id, count in rows:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status not in ["left", "kicked"]:
                valid_users.append((user_id, count))
        except Exception:
            continue
    return valid_users


async def get_all_user_ids_with_scores():
    db_path = str(SCORES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT user_id FROM user_scores")
        return [row[0] for row in await cursor.fetchall()]
