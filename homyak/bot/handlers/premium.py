from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, LabeledPrice
from aiosend.enums import InvoiceStatus
from datetime import timedelta, datetime
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from ..database.premium import set_premium
from ..config import ADMIN_CHAT_ID, CRYPTO_BOT_TOKEN
from aiogram.methods import RefundStarPayment
from ..database.money import add_money
from ..database.elixir import add_elixir
from ..database.cards import add_card
from ..database.shoph import get_item
from ..database.shopbuyers import has_bought, record_purchase
from ..services.cryptobot import CryptoBotService
from ..services import crypto_service
from ..database.premium import get_premium
import logging

logger = logging.getLogger(__name__)
router = Router()


_bot_instance: Bot | None = None

def set_bot_instance(bot: Bot):
    global _bot_instance
    _bot_instance = bot


PRICE_PLANS = {
    "1_month": 8,
    "3_months": 30,
    "6_months": 50,
    "1_year": 90,
    "lifetime": 200
}

def format_display_name(plan_key: str) -> str:
    name = plan_key.replace("_", " ")
    if "month" in name:
        name = name.replace("month", "месяц")
        if not name.startswith("1 "):
            name = name.replace("месяц", "месяца")
    elif "year" in name:
        name = name.replace("year", "год")
    elif "lifetime" in name:
        name = "навсегда"
    return name.title()

async def notify_user_about_payment(user_id: int, plan: str, amount: float, asset: str):
    if _bot_instance is None:
        logger.error("bot instance")
        return

    try:

        from ..database.premium import set_premium
        if plan == "lifetime":
            await set_premium(user_id, is_lifetime=True)
        elif plan == "1_year":
            await set_premium(user_id, days=365)
        else:
            months = int(plan.split("_")[0])
            await set_premium(user_id, days=months * 30)

        display_name = format_display_name(plan)
        await _bot_instance.send_message(
            user_id,
            f"✅ Premium активирован!\n"
            f"Срок: {'Навсегда' if plan == 'lifetime' else f'{months * 30} дней'}"
        )
    except Exception as e:
        logger.error(f"error by set premium 69 : {e}")

global_bot = None

@router.message(Command("premium"))
async def cmd_premium(message: Message):
    if message.chat.type != "private":
        bot_link = "https://t.me/homyakadventbot?start=premium"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Перейти в бота", url=bot_link)]
        ])
        await message.answer(
            "❌ Эта команда доступна только в личных сообщениях с ботом.",
            reply_markup=keyboard,
            reply_to_message_id=message.message_id
        )
        return

    await show_premium_menu(message)

