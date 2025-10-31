from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import aiosqlite
from ..config import RARITY_DB_PATH
from pathlib import Path
from ..database.admins import is_admin
from ..database.rarity import get_rarity, RARITY_NAMES, RARITY_POINTS
import logging
from pathlib import Path
import re
import os

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = Router()

class HomyakState(StatesGroup):
    waiting_for_name = State()
    renaming_homyak = State()
    viewing_homyak = State()
    changing_rarity = State()

HOMYAK_FILES_DIR = Path(__file__).parent.parent / "files"

@router.message(F.text == "/state")
async def cmd_state(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id) and message.from_user.id != 8142801405:
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти", callback_data="state_find")]
    ])
    await message.answer("🛠️ <b>Управление хомяками</b>\nНажмите Найти, чтобы начать.", 
                        reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "state_find")
async def find_homyak(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer("✏️ Введите название хомяка:")
    await state.set_state(HomyakState.waiting_for_name)
    await callback_query.answer()

@router.message(HomyakState.waiting_for_name)
async def process_homyak_name(message: Message, state: FSMContext, bot: Bot):
    query = message.text.strip()
    if query.startswith("/") or not query:
        await state.clear()
        await message.answer("❌ Отменено")
        return

    all_files = [
        f.name for f in HOMYAK_FILES_DIR.glob("*.png")
        if f.name.lower() != "welcome.mp4"
    ]

    matches = []
    query_lower = query.lower()
    for filename in all_files:
        name_without_ext = filename[:-4]
        if query_lower in name_without_ext.lower():
            matches.append(filename)

    attempts = await state.get_data()
    failed_attempts = attempts.get("failed_attempts", 0)

    if not matches:
        failed_attempts += 1
        await state.update_data(failed_attempts=failed_attempts)

        if failed_attempts >= 3:
            await state.clear()
            await message.answer("❌ Три неудачные попытки. Пожалуйста, начните поиск заново.")
            return

        await message.answer("❌ Хомяки не найдены. Попробуйте другое название.")
        return

    await state.update_data(failed_attempts=0)

    if len(matches) == 1:
        await show_homyak_details(message, matches[0], state)
    else:
        buttons = []
        for filename in matches[:10]:
            name = filename[:-4]
            buttons.append([InlineKeyboardButton(text=name, callback_data=f"state_select_{filename}")])
        
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="state_find")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer("🔍 Найдено несколько хомяков:", reply_markup=keyboard)

