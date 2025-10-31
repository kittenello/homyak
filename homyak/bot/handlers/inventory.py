from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from ..database.elixir import get_user_elixirs, consume_first_of_type
from ..database.cooldowns import get_remaining_time, reduce_cooldown
from .profile import cmd_profile
router = Router()

@router.message(Command("inventory"))
async def inventar_karoche_message(message: Message):
    if message.chat.type != "private":
        bot_link = "https://t.me/homyakadventbot?start=profile"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Перейти в бота", url=bot_link)]
        ])
        await message.answer(
            "❌ Эта команда работает только в личных сообщениях с ботом.",
            reply_markup=keyboard,
            reply_to_message_id=message.message_id
        )
        return
    await cmd_profile(message)


@router.callback_query(F.data.startswith("inventory:"))
async def inventar_karoche_callback(query: CallbackQuery):
    await inventory_handler(query.message, query)

async def inventory_handler(message: Message, query: CallbackQuery):
    user_id = query.from_user.id
    action = query.data.split(":", 1)[1]

    if action == "main":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚡️ Бустеры", callback_data="inventory:boosters")],
            [InlineKeyboardButton(text="‹ Назад", callback_data="profile:refresh")]
        ])
        await query.message.answer("🎒 Инвентарь\nВыберите тип предмета", reply_markup=kb)
        return

    if action == "boosters":
        elixirs = await get_user_elixirs(user_id)
        rows = []
        
        luck_count = sum(1 for e in elixirs if e["type"] == "luck")
        time_count = sum(1 for e in elixirs if e["type"] == "time")
        
        if luck_count:
            rows.append([InlineKeyboardButton(
                text=f"🍀 Удача [{luck_count} шт.]", 
                callback_data="inventory:boost:luck"
            )])
        if time_count:
            rows.append([InlineKeyboardButton(
                text=f"⏳ Ускорение времени [{time_count} шт.]",
                callback_data="inventory:boost:time"
            )])
            
        rows.append([InlineKeyboardButton(text="‹ Назад", callback_data="inventory:main")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        
        if not elixirs:
            text = "⚡️ <b>Бустеры</b>\n<blockquote>У вас пока нет бустеров</blockquote>"
        else:
            text = "⚡️ <b>Бустеры</b>\n<blockquote>Выберите бустер для использования</blockquote>"
            
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        return

    if action.startswith("boost:"):
        boost_type = action.split(":", 1)[1]
        elixirs = await get_user_elixirs(user_id)
        count = sum(1 for e in elixirs if e["type"] == boost_type)
        
        if boost_type == "luck":
            name = "🍀 Удача"
            desc = "При получении карточки повышает шанс редкости на 25%"
        else:
            name = "⏳ Ускорение времени"
            desc = "Мгновенно уменьшает время ожидания на 1 час"
            
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✨ Активировать", callback_data=f"inventory:activate:{boost_type}")],
            [InlineKeyboardButton(text="‹ Назад", callback_data="inventory:boosters")]
        ])
        
        text = f"⚡️ Бустеры [{name}] [{count} шт.]\n{desc}"
        await query.message.edit_text(text, reply_markup=kb)
        return

    if action.startswith("activate:"):
        boost_type = action.split(":", 1)[1]

        if boost_type == "luck":
            await consume_first_of_type(user_id, "luck")
            text = ("🍀 Бустер <b>«удача»</b> активирован\n"
                    "<blockquote>При получении карточки он будет использован</blockquote>")
        else:
            remaining = await get_remaining_time(user_id)
            if remaining > 0:
                await consume_first_of_type(user_id, "time")
                await reduce_cooldown(user_id, 3600)
                text = "⏳ Бустер <b>«Сокращение времени»</b> активирован\n<blockquote>Время ожидания уменьшено на 1 час</blockquote>"
            else:
                text = "⚠️ Вы можете прямо сейчас использывать «хомяк», использование бустера невозможно.\n❌ Или же ваше КД меньше часа, использование бустера невозможно."
                return

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="‹ Назад к бустерам", callback_data="inventory:boosters")]
        ])
        await query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        return