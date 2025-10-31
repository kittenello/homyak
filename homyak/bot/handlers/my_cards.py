from aiogram import Router, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, FSInputFile, Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from pathlib import Path

from ..database.cards import get_user_cards, get_total_cards_count
from ..database.rarity import get_rarity, RARITY_NAMES

router = Router()
HOMYAK_FILES_DIR = Path(__file__).parent.parent / "files"

class MyCardsState(StatesGroup):
    viewing = State()

PAGE_SIZE = 10

async def _purge_sent(message: Message, state: FSMContext):
    data = await state.get_data()
    ids: list[int] = data.get("msg_gc", [])
    for mid in ids:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=mid)
        except Exception:
            pass
    await state.update_data(msg_gc=[])

async def _track_sent(msg: Message, state: FSMContext):
    data = await state.get_data()
    ids: list[int] = data.get("msg_gc", [])
    ids.append(msg.message_id)
    await state.update_data(msg_gc=ids)

@router.callback_query(F.data == "my_cards")
async def show_my_cards_menu(callback_query: CallbackQuery, state: FSMContext):
    message_author_id = callback_query.from_user.id
    if callback_query.message.reply_to_message and callback_query.message.reply_to_message.from_user.id != message_author_id:
        await callback_query.answer("❌ Это не ваши кнопки!", show_alert=True)
        return
    user_id = callback_query.from_user.id

    user_cards = list(await get_user_cards(user_id))
    total_cards = await get_total_cards_count()
    opened = len(user_cards)

    buttons = [
        [InlineKeyboardButton(text="Последние", callback_data="cards_last")],
        [InlineKeyboardButton(text="Любимые", callback_data="cards_favorites")],
        [InlineKeyboardButton(text="Обычные", callback_data="cards_rarity_1")],
        [InlineKeyboardButton(text="Редкие", callback_data="cards_rarity_2")],
        [InlineKeyboardButton(text="Мифические", callback_data="cards_rarity_3")],
        [InlineKeyboardButton(text="Легендарные", callback_data="cards_rarity_4")],
        [InlineKeyboardButton(text="Секретные", callback_data="cards_rarity_5")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile")],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await _purge_sent(callback_query.message, state)
    msg = await callback_query.message.answer(
        f"🃏 Ваши карты\nВсего • {opened} из {total_cards}",
        reply_markup=keyboard,
    )
    await _track_sent(msg, state)

    await state.update_data(current_cards=user_cards, current_filter="last", current_page=1)
    await callback_query.answer()

@router.callback_query(F.data == "cards_favorites")
async def show_favorite_card(callback_query: CallbackQuery, state: FSMContext):
    message_author_id = callback_query.from_user.id
    if callback_query.message.reply_to_message and callback_query.message.reply_to_message.from_user.id != message_author_id:
        await callback_query.answer("❌ Это не ваши кнопки!", show_alert=True)
        return

    user_id = callback_query.from_user.id

    from ..database.favourite import get_favorite
    favorite_filename = await get_favorite(user_id)

    if not favorite_filename:
        await callback_query.answer("😒 У вас пока нет любимой карты.", show_alert=True)

        await show_my_cards_menu(callback_query, state)
        return

    await render_card_detail(callback_query.message, favorite_filename, state)
    await callback_query.answer()

@router.callback_query(F.data.startswith("cards_"))
async def list_cards(callback_query: CallbackQuery, state: FSMContext):
    message_author_id = callback_query.from_user.id
    if callback_query.message.reply_to_message and callback_query.message.reply_to_message.from_user.id != message_author_id:
        await callback_query.answer("❌ Это не ваши кнопки!", show_alert=True)
        return
    user_id = callback_query.from_user.id
    user_cards = list(await get_user_cards(user_id))

    parts = callback_query.data.split("_")
    if len(parts) < 2:
        await callback_query.answer("Некорректная команда.")
        return

    if parts[1] == "last":
        cards = user_cards
        filter_type = "last"
    elif parts[1] == "rarity" and len(parts) >= 3:
        try:
            rarity = int(parts[2])
        except Exception:
            await callback_query.answer("Некорректная редкость.")
            return
        cards = [f for f in user_cards if (await get_rarity(f)) == rarity]
        filter_type = f"rarity_{rarity}"
    else:
        await callback_query.answer("Некорректная команда.")
        return

    await show_cards_page(callback_query, cards, page=1, filter_type=filter_type, state=state)
    await state.update_data(current_cards=cards, current_filter=filter_type, current_page=1)

async def show_cards_page(callback_query: CallbackQuery, cards, page: int, filter_type: str, state: FSMContext):
    cards = list(cards) 

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_cards = cards[start:end]

    if not page_cards:
        await callback_query.answer("Нет карт этой редкости.")
        return

    lines = ["🃏 Ваши карты:"]
    buttons = []

    # Кнопки карточек
    for filename in page_cards:
        name = filename[:-4]  # убираем .png
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"card_detail_{filename}")])

    # Пагинация
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"cards_{filter_type}_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"Стр {page}", callback_data="noop"))
    if end < len(cards):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"cards_{filter_type}_{page+1}"))
    if nav:
        buttons.append(nav)

    # ⬅️ Назад — ВОЗВРАЩАЕТ В МЕНЮ «МОИ КАРТЫ» (гарантированно работает в этом модуле)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="my_cards")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = "\n".join(lines)

    await _purge_sent(callback_query.message, state)
    msg = await callback_query.message.answer(text, reply_markup=keyboard)
    await _track_sent(msg, state)

    await state.update_data(current_cards=cards, current_filter=filter_type, current_page=page)
    await callback_query.answer()

