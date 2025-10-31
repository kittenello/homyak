from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from time import time
import asyncio
from ..admin_logs.logger import casino_log
from ..config import ADMIN_CHAT_ID
from typing import Dict, Tuple, Union, Optional
import random

from bot.database.money import get_money, add_money

last_button_press = {}
COOLDOWN_SECONDS = 10

router = Router()


class CasinoStates(StatesGroup):
    waiting_bet_dice = State()
    waiting_choice_dice = State()
    waiting_bet_basket = State()
    waiting_choice_basket = State()
    waiting_bet_football = State()
    waiting_choice_football = State()
    waiting_bet_attempts = State()
    waiting_bet_rps = State()
    waiting_choice_rps = State()
    waiting_bet_slots = State()
    waiting_bet_darts = State()
    waiting_choice_darts = State()
    waiting_bet_mines = State()
    waiting_bombs_mines = State()
    playing_mines = State()


# (chat_id, message_id) -> owner_id
MESSAGE_OWNERS: Dict[Tuple[int, int], int] = {}

MINES_MULTIPLIERS = {
    2: [1.02, 1.11, 1.22, 1.34, 1.48, 1.64, 1.84, 2.07, 2.35, 2.68, 3.09, 3.61, 4.27, 5.12, 6.26, 7.83, 10.07, 13.42, 18.80, 28.20, 47.00, 94.00, 282.00],
    3: [1.06, 1.22, 1.40, 1.62, 1.89, 2.23, 2.64, 3.17, 3.86, 4.75, 5.93, 7.55, 9.82, 13.10, 18.01, 25.73, 38.60, 61.77, 108.10, 216.20, 540.50, 2162.00],
    5: [1.17, 1.48, 1.89, 2.45, 3.22, 4.29, 5.82, 8.07, 11.43, 16.63, 24.94, 38.80, 63.05, 108.09, 198.18, 396.36, 891.82, 2378.19, 8323.69, 49942.20],
    7: [1.30, 1.84, 2.64, 3.88, 5.82, 8.96, 14.19, 23.23, 39.49, 70.21, 131.66, 263.32, 570.52, 1369.26, 3765.48, 12551.61, 56482.25, 451858.00]
}


def get_multiplier(bet_amount: int) -> float:
    """Возвращает коэффициент в зависимости от ставки."""
    return 1.75 if bet_amount > 50 else 2.0


def remember_owner(msg: Message, owner_id: int):
    """
    Привязываем конкретное отправленное ботом сообщение
    к тому пользователю, которому оно принадлежит.
    """
    MESSAGE_OWNERS[(msg.chat.id, msg.message_id)] = owner_id


def is_on_cooldown(user_id: int) -> bool:
    """Проверяет, находится ли пользователь на кулдауне."""
    now = time()
    last = last_button_press.get(user_id, 0)
    if now - last < COOLDOWN_SECONDS:
        return True
    last_button_press[user_id] = now
    return False


async def get_balance_text(user_id: int) -> str:
    balance = await get_money(user_id)
    return f"💰 Ваш баланс: <b>{balance:,}</b> монет"


async def only_owner(event: Union[CallbackQuery, Message], state: Optional[FSMContext] = None) -> bool:
    """
    Проверка доступа.

    1) Если это CallbackQuery:
       - Смотрим, кому принадлежит КОНКРЕТНО ЭТО сообщение с кнопками.
       - Если не владелец → show_alert + запрет.

    2) Если это обычное Message (юзер шлёт ставку):
       - Если state есть, проверяем owner_id в FSM против отправителя.
         Это защищает игру в групповом чате.
    """
    if isinstance(event, CallbackQuery):
        chat_id = event.message.chat.id
        msg_id = event.message.message_id
        user_id = event.from_user.id

        owner_id = MESSAGE_OWNERS.get((chat_id, msg_id))

        if owner_id is None:
            await event.answer("❌ Эти кнопки больше не активны.", show_alert=True)
            return False

        if owner_id != user_id:
            await event.answer("❌ Это не ваши кнопки!", show_alert=True)
            return False

        return True

    # иначе это Message
    if state is not None:
        data = await state.get_data()
        owner_id = data.get("owner_id")
        if owner_id is not None and owner_id != event.from_user.id:
            await event.answer("❌ Это не ваши кнопки!")
            return False

    return True


async def reset_state_keep_owner(state: FSMContext, owner_id: int):
    await state.set_state(None)
    await state.set_data({"owner_id": owner_id})


# === ОСНОВНЫЕ ХЕНДЛЕРЫ ===

@router.message(Command("casino"))
async def cmd_casino(message: Message, state: FSMContext):
    if message.chat.type == "private":
        return await message.answer("❌ К сожалению, система казино работает только в группах")

    owner_id = message.from_user.id
    await state.update_data(owner_id=owner_id)

    balance_text = await get_balance_text(owner_id)
    user = message.from_user
    raw_name = user.full_name or user.first_name or "Без имени"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Кубик", callback_data="casino_dice"),
         InlineKeyboardButton(text="🏀 Баскетбол", callback_data="casino_basketball")],
        [InlineKeyboardButton(text="⚽ Футбол", callback_data="casino_football"),
         InlineKeyboardButton(text="✊ Камень-Ножницы-Бумага", callback_data="casino_rps")],
        [InlineKeyboardButton(text="🎰 Слоты", callback_data="casino_slots"),
         InlineKeyboardButton(text="🎯 Дартс", callback_data="casino_darts")],
        [InlineKeyboardButton(text="💣 Мины", callback_data="casino_mines")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="casino_close")]
    ])

    sent = await message.answer(
        f"🎰 Приветствуем вас, {raw_name}! в Casino-Хомяк!\n\n"
        f"🤔 Вас будут приветствовать знакомые азартные игры: кубик, баскет, футбол и другие игры!\n"
        f"💸 За выигрыш вы будете получать х2 ставку\n\n"
        f"🪙 Игры проводятся исключительно во внутренней валюте \"Монеты\"\n\n{balance_text}",
        reply_markup=kb,
        parse_mode="HTML"
    )
    remember_owner(sent, owner_id)


