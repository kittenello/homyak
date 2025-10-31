from aiogram import Router, F
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, LabeledPrice
from aiogram.methods import CreateInvoiceLink
from pathlib import Path
from ..config import SETTINGS
from ..database.money import get_money, add_money
from ..database.shoph import list_items, get_item
from ..database.cards import add_card
from ..database.elixir import add_elixir
from aiogram.filters import Command
from ..database.shoph import list_items, get_item, reduce_stock
from ..database.shopbuyers import has_bought, record_purchase
from ..database.rarity import get_rarity, RARITY_POINTS, RARITY_NAMES
from ..database.premium import is_premium_active
from ..database.bonus import get_bonus
from ..database.scores import add_score, get_score
from ..database.bundles import list_bundles, get_bundle, reduce_bundle_stock

router = Router()

COINS_TO_STARS = {
        50: 7,
        100: 13,
        200: 25,
        300: 44,
        400: 55,
        500: 71,
        800: 114,
        1000: 142,
        1500: 214,
        2000: 285,
    }

HOMYAK_FILES_DIR = Path(__file__).parent.parent / "files"
def make_main_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="• Монеты •", callback_data="shop:coins"),
            InlineKeyboardButton(text="• Бустеры •", callback_data="shop:boosters")
        ],
        [InlineKeyboardButton(text="• Наборы •", callback_data="shop:bundles"),
        InlineKeyboardButton(text="• Хомяки •", callback_data="shop:cards")],
    ])
    return kb

@router.message(Command(commands=["shop"]))
async def shop_command(message: Message):
    if message.chat.type != "private":
        bot_link = "https://t.me/homyakadventbot?start=shop"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Перейти в бота", url=bot_link)]
        ])
        await message.answer(
            "❌ Эта команда работает только в личных сообщениях с ботом.",
            reply_markup=keyboard,
            reply_to_message_id=message.message_id
        )
        return
    await show_shop_menu(message)

async def show_shop_menu(message: Message):
    await message.answer("🏪 Вы попали в <b>магазин</b>!\n\n⛄ В магазине можно приоберсти: бустеры, хомяков и монеты.\n\n⭐ Оплата происходит исключительно через валюту Telegram Stars и внутренюю валюту бота - Монеты.", reply_markup=make_main_keyboard())