async def show_premium_menu(message: Message):

    user_id = message.from_user.id
    from ..database.premium import get_premium
    premium_info = await get_premium(user_id)

    if premium_info and premium_info.get("is_lifetime"):
        description = (
            "👑 У вас активен Premium (навсегда)!\n\n"
            "💵 Ваши привилегии:\n"
            "КД 5 часов вместо 7\n"
            "+5% шанс на редкие хомяки\n"
            "+1000 очков за каждого хомяка"
        )
        await message.answer(description, parse_mode="HTML")
        return

    status_text = ""
    if premium_info and premium_info.get("expires_at"):
        from datetime import datetime
        expires_date = datetime.fromisoformat(premium_info["expires_at"]).strftime("%d.%m.%Y")
        status_text = f"👑 Premium активен до {expires_date}!\n\n"

    description = (
        f"{status_text}"
        "🌟 Premium-подписка даёт:\n"
        "КД 12 часов вместо 24\n"
        "+5% шанс на редкие хомяки\n"
        "+1000 очков за каждого хомяка\n\n"
        "Выберите способ оплаты:"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⭐️ Telegram Stars", callback_data=f"pay_stars_{user_id}"),
        InlineKeyboardButton(text="💰 CryptoBot", callback_data=f"pay_cryptobot_{user_id}")
    )
    await message.answer(description, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars(callback_query: CallbackQuery):
    target_user_id = int(callback_query.data.split("_")[-1])
    if callback_query.from_user.id != target_user_id:
        await callback_query.answer("❌ Это не ваши кнопки.", show_alert=True)
        return 
    
    builder = InlineKeyboardBuilder()
    for plan_key in PRICE_PLANS.keys():
        stars = PRICE_PLANS[plan_key]
        display_name = format_display_name(plan_key)
        builder.add(InlineKeyboardButton(
            text=f"📅 {display_name} - {stars} Stars",
            callback_data=f"stars_{plan_key}"
        ))
    builder.adjust(1)
    await callback_query.message.edit_text("🌟 Выберите тариф:", reply_markup=builder.as_markup())
    await callback_query.answer()

@router.callback_query(F.data.startswith("stars_"))
async def stars_plan_selected(callback_query: CallbackQuery):
    plan = "_".join(callback_query.data.split("_")[1:])
    if plan not in PRICE_PLANS:
        await callback_query.answer("❌ Неверный тариф", show_alert=True)
        return
    

    amount = PRICE_PLANS[plan]
    display_name = format_display_name(plan)
    prices = [LabeledPrice(label=f"Premium ({display_name})", amount=amount)]
    await callback_query.message.answer_invoice(
        title="Homyak Premium",
        description=f"Premium на {display_name}",
        payload=f"premium|{plan}|{callback_query.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=prices,
        need_name=False,
        need_email=False,
        need_phone_number=False,
        need_shipping_address=False,
        is_flexible=False,
    )
    await callback_query.answer()

@router.pre_checkout_query()
async def pre_checkout_query(query):
    await query.bot.answer_pre_checkout_query(query.id, ok=True)

@router.message(lambda m: m.successful_payment)
async def on_successful_payment(message: Message):
    payment = message.successful_payment
    user_id = message.from_user.id

    # Обработка премиум подписки
    if "|" in payment.invoice_payload:
        payload_parts = payment.invoice_payload.split("|")
        if len(payload_parts) != 3 or payload_parts[0] != "premium":
            await message.answer("❌ Неизвестный платеж.")
            return

        plan = payload_parts[1]
        buyer_id = int(payload_parts[2])
        if buyer_id != user_id:
            await message.answer("❌ Платёж не ваш.")
            return

        display_name = format_display_name(plan)
        if plan == "lifetime":
            await set_premium(user_id, is_lifetime=True)
        elif plan == "1_year":
            await set_premium(user_id, days=365)
        else:
            months = int(plan.split("_")[0])
            await set_premium(user_id, days=months * 30)

        await message.answer(f"✅ Вам выдан Premium на {display_name}!\nСпасибо за поддержку!")
        
        username = f"@{message.from_user.username}" if message.from_user.username else f"ID {user_id}"
        full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip() or "Без имени"
        text = (
            f"✅ Оплата произведена \n"
            f"Покупатель: {full_name} ({username})\n"
            f"ID: {buyer_id}\n"
            f"Покупка: Premium {display_name}\n"
            f"Стоимость: {payment.total_amount}\n"
            f"ID операции: {payment.telegram_payment_charge_id}"
        )
        try:
            await message.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, message_thread_id=5029)
        except Exception as e:
            logger.error(f"cant send log 194 premium: {e}")
        return

    # Обработка платежей магазина
    payload = payment.invoice_payload

    if payload.startswith("topup:"):
        # Пополнение монет
        amount = int(payload.split(":", 1)[1])
        await add_money(user_id, amount)
        await message.answer(f"✅ Успешно начислено {amount} монет!")
        
        username = f"@{message.from_user.username}" if message.from_user.username else f"ID {user_id}"
        text = (
            f"💰 Покупка монет\n"
            f"Покупатель: {username}\n"
            f"Количество: {amount} монет\n"
            f"ID операции: {payment.telegram_payment_charge_id}"
        )
        await message.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, message_thread_id=5029)
        return

    if payload.startswith("boost:"):
        # Покупка бустера
        boost_type = payload.split(":", 1)[1]
        await add_elixir(user_id, boost_type)
        name = "удачи" if boost_type == "luck" else "ускорения времени"
        await message.answer(f"✅ Бустер {name} успешно добавлен в инвентарь!")

        username = f"@{message.from_user.username}" if message.from_user.username else f"ID {user_id}"
        text = (
            f"🎲 Покупка бустера\n"
            f"Покупатель: {username}\n"
            f"Тип: {name}\n"
            f"ID операции: {payment.telegram_payment_charge_id}"
        )
        await message.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, message_thread_id=5029)
        return

    if payload.startswith("cardbuy:"):
        item_id = int(payload.split(":", 1)[1])
        item = await get_item(item_id)
        if not item:
            await message.answer("❌ Товар не найден.")
            return

        user_id = message.from_user.id

        if await has_bought(user_id, item_id):
            try:
                await message.bot(
                    RefundStarPayment(
                        user_id=user_id,
                        telegram_payment_charge_id=payment.telegram_payment_charge_id
                    )
                )
                await message.answer(f"❌ У вас уже есть хомяк «{item['name']}».\n⭐ Звёзды возвращены, хомяк и награды за него не были выданы.")
            except Exception as e:
                await message.answer(f"⚠ Ошибка возврата звёзд: {e}")
            return

        ok = await reduce_stock(item_id)
        if not ok:
            await message.answer("❌ Этот хомяк закончился.")
            return

        await add_card(user_id, item["filename"])
        original_rarity = await get_rarity(item["filename"])
        points = RARITY_POINTS[original_rarity]

        if await is_premium_active(user_id):
            points += 1000

        bonus_info = await get_bonus(user_id)
        if bonus_info and bonus_info.get("is_active"):
            points += 700 if (bonus_info.get("is_premium_at_activation") or await is_premium_active(user_id)) else 500

        await add_score(user_id, points, item["name"], chat_id=message.chat.id)
        await record_purchase(user_id, item_id, item["filename"])
        total_score, _ = await get_score(user_id)

        caption = (
            f"✅ Вы купили карточку «{item['name']}» за звёзды!\n\n"
            f"💎 Редкость • {RARITY_NAMES[original_rarity]}\n"
            f"✨ Очки • +{points:,} [{total_score:,}]\n"
            f"🔁 Если карточка уже была, добавлены только очки."
        )
        file_path = Path(HOMYAK_FILES_DIR) / item["filename"]
        await message.answer_photo(photo=FSInputFile(file_path), caption=caption)

        username = f"@{message.from_user.username}" if message.from_user.username else f"ID {user_id}"
        text = (
            f"🐹 Покупка хомяка за ⭐️\n"
            f"Покупатель: {username}\n"
            f"Хомяк: {item['name']}\n"
            f"ID операции: {payment.telegram_payment_charge_id}"
        )
        await message.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, message_thread_id=5029)
        return

    await message.answer("❌ Неизвестный платеж.")