@router.callback_query(F.data == "casino_close")
async def casino_close(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return
    await callback.message.delete()
    await callback.answer()


# === КУБИК ===

@router.callback_query(F.data == "casino_dice")
async def casino_dice_menu(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return
    if is_on_cooldown(callback.from_user.id):
        await callback.answer()
        return

    balance_text = await get_balance_text(callback.from_user.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])

    sent = await callback.message.answer(
        f"🎲 <b>Кубик</b>\n\n{balance_text}\n"
        f"💸 Если сумма ставки выше 50 монет - коэффициент 1.75х, если ниже 50 монет то коэффициент 2х\n"
        f"<b>💬 Введите ставку:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    remember_owner(sent, callback.from_user.id)

    await state.set_state(CasinoStates.waiting_bet_dice)
    await callback.answer()


@router.message(CasinoStates.waiting_bet_dice)
async def process_dice_bet(message: Message, state: FSMContext):
    if not await only_owner(message, state):
        return

    user_id = message.from_user.id
    balance = await get_money(user_id)
    data = await state.get_data()
    attempts = data.get("attempts", 0)

    try:
        bet_amount = int(message.text)
        if bet_amount < 1:
            return await message.answer("❌ Минимальная ставка — 1 монета!", parse_mode="HTML")
        if bet_amount > 70:
            return await message.answer("❌ Максимальная ставка — 70 монет!", parse_mode="HTML")
        if bet_amount > balance:
            return await message.answer(f"❌ Недостаточно монет! Ваш баланс: <b>{balance:,}</b>", parse_mode="HTML")

        await state.update_data(bet_amount=bet_amount)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Чёт", callback_data="dice_even"),
             InlineKeyboardButton(text="Нечёт", callback_data="dice_odd")],
            [InlineKeyboardButton(text="Больше", callback_data="dice_high"),
             InlineKeyboardButton(text="Меньше", callback_data="dice_low")],
            [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
        ])

        sent = await message.answer("🎲 <b>Выберите: Чёт или Нечёт?</b>", reply_markup=kb, parse_mode="HTML")
        remember_owner(sent, message.from_user.id)

        await state.set_state(CasinoStates.waiting_choice_dice)

    except ValueError:
        attempts += 1
        if attempts >= 3:
            await message.answer("❌ Действие отменено, введите заново /casino", parse_mode="HTML")
            data = await state.get_data()
            owner_id = data.get("owner_id")
            if owner_id:
                await reset_state_keep_owner(state, owner_id)
            else:
                await state.clear()
        else:
            await state.update_data(attempts=attempts)
            await message.answer("❌ Введите число!", parse_mode="HTML")


@router.callback_query(F.data.in_({"dice_high", "dice_low"}))
async def process_dice_high_low(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return

    user_id = callback.from_user.id
    data = await state.get_data()
    bet_amount = data.get("bet_amount")

    if bet_amount is None:
        await callback.answer("❌ Ставка не найдена. Начните игру заново.", show_alert=True)
        return

    balance_before = await get_money(user_id)
    await add_money(user_id, -bet_amount)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])
    await callback.message.edit_reply_markup(reply_markup=kb)

    dice_msg = await callback.message.answer_dice(emoji="🎲")
    await asyncio.sleep(4)
    dice_value = dice_msg.dice.value

    is_high = callback.data == "dice_high"
    is_win = (dice_value > 3) if is_high else (dice_value <= 3)
    user_choice = "Больше" if is_high else "Меньше"
    outcome_text = "больше" if dice_value > 3 else "меньше"

    if is_win:
        multiplier = get_multiplier(bet_amount)
        win_amount = int(bet_amount * multiplier)
        await add_money(user_id, win_amount)
        result_text = (
            f"🎲 <b>Вы выиграли!</b>\n"
            f"Ставка: <b>{bet_amount:,} [+{win_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount + win_amount:,} монет</b>\n"
            f"🗳️ Вы выбрали: {user_choice} [{outcome_text}]"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Кубик", win_amount - bet_amount,
            "выиграл", user_choice, f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=callback.message.chat.id,
            dice_message_id=dice_msg.message_id
        )
    else:
        result_text = (
            f"🎲 <b>Вы проиграли!</b>\n"
            f"Ставка: <b>{bet_amount:,} [-{bet_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount:,} монет</b>\n"
            f"🗳️ Вы выбрали: {user_choice} [{outcome_text}]"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Кубик", -bet_amount,
            "проиграл", user_choice, f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=callback.message.chat.id,
            dice_message_id=dice_msg.message_id
        )

    await callback.message.delete()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Ещё раз", callback_data="casino_dice"),
         InlineKeyboardButton(text="🏠 В меню", callback_data="casino_back")]
    ])
    sent = await callback.message.answer(result_text, reply_markup=kb, parse_mode="HTML")
    remember_owner(sent, user_id)

    owner_id = data.get("owner_id")
    if owner_id is None:
        await callback.answer("❌ Ошибка попробуйте еще раз. /casino", show_alert=True)
        await state.clear()
        return
    await reset_state_keep_owner(state, owner_id)

    await callback.answer()


@router.callback_query(F.data.in_({"dice_even", "dice_odd"}))
async def process_dice_choice(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return

    user_id = callback.from_user.id
    data = await state.get_data()
    bet_amount = data.get("bet_amount")

    if bet_amount is None:
        await callback.answer("❌ Ставка не найдена. Начните игру заново.", show_alert=True)
        return

    balance_before = await get_money(user_id)
    await add_money(user_id, -bet_amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])
    await callback.message.edit_reply_markup(reply_markup=kb)

    dice_msg = await callback.message.answer_dice(emoji="🎲")
    await asyncio.sleep(4)
    dice_value = dice_msg.dice.value

    is_even = callback.data == "dice_even"
    is_win = (dice_value % 2 == 0) if is_even else (dice_value % 2 != 0)
    user_choice = "Чёт" if is_even else "Нечёт"
    outcome_text = "чёт" if dice_value % 2 == 0 else "нечёт"

    if is_win:
        multiplier = get_multiplier(bet_amount)
        win_amount = int(bet_amount * multiplier)
        await add_money(user_id, win_amount)
        result_text = (
            f"🎲 <b>Вы выиграли!</b>\n"
            f"Ставка: <b>{bet_amount:,} [+{win_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount + win_amount:,} монет</b>\n"
            f"🗳️ Вы выбрали: {user_choice} [Итог: {outcome_text}]"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Кубик", win_amount - bet_amount,
            "выиграл", user_choice, f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=callback.message.chat.id,
            dice_message_id=dice_msg.message_id
        )
    else:
        result_text = (
            f"🎲 <b>Вы проиграли!</b>\n"
            f"Ставка: <b>{bet_amount:,} [-{bet_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount:,} монет</b>\n"
            f"🗳️ Вы выбрали: {user_choice} [Итог: {outcome_text}]"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Кубик", -bet_amount,
            "проиграл", user_choice, f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=callback.message.chat.id,
            dice_message_id=dice_msg.message_id
        )

    await callback.message.delete()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Ещё раз", callback_data="casino_dice"),
         InlineKeyboardButton(text="🏠 В меню", callback_data="casino_back")]
    ])
    sent = await callback.message.answer(result_text, reply_markup=kb, parse_mode="HTML")
    remember_owner(sent, user_id)

    owner_id = data.get("owner_id")
    if owner_id is None:
        await callback.answer("❌ Ошибка попробуйте еще раз. /casino", show_alert=True)
        await state.clear()
        return
    await reset_state_keep_owner(state, owner_id)

    await callback.answer()


