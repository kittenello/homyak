import aiosqlite
from ..config import BUNDLES_DB_PATH  # Укажи путь для БД наборов

# Инициализация БД (создание таблицы, если не существует)
async def init_db():
    db_path = str(BUNDLES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bundles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price_coins INTEGER NOT NULL,
                price_stars INTEGER NOT NULL,
                stock INTEGER NOT NULL,  -- 0 = неограниченно
                filenames_json TEXT NOT NULL  -- Список хомяков в наборе (JSON)
            )
        """)
        await db.commit()

# Добавление нового набора
async def add_bundle(name: str, filenames: list, price_coins: int, price_stars: int, stock: int):
    db_path = str(BUNDLES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO bundles (name, price_coins, price_stars, stock, filenames_json)
            VALUES (?, ?, ?, ?, ?)
        """, (name, price_coins, price_stars, stock, str(filenames)))
        await db.commit()

# Получение набора по ID
async def get_bundle(bundle_id: int):
    db_path = str(BUNDLES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT * FROM bundles WHERE id = ?", (bundle_id,))
        row = await cursor.fetchone()
        if row:
            filenames = eval(row[5])  # Преобразуем строку обратно в список
            return {"id": row[0], "name": row[1], "price_coins": row[2], "price_stars": row[3], "stock": row[4], "filenames": filenames}
        return None

# Получение списка всех наборов
async def list_bundles():
    db_path = str(BUNDLES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT * FROM bundles")
        rows = await cursor.fetchall()
        bundles = []
        for row in rows:
            filenames = eval(row[5])  # Преобразуем строку обратно в список
            bundles.append({"id": row[0], "name": row[1], "price_coins": row[2], "price_stars": row[3], "stock": row[4], "filenames": filenames})
        return bundles

# Удаление набора по ID
async def delete_bundle(bundle_id: int):
    db_path = str(BUNDLES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM bundles WHERE id = ?", (bundle_id,))
        await db.commit()

# Снижение stock (уменьшение на 1, если stock > 0)
async def reduce_bundle_stock(bundle_id: int) -> bool:
    db_path = str(BUNDLES_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT stock FROM bundles WHERE id = ?", (bundle_id,))
        row = await cursor.fetchone()
        if row and row[0] > 0:
            new_stock = row[0] - 1
            await db.execute("UPDATE bundles SET stock = ? WHERE id = ?", (new_stock, bundle_id))
            await db.commit()
            return True
        return False