async def render_card_detail(message, filename: str, state: FSMContext):
    from ..database.rarity import RARITY_POINTS, RARITY_NAMES
    from ..database.favourite import get_favorite

    homyak_name = filename[:-4]
    rarity_id = await get_rarity(filename)
    points = RARITY_POINTS[rarity_id]

    user_id = message.chat.id if message.chat.type == "private" else message.from_user.id
    user_id = (await state.get_data()).get("user_id") or message.from_user.id

    favorite_filename = await get_favorite(user_id)
    is_favorite = (favorite_filename == filename)

    favorite_btn = InlineKeyboardButton(
        text="💔" if is_favorite else "❤️",
        callback_data=f"toggle_favorite_{filename}"
    )
    back_btn = InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="back_to_cards_list"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[favorite_btn], [back_btn]])

    caption = (
        f"🐹 {homyak_name}\n"
        f"💎 Редкость: {RARITY_NAMES[rarity_id]}\n"
        f"✨ Очки: {points}"
    )

    file_path = HOMYAK_FILES_DIR / filename

    await _purge_sent(message, state)
    if not file_path.exists():
        msg = await message.answer(
            "card not found, write to admin",
            reply_markup=keyboard
        )
    else:
        msg = await message.answer_photo(
            photo=FSInputFile(file_path),
            caption=caption,
            reply_markup=keyboard
        )
    await _track_sent(msg, state)

    await state.update_data(current_filename=filename, user_id=user_id)

@router.callback_query(F.data.startswith("card_detail_"))
async def show_card_detail(callback_query: CallbackQuery, state: FSMContext):
    message_author_id = callback_query.from_user.id
    if callback_query.message.reply_to_message and callback_query.message.reply_to_message.from_user.id != message_author_id:
        await callback_query.answer("❌ Это не ваши кнопки!", show_alert=True)
        return
    
    filename = callback_query.data.removeprefix("card_detail_")
    await render_card_detail(callback_query.message, filename, state)
    await callback_query.answer()

@router.callback_query(F.data.startswith("toggle_favorite_"))
async def toggle_favorite(callback_query: CallbackQuery, state: FSMContext):
    message_author_id = callback_query.from_user.id
    if callback_query.message.reply_to_message and callback_query.message.reply_to_message.from_user.id != message_author_id:
        await callback_query.answer("❌ Это не ваши кнопки!", show_alert=True)
        return
    
    filename = callback_query.data.removeprefix("toggle_favorite_")
    user_id = callback_query.from_user.id

    from ..database.favourite import set_favorite
    await set_favorite(user_id, filename)

    await render_card_detail(callback_query.message, filename, state)
    await callback_query.answer("Выбрано как любимая ✅")

@router.callback_query(F.data == "back_to_cards_list")
async def back_to_cards_list(callback_query: CallbackQuery, state: FSMContext):
    message_author_id = callback_query.from_user.id
    if callback_query.message.reply_to_message and callback_query.message.reply_to_message.from_user.id != message_author_id:
        await callback_query.answer("❌ Это не ваши кнопки!", show_alert=True)
        return
    
    data = await state.get_data()
    cards = data.get("current_cards", [])
    filter_type = data.get("current_filter", "last")
    page = data.get("current_page", 1)

    await show_cards_page(callback_query, cards, page, filter_type, state)
    await callback_query.answer()