# === БАСКЕТБОЛ ===

@router.callback_query(F.data == "casino_basketball")
async def casino_basketball_menu(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return
    if is_on_cooldown(callback.from_user.id):
        await callback.answer()
        return

    balance_text = await get_balance_text(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])

    sent = await callback.message.answer(
        f"🏀 <b>Баскетбол</b>\n\n{balance_text}\n"
        f"💸 Если сумма ставки выше 50 монет - коэффициент 1.75х, если ниже 50 монет то коэффициент 2х\n"
        f"<b>💬 Введите ставку:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    remember_owner(sent, callback.from_user.id)

    await state.set_state(CasinoStates.waiting_bet_basket)
    await callback.answer()


@router.message(CasinoStates.waiting_bet_basket)
async def process_basket_bet(message: Message, state: FSMContext):
    if not await only_owner(message, state):
        return

    user_id = message.from_user.id
    balance = await get_money(user_id)
    data = await state.get_data()
    attempts = data.get("attempts", 0)

    try:
        bet_amount = int(message.text)
        if bet_amount < 1:
            return await message.answer("❌ Минимальная ставка — 1 монета!", parse_mode="HTML")
        if bet_amount > 70:
            return await message.answer("❌ Максимальная ставка — 70 монет!", parse_mode="HTML")
        if bet_amount > balance:
            return await message.answer(f"❌ Недостаточно монет! Ваш баланс: <b>{balance:,}</b>", parse_mode="HTML")

        await state.update_data(bet_amount=bet_amount)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Попадет", callback_data="basket_hit"),
             InlineKeyboardButton(text="Не попадет", callback_data="basket_miss")],
            [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
        ])

        sent = await message.answer("🏀 <b>Выберите: Попадет или Не попадет?</b>", reply_markup=kb, parse_mode="HTML")
        remember_owner(sent, message.from_user.id)

        await state.set_state(CasinoStates.waiting_choice_basket)

    except ValueError:
        attempts += 1
        if attempts >= 3:
            await message.answer("❌ Действие отменено, введите заново /casino", parse_mode="HTML")
            data = await state.get_data()
            owner_id = data.get("owner_id")
            if owner_id:
                await reset_state_keep_owner(state, owner_id)
            else:
                await state.clear()
        else:
            await state.update_data(attempts=attempts)
            await message.answer("❌ Введите число!", parse_mode="HTML")


@router.callback_query(F.data.in_({"basket_hit", "basket_miss"}))
async def process_basket_choice(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return

    user_id = callback.from_user.id
    data = await state.get_data()
    bet_amount = data.get("bet_amount")

    if bet_amount is None:
        await callback.answer("❌ Ставка не найдена. Начните игру заново.", show_alert=True)
        return

    balance_before = await get_money(user_id)
    await add_money(user_id, -bet_amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])
    await callback.message.edit_reply_markup(reply_markup=kb)

    dice_msg = await callback.message.answer_dice(emoji="🏀")
    await asyncio.sleep(4)
    dice_value = dice_msg.dice.value

    is_hit = callback.data == "basket_hit"
    hit = dice_value in (4, 5)
    user_choice = "Попадет" if is_hit else "Не попадет"
    outcome_text = "попало" if hit else "не попало"

    if hit == is_hit:
        multiplier = get_multiplier(bet_amount)
        win_amount = int(bet_amount * multiplier)
        await add_money(user_id, win_amount)
        result_text = (
            f"🏀 <b>Вы выиграли!</b>\n"
            f"Ставка: <b>{bet_amount:,} [+{win_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount + win_amount:,} монет</b>\n"
            f"🗳️ Вы выбрали: {user_choice} [{outcome_text}]"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Баскетбол", win_amount - bet_amount,
            "выиграл", user_choice, f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=callback.message.chat.id,
            dice_message_id=dice_msg.message_id
        )
    else:
        result_text = (
            f"🏀 <b>Вы проиграли!</b>\n"
            f"Ставка: <b>{bet_amount:,} [-{bet_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount:,} монет</b>\n"
            f"🗳️ Вы выбрали: {user_choice} [{outcome_text}]"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Баскетбол", -bet_amount,
            "проиграл", user_choice, f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=callback.message.chat.id,
            dice_message_id=dice_msg.message_id
        )

    await callback.message.delete()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏀 Ещё раз", callback_data="casino_basketball"),
         InlineKeyboardButton(text="🏠 В меню", callback_data="casino_back")]
    ])
    sent = await callback.message.answer(result_text, reply_markup=kb, parse_mode="HTML")
    remember_owner(sent, user_id)

    owner_id = data.get("owner_id")
    if owner_id is None:
        await callback.answer("❌ Ошибка попробуйте еще раз. /casino", show_alert=True)
        await state.clear()
        return
    await reset_state_keep_owner(state, owner_id)

    await callback.answer()


# === ФУТБОЛ ===

