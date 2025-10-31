from aiogram import Router
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from pathlib import Path
from datetime import datetime
from ..database.users import add_user_and_check
from ..admin_logs.logger import notify_new_user
from ..database.premium import get_premium

router = Router()

WELCOME_VIDEO_PATH = Path(__file__).parent.parent / "files" / "welcome.mp4"

@router.message(Command("start"))
async def cmd_start(message: Message):
    args = message.text.split(maxsplit=1)
    payload = args[1] if len(args) > 1 else None

    user = message.from_user
    is_new = await add_user_and_check(user.id, user.username, user.first_name, user.last_name)
    if is_new:
        await notify_new_user(message.bot, user)

    if payload == "bonus":
        from .bonus import show_bonus_menu
        await show_bonus_menu(message)
        return
    
    if payload == "premium":
        from .premium import show_premium_menu
        await show_premium_menu(message)
        return
    if payload == "shop":
        from .shop import show_shop_menu
        await show_shop_menu(message)
        return
    if payload == "inventory":
        from .inventory import inventory_handler
        await inventory_handler(message)
        return
    if payload == "profile":
        from .profile import cmd_profile
        await cmd_profile(message)
        return

    premium_info = await get_premium(user.id)
    premium_text = ""
    premium_ad = ""
    if premium_info:
        if premium_info["is_lifetime"]:
            premium_text = "\n👑 У вас активен Premium (навсегда)!"
        elif premium_info["expires_at"]:
            expires_date = datetime.fromisoformat(premium_info["expires_at"]).strftime("%d.%m.%Y")
            premium_text = f"\n👑 Premium активен до {expires_date}!"
    else:
        premium_ad = "\n💡 Вы можете приобрести Premium-подписку. Для этого напишите /premium"

    if not WELCOME_VIDEO_PATH.exists():
        await message.answer("⚠️ Приветственное видео не найдено.")
    else:
        caption = (
            "⭐️ Добро пожаловать в Homyak Адвент-Календарь!\n\n"
            "🎁 Каждый день Вас ждут любимые хомяки.\n"
            "  └ Открывайте хомяка, чтобы узнать, какой вы хомяк!\n\n"
            "🐹 Просто напишите «хомяк» — и откройте своего хомяка!"
            f"{premium_text}"
            f"{premium_ad}"
        )
        await message.answer_video(video=FSInputFile(WELCOME_VIDEO_PATH), caption=caption, reply_to_message_id=message.message_id, parse_mode="HTML")