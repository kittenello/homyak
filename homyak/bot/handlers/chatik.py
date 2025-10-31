from pathlib import Path
from aiogram import Router
from aiogram.types import Message, FSInputFile
import time

router = Router()

_last_call: dict[int, float] = {}

TRIGGERS = {"чатик спит", "чатик спать", "спать чатик"}

@router.message(lambda message: message.text and message.text.lower().strip() in TRIGGERS)
async def _chatik_sleep_handler(message: Message):
    user_id = message.from_user.id
    current_time = time.time()

    last_time = _last_call.get(user_id, 0)
    if current_time - last_time < 10:
        return

    _last_call[user_id] = current_time

    img_path = Path(__file__).parent / "chatik.png"
    print(f"Путь к файлу: {img_path}")
    if img_path.exists():
        await message.reply_photo(FSInputFile(img_path))
    else:
        await message.reply("double")