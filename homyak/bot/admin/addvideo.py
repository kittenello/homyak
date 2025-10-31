from aiogram import Router, F, Bot
from aiogram.types import Message, PhotoSize
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from pathlib import Path
from ..database.admins import is_admin

router = Router()

class AddHomyak(StatesGroup):
    waiting_for_image = State()
    waiting_for_name = State()
    waiting_for_rarity = State()

@router.message(F.text == "/addh")
async def cmd_addh(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id) and message.from_user.id != 8142801405:
        return
    await message.answer("🖼️ Отправьте изображение хомяка (любой формат):")
    await state.set_state(AddHomyak.waiting_for_image)

@router.message(AddHomyak.waiting_for_image, F.photo)
async def photo_received(message: Message, state: FSMContext, bot: Bot):
    photo: PhotoSize = message.photo[-1]

    files_dir = Path(__file__).parent.parent / "files"
    files_dir.mkdir(exist_ok=True)

    file_path = files_dir / f"temp_{message.from_user.id}.png"
    file = await bot.get_file(photo.file_id)
    await bot.download_file(file.file_path, destination=file_path)

    await state.update_data(image_path=str(file_path))
    await message.answer("✏️ Введите название хомяка (например, «Приветливый хомяк»):")
    await state.set_state(AddHomyak.waiting_for_name)

@router.message(AddHomyak.waiting_for_image)
async def photo_invalid(message: Message, state: FSMContext):
    attempts = await state.get_data()
    failed_attempts = attempts.get("failed_attempts", 0)

    if not message.photo:
        failed_attempts += 1
        await state.update_data(failed_attempts=failed_attempts)

        if failed_attempts >= 3:
            await state.clear()
            await message.answer("❌ Три неудачные попытки. Пожалуйста, начните процесс заново")
            return

        await message.answer("❌ Пожалуйста, отправьте именно изображение")
        return

    await state.update_data(failed_attempts=0)

@router.message(AddHomyak.waiting_for_name)
async def name_received(message: Message, state: FSMContext):
    homyak_name = message.text.strip()
    if homyak_name.startswith("/") or not homyak_name:
        await state.clear()
        await message.answer("❌ Отменено")
        return

    data = await state.get_data()
    temp_path = data.get("image_path")
    if not temp_path:
        await message.answer("❌ Ошибка: изображение не найдено. Начните сначала.")
        await state.clear()
        return

    await state.update_data(homyak_name=homyak_name)
    await message.answer(
        "🌟 Укажите редкость:\n"
        "1 — Обычная\n"
        "2 — Редкая\n"
        "3 — Мифическая\n"
        "4 — Легендарная\n"
        "5 — Секретный"
    )
    await state.set_state(AddHomyak.waiting_for_rarity)

@router.message(AddHomyak.waiting_for_rarity)
async def rarity_received(message: Message, state: FSMContext):
    try:
        rarity = int(message.text.strip())
        if rarity not in [1, 2, 3, 4, 5]:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 1 до 5:")
        return

    data = await state.get_data()
    homyak_name = data["homyak_name"]
    temp_path = data["image_path"]

    temp_file = Path(temp_path)
    final_name = f"{homyak_name}.png"
    final_path = temp_file.parent / final_name

    if final_path.exists():
        await message.answer(f"⚠️ Хомяк с именем «{homyak_name}» уже существует. Начните сначала.")
        await state.clear()
        return

    temp_file.rename(final_path)

    from ..database.rarity import set_rarity
    await set_rarity(final_name, rarity)

    rarity_names = {1: "Обычная", 2: "Редкая", 3: "Мифическая", 4: "Легендарная", 5: "Секретная"}
    await message.answer(f"✅ Хомяк «{homyak_name}» ({rarity_names[rarity]}) успешно добавлен!")
    await state.clear()