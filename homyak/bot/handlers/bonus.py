from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, ChatMemberUpdated
from aiogram.handlers import ChatMemberHandler
from aiogram.filters import Command
from ..database.bonus import set_bonus, get_bonus, remove_bonus
from ..config import BONUS_CHANNEL_ID, CHANNEL_ID_BONUS
from ..database.premium import is_premium_active
from ..config import ADMIN_CHAT_ID
import logging

logger = logging.getLogger(__name__)


router = Router()

@router.message(Command("bonus"))
async def cmd_bonus(message: Message):
    if message.chat.type != "private":
        bot_link = "https://t.me/homyakadventbot?start=bonus"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Перейти в бота", url=bot_link)]
        ])
        await message.answer(
            "❌ Эта команда работает только в личных сообщениях с ботом.",
            reply_markup=keyboard,
            reply_to_message_id=message.message_id
        )
        return

    await show_bonus_menu(message)

async def show_bonus_menu(message: Message):
    bonus_info = await get_bonus(message.from_user.id)
    if bonus_info and bonus_info.get("is_active"):
        await message.answer("✅ У вас уже активированы бонусы!")
        return

    subscribe_url = "https://t.me/homyakadventcl"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться", url=subscribe_url)],
        [InlineKeyboardButton(text="Проверить подписку", callback_data="check_bonus")]
    ])
    await message.answer(
        "📒 <b>Задания</b>\n"
        "Выполните все задания, чтобы получить бонус:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "check_bonus")
async def check_bonus(callback_query):
    user_id = callback_query.from_user.id
    user = callback_query.from_user
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Без имени"
    username = f"@{user.username}" if user.username else f"ID {user_id}"

    try:
        member = await callback_query.bot.get_chat_member(BONUS_CHANNEL_ID, user_id)
        if member.status in ["member", "administrator", "creator"]:
            log_subscribe = (
                f"🔔 <b>Новая подписка</b>\n"
                f"👤 Пользователь: {full_name} ({username})\n"
                f"🆔 ID: {user_id}\n"
                f"📢 Канал: {BONUS_CHANNEL_ID}"
            )
            await callback_query.bot.send_message(ADMIN_CHAT_ID, log_subscribe, parse_mode="HTML")

            is_premium = await is_premium_active(user_id)
            await set_bonus(user_id, is_premium=is_premium)

            bonus_type = "Premium" if is_premium else "Обычный"
            log_bonus = (
                f"🎁 <b>Бонусы активированы</b>\n"
                f"👤 Пользователь: {full_name} ({username})\n"
                f"🆔 ID: {user_id}\n"
                f"💎 Тип бонуса: {bonus_type}"
            )
            await callback_query.bot.send_message(ADMIN_CHAT_ID, log_bonus, parse_mode="HTML")

            await callback_query.message.edit_text(
                "✅ Бонусы активированы!\n"
                "Вам было выдано (навсегда):\n\n"
                "Кд 6 часов вместо 7 часа(При наличии Premium - 4 часов вместо 5)\n"
                "+500 очков с каждого хомяка(При наличии Premium - +700 очков)"
            )
        else:
            await callback_query.answer("❌ Вы не подписаны на канал", show_alert=True)
    except Exception as e:
        logger.error(f"check error sub: {e}")
        await callback_query.answer("❌ Ошибка проверки подписки", show_alert=True)

@router.chat_member()
@router.my_chat_member()
class HandleUserLeave(ChatMemberHandler):
    async def handle(self) -> None:
        event: ChatMemberUpdated = self.event
        user_id = event.from_user.id
        
        logger.info(f"{event.from_user.id} новое {event.new_chat_member.status}")
        
        logger.info(f"{event.chat.id} {CHANNEL_ID_BONUS}")

        if event.chat.id == CHANNEL_ID_BONUS:
            if event.new_chat_member.status == "left":

                bonus_info = await get_bonus(user_id)
                if bonus_info and bonus_info.get("is_active"):

                    try:
                        await remove_bonus(user_id)
                    except Exception as e:
                        logger.error(f"ошибка 113 bonus.py {e}")
                        subscribe_url = "https://t.me/homyakadventcl"
                        markup_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Подписаться", url=subscribe_url)],
                    ])
                    try:
                        await self.event.bot.send_message(
                            user_id,
                            "❌ Проблема!\n\n😭 Вы вышли из канала, и поэтому ваши бонусы были полностью отключены.\n🤔 Но если хотите их вернуть - подпишитесь заново на канал и не отписывайтесь.",
                            reply_markup=markup_keyboard
                        )
                    except Exception as e:
                        logger.error(f"error to send message userid {e}")

            full_name = f"{event.from_user.first_name or ''} {event.from_user.last_name or ''}".strip() or "Без имени"
            username = f"@{event.from_user.username}" if event.from_user.username else f"ID {user_id}"
            bonus_info = await get_bonus(user_id)
            if bonus_info and bonus_info.get("is_active"):
                log_leave = (
                    f"🎁 Отключение бонуса\n"
                    f"👤 Пользователь: {full_name} ({username})\n"
                    f"🆔 ID: {user_id}\n"
                    f"📢 Канал: {CHANNEL_ID_BONUS}\n"
                    f"❌ Причина: отписка от канала (@homyakadventcl)"
                )
                try:
                    await self.event.bot.send_message(ADMIN_CHAT_ID, log_leave, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"error {e}")