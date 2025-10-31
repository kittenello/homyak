from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from pathlib import Path
from ..database.admins import is_admin
import re

router = Router()

class PromoCreation(StatesGroup):
    waiting_for_code = State()
    waiting_for_type = State()
    waiting_for_value = State()
    waiting_for_duration = State()
    waiting_for_max_uses = State()
    waiting_for_homyak_selection = State()

HOMYAK_FILES_DIR = Path(__file__).parent.parent / "files"

@router.message(Command("createpromo"))
async def cmd_createpromo(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("✏️ Введите промокод:")
    await state.set_state(PromoCreation.waiting_for_code)

@router.message(PromoCreation.waiting_for_code)
async def process_code(message: Message, state: FSMContext):
    code = message.text.strip()
    if not code:
        await message.answer("❌ Промокод не может быть пустым.")
        return
    if not re.match(r'^[a-zA-Z0-9а-яА-Я_]+$', code):
        await message.answer("❌ Промокод может содержать только буквы, цифры и подчеркивания.")
        return
    await state.update_data(promo_code=code)
    await message.answer(
        "Укажи что будет в промокоде:\n"
        "1 - Очки\n"
        "2 - Хомяк\n"
        "3 - Снятие КД\n"
        "4 - +Очки за каждого хомяка\n"
        "5 - Монеты"
    )
    await state.set_state(PromoCreation.waiting_for_type)

@router.message(PromoCreation.waiting_for_type)
async def process_type(message: Message, state: FSMContext):
    attempts = await state.get_data()
    failed_attempts = attempts.get("failed_attempts", 0)

    try:
        reward_type = int(message.text.strip())
        if reward_type not in [1, 2, 3, 4, 5]:
            raise ValueError
    except ValueError:
        failed_attempts += 1
        await state.update_data(failed_attempts=failed_attempts)

        if failed_attempts >= 3:
            await state.clear()
            await message.answer("❌ Три неудачные попытки. Пожалуйста, начните процесс заново.")
            return

        await message.answer("❌ Введите число от 1 до 5.")
        return

    await state.update_data(reward_type=reward_type)

    if reward_type == 1:
        await message.answer("💰 Сколько очков выдавать?")
        await state.set_state(PromoCreation.waiting_for_value)
    elif reward_type == 2:
        await message.answer("🐹 Введите часть названия хомяка для поиска:")
        await state.set_state(PromoCreation.waiting_for_value)
    elif reward_type == 3:
        await message.answer("🔢 Сколько активаций максимум?")
        await state.set_state(PromoCreation.waiting_for_max_uses)
    elif reward_type == 4:
        await message.answer("✨ Сколько +очков за хомяка?")
        await state.set_state(PromoCreation.waiting_for_value)
    elif reward_type == 5:
        await message.answer("💰 Сколько монет выдавать?")
        await state.set_state(PromoCreation.waiting_for_value)

@router.message(PromoCreation.waiting_for_value)
async def process_value(message: Message, state: FSMContext):
    data = await state.get_data()
    reward_type = data.get("reward_type")
    attempts = await state.get_data()
    failed_attempts = attempts.get("failed_attempts", 0)

    if reward_type == 1:
        try:
            points = int(message.text.strip())
            if points <= 0:
                raise ValueError
        except ValueError:
            failed_attempts += 1
            await state.update_data(failed_attempts=failed_attempts)

            if failed_attempts >= 3:
                await state.clear()
                await message.answer("❌ Три неудачные попытки. Пожалуйста, начните процесс заново.")
                return

            await message.answer("❌ Введите положительное число.")
            return
        
        await state.update_data(reward_value=str(points))
        await message.answer("🔢 Сколько активаций максимум?")
        await state.set_state(PromoCreation.waiting_for_max_uses)

    elif reward_type == 2:  # <<< Хомяки
        query = message.text.strip().lower()
        matches = []
        for f in HOMYAK_FILES_DIR.glob("*.png"):
            if f.name.lower() != "welcome.png":
                name = f.stem.lower()
                if query in name:
                    matches.append(f.stem)
        
        if not matches:
            await message.answer("❌ Хомяки не найдены. Попробуйте снова.")
            return

        buttons = []
        from ..database.rarity import get_rarity, RARITY_NAMES
        for name in matches[:10]:
            rarity_id = await get_rarity(f"{name}.png")
            buttons.append([InlineKeyboardButton(
                text=f"{name} ({RARITY_NAMES[rarity_id]})",
                callback_data=f"promo_homyak_{name}"
            )])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer("🔍 Найдено несколько хомяков:", reply_markup=keyboard)
        await state.set_state(PromoCreation.waiting_for_homyak_selection)

    if reward_type == 5:
        try:
            amount = int(message.text.strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            failed_attempts += 1
            await state.update_data(failed_attempts=failed_attempts)

            if failed_attempts >= 3:
                await state.clear()
                await message.answer("❌ Три неудачные попытки. Пожалуйста, начните процесс заново.")
                return

            await message.answer("❌ Введите положительное число.")
            return
        
        await state.update_data(reward_value=str(amount))
        await message.answer("🔢 Сколько активаций максимум?")
        await state.set_state(PromoCreation.waiting_for_max_uses)

    elif reward_type == 4:
        attempts = await state.get_data()
        failed_attempts = attempts.get("failed_attempts", 0)

        try:
            bonus_points = int(message.text.strip())
            if bonus_points <= 0:
                raise ValueError
        except ValueError:
            failed_attempts += 1
            await state.update_data(failed_attempts=failed_attempts)

            if failed_attempts >= 3:
                await state.clear()
                await message.answer("❌ Три неудачные попытки. Пожалуйста, начните процесс заново.")
                return

            await message.answer("❌ Введите положительное число.")
            return

        await state.update_data(reward_value=str(bonus_points))
        await message.answer("⏳ На сколько выдавать (в часах)?")
        await state.set_state(PromoCreation.waiting_for_duration)


@router.callback_query(F.data.startswith("promo_homyak_"))
async def select_homyak(callback_query: CallbackQuery, state: FSMContext):
    match = re.match(r"promo_homyak_(.+)", callback_query.data)
    if match:
        homyak_name = match.group(1)
        await state.update_data(reward_value=homyak_name)
        print(f"Выбран хомяк: {homyak_name}")
        await callback_query.message.answer("🔢 Сколько активаций максимум?")
        await state.set_state(PromoCreation.waiting_for_max_uses)
    else:
        await callback_query.answer("❌ Ошибка выбора хомяка.")
    await callback_query.answer()

@router.message(PromoCreation.waiting_for_duration)
async def process_duration(message: Message, state: FSMContext):
    attempts = await state.get_data()
    failed_attempts = attempts.get("failed_attempts", 0)

    try:
        hours = int(message.text.strip())
        if hours <= 0:
            raise ValueError
    except ValueError:
        failed_attempts += 1
        await state.update_data(failed_attempts=failed_attempts)

        if failed_attempts >= 3:
            await state.clear()
            await message.answer("❌ Три неудачные попытки. Пожалуйста, начните процесс заново.")
            return

        await message.answer("❌ Введите положительное число часов.")
        return

    await state.update_data(duration=hours * 60)
    await message.answer("🔢 Сколько активаций максимум?")
    await state.set_state(PromoCreation.waiting_for_max_uses)

@router.message(PromoCreation.waiting_for_max_uses)
async def process_max_uses(message: Message, state: FSMContext):
    attempts = await state.get_data()
    failed_attempts = attempts.get("failed_attempts", 0)

    try:
        max_uses = int(message.text.strip())
        if max_uses <= 0:
            raise ValueError
    except ValueError:
        failed_attempts += 1
        await state.update_data(failed_attempts=failed_attempts)
        if failed_attempts >= 3:
            await state.clear()
            await message.answer("❌ Три неудачные попытки. Пожалуйста, начните процесс заново.")
            return
        await message.answer("❌ Введите положительное число.")
        return

    data = await state.get_data()
    reward_type = data["reward_type"]
    reward_value = data.get("reward_value", "")
    duration = data.get("duration", 0)

    from ..database.promo import create_promo
    success = await create_promo(
        code=data["promo_code"],
        creator_id=message.from_user.id,
        reward_type=reward_type,
        reward_value=reward_value,
        duration=duration,
        max_uses=max_uses
    )

    if success:
        await message.answer(f"✅ Промокод «{data['promo_code']}» создан!")
    else:
        await message.answer(f"❌ Не удалось создать промокод «{data['promo_code']}». Возможно, такой промокод уже существует.")
    await state.clear()