@router.callback_query(F.data.startswith("pay_cryptobot_"))
async def pay_cryptobot_menu(callback_query: CallbackQuery):
    target_user_id = int(callback_query.data.split("_")[-1])
    if callback_query.from_user.id != target_user_id:
        await callback_query.answer("❌ Это не ваши кнопки.", show_alert=True)
        return 

    builder = InlineKeyboardBuilder()
    CRYPTO_PRICES = {"1_month": 0.2, "3_months": 0.4, "6_months": 0.6, "1_year": 1.1, "lifetime": 2.5}
    for plan_key in CRYPTO_PRICES.keys():
        usdt = CRYPTO_PRICES[plan_key]
        display_name = format_display_name(plan_key)
        builder.add(InlineKeyboardButton(
            text=f"📅 {display_name} - {usdt} USDT",
            callback_data=f"crypto_{plan_key}"
        ))
    builder.adjust(1)
    await callback_query.message.edit_text("💰 Выберите премиум для оплаты в USDT:", reply_markup=builder.as_markup())
    await callback_query.answer()

@router.callback_query(F.data.startswith("crypto_"))
async def crypto_plan_selected(callback_query: CallbackQuery):
    if not CRYPTO_BOT_TOKEN:
        await callback_query.answer("cb non work", show_alert=True)
        return

    plan = callback_query.data[7:]
    CRYPTO_PRICES = {"1_month": 0.2, "3_months": 0.4, "6_months": 0.6, "1_year": 1.1, "lifetime": 2.5}
    if plan not in CRYPTO_PRICES:
        await callback_query.answer("❌ Неверный выбор", show_alert=True)
        return

    try:
        service = crypto_service.service
        if service is None:
            raise ValueError("кб нон ворк")
        
        invoice = await service.create_invoice(plan, callback_query.from_user.id)
        
        display_name = format_display_name(plan)
        amount = CRYPTO_PRICES[plan]
        
        caption = (
            f"🛒 <b>Покупка Premium: {display_name}</b>\n\n"
            f"💰 <b>Стоимость:</b> {amount} USDT\n"
            f"💳 <b>Способ оплаты:</b> CryptoBot \n\n"
            f"Нажмите кнопку ниже, чтобы перейти к оплате!"
        )
        
        pay_button = InlineKeyboardButton(
            text="💵 Оплатить",
            url=invoice.bot_invoice_url
        )
        check_button = InlineKeyboardButton(
            text="🔍 Проверить оплату",
            callback_data=f"check_crypto_{invoice.invoice_id}_{callback_query.from_user.id}_{plan}"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[pay_button], [check_button]])
        
        await callback_query.message.answer(
            caption,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"cb ошибка 261 premium: {e}")
        await callback_query.message.answer("❌ Ошибка создания оплаты.")

