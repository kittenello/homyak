from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
from aiogram.methods import RefundStarPayment

from datetime import datetime, timedelta
from ..database.premium import remove_premium
from ..database.admins import is_admin, is_owner, add_admin, remove_admin
from ..database.cooldowns import get_last_used, set_infinite_mode
from ..database.premium import get_premium, set_premium
from ..database.rarity import get_rarity_stats
from ..database.money import set_money
from ..config import SETTINGS, HOMYAK_FILES_DIR

router = Router()

GLOBAL_COOLDOWN_MINUTES = 1440

refunded_tx: set[str] = set()

def parse_user_id(text: str) -> int | None:
    """Извлекает user_id из строки: либо число, либо @username"""
    text = text.strip()
    if text.isdigit():
        return int(text)
    if text.startswith('@'):
        return None
    return None

@router.message(Command("makeadmin"))
async def cmd_makeadmin(message: Message):
    if not await is_owner(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /makeadmin [user_id]")
        return

    user_id = parse_user_id(args[1])
    if user_id is None:
        await message.answer("❌ Неверный ID. Поддерживаются только числовые ID.")
        return

    await add_admin(user_id)
    await message.answer(f"✅ Пользователь {user_id} теперь админ!")

@router.message(Command('refund'))
async def cmd_refund(message: Message):
    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:
        return await message.answer('❌ Использование: /refund <transaction_id>')

    tx_id = parts[1].strip()
    user_id = message.from_user.id

    if tx_id in refunded_tx:
        return await message.answer('🔄 Возврат по этому платежу уже был выполнён.')

    try:
        success: bool = await message.bot(
            RefundStarPayment(
                user_id=user_id,
                telegram_payment_charge_id=tx_id
            )
        )
    except Exception as e:
        if 'CHARGE_ALREADY_REFUNDED' in str(e):
            refunded_tx.add(tx_id)
            return await message.answer('🔄 Возврат по этому платежу уже был выполнён.')
        return await message.answer(f'❌ Ошибка возврата: {e}')

    if success:
        refunded_tx.add(tx_id)
        await message.answer(f'⭐️ Возврат успешен для транзакции {tx_id}!')
    else:
        await message.answer(f'❌ Не удалось вернуть средства по транзакции {tx_id}')

@router.message(Command("setcoins"))
async def cmd_setcoins(message: Message, command: CommandObject):
    if not await is_admin(message.from_user.id):
        return
        
    if not command.args:
        await message.answer("❌ Использование: /setcoins [user_id] [количество]")
        return
        
    try:
        user_id, amount = map(int, command.args.split())
        await set_money(user_id, amount)
        await message.answer(f"✅ Установлено {amount} монет для пользователя {user_id}")
    except ValueError:
        await message.answer("❌ Неверный формат. Использование: /setcoins [user_id] [количество]")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("resetcoins"))
async def cmd_resetcoins(message: Message, command: CommandObject):
    if not await is_admin(message.from_user.id):
        return
        
    if not command.args:
        await message.answer("❌ Использование: /resetcoins [user_id]")
        return
        
    try:
        user_id = int(command.args)
        await set_money(user_id, 0)
        await message.answer(f"✅ Поставил 0 монет человеку с ID {user_id}")
    except ValueError:
        await message.answer("❌ Неверный формат. Использование: /resetcoins [user_id]")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("panel"))
async def cmd_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return

    text = (
        "🛡️ <b>Админ-панель</b>\n\n"
        "• /makeadmin [id] — выдать админку (только главный)\n"
        "• /unadmin [id] — снять админку\n"
        "• /rkd [id] — убрать КД\n"
        "• /gtime [id] — время последнего открытия\n"
        "• /ttime [id] — сколько осталось до КД\n"
        "• /gkd [мин] — установить глобальный КД\n"
        "• /gad — бесконечный режим (для себя)\n"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("unadmin"))
async def cmd_unadmin(message: Message):
    if not await is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /unadmin [user_id]")
        return

    user_id = parse_user_id(args[1])
    if user_id is None:
        await message.answer("❌ Неверный ID.")
        return

    success = await remove_admin(user_id, message.from_user.id)
    if success:
        await message.answer(f"✅ Админка у {user_id} снята.")

@router.message(Command("rkd"))
async def cmd_rkd(message: Message):
    if not await is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /rkd [id]")
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return

    from ..database.cooldowns import reset_cooldown
    await reset_cooldown(user_id)

    await message.answer(f"✅ КД сброшен для {user_id}")

