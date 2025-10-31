from aiogram import Bot
from aiogram.types import BotCommand

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Начать работу"),
        BotCommand(command="/profile", description="Посмотреть профиль"),
        BotCommand(command="/premium", description="Оплата Premium-подписки"),
        BotCommand(command="/bonus", description="Получение бонуса"),
        BotCommand(command="/inventory", description="Инвентарь"),
        BotCommand(command="/shop", description="Магазин"),
        BotCommand(command="/casino", description="Казино"),
        BotCommand(command="/top", description="Топ участников по очкам"),
    ]
    await bot.set_my_commands(commands)