@router.callback_query(F.data == "casino_football")
async def casino_football_menu(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return
    if is_on_cooldown(callback.from_user.id):
        await callback.answer()
        return

    balance_text = await get_balance_text(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])

    sent = await callback.message.answer(
        f"⚽ <b>Футбол</b>\n\n{balance_text}\n"
        f"💸 Если сумма ставки выше 50 монет - коэффициент 1.75х, если ниже 50 монет то коэффициент 2х\n"
        f"<b>💬 Введите ставку:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    remember_owner(sent, callback.from_user.id)

    await state.set_state(CasinoStates.waiting_bet_football)
    await callback.answer()


@router.message(CasinoStates.waiting_bet_football)
async def process_football_bet(message: Message, state: FSMContext):
    if not await only_owner(message, state):
        return

    user_id = message.from_user.id
    balance = await get_money(user_id)
    data = await state.get_data()
    attempts = data.get("attempts", 0)

    try:
        bet_amount = int(message.text)
        if bet_amount < 1:
            return await message.answer("❌ Минимальная ставка — 1 монета!", parse_mode="HTML")
        if bet_amount > 70:
            return await message.answer("❌ Максимальная ставка — 70 монет!", parse_mode="HTML")
        if bet_amount > balance:
            return await message.answer(f"❌ Недостаточно монет! Ваш баланс: <b>{balance:,}</b>", parse_mode="HTML")

        await state.update_data(bet_amount=bet_amount)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Забьёт", callback_data="foot_goal"),
             InlineKeyboardButton(text="Промахнётся", callback_data="foot_miss")],
            [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
        ])

        sent = await message.answer("⚽ <b>Выберите: Забьёт или Промахнётся?</b>", reply_markup=kb, parse_mode="HTML")
        remember_owner(sent, message.from_user.id)

        await state.set_state(CasinoStates.waiting_choice_football)

    except ValueError:
        attempts += 1
        if attempts >= 3:
            await message.answer("❌ Действие отменено, введите заново /casino", parse_mode="HTML")
            data = await state.get_data()
            owner_id = data.get("owner_id")
            if owner_id:
                await reset_state_keep_owner(state, owner_id)
            else:
                await state.clear()
        else:
            await state.update_data(attempts=attempts)
            await message.answer("❌ Введите число!", parse_mode="HTML")


@router.callback_query(F.data.in_({"foot_goal", "foot_miss"}))
async def process_football_choice(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return

    user_id = callback.from_user.id
    data = await state.get_data()
    bet_amount = data.get("bet_amount")

    if bet_amount is None:
        await callback.answer("❌ Ставка не найдена. Начните игру заново.", show_alert=True)
        return

    balance_before = await get_money(user_id)
    await add_money(user_id, -bet_amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])
    await callback.message.edit_reply_markup(reply_markup=kb)

    dice_msg = await callback.message.answer_dice(emoji="⚽")
    await asyncio.sleep(4)
    dice_value = dice_msg.dice.value

    is_goal = callback.data == "foot_goal"
    goal = dice_value >= 3
    user_choice = "Забьёт" if is_goal else "Промахнётся"
    outcome_text = "Забил" if goal else "Промахнулся"

    if goal == is_goal:
        multiplier = get_multiplier(bet_amount)
        win_amount = int(bet_amount * multiplier)
        await add_money(user_id, win_amount)
        result_text = (
            f"⚽ <b>Вы выиграли!</b>\n"
            f"Ставка: <b>{bet_amount:,} [+{win_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount + win_amount:,} монет</b>\n"
            f"🗳️ Вы выбрали: {user_choice} [{outcome_text}]"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Футбол", win_amount - bet_amount,
            "выиграл", user_choice, f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=callback.message.chat.id,
            dice_message_id=dice_msg.message_id
        )
    else:
        result_text = (
            f"⚽ <b>Вы проиграли!</b>\n"
            f"Ставка: <b>{bet_amount:,} [-{bet_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount:,} монет</b>\n"
            f"🗳️ Вы выбрали: {user_choice} [{outcome_text}]"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Футбол", -bet_amount,
            "проиграл", user_choice, f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=callback.message.chat.id,
            dice_message_id=dice_msg.message_id
        )

    await callback.message.delete()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Ещё раз", callback_data="casino_football"),
         InlineKeyboardButton(text="🏠 В меню", callback_data="casino_back")]
    ])
    sent = await callback.message.answer(result_text, reply_markup=kb, parse_mode="HTML")
    remember_owner(sent, user_id)

    owner_id = data.get("owner_id")
    if owner_id is None:
        await callback.answer("❌ Ошибка попробуйте еще раз. /casino", show_alert=True)
        await state.clear()
        return
    await reset_state_keep_owner(state, owner_id)

    await callback.answer()


# === К-Н-Б ===

@router.callback_query(F.data == "casino_rps")
async def casino_rps_menu(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return
    if is_on_cooldown(callback.from_user.id):
        await callback.answer()
        return

    balance_text = await get_balance_text(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])

    sent = await callback.message.answer(
        f"✊ <b>Камень, Ножницы, Бумага</b>\n\n{balance_text}\n"
        f"💸 Если сумма ставки выше 50 монет - коэффициент 1.75х, если ниже 50 монет то коэффициент 2х\n"
        f"<b>💬 Введите ставку:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    remember_owner(sent, callback.from_user.id)

    await state.set_state(CasinoStates.waiting_bet_rps)
    await callback.answer()


@router.message(CasinoStates.waiting_bet_rps)
async def process_rps_bet(message: Message, state: FSMContext):
    if not await only_owner(message, state):
        return

    user_id = message.from_user.id
    balance = await get_money(user_id)
    data = await state.get_data()
    attempts = data.get("attempts", 0)

    try:
        bet_amount = int(message.text)
        if bet_amount < 1:
            return await message.answer("❌ Минимальная ставка — 1 монета!", parse_mode="HTML")
        if bet_amount > 70:
            return await message.answer("❌ Максимальная ставка — 70 монет!", parse_mode="HTML")
        if bet_amount > balance:
            return await message.answer(f"❌ Недостаточно монет! Ваш баланс: <b>{balance:,}</b>", parse_mode="HTML")

        await state.update_data(bet_amount=bet_amount)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Камень", callback_data="rps_rock"),
             InlineKeyboardButton(text="Ножницы", callback_data="rps_scissors"),
             InlineKeyboardButton(text="Бумага", callback_data="rps_paper")],
            [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
        ])

        sent = await message.answer("✊ <b>Выберите: Камень, Ножницы или Бумага?</b>", reply_markup=kb, parse_mode="HTML")
        remember_owner(sent, message.from_user.id)

        await state.set_state(CasinoStates.waiting_choice_rps)

    except ValueError:
        attempts += 1
        if attempts >= 3:
            await message.answer("❌ Действие отменено, введите заново /casino", parse_mode="HTML")
            data = await state.get_data()
            owner_id = data.get("owner_id")
            if owner_id:
                await reset_state_keep_owner(state, owner_id)
            else:
                await state.clear()
        else:
            await state.update_data(attempts=attempts)
            await message.answer("❌ Введите число!", parse_mode="HTML")


