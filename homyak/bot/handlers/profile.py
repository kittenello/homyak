from html import escape
from datetime import datetime
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ..database.premium import get_premium
from ..database.scores import get_score
from ..database.cards import get_user_cards, get_total_cards_count
from ..database.admins import is_admin

router = Router()


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user = message.from_user
    user_id = user.id

    # 🛡 Экранируем имя для HTML parse_mode
    raw_name = user.full_name or user.first_name or "Без имени"
    name = escape(raw_name)

    # --- Premium ---
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

    # --- Очки и последний хомяк ---
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

    # --- Карточки ---
    try:
        user_cards = await get_user_cards(user_id)
        opened_cards = len(user_cards)
    except Exception:
        opened_cards = 0

    try:
        total_cards = await get_total_cards_count()
    except Exception:
        total_cards = 0

    # --- Админ ---
    admin_status = ""
    try:
        if await is_admin(user_id):
            admin_status = "🔧 <i>Вы администратор</i>"
    except Exception:
        pass

    # --- Получаем аватар пользователя ---
    photo_file_id = None
    try:
        photos = await message.bot.get_user_profile_photos(user_id, limit=1)
        if photos.photos:
            # Берём последнее (самое большое) фото
            photo_file_id = photos.photos[0][-1].file_id
    except Exception:
        pass

    # --- Формируем текст профиля ---
    text = (
        f"👋 Привет, {name}!{premium_text}\n\n"
        f"✨ Очки: {total_score:,}\n"
        f"🃏 Карточек: {opened_cards} / {total_cards}\n"
        f"🐹 Последний хомяк: {last_homyak_text}\n"
        f"🎁 Открывай хомяков каждый день и собирай свою коллекцию!\n\n"
        f"{admin_status}"
    )

    # --- Отправляем сообщение ---
    if photo_file_id:
        await message.answer_photo(photo=photo_file_id, caption=text)
    else:
        await message.answer(text)
