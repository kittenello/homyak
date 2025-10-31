from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from difflib import SequenceMatcher
from pathlib import Path
from ..handlers.homyak import HOMYAK_FILES_DIR
from ..database.shoph import add_item, list_items, delete_item
from aiogram.fsm.context import FSMContext
from ..database.bundles import add_bundle, list_bundles, delete_bundle
from aiogram.fsm.state import StatesGroup, State
from ..database.admins import is_admin

router = Router()

class SetShopStates(StatesGroup):
    waiting_name = State()
    waiting_price_coins = State()
    waiting_price_stars = State()
    waiting_stock = State()
    waiting_confirm = State()
    waiting_bundle_name = State()
    waiting_bundle_price_coins = State()
    waiting_bundle_price_stars = State()
    waiting_bundle_stock = State()
    waiting_bundle_items = State()
    waiting_bundle_confirm = State() 

@router.message(Command(commands=["setshop"]))
async def cmd_setshop(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="setshop:action:add")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data="setshop:action:delete")],
        [InlineKeyboardButton(text="📦 Наборы", callback_data="setshop:action:bundles")]
    ])
    await message.answer("Выберите действие для магазина:", reply_markup=kb)
    await state.clear()

@router.callback_query(lambda c: c.data and c.data.startswith("setshop:action:"))
async def setshop_action_cb(query: CallbackQuery, state: FSMContext):
    user_id = query.from_user.id
    if not await is_admin(user_id):
        return

    action = query.data.split(":", 2)[2]
    if action == "add":
        await state.clear()
        await state.set_state(SetShopStates.waiting_name)
        await query.message.edit_text("Отправьте название хомяка (частично или полностью) для добавления")
        await query.answer()
        return

    if action == "delete":
        items = await list_items()
        if not items:
            await query.message.edit_text("В магазине нет товаров для удаления.")
            await query.answer()
            return
        rows = []
        for it in items:
            rows.append([InlineKeyboardButton(text=f"{it['name']} • {it['price_coins']} / {it['price_stars']} • stock:{it['stock']}", callback_data=f"setshop:del:{it['id']}")])
        rows.append([InlineKeyboardButton(text="Отмена", callback_data="setshop:cancel")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        await query.message.edit_text("Выберите товар для удаления:", reply_markup=kb)
        await query.answer()
        return
    
    if action == "bundles":
        print("1")
        user_id = query.from_user.id
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать набор", callback_data="setshop:bundles:create")],
            [InlineKeyboardButton(text="🗑️ Удалить набор", callback_data="setshop:bundles:delete")],
            [InlineKeyboardButton(text="‹ Назад", callback_data="setshop:action:back")]
        ])
        await query.message.edit_text("📦 Управление наборами:", reply_markup=kb)
        await query.answer()
        return
    
@router.callback_query(lambda c: c.data and c.data.startswith("setshop:del:"))
async def setshop_delete_pick(query: CallbackQuery):
    user_id = query.from_user.id
    if not await is_admin(user_id):
        await query.answer("Нет доступа", show_alert=True)
        return
    item_id = int(query.data.split(":", 2)[2])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Удалить", callback_data=f"setshop:del_confirm:{item_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="setshop:cancel")]
    ])
    await query.message.edit_text(f"Вы уверены, что хотите удалить товар ID {item_id}?", reply_markup=kb)
    await query.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("setshop:del_confirm:"))
async def setshop_delete_confirm(query: CallbackQuery):
    user_id = query.from_user.id
    if not await is_admin(user_id):
        await query.answer("Нет доступа", show_alert=True)
        return
    item_id = int(query.data.split(":", 2)[2])
    ok = await delete_item(item_id)
    if ok:
        await query.message.edit_text("Товар удалён из магазина.")
    else:
        await query.message.edit_text("Не удалось удалить товар (возможно его нет).")
    await query.answer()

@router.message(SetShopStates.waiting_name)
async def process_name(message: Message, state: FSMContext):
    query = message.text.strip().lower()
    files = list(HOMYAK_FILES_DIR.glob("*.png"))
    candidates = []
    for f in files:
        name = f.stem.lower()
        ratio = SequenceMatcher(None, query, name).ratio()
        if ratio >= 0.6:
            candidates.append((f.name, f.stem, ratio))
    
    if not candidates:
        await message.answer("Не найдено похожих хомяков. Попробуйте снова или Отмена")
        return

    buttons = []
    for fname, stem, r in candidates:
        buttons.append([InlineKeyboardButton(text=f"{stem}", callback_data=f"setshop:pick:{fname}")])
    
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="setshop:cancel")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите хомяка", reply_markup=kb)
    await state.update_data(candidates=[c[0] for c in candidates])
    await state.set_state(SetShopStates.waiting_price_coins)

