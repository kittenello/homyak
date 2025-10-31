from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
import logging


class AdminNotifyMiddleware(BaseMiddleware):
    def __init__(self, bot, admin_chat_id):
        self.bot = bot
        self.admin_chat_id = admin_chat_id
        super().__init__()

    async def __call__(
            self,
            handler,
            event: TelegramObject,
            data: dict
    ):
        try:
            return await handler(event, data)
        except Exception as e:
            logging.error(f"Ошибка в обработке события: {e}")

            error_message = f"Произошла ошибка: {str(e)}"
            await self.bot.send_message(self.admin_chat_id, error_message, message_thread_id=5658)

            raise e
