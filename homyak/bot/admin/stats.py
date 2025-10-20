from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from ..database.admins import is_admin
from ..database.scores import reset_user_scores
from ..database.cards import reset_user_cards
from ..database.cooldowns import reset_user_cooldown
from ..database.premium import remove_premium
from ..database.bonus import remove_bonus

router = Router()

@router.message(Command("rss"))
async def cmd_resetstats(message: Message):
    if not await is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /rss [user_id]")
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return

    await reset_user_scores(user_id)
    await reset_user_cards(user_id)
    await reset_user_cooldown(user_id)
    await remove_premium(user_id)
    await remove_bonus(user_id)

    await message.answer(f"✅ Статистика пользователя {user_id} полностью сброшена!")