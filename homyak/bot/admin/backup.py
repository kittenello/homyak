import asyncio
import zipfile
import os
from datetime import datetime
from aiogram import Router, Bot, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from ..database.admins import is_admin
from ..config import ADMIN_CHAT_ID
import tempfile

router = Router()

_bot_instance: Bot | None = None
_backup_task: asyncio.Task | None = None
_is_backup_enabled = False

def set_bot_instance(bot: Bot):
    global _bot_instance
    _bot_instance = bot

async def backup_loop():
    """Цикл отправки бэкапов каждые 30 минут"""
    while _is_backup_enabled:
        try:
            if _bot_instance:
                data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                zip_path = os.path.join(tempfile.gettempdir(), f"backup_{timestamp}.zip")

                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(data_dir):
                        for file in files:
                            if file.endswith(".db"):
                                file_path = os.path.join(root, file)
                                zipf.write(file_path, arcname=file)

                await _bot_instance.send_document(
                    chat_id=ADMIN_CHAT_ID,
                    document=FSInputFile(zip_path),
                    message_thread_id=2696,
                    caption=f"💾 Время: {timestamp}"
                )

                os.remove(zip_path)

        except Exception as e:
            print(f"[BACKUP ERROR] {e}")

        await asyncio.sleep(1500)

@router.message(Command("dbon"))
async def cmd_dbon(message: Message):
    global _is_backup_enabled, _backup_task
    if not await is_admin(message.from_user.id):
        return

    if _is_backup_enabled:
        await message.answer("✅ Бэкапы уже включены.")
        return

    _is_backup_enabled = True
    _backup_task = asyncio.create_task(backup_loop())
    await message.answer("✅")

@router.message(Command("dboff"))
async def cmd_dboff(message: Message):
    global _is_backup_enabled, _backup_task
    if not await is_admin(message.from_user.id):
        return

    if not _is_backup_enabled:
        await message.answer("✅ Бэкапы уже выключены.")
        return

    _is_backup_enabled = False
    if _backup_task:
        _backup_task.cancel()
        _backup_task = None

    await message.answer("⏹️ Автоматические бэкапы выключены.")