@router.callback_query(F.data.in_({"rps_rock", "rps_scissors", "rps_paper"}))
async def process_rps_choice(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return

    user_id = callback.from_user.id
    data = await state.get_data()
    bet_amount = data.get("bet_amount")

    if bet_amount is None:
        await callback.answer("❌ Ставка не найдена. Начните игру заново.", show_alert=True)
        return

    balance_before = await get_money(user_id)
    await add_money(user_id, -bet_amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])
    await callback.message.edit_reply_markup(reply_markup=kb)

    choice_map = {
        "rps_rock": "камень",
        "rps_scissors": "ножницы",
        "rps_paper": "бумага"
    }
    player_choice = choice_map[callback.data]

    bot_choice_num = random.randint(1, 3)
    bot_choices = {1: "камень", 2: "ножницы", 3: "бумага"}
    bot_choice = bot_choices[bot_choice_num]

    emoji_map = {"камень": "👊", "ножницы": "✌️", "бумага": "✋"}
    player_emoji = emoji_map[player_choice]
    bot_emoji = emoji_map[bot_choice]

    wins = {"камень": "ножницы", "ножницы": "бумага", "бумага": "камень"}

    if wins[player_choice] == bot_choice:
        multiplier = get_multiplier(bet_amount)
        win_amount = int(bet_amount * multiplier)
        await add_money(user_id, win_amount)
        final_balance = balance_before - bet_amount + win_amount
        result_text = (
            f"✊ <b>Вы выиграли!</b>\n"
            f"{player_emoji} vs {bot_emoji}[Бот]\n"
            f"Ставка: <b>{bet_amount:,} [+{win_amount:,}] монет</b>\n"
            f"Баланс: <b>{final_balance:,} монет</b>\n"
            f"🗳️ Вы выбрали: {player_choice}"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Камень Ножницы Бумага", win_amount - bet_amount,
            "выиграл", player_choice, f"Бот: {bot_choice}",
            balance_before=balance_before,
            from_chat_id=None,
            dice_message_id=None
        )
    elif player_choice == bot_choice:
        await add_money(user_id, bet_amount)  # возврат
        final_balance = balance_before
        result_text = (
            f"✊ <b>Ничья!</b>\n"
            f"{player_emoji} vs {bot_emoji}[Бот]\n"
            f"Ставка: <b>{bet_amount:,} [возвращена] монет</b>\n"
            f"Баланс: <b>{final_balance:,} монет</b>\n"
            f"🗳️ Вы выбрали: {player_choice}"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Камень Ножницы Бумага", 0,
            "ничья", player_choice, f"Бот: {bot_choice}",
            balance_before=balance_before,
            from_chat_id=None,
            dice_message_id=None
        )
    else:
        final_balance = balance_before - bet_amount
        result_text = (
            f"✊ <b>Вы проиграли!</b>\n"
            f"{player_emoji} vs {bot_emoji}[Бот]\n"
            f"Ставка: <b>{bet_amount:,} [-{bet_amount:,}] монет</b>\n"
            f"Баланс: <b>{final_balance:,} монет</b>\n"
            f"🗳️ Вы выбрали: {player_choice}"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Камень Ножницы Бумага", -bet_amount,
            "проиграл", player_choice, f"Бот: {bot_choice}",
            balance_before=balance_before,
            from_chat_id=None,
            dice_message_id=None
        )

    await callback.message.delete()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✊ Ещё раз", callback_data="casino_rps"),
         InlineKeyboardButton(text="🏠 В меню", callback_data="casino_back")]
    ])
    sent = await callback.message.answer(result_text, reply_markup=kb, parse_mode="HTML")
    remember_owner(sent, user_id)

    owner_id = data.get("owner_id")
    if owner_id is None:
        await callback.answer("❌ Ошибка попробуйте еще раз. /casino", show_alert=True)
        await state.clear()
        return
    await reset_state_keep_owner(state, owner_id)

    await callback.answer()


# === СЛОТЫ ===

@router.callback_query(F.data == "casino_slots")
async def casino_slots_menu(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return
    if is_on_cooldown(callback.from_user.id):
        await callback.answer()
        return

    balance_text = await get_balance_text(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])

    sent = await callback.message.answer(
        f"🎰 <b>Слоты</b>\n\n{balance_text}\n"
        f"💸 Коэффициент: x3\n"
        f"<b>💬 Введите ставку:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    remember_owner(sent, callback.from_user.id)

    await state.set_state(CasinoStates.waiting_bet_slots)
    await callback.answer()


@router.message(CasinoStates.waiting_bet_slots)
async def process_slots_bet(message: Message, state: FSMContext):
    if not await only_owner(message, state):
        return

    user_id = message.from_user.id
    balance = await get_money(user_id)
    data = await state.get_data()
    attempts = data.get("attempts", 0)

    try:
        bet_amount = int(message.text)
        if bet_amount < 1:
            return await message.answer("❌ Минимальная ставка — 1 монета!", parse_mode="HTML")
        if bet_amount > 70:
            return await message.answer("❌ Максимальная ставка — 70 монет!", parse_mode="HTML")
        if bet_amount > balance:
            return await message.answer(f"❌ Недостаточно монет! Ваш баланс: <b>{balance:,}</b>", parse_mode="HTML")

        await state.update_data(bet_amount=bet_amount)
        await process_slots_spin_direct(message, state, bet_amount, user_id)

    except ValueError:
        attempts += 1
        if attempts >= 3:
            await message.answer("❌ Действие отменено, введите заново /casino", parse_mode="HTML")
            data = await state.get_data()
            owner_id = data.get("owner_id")
            if owner_id:
                await reset_state_keep_owner(state, owner_id)
            else:
                await state.clear()
        else:
            await state.update_data(attempts=attempts)
            await message.answer("❌ Введите число!", parse_mode="HTML")


async def process_slots_spin_direct(message: Message, state: FSMContext, bet_amount: int, owner_id: int):
    balance_before = await get_money(owner_id)
    await add_money(owner_id, -bet_amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])
    await message.edit_reply_markup(reply_markup=kb)

    dice_msg = await message.answer_dice(emoji="🎰")
    await asyncio.sleep(4)
    dice_value = dice_msg.dice.value

    triple_same = {1, 43, 22, 52, 27, 38}
    jackpot_777 = 64

    if dice_value == jackpot_777:
        win_amount = bet_amount * 3
        await add_money(owner_id, win_amount)
        result_text = (
            f"🎰 <b>ДЖЕКПОТ! 777!</b>\n"
            f"Ставка: <b>{bet_amount:,} [+{win_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount + win_amount:,} монет</b>"
        )
        await casino_log(
            message.bot, message.from_user, bet_amount, "Слоты", win_amount - bet_amount,
            "выиграл", "777", f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=message.chat.id,
            dice_message_id=dice_msg.message_id
        )
    elif dice_value in triple_same:
        multiplier = get_multiplier(bet_amount)
        win_amount = int(bet_amount * multiplier)
        await add_money(owner_id, win_amount)
        combo_name = "BAR" if dice_value == 1 else "три одинаковых"
        result_text = (
            f"🎰 <b>{combo_name.capitalize()}!</b>\n"
            f"Ставка: <b>{bet_amount:,} [+{win_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount + win_amount:,} монет</b>"
        )
        await casino_log(
            message.bot, message.from_user, bet_amount, "Слоты", win_amount - bet_amount,
            "выиграл", combo_name, f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=message.chat.id,
            dice_message_id=dice_msg.message_id
        )
    else:
        result_text = (
            f"🎰 <b>Неудачная комбинация.</b>\n"
            f"Ставка: <b>{bet_amount:,} [-{bet_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount:,} монет</b>"
        )
        await casino_log(
            message.bot, message.from_user, bet_amount, "Слоты", -bet_amount,
            "проиграл", "обычная", f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=message.chat.id,
            dice_message_id=dice_msg.message_id
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Ещё раз", callback_data="casino_slots"),
         InlineKeyboardButton(text="🏠 В меню", callback_data="casino_back")]
    ])
    sent = await message.answer(result_text, reply_markup=kb, parse_mode="HTML")
    remember_owner(sent, owner_id)

    data = await state.get_data()
    owner_state_id = data.get("owner_id", message.from_user.id)
    await reset_state_keep_owner(state, owner_state_id)