@router.callback_query(lambda c: c.data and c.data.startswith("setshop:"))
async def setshop_callbacks(query, state: FSMContext):
    data = query.data
    if data == "setshop:cancel":
        await query.message.edit_text("Отменено")
        await state.clear()
        await query.answer()
        return
    if data.startswith("setshop:pick:"):
        filename = data.split(":",2)[2]
        await state.update_data(filename=filename)
        await query.message.edit_text(f"Вы выбрали {filename}\nУкажите цену в монетах")
        await query.answer()
        await state.set_state(SetShopStates.waiting_price_coins)
        return

@router.message(SetShopStates.waiting_price_coins)
async def got_price_coins(message: Message, state: FSMContext):
    try:
        coins = int(message.text.strip())
    except:
        await message.answer("Введите число")
        return
    await state.update_data(price_coins=coins)
    await message.answer("Укажите цену в звёздах (целое число)")
    await state.set_state(SetShopStates.waiting_price_stars)

@router.message(SetShopStates.waiting_price_stars)
async def got_price_stars(message: Message, state: FSMContext):
    try:
        stars = int(message.text.strip())
    except:
        await message.answer("Введите число")
        return
    await state.update_data(price_stars=stars)
    await message.answer("Укажите количество в магазине (0 = неограничено)")
    await state.set_state(SetShopStates.waiting_stock)

@router.message(SetShopStates.waiting_stock)
async def got_stock(message: Message, state: FSMContext):
    try:
        stock = int(message.text.strip())
        if stock < 0:
            raise ValueError()
    except:
        await message.answer("Укажите количество в магазине (0 = неограничено)")
        return
    data = await state.get_data()
    filename = data.get("filename")
    price_coins = data.get("price_coins", 0)
    price_stars = data.get("price_stars", 0)
    name = Path(filename).stem
    await add_item(filename, name, price_coins, price_stars, stock)
    await message.answer("Товар добавлен в магазин")
    await state.clear()

@router.callback_query(lambda c: c.data and c.data == "setshop:cancel")
async def setshop_cancel(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text("Действие отменено.")
    await query.answer()

# @router.callback_query(lambda c: c.data == "setshop:action:bundles")
# async def setshop_bundles_root(query: CallbackQuery, state: FSMContext):
#     user_id = query.from_user.id
#     print("1")
#     # if not await is_admin(user_id):
#     #     return
#     kb = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="➕ Создать набор", callback_data="setshop:bundles:create")],
#         [InlineKeyboardButton(text="🗑️ Удалить набор", callback_data="setshop:bundles:delete")],
#         [InlineKeyboardButton(text="‹ Назад", callback_data="setshop:action:back")]
#     ])
#     await query.message.edit_text("📦 Управление наборами:", reply_markup=kb)
#     await query.answer()

@router.callback_query(lambda c: c.data == "setshop:action:back")
async def setshop_back(query: CallbackQuery, state: FSMContext):
    if not await is_admin(query.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="setshop:action:add")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data="setshop:action:delete")],
        [InlineKeyboardButton(text="📦 Наборы", callback_data="setshop:action:bundles")]
    ])
    await query.message.edit_text("Выберите действие для магазина:", reply_markup=kb)
    await state.clear()
    await query.answer()

@router.callback_query(lambda c: c.data == "setshop:bundles:create")
async def bundles_create_start(query: CallbackQuery, state: FSMContext):
    print("1")
    if not await is_admin(query.from_user.id):
        return
    await state.clear()
    await state.set_state(SetShopStates.waiting_bundle_name)
    await query.message.edit_text("Введите название набора")
    await query.answer()

@router.message(SetShopStates.waiting_bundle_name)
async def bundles_get_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(bundle_name=name)
    await state.set_state(SetShopStates.waiting_bundle_items)
    await message.answer("Теперь выберите хомяков для набора. Отправьте часть названия для поиска.")