@router.callback_query(F.data.startswith("check_crypto_"))
async def check_crypto_payment(callback_query: CallbackQuery):
    parts = callback_query.data.split("_")
    if len(parts) < 5:
        await callback_query.answer("❌ Неверные данные.", show_alert=True)
        return
        
    invoice_id = parts[2]
    try:
        user_id = int(parts[3])
        plan = parts[4]
    except (ValueError, IndexError):
        await callback_query.answer("❌ Ошибка данных.", show_alert=True)
        return

    try:
        service = crypto_service.service
        if service is None:
            await callback_query.answer("❌ Оплата временно недоступна.", show_alert=True)
            return

        invoice_info = await service.crypto_pay.get_invoice(invoice_id)
        
        if invoice_info.status == InvoiceStatus.PAID:
            from ..database.premium import set_premium
            if plan == "lifetime":
                await set_premium(user_id, is_lifetime=True)
            elif plan == "1_year":
                await set_premium(user_id, days=365)
            else:
                months = int(plan.split("_")[0])
                await set_premium(user_id, days=months * 30)
            
            user = await callback_query.bot.get_chat(user_id)
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Без имени"
            username = f"@{user.username}" if user.username else "нет"
            display_name = format_display_name(plan)
            CRYPTO_PRICES = {"1_month": 0.2, "3_months": 0.4, "6_months": 2.0, "1_year": 1.1, "lifetime": 2.5}
            amount = CRYPTO_PRICES.get(plan, 0)

            oplata = (
                f"✅ Оплата по CryptoBot\n\n"
                f"👤 Покупатель: {full_name} ({username})\n"
                f"🆔 ID: {user_id}\n"
                f"📅 Тариф: {display_name}\n"
                f"💰 Сумма: {amount} USDT\n"
                f"🧾 Инвойс ID: {invoice_id}"
            )
            await callback_query.bot.send_message(ADMIN_CHAT_ID, oplata, parse_mode="HTML", message_thread_id=5029)
            
            await callback_query.message.edit_text(f"✅ Спасибо за покупку!\nВаш Premium активирован на {display_name} месяц")
        else:
            await callback_query.answer(
                "⏳ Оплата не найдена. Попробуйте через 10 секунд.",
                show_alert=True
            )
            
    except Exception as e:
        logger.error(f"Error checking payment 322 premium.py :{e}")
        await callback_query.answer("❌ Ошибка проверки оплаты.", show_alert=True)

async def is_premium_active(user_id: int) -> bool:
    premium = await get_premium(user_id)
    if not premium:
        return False
    if premium["is_lifetime"]:
        return True
    if premium["expires_at"]:
        from datetime import datetime
        return datetime.fromisoformat(premium["expires_at"]) > datetime.now()
    return False