# === ДАРТС ===

@router.callback_query(F.data == "casino_darts")
async def casino_darts_menu(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return
    if is_on_cooldown(callback.from_user.id):
        await callback.answer()
        return

    balance_text = await get_balance_text(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])

    sent = await callback.message.answer(
        f"🎯 <b>Дартс</b>\n\n{balance_text}\n"
        f"💸 Если сумма ставки выше 50 монет - коэффициент 1.75х, если ниже 50 монет то коэффициент 2х\n"
        f"<b>💬 Введите ставку:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    remember_owner(sent, callback.from_user.id)

    await state.set_state(CasinoStates.waiting_bet_darts)
    await callback.answer()


@router.message(CasinoStates.waiting_bet_darts)
async def process_darts_bet(message: Message, state: FSMContext):
    if not await only_owner(message, state):
        return

    user_id = message.from_user.id
    balance = await get_money(user_id)
    data = await state.get_data()
    attempts = data.get("attempts", 0)

    try:
        bet_amount = int(message.text)
        if bet_amount < 1:
            return await message.answer("❌ Минимальная ставка — 1 монета!", parse_mode="HTML")
        if bet_amount > 70:
            return await message.answer("❌ Максимальная ставка — 70 монет!", parse_mode="HTML")
        if bet_amount > balance:
            return await message.answer(f"❌ Недостаточно монет! Ваш баланс: <b>{balance:,}</b>", parse_mode="HTML")

        await state.update_data(bet_amount=bet_amount)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Промах", callback_data="darts_miss"),
             InlineKeyboardButton(text="Белое", callback_data="darts_white"),
             InlineKeyboardButton(text="Красное", callback_data="darts_red")],
            [InlineKeyboardButton(text="Яблочко", callback_data="darts_bullseye")],
            [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
        ])

        sent = await message.answer("🎯 <b>Выберите зону попадания:</b>", reply_markup=kb, parse_mode="HTML")
        remember_owner(sent, message.from_user.id)

        await state.set_state(CasinoStates.waiting_choice_darts)

    except ValueError:
        attempts += 1
        if attempts >= 3:
            await message.answer("❌ Действие отменено, введите заново /casino", parse_mode="HTML")
            data = await state.get_data()
            owner_id = data.get("owner_id")
            if owner_id:
                await reset_state_keep_owner(state, owner_id)
            else:
                await state.clear()
        else:
            await state.update_data(attempts=attempts)
            await message.answer("❌ Введите число!", parse_mode="HTML")


@router.callback_query(F.data.in_({"darts_miss", "darts_white", "darts_red", "darts_bullseye"}))
async def process_darts_choice(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return

    user_id = callback.from_user.id
    data = await state.get_data()
    bet_amount = data.get("bet_amount")

    if bet_amount is None:
        await callback.answer("❌ Ставка не найдена. Начните игру заново.", show_alert=True)
        return

    balance_before = await get_money(user_id)
    await add_money(user_id, -bet_amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])
    await callback.message.edit_reply_markup(reply_markup=kb)

    dice_msg = await callback.message.answer_dice(emoji="🎯")
    await asyncio.sleep(4)
    dice_value = dice_msg.dice.value

    choice_map = {
        "darts_miss": ("Промах", [1]),
        "darts_white": ("Белое", [3, 5]),
        "darts_red": ("Красное", [2, 4]),
        "darts_bullseye": ("Яблочко", [6])
    }
    user_choice, winning_values = choice_map[callback.data]

    if dice_value == 1:
        outcome_text = "промах"
    elif dice_value in (3, 5):
        outcome_text = "белое"
    elif dice_value in (2, 4):
        outcome_text = "красное"
    else:
        outcome_text = "яблочко"

    if dice_value in winning_values:
        multiplier = get_multiplier(bet_amount)
        win_amount = int(bet_amount * multiplier)
        await add_money(user_id, win_amount)
        result_text = (
            f"🎯 <b>Вы выиграли!</b>\n"
            f"Ставка: <b>{bet_amount:,} [+{win_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount + win_amount:,} монет</b>\n"
            f"🗳️ Вы выбрали: {user_choice} [{outcome_text}]"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Дартс", win_amount - bet_amount,
            "выиграл", user_choice, f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=callback.message.chat.id,
            dice_message_id=dice_msg.message_id
        )
    else:
        result_text = (
            f"🎯 <b>Вы проиграли!</b>\n"
            f"Ставка: <b>{bet_amount:,} [-{bet_amount:,}] монет</b>\n"
            f"Баланс: <b>{balance_before - bet_amount:,} монет</b>\n"
            f"🗳️ Вы выбрали: {user_choice} [{outcome_text}]"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Дартс", -bet_amount,
            "проиграл", user_choice, f"Выпало: {dice_value}",
            balance_before=balance_before,
            from_chat_id=callback.message.chat.id,
            dice_message_id=dice_msg.message_id
        )

    await callback.message.delete()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Ещё раз", callback_data="casino_darts"),
         InlineKeyboardButton(text="🏠 В меню", callback_data="casino_back")]
    ])
    sent = await callback.message.answer(result_text, reply_markup=kb, parse_mode="HTML")
    remember_owner(sent, user_id)

    owner_id = data.get("owner_id")
    if owner_id is None:
        await callback.answer("❌ Ошибка попробуйте еще раз. /casino", show_alert=True)
        await state.clear()
        return
    await reset_state_keep_owner(state, owner_id)

    await callback.answer()


