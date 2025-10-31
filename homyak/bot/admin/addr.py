from aiogram import Router, F, Bot
from aiogram.types import Message, PhotoSize, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from pathlib import Path
import random
from difflib import SequenceMatcher
from ..database.admins import is_admin

router = Router()

class AddRandomRarity(StatesGroup):
    waiting_for_image = State()
    waiting_for_name = State()
    waiting_for_confirmation = State()
async def check_callback_author(callback_query: CallbackQuery, state: FSMContext) -> bool:
    user_id = callback_query.from_user.id

    if not await is_admin(user_id):
        await callback_query.answer("самый хитрый или че", show_alert=True)
        return False

    data = await state.get_data()
    initiator_id = data.get("initiator_id")
    if initiator_id is None or initiator_id != user_id:
        await callback_query.answer("❌ Это не ваша кнопка!", show_alert=True)
        return False

    return True

@router.message(Command("addr"))
async def cmd_addr(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id) and message.from_user.id != 8142801405:
        return
    await state.update_data(initiator_id=message.from_user.id)  # 🔑 Сохраняем ID
    await message.answer("🖼️ якиями Отправьте изображение хомяка (любой формат):")
    await state.set_state(AddRandomRarity.waiting_for_image)

@router.message(AddRandomRarity.waiting_for_image, F.photo)
async def photo_received(message: Message, state: FSMContext, bot: Bot):
    photo: PhotoSize = message.photo[-1]
    files_dir = Path(__file__).parent.parent / "files"
    files_dir.mkdir(exist_ok=True)

    file_path = files_dir / f"temp_{message.from_user.id}.png"
    file = await bot.get_file(photo.file_id)
    await bot.download_file(file.file_path, destination=file_path)

    await state.update_data(image_path=str(file_path))
    await message.answer("✏️ Введите название хомяка:")
    await state.set_state(AddRandomRarity.waiting_for_name)

@router.message(AddRandomRarity.waiting_for_image)
async def photo_invalid(message: Message, state: FSMContext):
    if not message.photo:
        attempts = await state.get_data()
        failed_attempts = attempts.get("failed_attempts", 0)
        failed_attempts += 1
        await state.update_data(failed_attempts=failed_attempts)

        if failed_attempts >= 3:
            await state.clear()
            await message.answer("❌ Три неудачные попытки. Пожалуйста, начните процесс заново")
            return

        await message.answer("❌ Пожалуйста, отправьте именно изображение")
        return

    await state.update_data(failed_attempts=0)

def clean_name(name: str) -> str:
    words_to_remove = ["хомяк", "хомяка", "хомяку", "хомяком", "хомяке", "хомяки", "хомяков"]
    cleaned = name.lower()
    for word in words_to_remove:
        cleaned = cleaned.replace(word, "")
    cleaned = "".join(c for c in cleaned if c.isalnum() or c.isspace())
    return cleaned.strip()

def similarity(a: str, b: str) -> float:
    clean_a = clean_name(a)
    clean_b = clean_name(b)
    if not clean_a or not clean_b:
        return 0.0
    return SequenceMatcher(None, clean_a, clean_b).ratio()

@router.message(AddRandomRarity.waiting_for_name)
async def name_received(message: Message, state: FSMContext):
    homyak_name = message.text.strip()
    if homyak_name.startswith("/") or not homyak_name:
        await state.clear()
        await message.answer("❌ Отменено")
        return

    files_dir = Path(__file__).parent.parent / "files"
    existing_names = []
    for f in files_dir.glob("*.png"):
        if f.name.lower() != "welcome.png":
            existing_names.append(f.stem)

    similar = []
    for name in existing_names:
        sim = similarity(homyak_name, name)
        if sim >= 0.6:
            similar.append((name, sim))

    if similar:
        best_match, best_score = max(similar, key=lambda x: x[1])
        percent = int(best_score * 100)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Продолжить", callback_data="addr_confirm_yes")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="addr_confirm_no")]
        ])

        await state.update_data(
            homyak_name=homyak_name,
            similar_name=best_match,
            similarity=percent
        )
        await message.answer(
            f"⚠️ Возможно, этот хомяк уже добавлен:\n"
            f"Схожесть: {percent}% — «{best_match}»\n\n"
            f"Продолжить добавление?",
            reply_markup=keyboard
        )
        await state.set_state(AddRandomRarity.waiting_for_confirmation)
    else:
        await finalize_addition(message, state, homyak_name)

async def finalize_addition(message: Message, state: FSMContext, homyak_name: str):
    data = await state.get_data()
    temp_path = data.get("image_path")
    if not temp_path:
        await message.answer("❌ Ошибка: изображение не найдено.")
        await state.clear()
        return

    temp_file = Path(temp_path)
    final_name = f"{homyak_name}.png"
    final_path = temp_file.parent / final_name

    if final_path.exists():
        await message.answer(f"⚠️ Хомяк «{homyak_name}» уже существует.")
        await state.clear()
        return

    rand = random.random()
    if rand < 0.10:
        rarity = 4
    elif rand < 0.25:
        rarity = 3
    elif rand < 0.50:
        rarity = 2
    else:
        rarity = 1

    temp_file.rename(final_path)

    from ..database.rarity import set_rarity
    await set_rarity(final_name, rarity)

    rarity_names = {1: "Обычная", 2: "Редкая", 3: "Мифическая", 4: "Легендарная"}
    await message.answer(f"✅ Хомяк «{homyak_name}» ({rarity_names[rarity]}) успешно добавлен!")
    await state.clear()

@router.callback_query(F.data == "addr_confirm_yes")
async def confirm_yes(callback_query: CallbackQuery, state: FSMContext):
    if not await check_callback_author(callback_query, state):
        return
    data = await state.get_data()
    homyak_name = data["homyak_name"]
    await finalize_addition(callback_query.message, state, homyak_name)
    await callback_query.answer()

@router.callback_query(F.data == "addr_confirm_no")
async def confirm_no(callback_query: CallbackQuery, state: FSMContext):
    if not await check_callback_author(callback_query, state):
        return
    await callback_query.message.edit_text("❌ Добавление отменено.")
    await state.clear()
    await callback_query.answer()