async def show_homyak_details(message: Message, filename: str, state: FSMContext):
    
    file_path = HOMYAK_FILES_DIR / filename
    homyak_name = filename[:-4]

    rarity_id = await get_rarity(filename)
    points = RARITY_POINTS[rarity_id]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"state_delete_{filename}")],  # Здесь передаем имя файла
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"state_rename_{filename}")],
        [InlineKeyboardButton(text="🌟 Изменить редкость", callback_data=f"state_change_rarity_{filename}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="state_find")]
    ])

    caption = (
        f"🪄 <b>{homyak_name}</b>\n\n"
        f"💎 Редкость: {RARITY_NAMES[rarity_id]}\n"
        f"✨ Очки: {points}\n"
    )

    await message.answer_photo(
        photo=FSInputFile(file_path),
        caption=caption,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.update_data(current_filename=filename)
    await state.set_state(HomyakState.viewing_homyak)

@router.callback_query(F.data.startswith("state_delete_"))
async def delete_homyak(callback_query: CallbackQuery, state: FSMContext):
    try:
        import re
        match = re.search(r"state_delete_(.*)", callback_query.data)
        if match:
            filename = match.group(1)  # Это будет корректное имя файла
        else:
            await callback_query.answer("Не удалось извлечь имя файла.")
            return

        file_path = Path(HOMYAK_FILES_DIR) / filename  # Здесь будет полный путь к файлу
        print(f"Путь к файлу для удаления: {file_path}")

        if file_path.exists():
            file_path.unlink()  # Удаляем файл
            print(f"Файл {filename} удалён.")
        else:
            await callback_query.message.edit_caption(caption="❌ Файл уже удалён.")
            await state.clear()
            await callback_query.answer()
            return

        # Дополнительные действия (удаление из базы данных и т.д.)
        from ..database.rarity import remove_rarity
        await remove_rarity(filename)

        from ..database.cards import remove_homyak_from_all_users
        await remove_homyak_from_all_users(filename)

        await callback_query.message.edit_caption(caption="✅ Хомяк полностью удалён!")
    except Exception as e:
        await callback_query.message.edit_caption(caption=f"❌ Ошибка удаления: {e}")

    await state.clear()
    await callback_query.answer()

@router.callback_query(F.data == "state_rename_current")
async def rename_homyak_start(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    filename = data.get("current_filename")
    if not filename:
        await callback_query.answer("❌ Ошибка: файл не найден.")
        return
        
    await callback_query.message.answer("✏️ Введите новое название:")
    await state.update_data(rename_filename=filename)
    await state.set_state(HomyakState.renaming_homyak)
    await callback_query.answer()

@router.message(HomyakState.renaming_homyak)
async def rename_homyak_process(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if new_name.startswith("/") or not new_name:
        await state.clear()
        await message.answer("❌ Отменено")
        return

    data = await state.get_data()
    old_filename = data.get("rename_filename")
    if not old_filename:
        await state.clear()
        await message.answer("❌ Ошибка: файл не найден.")
        return

    old_filename_no_ext, old_ext = old_filename.rsplit('.', 1)
    old_filename_normalized = old_filename_no_ext + '.' + old_ext
    new_filename_normalized = new_name.strip() + ".png"

    old_path = HOMYAK_FILES_DIR / old_filename_normalized
    new_path = HOMYAK_FILES_DIR / new_filename_normalized

    logger.info(f"Старый путь файла: {old_path}")
    logger.info(f"Новый путь файла: {new_path}")

    if new_path.exists():
        await state.clear()
        await message.answer("❌ Хомяк с таким названием уже существует, начните заново /state")
        return

    if not old_path.exists():
        await state.clear()
        logger.error(f"Файл не найден: {old_path}")
        await message.answer("❌ Оригинальный файл не найден, начните заново /state")
        return

    try:
        old_path.rename(new_path)

        from ..database.rarity import get_rarity, set_rarity
        rarity = await get_rarity(old_filename)
        await set_rarity(new_filename_normalized, rarity)

        from ..database.rarity import remove_rarity
        await remove_rarity(old_filename)

        from ..database.cards import rename_homyak_in_cards
        await rename_homyak_in_cards(old_filename, new_filename_normalized)

        await message.answer(f"✅ Название изменено на «{new_name}».")
    except Exception as e:
        logger.error(f"Ошибка при переименовании: {e}")
        await message.answer(f"❌ Произошла ошибка при переименовании файла. {e}")
    finally:
        await state.clear()


@router.callback_query(F.data.startswith("state_change_rarity_"))
async def change_rarity_start(callback_query: CallbackQuery, state: FSMContext):
    filename = callback_query.data[len("state_change_rarity_"):]

    await state.update_data(change_rarity_filename=filename)
    
    rarity_buttons = [
        [InlineKeyboardButton(text="1 — Обычная", callback_data="rarity_1")],
        [InlineKeyboardButton(text="2 — Редкая", callback_data="rarity_2")],
        [InlineKeyboardButton(text="3 — Мифическая", callback_data="rarity_3")],
        [InlineKeyboardButton(text="4 — Легендарная", callback_data="rarity_4")],
        [InlineKeyboardButton(text="5 — Секретный", callback_data="rarity_5")],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="state_cancel_rarity")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=rarity_buttons)
    await callback_query.message.answer("Выберите новую редкость:", reply_markup=keyboard)
    await state.set_state(HomyakState.changing_rarity)
    await callback_query.answer()

@router.callback_query(F.data.startswith("rarity_"))
async def set_new_rarity(callback_query: CallbackQuery, state: FSMContext):
    try:
        # Извлекаем редкость из callback_data
        rarity_str = callback_query.data[len("rarity_"):]
        if not rarity_str:
            raise ValueError("empty")
        
        rarity = int(rarity_str)
        if rarity not in [1, 2, 3, 4, 5]:
            raise ValueError("invalid rarity")
        
        # Получаем имя файла хомяка из состояния
        data = await state.get_data()
        filename = data.get("change_rarity_filename")
        if not filename:
            raise ValueError("Filename not found in state")
        
        homyak_name = filename[:-4]  # Убираем расширение .png

        # Обновляем редкость в базе данных
        from ..database.rarity import set_rarity
        await set_rarity(homyak_name, rarity)

        # Получаем новую редкость из базы данных
        rarity_id = await get_rarity(f"{homyak_name}.png")
        print(f"Rarity updated to {rarity_id} for {homyak_name}")

        # Названия редкости
        rarity_names = {1: "Обычная", 2: "Редкая", 3: "Мифическая", 4: "Легендарная", 5: "Секретный"}
        
        # Удаляем старое сообщение и отправляем новое
        await callback_query.message.delete()
        await callback_query.message.answer(f"✅ Редкость изменена на «{rarity_names[rarity]}»!")

        # Показываем хомяка с новой редкостью
        await show_homyak_details(callback_query.message, homyak_name, state)
        
    except Exception as e:
        await callback_query.message.answer(f"Ошибка: {e}")
    finally:
        await state.clear()

@router.callback_query(F.data == "state_cancel_rarity")
async def cancel_rarity_change(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    filename = data.get("change_rarity_filename", "")
    if filename:
        await show_homyak_details(callback_query.message, filename, state)
    else:
        await callback_query.message.edit_text("❌ Отменено.")
    await state.clear()
    await callback_query.answer()