@router.message(SetShopStates.waiting_bundle_items)
async def bundles_search_cards(message: Message, state: FSMContext):
    q = message.text.strip().lower()
    files = list(HOMYAK_FILES_DIR.glob("*.png"))
    found = [f for f in files if q in f.stem.lower()]
    data = await state.get_data()
    buttons = []
    for f in found[:40]:
        buttons.append([InlineKeyboardButton(text=f"➕ {f.stem}", callback_data=f"bundles:toggle:{f.name}")])
    buttons.append([InlineKeyboardButton(text="Готово", callback_data="bundles:done")])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="setshop:cancel")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите из списка хомяков для набора:", reply_markup=kb)

@router.callback_query(lambda c: c.data and c.data.startswith("bundles:toggle:"))
async def bundles_toggle(query: CallbackQuery, state: FSMContext):
    if not await is_admin(query.from_user.id):
        return
    fname = query.data.split(":", 2)[2]
    data = await state.get_data()
    selected = set(data.get("selected", []))
    if fname in selected:
        selected.remove(fname)
    else:
        selected.add(fname)
    await state.update_data(selected=list(selected))
    await query.answer("Выбран/удален хомяк.")

@router.callback_query(lambda c: c.data == "bundles:done")
async def bundles_done_select(query: CallbackQuery, state: FSMContext):
    if not await is_admin(query.from_user.id):
        return
    data = await state.get_data()
    selected = data.get("selected", [])
    if len(selected) < 2:
        await query.answer("Набор должен содержать хотя бы 2 хомяков.", show_alert=True)
        return
    await state.set_state(SetShopStates.waiting_bundle_price_coins)
    await query.message.edit_text("Укажите цену набора в монетах")
    await query.answer()

@router.message(SetShopStates.waiting_bundle_price_coins)
async def got_bundle_price_coins(message: Message, state: FSMContext):
    try:
        coins = int(message.text.strip())
    except:
        await message.answer("Введите цену набора в монетах")
        return
    await state.update_data(bundle_price_coins=coins)
    await state.set_state(SetShopStates.waiting_bundle_price_stars)
    await message.answer("Укажите цену набора в звёздах")

@router.message(SetShopStates.waiting_bundle_price_stars)
async def got_bundle_price_stars(message: Message, state: FSMContext):
    try:
        stars = int(message.text.strip())
    except:
        await message.answer("Введите цену набора в звёздах")
        return
    await state.update_data(bundle_price_stars=stars)
    await state.set_state(SetShopStates.waiting_bundle_stock)
    await message.answer("Укажите количество наборов в магазине (0 = неограничено)")

@router.message(SetShopStates.waiting_bundle_stock)
async def got_bundle_stock(message: Message, state: FSMContext):
    try:
        stock = int(message.text.strip())
        if stock < 0:
            raise ValueError()
    except:
        await message.answer("Укажите количество наборов в магазине (0 = неограничено)")
        return
    data = await state.get_data()
    name = data.get("bundle_name")
    filenames = data.get("selected", [])
    price_coins = data.get("bundle_price_coins", 0)
    price_stars = data.get("bundle_price_stars", 0)
    await add_bundle(name, filenames, price_coins, price_stars, stock)
    await message.answer("Набор добавлен в магазин")
    await state.clear()

@router.callback_query(lambda c: c.data and c.data.startswith("setshop:bundles:delete"))
async def bundles_delete_menu(query: CallbackQuery, state: FSMContext):
    if not await is_admin(query.from_user.id):
        return
    bundles = await list_bundles()
    if not bundles:
        await query.message.edit_text("Нет наборов для удаления.")
        await query.answer()
        return
    rows = []
    for b in bundles:
        rows.append([InlineKeyboardButton(
            text=f"{b['name']} • {b['price_coins']} монет / {b['price_stars']} ⭐ • stock:{b['stock']}",
            callback_data=f"setshop:bundles:del:{b['id']}"
        )])
    rows.append([InlineKeyboardButton(text="‹ Назад", callback_data="setshop:action:bundles")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await query.message.edit_text("Выберите набор для удаления:", reply_markup=kb)
    await query.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("setshop:bundles:del:"))
async def bundles_delete_confirm(query: CallbackQuery, state: FSMContext):
    if not await is_admin(query.from_user.id):
        return
    bundle_id = int(query.data.split(":", 2)[2])
    ok = await delete_bundle(bundle_id)
    await query.message.edit_text("Набор удалён." if ok else "Не удалось удалить набор.")
    await query.answer()