@router.callback_query(F.data.startswith("shop:"))
async def shop_callbacks(query: CallbackQuery):
    data = query.data
    if data == "shop:coins":
        amounts = list(COINS_TO_STARS.items())
        rows = []
        for i in range(0, len(amounts), 3):
            row = []
            for coins, stars in amounts[i:i+3]:
                row.append(
                    InlineKeyboardButton(
                        text=f"💰 {coins} — {stars} ⭐",
                        callback_data=f"shop:buycoins:{coins}"
                    )
                )
            rows.append(row)
        rows.append([InlineKeyboardButton(text="‹ Назад", callback_data="shop:main")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await query.message.edit_text("💰<b>Монеты</b>\n<blockquote>Приобрести их можно ТОЛЬКО за звезды</blockquote>", reply_markup=kb, parse_mode="HTML")
        await query.answer()
        return

    if data == "shop:boosters":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🍀 Удача — 40 монет", callback_data="shop:boost:luck")],
            [InlineKeyboardButton(text="⏳ Ускоритель времени — 30 монет", callback_data="shop:boost:time")],
            [InlineKeyboardButton(text="‹ Назад", callback_data="shop:main")]
        ])
        await query.message.edit_text("⚡️<b>Бустеры</b>\n\nВ данном разделе вы можете приобрести разные бустеры, на удачу или ускорение времени", reply_markup=kb, parse_mode="HTML")
        await query.answer()
        return

    if data == "shop:cards":
        items = await list_items()
        if not items:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="‹ Назад", callback_data="shop:main")]])
            await query.message.answer("😭 Не удача!\n\nПока что в данный момент хомяков в магазине нет, возможно они появятся в будущем", reply_markup=kb, parse_mode="HTML")
            await query.answer()
            return
        rows = []
        for it in items:
            stock_text = "∞" if it["stock"] == 0 else str(it["stock"])
            rows.append([InlineKeyboardButton(text=f"{it['name']} • {it['price_coins']} монет / {it['price_stars']} ⭐ • {stock_text}", callback_data=f"shop:card:{it['id']}")])
        rows.append([InlineKeyboardButton(text="‹ Назад", callback_data="shop:main")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await query.message.answer("😎 <b>Хомяки</b>\n\n🤔 В данном раделе вы можете купить исключительно хомяков с редкостью «Секретный», других к сожалению пока запрещено покупать.", reply_markup=kb, parse_mode="HTML")
        await query.answer()
        return

    if data == "shop:main":
        await query.message.edit_text("🏪 Вы попали в магазин!\n\n⛄ В магазине можно приоберсти: бустеры, хомяков и монеты.\n\n⭐ Оплата происходит исключительно через валюту Telegram Stars и внутренюю валюту бота - Монеты.", parse_mode="HTML", reply_markup=make_main_keyboard())
        await query.answer()
        return

    if data.startswith("shop:buycoins:"):
            coins = int(data.split(":", 2)[2])
            stars_price = COINS_TO_STARS.get(coins)
            if stars_price is None:
                await query.answer("Неверная сумма", show_alert=True)
                return
            try:
                link = await query.bot.create_invoice_link(
                    title=f"Пополнение монет: {coins}",
                    description=f"Покупка {coins} монет",
                    payload=f"topup:{coins}",
                    provider_token="",
                    currency="XTR",
                    prices=[LabeledPrice(label=f"{coins} монет", amount=stars_price)]
                )

                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"Купить {coins} монет за {stars_price} ⭐", url=link)],
                    [InlineKeyboardButton(text="‹ Назад", callback_data="shop:coins")]
                ])
                await query.message.edit_text(f"💸 Покупка {coins} монет — цена {stars_price} ⭐", reply_markup=kb)
                await query.answer()
                return
            except Exception as e:
                print(f"Error creating invoice link: {e}")
                await query.answer("привет это ошибка попробуй заново или напиши @ceotraphouse и опиши ситуацию", show_alert=True)
                return

    if data.startswith("shop:buycoins_fallback:"):
        amount = int(data.split(":",2)[2])
        provider = SETTINGS.get("STARS_PROVIDER_TOKEN")
        currency = SETTINGS.get("STARS_CURRENCY", "RUB")
        title = f"Пополнение монет: {amount}"
        description = f"Покупка {amount} монет"
        price_value = amount * 100
        prices = [LabeledPrice(label=f"{amount} монет", amount=price_value)]
        try:
            link = await CreateInvoiceLink(title=title, description=description, payload=f"topup:{amount}", provider_token=provider, currency=currency, prices=prices).send(query.bot)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить", url=link.url)],
                [InlineKeyboardButton(text="‹ Назад", callback_data="shop:coins")]
            ])
            await query.message.edit_text("привет это ошибка попробуй заново или напиши @ceotraphouse и опиши ситуацию", reply_markup=kb)
            await query.answer()
            return
        except Exception:
            await query.answer("привет это ошибка попробуй заново или напиши @ceotraphouse и опиши ситуацию", show_alert=True)
            return

    if data.startswith("shop:boost:"):
        typ = data.split(":",2)[2]
        price_coins = 100 if typ == "luck" else 70
        price_stars = 9 if typ == "luck" else 8

        text = ("🍀 Бустер «удача»\nУвеличивает вероятность выпадения редких карт на 35%\n"
               f"💰 Цена • {price_coins} монет или {price_stars} ⭐\n"
               "⌚️ Время действия • однократное использование"
               if typ == "luck" else
               "⚡️ Бустер «Сокращение времени»\nСокращает время ожидания получения карточки на 1 час\n"
               f"💰 Цена • {price_coins} монет или {price_stars} ⭐\n"
               "⌚️ Время действия • однократное использование")

        try:
            link = await query.bot.create_invoice_link(
                title=f"Бустер {typ}",
                description=f"Покупка бустера {typ}",
                payload=f"boost:{typ}",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label=f"Бустер {typ}", amount=price_stars)]
            )

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"Купить за монеты ({price_coins})", callback_data=f"shop:buy_boost_coins:{typ}")],
                [InlineKeyboardButton(text=f"Купить за {price_stars} ⭐", url=link)],
                [InlineKeyboardButton(text="‹ Назад", callback_data="shop:boosters")]
            ])

            await query.message.edit_text(text, reply_markup=kb)
            await query.answer()
            return
        except Exception as e:
            print(f"Error creating invoice link: {e}")
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"Купить за монеты ({price_coins})", callback_data=f"shop:buy_boost_coins:{typ}")],
                [InlineKeyboardButton(text="‹ Назад", callback_data="shop:boosters")]
            ])
            await query.message.edit_text(text, reply_markup=kb)
            await query.answer("привет это ошибка попробуй заново или напиши @ceotraphouse и опиши ситуацию", show_alert=True)
            return

    if data.startswith("shop:buy_boost_stars_fallback:"):
        typ = data.split(":",2)[2]
        price_stars = 8 if typ=="luck" else 7
        provider = SETTINGS.get("STARS_PROVIDER_TOKEN")
        currency = SETTINGS.get("STARS_CURRENCY", "RUB")
        title = f"Бустер {typ}"
        description = f"Покупка бустера {typ}"
        price_value = price_stars * 100
        prices = [LabeledPrice(label=f"{price_stars} ⭐", amount=price_value)]
        try:
            link = await CreateInvoiceLink(title=title, description=description, payload=f"boost:{typ}", provider_token=provider, currency=currency, prices=prices).send(query.bot)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить", url=link.url)],
                [InlineKeyboardButton(text="‹ Назад", callback_data="shop:boosters")]
            ])
            await query.message.edit_text("привет это ошибка попробуй заново или напиши @ceotraphouse и опиши ситуацию", reply_markup=kb)
            await query.answer()
            return
        except Exception:
            await query.answer("привет это ошибка попробуй заново или напиши @ceotraphouse и опиши ситуацию", show_alert=True)
            return

    if data.startswith("shop:buy_boost_coins:"):
        typ = data.split(":",3)[2]
        price = 100 if typ =="luck" else 70
        user_id = query.from_user.id
        bal = await get_money(user_id)
        if bal < price:
            await query.answer("❌ У вас недостаточно монет", show_alert=True)
            return
        await add_money(user_id, -price)
        await add_elixir(user_id, typ)
        booster_name = "«удача»" if typ == "luck" else "«ускоритель времени»"
        await query.message.edit_text(f"✅ Вы успешно купили бустер {booster_name}.\n\n🎒 Он добавлен в ваш инвентарь используйте /inventory или посмотрите в /profile.")
        await query.answer()
        return

    if data.startswith("shop:buy_boost_stars:"):
        typ = data.split(":",3)[2]
        price_stars = 9 if typ=="luck" else 8
        provider = SETTINGS.get("STARS_PROVIDER_TOKEN")
        currency = SETTINGS.get("STARS_CURRENCY", "RUB")
        title = f"Бустер {typ}"
        description = f"Покупка бустера {typ}"
        price_value = price_stars * 100
        prices = [LabeledPrice(label=f"{price_stars} ⭐", amount=price_value)]
        try:
            link = await CreateInvoiceLink(title=title, description=description, payload=f"boost:{typ}", provider_token=provider, currency=currency, prices=prices).send(query.bot)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить", url=link.url)],
                [InlineKeyboardButton(text="‹ Назад", callback_data="shop:boosters")]
            ])
            await query.message.edit_text("привет это ошибка попробуй заново или напиши @ceotraphouse и опиши ситуацию", reply_markup=kb)
            await query.answer()
            return
        except Exception:
            await query.answer("привет это ошибка попробуй заново или напиши @ceotraphouse и опиши ситуацию", show_alert=True)
            return

    if data.startswith("shop:card:"):
        item_id = int(data.split(":", 2)[2])
        item = await get_item(item_id)
        if not item:
            await query.answer("❌ Товар не найден", show_alert=True)
            return

        file_path = Path(HOMYAK_FILES_DIR) / item["filename"]
        if not file_path.exists():
            await query.answer("❌ Товар не найден (accuraced)", show_alert=True)
            return

        original_rarity = await get_rarity(item["filename"])
        display_rarity = original_rarity
        is_prem = await is_premium_active(query.from_user.id)
        points = RARITY_POINTS[display_rarity]
        if is_prem:
            points += 1000
        bonus_info = await get_bonus(query.from_user.id)
        if bonus_info and bonus_info.get("is_active"):
            points += 700 if (bonus_info.get("is_premium_at_activation") or is_prem) else 500
        total_score, _ = await get_score(query.from_user.id)

        caption_lines = [
            f"Хомяк «{item['name']}»",
            "",
            f"💎 Редкость • {RARITY_NAMES[display_rarity]}",
            f"✨ Очки при покупке • +{points:,} [{total_score:,}]",
            f"💰 Цена • {item['price_coins']} монет или {item['price_stars']} ⭐",
            f"📦 В наличии: {'неограниченно' if item['stock'] == 0 else item['stock']}"
        ]
        caption = "\n".join(caption_lines)

        try:
            link = await query.bot.create_invoice_link(
                title=f"Хомяк {item['name']}",
                description=f"Покупка хомяка {item['name']}",
                payload=f"cardbuy:{item_id}",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label=f"Хомяк {item['name']}", amount=item["price_stars"])]
            )
            stars_btn = InlineKeyboardButton(text=f"Купить за {item['price_stars']} ⭐", url=link)
        except Exception as e:
            print(f"error creating invoice link: {e}")
            stars_btn = InlineKeyboardButton(text=f"Купить за {item['price_stars']} ⭐", callback_data=f"shop:buy_card_stars_fallback:{item_id}")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Купить за монеты ({item['price_coins']})", callback_data=f"shop:buy_card_coins:{item_id}")],
            [stars_btn],
            [InlineKeyboardButton(text="‹ Назад", callback_data="shop:cards")]
        ])

        await query.message.answer_photo(photo=FSInputFile(file_path), caption=caption, reply_markup=kb)
        await query.answer()
        return

    if data.startswith("shop:buy_card_coins:"):
        item_id = int(data.split(":",2)[2])
        item = await get_item(item_id)
        if not item:
            await query.answer("❌ Товар не найден", show_alert=True)
            return
        user_id = query.from_user.id

        if await has_bought(user_id, item_id):
            await query.answer("❌ Повторная покупка хомяка запрещена, вы уже покупали его.", show_alert=True)
            return
        bal = await get_money(user_id)
        if bal < item["price_coins"]:
            await query.answer("❌ У вас недостаточно монет", show_alert=True)
            return

        ok = await reduce_stock(item_id)
        if not ok:
            await query.answer("❌ Товар закончился", show_alert=True)
            return

        await add_money(user_id, -item["price_coins"])
        await add_card(user_id, item["filename"])
        original_rarity = await get_rarity(item["filename"])
        points = RARITY_POINTS[original_rarity]
        if await is_premium_active(user_id):
            points += 1000
        bonus_info = await get_bonus(user_id)
        if bonus_info and bonus_info["is_active"]:
            points += 700 if (bonus_info["is_premium_at_activation"] or await is_premium_active(user_id)) else 500
        await add_score(user_id, points, item["name"], chat_id=query.message.chat.id)
        await record_purchase(user_id, item_id, item["filename"])
        total_score, _ = await get_score(user_id)
        caption = (
            f"Вы купили в магазине карточку «{item['name']}»!\n\n"
            f"💎 Редкость • {RARITY_NAMES[original_rarity]}\n"
            f"✨ Очки • +{points:,} [{total_score:,}]\n"
            f"🔁 Если карточка у вас уже была, добавлены только очки."
        )
        file_path = Path(HOMYAK_FILES_DIR) / item["filename"]
        await query.message.answer_photo(photo=FSInputFile(file_path), caption=caption)
        await query.answer()
        return

    if data.startswith("shop:buy_card_stars:"):
        item_id = int(data.split(":",2)[2])
        item = await get_item(item_id)
        if not item:
            await query.answer("Товар не найден", show_alert=True)
            return
        provider = SETTINGS.get("STARS_PROVIDER_TOKEN")
        currency = SETTINGS.get("STARS_CURRENCY", "RUB")
        title = f"Хомяк {item['name']}"
        description = f"Покупка хомяка {item['name']}"
        price_value = item["price_stars"] * 100
        prices = [LabeledPrice(label=f"{item['price_stars']} ⭐", amount=price_value)]
        try:
            link = await CreateInvoiceLink(title=title, description=description, payload=f"cardbuy:{item_id}", provider_token=provider, currency=currency, prices=prices).send(query.bot)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить", url=link.url)],
                [InlineKeyboardButton(text="‹ Назад", callback_data=f"shop:card:{item_id}")]
            ])
            await query.message.edit_text("привет это ошибка попробуй заново или напиши @ceotraphouse и опиши ситуацию", reply_markup=kb)
            await query.answer()
            return
        except Exception:
            await query.answer("привет это ошибка попробуй заново или напиши @ceotraphouse и опиши ситуацию", show_alert=True)
            return
        
    if data == "shop:bundles":
        bundles = await list_bundles()
        if not bundles:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="‹ Назад", callback_data="shop:main")]
            ])
            await query.message.edit_text(
                "📦 <b>Наборы</b>\n\nПока наборов нет. Загляните позже!",
                reply_markup=kb, parse_mode="HTML"
            )
            await query.answer()
            return

        rows = []
        for b in bundles:
            stock_text = "∞" if b["stock"] == 0 else str(b["stock"])
            rows.append([
                InlineKeyboardButton(
                    text=f"{b['name']} • {b['price_coins']} монет / {b['price_stars']} ⭐ • {stock_text}",
                    callback_data=f"shop:bundle:{b['id']}"
                )
            ])
        rows.append([InlineKeyboardButton(text="‹ Назад", callback_data="shop:main")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await query.message.edit_text(
            "📦 <b>Наборы</b>\n\nКомплекты из 2–3+ хомяков. Выгоднее, чем брать по одному.",
            reply_markup=kb, parse_mode="HTML"
        )
        await query.answer()
        return

    # --- НАБОРЫ: карточка набора ---
    if data.startswith("shop:bundle:"):
        bundle_id = int(data.split(":", 2)[2])
        bundle = await get_bundle(bundle_id)
        if not bundle:
            await query.answer("❌ Набор не найден", show_alert=True)
            return

        # bundle = { id, name, price_coins, price_stars, stock, filenames: [str,...] }
        filenames = bundle.get("filenames", [])
        count = len(filenames)

        # считаем итоговые очки (как сумма по картам с бонусами/премиумом)
        user_id = query.from_user.id
        is_prem = await is_premium_active(user_id)
        bonus_info = await get_bonus(user_id)
        total_score_now, _ = await get_score(user_id)

        points_sum = 0
        for fn in filenames:
            r = await get_rarity(fn)
            pts = RARITY_POINTS[r]
            if is_prem:
                pts += 1000
            if bonus_info and bonus_info.get("is_active"):
                pts += 700 if (bonus_info.get("is_premium_at_activation") or is_prem) else 500
            points_sum += pts

        names_list = []
        for fn in filenames:
            names_list.append(Path(fn).stem)

        caption_lines = [
            f"📦 Набор «{bundle['name']}»",
            "",
            f"👥 В наборе • {count} хомяка(ов)",
            "— " + "\n— ".join(names_list) if names_list else "",
            "",
            f"✨ Очки при покупке • +{points_sum:,} [{total_score_now:,}]",
            f"💰 Цена • {bundle['price_coins']} монет или {bundle['price_stars']} ⭐",
            f"📦 В наличии: {'неограниченно' if bundle['stock'] == 0 else bundle['stock']}"
        ]
        caption = "\n".join([ln for ln in caption_lines if ln is not None])

        # покажем первую картинку как превью (если есть), иначе просто текст
        preview_path = None
        for fn in filenames:
            p = Path(HOMYAK_FILES_DIR) / fn
            if p.exists():
                preview_path = p
                break

        # Stars-инвоис (основной), с фоллбеком
        try:
            link = await query.bot.create_invoice_link(
                title=f"Набор {bundle['name']}",
                description=f"Покупка набора {bundle['name']}",
                payload=f"bundlebuy:{bundle_id}",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label=f"Набор {bundle['name']}", amount=bundle["price_stars"])]
            )
            stars_btn = InlineKeyboardButton(text=f"Купить за {bundle['price_stars']} ⭐", url=link)
        except Exception as e:
            print(f"Error creating bundle invoice: {e}")
            stars_btn = InlineKeyboardButton(text=f"Купить за {bundle['price_stars']} ⭐", callback_data=f"shop:buy_bundle_stars_fallback:{bundle_id}")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Купить за монеты ({bundle['price_coins']})", callback_data=f"shop:buy_bundle_coins:{bundle_id}")],
            [stars_btn],
            [InlineKeyboardButton(text="‹ Назад", callback_data="shop:bundles")]
        ])

        if preview_path:
            await query.message.answer_photo(photo=FSInputFile(preview_path), caption=caption, reply_markup=kb)
        else:
            await query.message.answer(caption, reply_markup=kb, parse_mode="HTML")

        await query.answer()
        return

    # --- НАБОРЫ: покупка за монеты ---
    if data.startswith("shop:buy_bundle_coins:"):
        bundle_id = int(data.split(":", 2)[2])
        bundle = await get_bundle(bundle_id)
        if not bundle:
            await query.answer("❌ Набор не найден", show_alert=True)
            return

        user_id = query.from_user.id
        bal = await get_money(user_id)
        if bal < bundle["price_coins"]:
            await query.answer("❌ Недостаточно монет", show_alert=True)
            return

        ok = await reduce_bundle_stock(bundle_id)
        if not ok:
            await query.answer("❌ Набор закончился", show_alert=True)
            return

        await add_money(user_id, -bundle["price_coins"])

        # выдаём все карты из набора
        filenames = bundle.get("filenames", [])
        gained_points = 0
        is_prem = await is_premium_active(user_id)
        bonus_info = await get_bonus(user_id)

        for fn in filenames:
            await add_card(user_id, fn)
            r = await get_rarity(fn)
            pts = RARITY_POINTS[r]
            if is_prem:
                pts += 1000
            if bonus_info and bonus_info.get("is_active"):
                pts += 700 if (bonus_info.get("is_premium_at_activation") or is_prem) else 500
            gained_points += pts
            # имя для лога очков — по стему
            await add_score(user_id, pts, Path(fn).stem, chat_id=query.message.chat.id)

        total_score_after, _ = await get_score(user_id)

        await query.message.answer(
            f"✅ Вы купили набор «{bundle['name']}»!\n\n"
            f"👥 Выдано карточек: {len(filenames)}\n"
            f"✨ Очки • +{gained_points:,} [{total_score_after:,}]"
        )
        await query.answer()
        return

    if data.startswith("shop:buy_bundle_stars_fallback:"):
        bundle_id = int(data.split(":", 2)[2])
        bundle = await get_bundle(bundle_id)
        if not bundle:
            await query.answer("❌ Набор не найден", show_alert=True)
            return
        provider = SETTINGS.get("STARS_PROVIDER_TOKEN")
        currency = SETTINGS.get("STARS_CURRENCY", "RUB")
        title = f"Набор {bundle['name']}"
        description = f"Покупка набора {bundle['name']}"
        price_value = bundle["price_stars"] * 100
        prices = [LabeledPrice(label=f"{bundle['price_stars']} ⭐", amount=price_value)]
        try:
            link = await CreateInvoiceLink(
                title=title, description=description, payload=f"bundlebuy:{bundle_id}",
                provider_token=provider, currency=currency, prices=prices
            ).send(query.bot)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить", url=link.url)],
                [InlineKeyboardButton(text="‹ Назад", callback_data=f"shop:bundle:{bundle_id}")]
            ])
            await query.message.edit_text(
                "привет это ошибка попробуй заново или напиши @ceotraphouse и опиши ситуацию", reply_markup=kb
            )
            await query.answer()
            return
        except Exception:
            await query.answer("привет это ошибка попробуй заново или напиши @ceotraphouse и опиши ситуацию", show_alert=True)
            return