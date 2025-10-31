import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiosend import CryptoPay
from bot.services.cryptobot import CryptoBotService
from .config import BOT_TOKEN, CRYPTO_BOT_TOKEN
from .handlers import routers as user_routers
from bot.services import crypto_service
from .middlewares.admin_notify import AdminNotifyMiddleware
from .database.users import init_db as init_users_db
from .database.cooldowns import init_db as init_cooldowns_db
from bot.handlers.premium import set_bot_instance, notify_user_about_payment
from .database.admins import init_db as init_admins_db
from .database.premium import init_db as init_premium_db
from .database.rarity import init_db as init_rarity_db
from .database.scores import init_db as init_scores_db
from .database.money import init_db as init_money_db
from .database.shoph import init_db as init_shoph_db
from .database.bonus import init_db as init_bonus_db
from .database.games import init_db as init_games_db
from .database.cards import init_db as init_cards_db
from .database.shopbuyers import init_db as init_buyers_db
from .database.elixir import init_db as init_elixir_db
from .database.favourite import init_db as init_favourite_db
from .database.bundles import init_db as init_bundles_db
from .admin.backup import set_bot_instance
from .config import ADMIN_CHAT_ID
from .database.promo import init_db as init_promo_db
from .services.commands import set_bot_commands
from .admin import admin_routers
bot = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def main():
    try:
        await init_users_db()
        await init_cooldowns_db()
        await init_admins_db()
        await init_rarity_db()
        await init_promo_db()
        await init_cards_db()
        await init_elixir_db()
        await init_favourite_db()
        await init_money_db()
        await init_bundles_db()
        await init_shoph_db()
        await init_buyers_db()
        await init_scores_db()
        await init_bonus_db()
        await init_games_db()
        await init_premium_db()

        global bot
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        await set_bot_commands(bot)
        set_bot_instance(bot)
        dp = Dispatcher(storage=MemoryStorage())
        cp = CryptoPay("474438:AAYWC70n1d5XN5BPCfUZQGT0j1BacZb9mlL")

        if CRYPTO_BOT_TOKEN:
            try:
                crypto_service.service = CryptoBotService(CRYPTO_BOT_TOKEN, bot)
                crypto_service.service.set_payment_callback(notify_user_about_payment)
                logger.info(f"Bot created: {bot}")
                logger.info("cryptobot is on")
            except Exception as e:
                logger.error(f"cryptobot error {e}")
                crypto_service.service = None

        dp.update.middleware(AdminNotifyMiddleware(bot, ADMIN_CHAT_ID))

        for router in admin_routers:
            dp.include_router(router)
        for router in user_routers:
            dp.include_router(router)

        if crypto_service:
            logger.info("cryptobot and bot is on")
            await bot.delete_webhook(drop_pending_updates=True)
            await asyncio.gather(
                dp.start_polling(bot),
                cp.start_polling()
            )
        else:
            logger.info("only for bot polling rn")
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"error {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())