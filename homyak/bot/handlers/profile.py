from html import escape
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import re

from ..database.favourite import get_favorite
from ..database.money import get_money 
from ..database.premium import get_premium
from ..database.scores import get_score
from ..database.cards import get_user_cards, get_total_cards_count
from ..database.admins import is_admin

router = Router()

@router.callback_query(F.data == "gafdlkgafdklgadfkl")
async def handle_my_cards(callback_query: CallbackQuery):
    message_author_id = callback_query.from_user.id
    if callback_query.message.reply_to_message and callback_query.message.reply_to_message.from_user.id != message_author_id:
        await callback_query.answer("❌ Это не ваши кнопки!", show_alert=True)
        return
    if callback_query.message.reply_to_message and callback_query.message.reply_to_message.from_user.id == message_author_id:
        await callback_query.answer("🃏 Посмотреть свои карты можно в личных сообщениях с ботом.", show_alert=True)
        return
    await callback_query.answer()


@router.callback_query(F.data == "gafdlkgafdklgadfkls")
async def handle_my_cards(callback_query: CallbackQuery):
    message_author_id = callback_query.from_user.id
    if callback_query.message.reply_to_message and callback_query.message.reply_to_message.from_user.id != message_author_id:
        await callback_query.answer("❌ Это не ваши кнопки!", show_alert=True)
        return
    if callback_query.message.reply_to_message and callback_query.message.reply_to_message.from_user.id == message_author_id:
        await callback_query.answer("🎒 Использование и просмотр инвентаря доступен только в личных сообщениях с ботом.", show_alert=True)
        return
    await callback_query.answer()

@router.message(F.text.lower().in_({"профиль", "мой профиль", "хомяк профиль"}))
@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user = message.from_user
    user_id = user.id

    raw_name = user.full_name or user.first_name or "Без имени"
    name = escape(raw_name)

    premium_text = ""
    premium = await get_premium(user_id)
    if premium:
        if premium.get("is_lifetime"):
            premium_text = "\n👑 Premium: навсегда"
        elif premium.get("expires_at"):
            try:
                expires_date = datetime.fromisoformat(premium["expires_at"]).strftime("%d.%m.%Y")
                premium_text = f"\n👑 Premium до: {escape(expires_date)}"
            except Exception:
                pass

    total_score = 0
    last_homyak = None
    try:
        result = await get_score(user_id)
        if isinstance(result, (tuple, list)) and len(result) >= 2:
            total_score, last_homyak = result
        elif isinstance(result, dict):
            total_score = result.get("total_score", 0)
            last_homyak = result.get("last_homyak")
    except Exception:
        pass

    total_score = total_score or 0
    last_homyak_text = escape(last_homyak) if last_homyak else "ещё не было"

    try:
        user_cards = await get_user_cards(user_id)
        opened_cards = len(user_cards)
    except Exception:
        opened_cards = 0

    try:
        total_cards = await get_total_cards_count()
    except Exception:
        total_cards = 0

    admin_status = ""
    try:
        if await is_admin(user_id):
            admin_status = "🔧 <i>Вы администратор</i>"
    except Exception:
        pass

    photo_file_id = None
    try:
        photos = await message.bot.get_user_profile_photos(user_id, limit=1)
        if photos.photos:
            photo_file_id = photos.photos[0][-1].file_id
    except Exception:
        pass

    if message.chat.type == "private":
        callback_data = "my_cards"
    else:
        callback_data = "gafdlkgafdklgadfkl"
    
    if message.chat.type == "private":
        colback_data = "inventory:main"
    else:
        colback_data = "gafdlkgafdklgadfkls"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🃏 Мои карты", callback_data=callback_data)],
        [InlineKeyboardButton(text="🎒 Инвентарь", callback_data=colback_data)]
    ])
    favorite_filename = await get_favorite(user_id)
    if favorite_filename:
        favorite_name = favorite_filename[:-4]
        favorite_text = f"\n❤️‍🔥 Любимая карта • {favorite_name}"
    else:
        favorite_text = "\n❤️‍🔥 Любимая карта • Не выбрана"

    money = await get_money(user_id)

    text = (
        f"👋 Привет, {name}!{premium_text}\n\n"
        f"✨ Очки: {total_score:,}\n"
        f"💰 Монеты: {money:,}\n"
        f"🃏 Карточек: {opened_cards} / {total_cards}\n"
        f"🐹 Последний хомяк: {last_homyak_text}\n"
        f"{favorite_text}\n"
        f"🎁 Открывай хомяков каждый день и собирай свою коллекцию!\n\n"
        f"{admin_status}"
    )

    if photo_file_id:
        await message.answer_photo(photo=photo_file_id, caption=text, reply_markup=keyboard, reply_to_message_id=message.message_id, parse_mode="HTML")
    else:
        await message.answer(text, reply_to_message_id=message.message_id, reply_markup=keyboard, parse_mode="HTML")