@router.message(Command("gtime"))
async def cmd_gtime(message: Message):
    if not await is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /gtime [user_id]")
        return

    user_id = parse_user_id(args[1])
    if user_id is None:
        await message.answer("❌ Неверный ID.")
        return

    last_used = await get_last_used(user_id)
    if last_used:
        await message.answer(f"🕒 Последнее открытие: {last_used.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        await message.answer("🕒 Пользователь ещё не открывал хомяка.")

@router.message(Command("ttime"))
async def cmd_ttime(message: Message):
    if not await is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /ttime [user_id]")
        return

    user_id = parse_user_id(args[1])
    if user_id is None:
        await message.answer("❌ Неверный ID.")
        return

    last_used = await get_last_used(user_id)
    if not last_used:
        await message.answer("🕒 Пользователь ещё не открывал хомяка.")
        return

    cooldown_end = last_used + timedelta(minutes=GLOBAL_COOLDOWN_MINUTES)
    now = datetime.now()
    if now >= cooldown_end:
        await message.answer("✅ КД уже прошёл!")
    else:
        remaining = cooldown_end - now
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes = remainder // 60
        await message.answer(f"⏳ Осталось: {hours}ч {minutes}мин")

router.message(Command("gkd"))
async def cmd_gkd(message: Message):
    if not await is_owner(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("test")
        return

    try:
        value = int(args[1])
    except ValueError:
        await message.answer("❌ Введите число")
        return

    if value == 0:
        from ..database.cooldowns import reset_all_cooldowns
        await reset_all_cooldowns()
        SETTINGS["GLOBAL_COOLDOWN_MINUTES"] = 0
        await message.answer("on")
    elif value == 1:
        SETTINGS["GLOBAL_COOLDOWN_MINUTES"] = 1440
        await message.answer("24")
    else:
        if value < 0:
            await message.answer("nowork")
            return
        SETTINGS["GLOBAL_COOLDOWN_MINUTES"] = value
        await message.answer(f"{value}")

@router.message(Command("gad"))
async def cmd_gad(message: Message):
    if not await is_admin(message.from_user.id):
        return

    await set_infinite_mode(message.from_user.id, True)
    await message.answer("✅ Вам выдан бесконечный режим (КД снят).")

@router.message(Command("ungad"))
async def cmd_ungad(message: Message):
    if not await is_admin(message.from_user.id):
        return

    from ..database.cooldowns import set_infinite_mode
    await set_infinite_mode(message.from_user.id, False)
    await message.answer("✅ Бесконечный режим отключён. КД снова активен.")

@router.message(Command("givepremium"))
async def cmd_admin_premium(message: Message):
    if not await is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer(
            "❌ Использование:\n"
            "/givepremium [user_id/@username] [месяцы/lifetime/лт/lt]"
        )
        return

    target = args[1]
    period = args[2].lower()

    user_id = None
    if target.startswith('@'):
        await message.answer("по айди пока не")
        return
    else:
        try:
            user_id = int(target)
        except ValueError:
            await message.answer("❌ Неверный ID.")
            return

    is_lifetime = False
    days = 0

    if period in ["lifetime", "лайфтайм", "лт", "lt"]:
        is_lifetime = True
    else:
        try:
            months = int(period)
            days = months * 30
        except ValueError:
            await message.answer("❌ Неверный период. Используйте число или 'lifetime/лт/lt'.")
            return


    await set_premium(user_id, days=days, is_lifetime=is_lifetime)
    
    try:
        user = await message.bot.get_chat(user_id)
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Без имени"
        username = f"@{user.username}" if user.username else "нет"
    except:
        full_name = "Неизвестный"
        username = "нет"

    if is_lifetime:
        await message.answer(f"✅ Premium (навсегда) выдан:\n{full_name} ({username}) | ID: {user_id}")
    else:
        await message.answer(f"✅ Premium на {days//30} мес. выдан:\n{full_name} ({username}) | ID: {user_id}")

@router.message(Command("unpremium"))
async def cmd_unpremium(message: Message):
    if not await is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /unpremium [user_id/@username]")
        return

    target = args[1]
    if target.startswith('@'):
        await message.answer("пока не работает по тегу")
        return

    try:
        user_id = int(target)
    except ValueError:
        await message.answer("❌ Неверный ID.")
        return

    premium_info = await get_premium(user_id)
    if not premium_info:
        await message.answer("⚠️ У пользователя нет Premium.")
        return

    try:
        user = await message.bot.get_chat(user_id)
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Без имени"
        username = f"@{user.username}" if user.username else "нет"
    except:
        full_name = "Неизвестный"
        username = "нет"

    if premium_info["is_lifetime"]:
        status_text = "Premium (навсегда)"
    elif premium_info["expires_at"]:
        from datetime import datetime
        expires_date = datetime.fromisoformat(premium_info["expires_at"]).strftime("%d.%m.%Y")
        status_text = f"Premium до {expires_date}"
    else:
        status_text = "временный Premium"

    from ..database.premium import init_db
    db_path = str(init_db.__globals__["PREMIUM_DB_PATH"])
    async with __import__("aiosqlite").connect(db_path) as db:
        await db.execute("DELETE FROM premium WHERE user_id = ?", (user_id,))
        await db.commit()

    await message.answer(
        f"✅ Premium снят:\n"
        f"{full_name} ({username}) | ID: {user_id}\n"
        f"Был: {status_text}"
    )
    await remove_premium(user_id)

@router.message(Command("hstats"))
async def cmd_hstats(message: Message):
    if not await is_admin(message.from_user.id):
        return

    all_cards = [
        f for f in HOMYAK_FILES_DIR.glob("*.png")
        if f.name.lower() != "welcome.mp4"
    ]
    total = len(all_cards)

    if total == 0:
        await message.answer("📭 Нет хомяков в базе.")
        return

    stats = await get_rarity_stats()

    rarity_names = {
        1: "Обычная",
        2: "Редкая",
        3: "Мифическая",
        4: "Легендарная",
        5: "Секретный"
    }

    stats_text = "\n".join(
        f"• {rarity_names[rarity]}: {count}"
        for rarity, count in sorted(stats.items())
    )

    await message.answer(
        f"📊 <b>Статистика хомяков</b>\n\n"
        f"Всего карточек: {total}\n"
        f"{stats_text}",
        parse_mode="HTML"
    )