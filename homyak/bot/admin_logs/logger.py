from aiogram import Bot
from aiogram.types import User, FSInputFile
from datetime import datetime
from ..database.money import get_money
from ..config import HOMYAK_FILES_DIR, ADMIN_CHAT_ID
import logging

logger = logging.getLogger(__name__)

async def notify_new_user(bot: Bot, user: User):
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Без имени"
    username = f"@{user.username}" if user.username else "нет"
    text = (
        f"🆕 Новый пользователь!\n"
        f"ID: {user.id}\n"
        f"Имя: {full_name}\n"
        f"Юзернейм: {username}"
    )
    try:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"cant send log found new user: {e}")

async def notify_homyak_found(bot: Bot, user: User, homyak_name: str, chat_type: str):
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Без имени"
    username = f"@{user.username}" if user.username else "нет"
    
    text = (
        f"🐹 Выпадение хомяка\n"
        f"Пользователь: {full_name} ({username})\n"
        f"ID: {user.id}\n"
        f"Хомяк: {homyak_name} (Редкость: \n"
        f"Источник: {chat_type}"
    )
    
    filename = f"{homyak_name}.png"
    file_path = HOMYAK_FILES_DIR / filename

    try:
        if file_path.exists():
            await bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=FSInputFile(file_path),
                caption=text
            )
        else:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"cant send log found homyak: {e}")

async def notify_promo_used(bot, user_id, username, full_name, promo_code, reward_type, reward_value, creator_id, remaining_uses):
    reward_names = {
        1: "Очки",
        2: "Хомяк",
        3: "Снятие КД",
        4: "Множитель очков",
        5: "Монеты"
    }
    reward_text = reward_names.get(reward_type, "Неизвестно")
    if reward_type == 1:
        reward_text += f" ({reward_value} очков)"
    elif reward_type == 2:
        reward_text += f" ({reward_value})"
    elif reward_type == 4:
        reward_text += f" (+{reward_value} очков)"
    elif reward_type == 5:
        reward_text += f" (+{reward_value} монет)"

    text = (
        f"🎟️ <b>Активация промокода</b>\n"
        f"👤 Пользователь: {full_name} (@{username})\n"
        f"🆔 ID: {user_id}\n"
        f"🎫 Промокод: {promo_code}\n"
        f"🎁 Выдалось: {reward_text}\n"
        f"🔄 Осталось активаций: {remaining_uses}\n"
        f"🛠️ Создал: {creator_id} (ID)"
    )
    try:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"cant send log promo:  {e}")

async def casino_log(
    bot: Bot,
    user: User,
    bet_amount: int,
    game_type: str,
    win_amount: int,
    result: str,
    user_choice: str,
    game_result: str,
    balance_before: int,
    from_chat_id: int = None,
    dice_message_id: int = None
):

    balance_after = balance_before + win_amount
    if from_chat_id is not None and dice_message_id is not None:
        try:
            forwarded_msg = await bot.forward_message(
                chat_id=ADMIN_CHAT_ID,
                from_chat_id=from_chat_id,
                message_id=dice_message_id,
                message_thread_id=5899
            )
            reply_to_id = forwarded_msg.message_id
        except Exception as e:
            logger.error(f"Не удалось переслать смайлик: {e}")
            reply_to_id = None

    username = f"@{user.username}" if user.username else "нет"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Без имени"
    user_id = user.id

    balance_before = await get_money(user_id)
    balance_after = balance_before + win_amount

    log_text = (
        f"📝 Казино\n"
        f"Пользователь: {full_name} ({username})\n"
        f"ID: {user_id}\n"
        f"❗Тип игры: {game_type}\n"
        f"Ставка: {bet_amount:,} монет\n"
        f"Результат: {result}\n"
        f"❗Выбор пользователя: {user_choice}\n"
        f"‼️Результат игры: {game_result}\n"
        f"Выигрыш/Проигрыш: {win_amount:,} монет\n"
        f"Баланс до игры: {balance_before:,} монет\n"
        f"Баланс после игры: {balance_after:,} монет\n"
    )

    try:
        if 'reply_to_id' in locals():
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=log_text,
                parse_mode="HTML",
                message_thread_id=5899,
                reply_to_message_id=reply_to_id
            )
        else:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=log_text,
                parse_mode="HTML",
                message_thread_id=5899
            )
    except Exception as e:
        logger.error(f"Не удалось отправить лог казино: {e}")