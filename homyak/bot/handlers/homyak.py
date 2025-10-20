from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from datetime import datetime, timedelta
import random
from pathlib import Path
from ..config import SETTINGS
from ..database.cooldowns import get_last_used, set_last_used, is_infinite
from ..database.admins import is_admin
from ..database.rarity import get_rarity, RARITY_NAMES, RARITY_POINTS
from ..database.scores import add_score, get_score
from ..database.bonus import get_bonus
from ..database.premium import is_premium_active
from ..database.cards import add_card, get_user_cards, get_total_cards_count
from ..admin_logs.logger import notify_homyak_found

router = Router()
HOMYAK_FILES_DIR = Path(__file__).parent.parent / "files"

triggers = {"хомяк", "хома", "хомя", "хомячок", "хомяччело", "гамяк", "гомяк", "хамяк", "хомячелло"}

@router.message(F.text)
async def handle_homyak(message: Message):
    text = message.text.strip().lower()
    if text not in triggers:
        return

    user = message.from_user
    user_id = user.id


    is_premium = await is_premium_active(user_id)
    base_cooldown = 300 if is_premium else SETTINGS["GLOBAL_COOLDOWN_MINUTES"]

    bonus_info = await get_bonus(user_id)
    if bonus_info and bonus_info["is_active"]:
        if bonus_info["is_premium_at_activation"] or is_premium:
            base_cooldown = 240  
        else:
            base_cooldown = 360

    if base_cooldown == 0:
        pass
    elif await is_admin(user_id) and await is_infinite(user_id):
        pass
    else:
        last_used = await get_last_used(user_id)
        if last_used:
            cooldown_end = last_used + timedelta(minutes=base_cooldown)
            if datetime.now() < cooldown_end:
                remaining = cooldown_end - datetime.now()
                hours, remainder = divmod(remaining.seconds, 3600)
                minutes = remainder // 60
                await message.answer(
                    f"⏳ Вы уже открывали хомяка сегодня!\n"
                    f"Следующий хомяк через: {hours}ч {minutes}мин"
                )
                return

    image_files = [
        f for f in HOMYAK_FILES_DIR.glob("*.png")
        if f.name.lower() != "welcome.png"
    ]

    non_secret_files = []
    for f in image_files:
        rarity = await get_rarity(f.name)
        if rarity != 5: # <<< секретная
            non_secret_files.append(f)

    if not image_files:
        await message.answer("test teest")
        return

    chosen = random.choice(image_files)
    filename = chosen.name
    homyak_name = chosen.stem

    original_rarity = await get_rarity(filename)
    display_rarity = original_rarity

    points = RARITY_POINTS[display_rarity]
    if is_premium:
        points += 1000
    if bonus_info and bonus_info["is_active"]:
        points += 700 if (bonus_info["is_premium_at_activation"] or is_premium) else 500

    if base_cooldown != 0 and not (await is_admin(user_id) and await is_infinite(user_id)):
        await set_last_used(user_id)

    user_cards = await get_user_cards(user_id)
    is_new_card = filename not in user_cards

    if is_new_card:
        await add_card(user_id, filename)

    await add_score(user_id, points, homyak_name, chat_id=message.chat.id)
    total_score, _ = await get_score(user_id)

    caption_lines = [
        f"🪄 Вы нашли карточку «{homyak_name}»",
        "",
        f"💎 Редкость • {RARITY_NAMES[display_rarity]}",
        f"✨ Очки • +{points:,} [{total_score:,}]"
    ]

    if not is_new_card:
        caption_lines.append("")
        caption_lines.append("🔁 Эта карточка у вас уже есть — добавлены только очки.")

    caption_lines.append("\n🎁 Получи бонусы с помощью команды /bonus")
    caption = "\n".join(caption_lines)

    await message.answer_photo(photo=FSInputFile(chosen), caption=caption, reply_to_message_id=message.message_id)
    chat_type = "Личка" if message.chat.type == "private" else "Группа"
    chat_name = message.chat.title if message.chat.type != "private" else "Личка"
    await notify_homyak_found(message.bot, user, homyak_name, f"{chat_type} ({chat_name})")

    if not is_premium:
        if random.random() < 0.3:
            await message.answer(
                "💡 Хотите открывать хомяков чаще и получать больше очков?\n"
                "Приобретите Premium-подписку: /premium"
            )

async def send_homyak_by_name(message: Message, homyak_name: str):
    print(f"Получено имя хомяка: {homyak_name}")
    user = message.from_user
    user_id = user.id

    filename = f"{homyak_name}.png"
    file_path = HOMYAK_FILES_DIR / filename

    if not file_path.exists():
        await message.answer(f"❌ Хомяк «{homyak_name}» не найден.")
        return

    original_rarity = await get_rarity(filename)
    display_rarity = original_rarity

    is_premium = await is_premium_active(user_id)
    points = RARITY_POINTS[display_rarity]
    if is_premium:
        points += 1000

    bonus_info = await get_bonus(user_id)
    if bonus_info and bonus_info["is_active"]:
        points += 700 if (bonus_info["is_premium_at_activation"] or is_premium) else 500

    user_cards = await get_user_cards(user_id)
    is_new_card = filename not in user_cards
    if is_new_card:
        await add_card(user_id, filename)

    await add_score(user_id, points, homyak_name, chat_id=message.chat.id)
    total_score, _ = await get_score(user_id)


    caption_lines = [
        f"🪄 С помощью промокода вы получили карточку «{homyak_name}»!",
        "",
        f"💎 Редкость • {RARITY_NAMES[display_rarity]}",
        f"✨ Очки • +{points:,} [{total_score:,}]"
    ]

    if not is_new_card:
        caption_lines.append("")
        caption_lines.append("🔁 Эта карточка у вас уже есть — добавлены только очки.")

    caption = "\n".join(caption_lines)

    await message.answer_photo(photo=FSInputFile(file_path), caption=caption, reply_to_message_id=message.message_id)

    from ..admin_logs.logger import notify_homyak_found
    chat_type = "Личка" if message.chat.type == "private" else "Группа"
    chat_name = message.chat.title if message.chat.type != "private" else "Личка"
    await notify_homyak_found(message.bot, user, homyak_name, f"{chat_type} ({chat_name})")