# === МИНЫ ===

@router.callback_query(F.data == "casino_mines")
async def casino_mines_menu(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return
    if is_on_cooldown(callback.from_user.id):
        await callback.answer()
        return

    balance_text = await get_balance_text(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])

    sent = await callback.message.answer(
        f"💣 <b>Мины</b>\n\n{balance_text}\n"
        f"💸 Введите ставку (3–20 монет)\n"
        f"<b>💬 Введите ставку:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    remember_owner(sent, callback.from_user.id)

    await state.set_state(CasinoStates.waiting_bet_mines)
    await callback.answer()


async def show_final_mines_field(
    bot: Bot,
    chat_id: int,
    mine_positions: list[tuple[int, int]],
    revealed: list[tuple[int, int]],
    message_thread_id: Optional[int] = None
):
    """
    Отправляет финальное поле мин после окончания раунда (в лог канал админа).
    """
    lost_cell = revealed[-1] if revealed and revealed[-1] in mine_positions else None
    buttons = []
    for r in range(5):
        row = []
        for c in range(5):
            pos = (r, c)
            if pos == lost_cell:
                text = "💣❌"
            elif pos in revealed:
                text = "💎✅"
            elif pos in mine_positions:
                text = "💣"
            else:
                text = "🟦"
            row.append(InlineKeyboardButton(text=text, callback_data="noop"))
        buttons.append(row)

    await bot.send_message(
        chat_id,
        "<b>💣 Финальное поле мин:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
        message_thread_id=message_thread_id
    )


@router.message(CasinoStates.waiting_bet_mines)
async def process_mines_bet(message: Message, state: FSMContext):
    if not await only_owner(message, state):
        return

    user_id = message.from_user.id
    balance = await get_money(user_id)
    try:
        bet_amount = int(message.text)
        if bet_amount < 3:
            return await message.answer("❌ Минимальная ставка — 3 монета!", parse_mode="HTML")
        if bet_amount > 20:
            return await message.answer("❌ Максимальная ставка — 20 монет!", parse_mode="HTML")
        if bet_amount > balance:
            return await message.answer(f"❌ Недостаточно монет! Ваш баланс: <b>{balance:,}</b>", parse_mode="HTML")

        await state.update_data(bet_amount=bet_amount)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="2", callback_data="mines_bombs:2"),
             InlineKeyboardButton(text="3", callback_data="mines_bombs:3")],
            [InlineKeyboardButton(text="5", callback_data="mines_bombs:5"),
             InlineKeyboardButton(text="7", callback_data="mines_bombs:7")],
            [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
        ])

        sent = await message.answer("💣 <b>Выберите количество бомб:</b>", reply_markup=kb, parse_mode="HTML")
        remember_owner(sent, message.from_user.id)

        await state.set_state(CasinoStates.waiting_bombs_mines)

    except ValueError:
        await message.answer("❌ Введите число!", parse_mode="HTML")


@router.callback_query(F.data.startswith("mines_bombs:"), CasinoStates.waiting_bombs_mines)
async def process_mines_bombs(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return

    bombs = int(callback.data.split(":")[1])
    if bombs not in MINES_MULTIPLIERS:
        await callback.answer("❌ Недопустимое количество бомб.", show_alert=True)
        return

    data = await state.get_data()
    bet_amount = data["bet_amount"]
    user_id = callback.from_user.id

    balance_before = await get_money(user_id)
    await add_money(user_id, -bet_amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Назад", callback_data="casino_back")]
    ])
    await callback.message.edit_reply_markup(reply_markup=kb)

    all_cells = [(r, c) for r in range(5) for c in range(5)]
    mine_positions = random.sample(all_cells, bombs)

    await state.update_data(
        bombs=bombs,
        mine_positions=mine_positions,
        revealed=[],
        balance_before=balance_before
    )

    await show_mines_field(callback.message, state)
    await state.set_state(CasinoStates.playing_mines)
    await callback.answer()


