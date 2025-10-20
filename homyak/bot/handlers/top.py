from html import escape
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

from ..database.scores import get_top_scores_in_chat, get_top_cards_in_chat

router = Router()

message_data = {}

def build_top_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="🏆 Топ по очкам", callback_data="top:points")],
        [InlineKeyboardButton(text="🃏 Топ по карточкам", callback_data="top:cards")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def build_back_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="🔙 Назад", callback_data="top:back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def render_top(rows: list[tuple[int, int, str, str]], category: str, title: str, medal_emoji: str, user_id: int) -> str:
    if not rows:
        return f"{medal_emoji} Пока нет участников в этом чате."
    
    lines = [f"{medal_emoji} <b>{title}</b>"]
    medals = ["🥇", "🥈", "🥉"]
    
    user_position = None
    
    rows = rows[:10]

    lines.append("<blockquote>")

    for position, (user_id_in_top, count, first_name, username) in enumerate(rows, start=1):
        display_name = escape(first_name) if first_name else "Без имени"
        display = f"@{username}" if username else f"<a href=\"tg://user?id={user_id_in_top}\">{display_name}</a>"
        medal = medals[position - 1] if position <= 3 else f"{position}."
        
        if user_id_in_top == user_id:
            user_position = position
        
        lines.append(f"{medal} {display} — <b>{count:,}</b> {category}")
    
    lines.append("</blockquote>")

    if user_position is None:
        lines.append(f"🎖️ Ваше место — {len(rows) + 1}")
    else:
        lines.append(f"🎖️ Ваше место — {user_position}")
    
    return "\n".join(lines)

async def safe_edit(message, *, text: str, reply_markup: InlineKeyboardMarkup | None = None):
    try:
        await message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            try:
                await message.edit_reply_markup(reply_markup=reply_markup)
            except TelegramBadRequest:
                pass
        else:
            raise

@router.message(F.text.lower().startswith(("топ", "топ беседы")))
@router.message(Command("top"))
async def cmd_top(message: Message):
    if message.chat.type == "private":
        await message.answer("🏆 Команда доступна только в групповых чатах.")
        return
    
    response = await message.answer(
        "🏆 Топ 10 игроков этой группы\n"
        "<blockquote>Выберите по какому значению показать топ</blockquote>",
        reply_markup=build_top_keyboard(),
        parse_mode="HTML"
    )
    message_data[response.message_id] = {"original_user_id": message.from_user.id}

@router.callback_query(F.data.startswith("top:"))
async def cb_top_handler(callback: CallbackQuery):
    message_id = callback.message.message_id
    data = message_data.get(message_id, {})
    original_user_id = data.get("original_user_id")
    
    if original_user_id != callback.from_user.id:
        await callback.answer("❌ Это не ваши кнопки!", show_alert=True)
        return

    if callback.data == "top:points":
        chat = callback.message.chat
        rows = await get_top_scores_in_chat(callback.bot, chat.id, limit=10)
        user_id = callback.from_user.id 
        text = render_top(rows, "очков", "Топ 10 игроков по очкам в этой группе", "🏆", user_id)
        await safe_edit(callback.message, text=text, reply_markup=build_back_keyboard())
        await callback.answer("🏆 Топ по очкам")
    
    elif callback.data == "top:cards":
        chat = callback.message.chat
        rows = await get_top_cards_in_chat(callback.bot, chat.id, limit=10)
        user_id = callback.from_user.id 
        text = render_top(rows, "карточек", "Топ 10 игроков по карточкам в этой группе", "🃏", user_id)
        await safe_edit(callback.message, text=text, reply_markup=build_back_keyboard())
        await callback.answer("🃏 Топ по карточкам")
    
    elif callback.data == "top:back":
        await callback.message.edit_text(
            "🏆 Топ 10 игроков этой группы\n"
            "<blockquote>Выберите по какому значению показать топ</blockquote>",
            reply_markup=build_top_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer("🔙 Назад")