async def show_mines_field(message: Message, state: FSMContext):
    data = await state.get_data()
    bet_amount = data["bet_amount"]
    bombs = data["bombs"]
    revealed = data.get("revealed", [])
    opened = len(revealed)
    owner_id = data.get("owner_id", message.from_user.id)

    current_win = 0
    if opened > 0:
        multiplier = MINES_MULTIPLIERS[bombs][opened - 1]
        current_win = int(bet_amount * multiplier)

    buttons = []
    for r in range(5):
        row = []
        for c in range(5):
            if (r, c) in revealed:
                row.append(InlineKeyboardButton(text="💎", callback_data=f"mines_open:{r}:{c}"))
            else:
                row.append(InlineKeyboardButton(text="🟦", callback_data=f"mines_open:{r}:{c}"))
        buttons.append(row)

    cashout_text = f"💰 Забрать: {current_win:,} монет" if current_win > 0 else "💰 Забрать выигрыш"
    buttons.append([InlineKeyboardButton(text=cashout_text, callback_data="mines_cashout")])
    buttons.append([InlineKeyboardButton(text="❓ Правила", url="https://telegra.ph/PRAVILA-IGRY-V-MINY---Homyak-Advent-10-30")])

    sent = await message.edit_text(
        f"💣 <b>Мины</b>\n"
        f"Бомб: {bombs}\n"
        f"Открыто: {opened}\n"
        f"Выигрыш: {current_win:,} монет",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    remember_owner(sent, owner_id)


@router.callback_query(F.data == "casino_mines", CasinoStates.playing_mines)
async def restart_mines_from_playing(callback: CallbackQuery, state: FSMContext):
    # пользователь решил начать заново прямо из режима игры
    await casino_mines_menu(callback, state)


@router.callback_query(F.data == "mines_cashout", CasinoStates.playing_mines)
async def mines_cashout(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return

    data = await state.get_data()
    user_id = callback.from_user.id
    bet_amount = data["bet_amount"]
    bombs = data["bombs"]
    revealed = data.get("revealed", [])
    balance_before = data["balance_before"]
    opened = len(revealed)

    if opened == 0:
        win_amount = 0
        result_text = "💣 Вы не открыли ни одной клетки. Ставка потеряна."
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Мины", -bet_amount,
            "проиграл", f"{bombs} бомб", "Ни одной клетки не открыто",
            balance_before=balance_before, from_chat_id=None, dice_message_id=None
        )

        await show_final_mines_field(
            bot=callback.bot,
            chat_id=ADMIN_CHAT_ID,
            mine_positions=data["mine_positions"],
            revealed=revealed,
            message_thread_id=5899
        )
    else:
        multiplier = MINES_MULTIPLIERS[bombs][opened - 1]
        win_amount = int(bet_amount * multiplier)
        await add_money(user_id, win_amount)
        result_text = (
            f"💣 <b>Вы забрали выигрыш!</b>\n"
            f"Ставка: {bet_amount:,} монет\n"
            f"Бомб: {bombs}\n"
            f"Открыто клеток: {opened}\n"
            f"Выигрыш: <b>{win_amount:,} монет</b>"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Мины", win_amount - bet_amount,
            "выиграл", f"{bombs} бомб", f"Открыто: {opened} клеток",
            balance_before=balance_before, from_chat_id=None, dice_message_id=None
        )

        await show_final_mines_field(
            bot=callback.bot,
            chat_id=ADMIN_CHAT_ID,
            mine_positions=data["mine_positions"],
            revealed=revealed,
            message_thread_id=5899
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💣 Ещё раз", callback_data="casino_mines"),
         InlineKeyboardButton(text="🏠 В меню", callback_data="casino_back")]
    ])
    sent = await callback.message.edit_text(result_text, reply_markup=kb, parse_mode="HTML")
    remember_owner(sent, user_id)

    owner_id = data.get("owner_id")
    if owner_id is None:
        await callback.answer("❌ Ошибка попробуйте еще раз. /casino", show_alert=True)
        await state.clear()
        return
    await reset_state_keep_owner(state, owner_id)

    await callback.answer()


@router.callback_query(F.data.startswith("mines_open:"), CasinoStates.playing_mines)
async def mines_open_cell(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return

    data = await state.get_data()
    user_id = callback.from_user.id

    r, c = map(int, callback.data.split(":")[1:3])
    pos = (r, c)

    if pos in data.get("revealed", []):
        await callback.answer("Уже открыто!", show_alert=True)
        return

    mine_positions = data["mine_positions"]
    revealed = data.get("revealed", []) + [pos]
    await state.update_data(revealed=revealed)

    if pos in mine_positions:
        bet_amount = data["bet_amount"]
        balance_before = data["balance_before"]
        result_text = (
            f"💣 Вы попали на <b>бомбу</b>!\n"
            f"❌ Вы проиграли {bet_amount:,} монет!"
        )
        await casino_log(
            callback.bot, callback.from_user, bet_amount, "Мины", -bet_amount,
            "проиграл", f"{data['bombs']} бомб", f"Бомба на {r+1},{c+1}",
            balance_before=balance_before, from_chat_id=None, dice_message_id=None
        )

        await show_final_mines_field(
            bot=callback.bot,
            chat_id=ADMIN_CHAT_ID,
            mine_positions=data["mine_positions"],
            revealed=revealed,
            message_thread_id=5899
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💣 Ещё раз", callback_data="casino_mines"),
             InlineKeyboardButton(text="🏠 В меню", callback_data="casino_back")]
        ])
        sent = await callback.message.answer(result_text, reply_markup=kb, parse_mode="HTML")
        remember_owner(sent, user_id)

        owner_id = data.get("owner_id")
        if owner_id is None:
            await callback.answer("❌ Ошибка попробуйте еще раз. /casino", show_alert=True)
            await state.clear()
            return
        await reset_state_keep_owner(state, owner_id)
    else:
        # продолжаем игру (показываем поле заново)
        await show_mines_field(callback.message, state)

    await callback.answer()


# === НАЗАД В МЕНЮ ===

@router.callback_query(F.data == "casino_back")
async def casino_back(callback: CallbackQuery, state: FSMContext):
    if not await only_owner(callback, state):
        return

    data = await state.get_data()
    owner_id = data.get("owner_id")
    if owner_id is None:
        await callback.answer("❌ Ошибка попробуйте еще раз. /casino", show_alert=True)
        await state.clear()
        return
    await reset_state_keep_owner(state, owner_id)

    balance_text = await get_balance_text(callback.from_user.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Кубик", callback_data="casino_dice"),
         InlineKeyboardButton(text="🏀 Баскетбол", callback_data="casino_basketball")],
        [InlineKeyboardButton(text="⚽ Футбол", callback_data="casino_football"),
         InlineKeyboardButton(text="✊ Камень-Ножницы-Бумага", callback_data="casino_rps")],
        [InlineKeyboardButton(text="🎰 Слоты", callback_data="casino_slots"),
         InlineKeyboardButton(text="🎯 Дартс", callback_data="casino_darts")],
        [InlineKeyboardButton(text="💣 Мины", callback_data="casino_mines")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="casino_close")]
    ])

    sent = await callback.message.answer(
        f"🎰 Приветствуем вас в Casino-Хомяк!\n\n"
        f"🤔 Вас будут приветствовать знакомые азартные игры: кубик, баскет, футбол и другие игры!\n"
        f"💸 За выигрыш вы будете получать х2 ставку\n\n"
        f"🪙 Игры проводятся исключительно во внутренней валюте \"Монеты\"\n\n{balance_text}",
        reply_markup=kb,
        parse_mode="HTML",
    )
    remember_owner(sent, callback.from_user.id)

    await callback.answer()
