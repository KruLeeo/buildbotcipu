import asyncio

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from config import ADMIN_ID, BOT_TOKEN
from db_manager import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_LABELS,
    STATUS_PROCESSING,
    db,
)
from handlers import admin_catalog_router, admin_faq_router, admin_users_router
from helpers import (
    WELCOME_TEXT,
    format_dashboard_text,
    format_order_detail,
    is_admin,
    menu_for,
    send_product_card,
)
from middleware.stats import StatsMiddleware
from utils.logger import setup_logging
from utils.validators import normalize_phone, validate_city, validate_fio
import kb
from states import CartQtyStates, CheckoutStates, ProfileStates, SearchStates

CART_PLUS_CLICK_LIMIT = 3
_cart_plus_clicks: dict[tuple[int, int], int] = {}


def _reset_plus_clicks(user_id: int, product_id: int | None = None):
    if product_id is not None:
        _cart_plus_clicks.pop((user_id, product_id), None)
    else:
        for key in [k for k in _cart_plus_clicks if k[0] == user_id]:
            _cart_plus_clicks.pop(key, None)

logger = setup_logging()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
dp.update.middleware(StatsMiddleware())
dp.include_router(admin_catalog_router)
dp.include_router(admin_faq_router)
dp.include_router(admin_users_router)


# --- START / В НАЧАЛО ---
async def _send_home(chat_id: int, user: types.User, state: FSMContext):
    await state.clear()
    uid = user.id
    role = "admin" if is_admin(user) else db.get_role(uid)
    db.touch_user(uid, user.username, user.first_name)
    if role == "admin":
        db.set_role(uid, "admin")
    await bot.send_message(
        chat_id,
        WELCOME_TEXT,
        reply_markup=await menu_for(uid, role),
        parse_mode="Markdown",
    )


@dp.message(Command("start"))
@dp.message(F.text == kb.HOME_TEXT)
async def start(message: types.Message, state: FSMContext):
    logger.info("User %s home", message.from_user.id)
    await _send_home(message.chat.id, message.from_user, state)


@dp.callback_query(F.data == kb.HOME_CALLBACK)
async def go_home_callback(callback: types.CallbackQuery, state: FSMContext):
    await _send_home(callback.message.chat.id, callback.from_user, state)
    await callback.answer()


# --- КАТАЛОГ ---
@dp.message(F.text == "🏬 Каталог")
async def show_catalog(message: types.Message):
    if not db.get_categories():
        return await message.answer("Каталог пуст.")
    await message.answer("Выберите раздел:", reply_markup=kb.get_catalog_kb())


@dp.callback_query(F.data.startswith("cat_"))
async def show_items(callback: types.CallbackQuery):
    category = callback.data.removeprefix("cat_")
    items = db.get_products(category)
    if not items:
        return await callback.answer("В категории нет товаров", show_alert=True)
    for item in items:
        await send_product_card(
            bot, callback.message.chat.id, item, is_admin(callback.from_user),
            user_id=callback.from_user.id,
        )
    await callback.answer()


# --- АВАРИЯ ---
@dp.message(F.text == "🚨 Авария 24/7")
async def emergency(message: types.Message):
    items = db.get_emergency_products()
    if not items:
        return await message.answer("Список аварийных позиций пуст.")
    await message.answer("🚨 **Срочные позиции:**", parse_mode="Markdown")
    for item in items:
        await send_product_card(
            bot, message.chat.id, item, is_admin(message.from_user),
            user_id=message.from_user.id,
        )


# --- ПОИСК ---
@dp.message(F.text == "🔍 Поиск")
async def search_start(message: types.Message, state: FSMContext):
    await message.answer("Введите название, артикул или бренд:")
    await state.set_state(SearchStates.query)


@dp.message(SearchStates.query)
async def search_run(message: types.Message, state: FSMContext):
    items = db.search_products(message.text)
    await state.clear()
    if not items:
        return await message.answer("Ничего не найдено.")
    await message.answer(f"Найдено: {len(items)}")
    for item in items:
        await send_product_card(
            bot, message.chat.id, item, is_admin(message.from_user),
            user_id=message.from_user.id,
        )


# --- ИЗБРАННОЕ ---
@dp.message(F.text == "⭐ Избранное")
async def favorites(message: types.Message):
    items = db.get_favorites(message.from_user.id)
    if not items:
        return await message.answer("Избранное пусто.")
    for item in items:
        await send_product_card(
            bot, message.chat.id, item, is_admin(message.from_user),
            user_id=message.from_user.id,
            in_favorites=True,
        )


@dp.callback_query(F.data.startswith("fav_"))
async def toggle_fav(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    uid = callback.from_user.id
    added = db.toggle_favorite(uid, pid)
    await callback.answer("Добавлено в избранное" if added else "Убрано из избранного")

    p = db.get_product_by_id(pid)
    if not p:
        return
    try:
        await callback.message.edit_reply_markup(
            reply_markup=kb.product_kb(
                pid,
                is_admin=is_admin(callback.from_user),
                in_stock=(p.get("stock") or 0) > 0,
                in_favorites=db.is_favorite(uid, pid),
            )
        )
    except Exception:
        pass


# --- КОРЗИНА ---
@dp.callback_query(F.data.startswith("buy_"))
async def buy(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    ok, err = db.add_to_cart(callback.from_user.id, pid)
    if not ok:
        return await callback.answer(err, show_alert=True)
    await callback.answer("Добавлено")
    await callback.message.answer(
        f"✅ В корзине: {db.get_cart_count(callback.from_user.id)}",
        reply_markup=await menu_for(callback.from_user.id),
    )


@dp.message(F.text.startswith("🛒 Корзина"))
async def show_cart(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    _reset_plus_clicks(uid)
    text, *_ = db.format_cart_text(uid)
    if not text:
        return await message.answer("Корзина пуста.")
    await message.answer(
        text,
        reply_markup=kb.cart_items_kb(uid),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "cart_noop")
async def cart_noop(callback: types.CallbackQuery):
    await callback.answer()


@dp.callback_query(F.data.startswith("cart_plus_"))
async def cart_plus(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    pid = int(callback.data.split("_")[2])
    key = (uid, pid)
    clicks = _cart_plus_clicks.get(key, 0) + 1

    if clicks > CART_PLUS_CLICK_LIMIT:
        _cart_plus_clicks[key] = 0
        product = db.get_product_by_id(pid)
        stock = product["stock"] if product else 0
        await state.update_data(cart_pid=pid, cart_message_id=callback.message.message_id)
        await state.set_state(CartQtyStates.qty)
        await callback.answer()
        await callback.message.answer(
            f"Введите нужное количество (от 1 до {stock}):"
        )
        return

    if not db.change_cart_qty(uid, pid, 1):
        return await callback.answer("Недостаточно на складе", show_alert=True)

    _cart_plus_clicks[key] = clicks
    await callback.answer()
    await _refresh_cart_view(callback)


@dp.message(CartQtyStates.qty)
async def cart_qty_entered(message: types.Message, state: FSMContext):
    if not message.text.strip().isdigit():
        return await message.answer("Введите целое число, например: 10")
    qty = int(message.text.strip())
    data = await state.get_data()
    pid = data["cart_pid"]
    uid = message.from_user.id

    ok, err = db.set_cart_qty(uid, pid, qty)
    if not ok:
        return await message.answer(err)

    _reset_plus_clicks(uid, pid)
    await state.clear()

    text, *_ = db.format_cart_text(uid)
    msg_id = data.get("cart_message_id")
    if text and msg_id:
        try:
            await bot.edit_message_text(
                text,
                chat_id=message.chat.id,
                message_id=msg_id,
                reply_markup=kb.cart_items_kb(uid),
                parse_mode="Markdown",
            )
            await message.answer(f"✅ Установлено: {qty} шт.")
            return
        except Exception:
            pass
    if text:
        await message.answer(
            text,
            reply_markup=kb.cart_items_kb(uid),
            parse_mode="Markdown",
        )
    else:
        await message.answer("Корзина пуста.", reply_markup=await menu_for(uid))


@dp.callback_query(F.data.startswith("cart_minus_"))
async def cart_minus(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[2])
    db.change_cart_qty(callback.from_user.id, pid, -1)
    await callback.answer()
    await _refresh_cart_view(callback)


@dp.callback_query(F.data.startswith("cart_remove_"))
async def cart_remove(callback: types.CallbackQuery):
    uid = callback.from_user.id
    pid = int(callback.data.split("_")[2])
    db.remove_from_cart(uid, pid)
    _reset_plus_clicks(uid, pid)
    await callback.answer("Удалено")
    await _refresh_cart_view(callback)


async def _refresh_cart_view(callback: types.CallbackQuery):
    uid = callback.from_user.id
    text, *_ = db.format_cart_text(uid)
    if not text:
        await callback.message.edit_text("🗑 Корзина пуста.")
        await callback.message.answer(
            "Выберите товары в каталоге.",
            reply_markup=await menu_for(uid),
        )
        return
    try:
        await callback.message.edit_text(
            text,
            reply_markup=kb.cart_items_kb(uid),
            parse_mode="Markdown",
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=kb.cart_items_kb(uid),
            parse_mode="Markdown",
        )


@dp.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if not db.get_cart_count(uid):
        return await callback.answer("Корзина пуста", show_alert=True)
    db.clear_cart(uid)
    _reset_plus_clicks(uid)
    await callback.message.edit_text("🗑 Корзина очищена.")
    await callback.message.answer(reply_markup=await menu_for(callback.from_user.id))
    await callback.answer()


# --- CHECKOUT ---
@dp.callback_query(F.data == "checkout_start")
async def checkout_start(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if not db.get_cart_count(uid):
        return await callback.answer("Корзина пуста", show_alert=True)
    if not db.get_profile(uid):
        await callback.message.answer("Заполните профиль.")
        await state.set_state(ProfileStates.name)
        await callback.message.answer("Введите ФИО (2–4 слова, без цифр):")
        return await callback.answer()
    await callback.message.answer("Способ получения:", reply_markup=kb.delivery_kb())
    await state.set_state(CheckoutStates.delivery_type)
    await callback.answer()


@dp.callback_query(CheckoutStates.delivery_type, F.data.startswith("delivery_"))
async def checkout_delivery(callback: types.CallbackQuery, state: FSMContext):
    dtype = "pickup" if callback.data == "delivery_pickup" else "courier"
    await state.update_data(delivery_type=dtype)
    await callback.message.answer("Телефон:", reply_markup=kb.phone_request_kb())
    await state.set_state(CheckoutStates.phone)
    await callback.answer()


@dp.message(CheckoutStates.phone, F.contact)
async def checkout_phone_contact(message: types.Message, state: FSMContext):
    ok, phone = normalize_phone(message.contact.phone_number)
    if not ok:
        return await message.answer(phone)
    await state.update_data(phone=phone)
    await _checkout_after_phone(message, state)


@dp.message(CheckoutStates.phone)
async def checkout_phone_text(message: types.Message, state: FSMContext):
    ok, phone = normalize_phone(message.text)
    if not ok:
        return await message.answer(phone + "\nИли нажмите кнопку отправки контакта.")
    await state.update_data(phone=phone)
    await _checkout_after_phone(message, state)


async def _checkout_after_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data.get("delivery_type") == "courier":
        await message.answer("Адрес доставки:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(CheckoutStates.address)
    else:
        await state.update_data(address="Самовывоз")
        await _show_order_preview(message, state)


@dp.message(CheckoutStates.address)
async def checkout_address(message: types.Message, state: FSMContext):
    await state.update_data(address=message.text)
    await _show_order_preview(message, state)


async def _show_order_preview(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    text, subtotal, discount, total, _ = db.format_cart_text(uid)
    data = await state.get_data()
    label = "🏪 Самовывоз" if data["delivery_type"] == "pickup" else "🚚 Доставка"
    preview = (
        f"{text}\n\n**Способ:** {label}\n**Телефон:** {data['phone']}\n"
        f"**Адрес:** {data.get('address', '—')}\n\nПодтвердите:"
    )
    await state.update_data(subtotal=subtotal, discount=discount, total=total)
    await message.answer(preview, reply_markup=kb.confirm_order_kb(), parse_mode="Markdown")
    await state.set_state(CheckoutStates.confirm)


@dp.callback_query(CheckoutStates.confirm, F.data == "checkout_confirm")
async def checkout_confirm(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    data = await state.get_data()
    items = db.get_cart_items(uid)
    if not items:
        await state.clear()
        return await callback.answer("Корзина пуста", show_alert=True)
    items_text = ", ".join(f"{i['name']} × {i['qty']}" for i in items)
    total = data["total"]
    order_id = db.add_order(
        uid, items_text, total, data["delivery_type"],
        data["phone"], data.get("address", ""), data.get("discount", 0),
    )
    for i in items:
        db.decrease_stock(i["product_id"], i["qty"])
    db.clear_cart(uid)
    profile = db.get_profile(uid)
    client = f"@{callback.from_user.username}" if callback.from_user.username else f"ID: {uid}"
    if profile:
        client += f"\n👤 {profile[0]} | 📞 {profile[1]}"
    label = "Самовывоз" if data["delivery_type"] == "pickup" else "Доставка"
    await callback.message.edit_text(
        f"✅ **Заказ №{order_id} принят!**\n{items_text}\n💰 {int(total):,} ₽",
        parse_mode="Markdown",
    )
    await callback.message.answer("Спасибо!", reply_markup=await menu_for(uid))
    await bot.send_message(
        ADMIN_ID,
        f"🔔 **ЗАКАЗ №{order_id}**\n{client}\n🛒 {items_text}\n💰 {int(total):,} ₽\n📞 {data['phone']}\n📍 {data.get('address')}\n{label}",
        parse_mode="Markdown",
        reply_markup=kb.admin_order_manage_kb(order_id),
    )
    logger.info("Order #%s from user %s total %s", order_id, uid, total)
    await state.clear()
    await callback.answer()


@dp.callback_query(CheckoutStates.confirm, F.data == "checkout_cancel")
async def checkout_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Оформление отменено.")
    await callback.answer()


@dp.callback_query(F.data == "repeat_order")
async def repeat_order(callback: types.CallbackQuery):
    order = db.get_last_completed_order(callback.from_user.id)
    if not order:
        return await callback.answer("Нет завершённых заказов", show_alert=True)
    await callback.message.answer(f"Последний заказ №{order['id']}:\n{order['items_text']}")
    await callback.answer()


# --- ПРОФИЛЬ ---
@dp.message(F.text == "👤 Профиль")
async def profile(message: types.Message):
    p = db.get_profile(message.from_user.id)
    text = f"👤 **Профиль**\n\nФИО: {p[0]}\nТел: {p[1]}\nГород: {p[2]}" if p else "Профиль не заполнен."
    await message.answer(text, reply_markup=kb.user_profile_kb(), parse_mode="Markdown")


@dp.callback_query(F.data == "edit_profile")
async def profile_edit(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введите ФИО (минимум 2 слова, без цифр):",
        reply_markup=types.ReplyKeyboardRemove(),
    )
    await state.set_state(ProfileStates.name)
    await callback.answer()


@dp.message(ProfileStates.name)
async def p_name(message: types.Message, state: FSMContext):
    ok, result = validate_fio(message.text)
    if not ok:
        return await message.answer(result)
    await state.update_data(name=result)
    await message.answer("Телефон (+7...) или кнопка ниже:", reply_markup=kb.phone_request_kb())
    await state.set_state(ProfileStates.phone)


@dp.message(ProfileStates.phone, F.contact)
async def p_phone_contact(message: types.Message, state: FSMContext):
    ok, phone = normalize_phone(message.contact.phone_number)
    if not ok:
        return await message.answer(phone)
    await state.update_data(phone=phone)
    await message.answer("Город:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(ProfileStates.city)


@dp.message(ProfileStates.phone)
async def p_phone(message: types.Message, state: FSMContext):
    ok, phone = normalize_phone(message.text)
    if not ok:
        return await message.answer(phone)
    await state.update_data(phone=phone)
    await message.answer("Город:")
    await state.set_state(ProfileStates.city)


@dp.message(ProfileStates.city)
async def p_city(message: types.Message, state: FSMContext):
    ok, city = validate_city(message.text)
    if not ok:
        return await message.answer(city)
    data = await state.get_data()
    uid = message.from_user.id
    db.save_profile(uid, data["name"], data["phone"], city)
    await state.clear()
    logger.info("Profile saved for user %s", uid)
    await message.answer("✅ Профиль сохранён!", reply_markup=await menu_for(uid))


# --- КОНСУЛЬТАЦИЯ ---
@dp.message(F.text == "💬 Консультация")
async def consultation(message: types.Message):
    if not db.get_faq_items():
        return await message.answer(
            "Раздел в настройке. Свяжитесь с менеджером:",
            reply_markup=kb.manager_kb(),
        )
    await message.answer(
        "Частые вопросы по сантехнике:",
        reply_markup=kb.get_consultation_kb(),
    )


@dp.callback_query(F.data.regexp(r"^faq_\d+$"))
async def faq_answer(callback: types.CallbackQuery):
    faq_id = int(callback.data.split("_")[1])
    item = db.get_faq_by_id(faq_id)
    if not item or not item["is_active"]:
        return await callback.answer("Тема недоступна", show_alert=True)
    await callback.message.answer(item["content"], parse_mode="Markdown")
    await callback.answer()


@dp.message(F.text == "👨‍💻 Менеджер")
async def manager(message: types.Message):
    await message.answer("Связь с менеджером:", reply_markup=kb.manager_kb())


# --- ЗАКАЗЫ ---
@dp.callback_query(F.data == "my_orders_menu")
async def my_orders_menu(callback: types.CallbackQuery):
    await callback.message.answer("Категория:", reply_markup=kb.user_orders_type_kb())
    await callback.answer()


@dp.callback_query(F.data.startswith("u_history_"))
async def show_user_history(callback: types.CallbackQuery):
    key = callback.data.split("_")[2]
    smap = {"processing": STATUS_PROCESSING, "done": STATUS_COMPLETED, "cancel": STATUS_CANCELLED}
    orders = db.get_user_orders(callback.from_user.id, smap[key])
    if not orders:
        return await callback.answer("Нет заказов", show_alert=True)
    for o in orders:
        await callback.message.answer(
            f"🆔 #{o['id']}\n🛒 {o['items_text']}\n💰 {int(o['total']):,} ₽",
            parse_mode="Markdown",
        )
    await callback.answer()


# --- ДЕШБОРД ---
@dp.message(F.text == "📊 Дешборд")
async def dashboard(message: types.Message):
    if not is_admin(message.from_user):
        return
    await message.answer(format_dashboard_text(), reply_markup=kb.admin_dashboard_kb, parse_mode="Markdown")
    for o in db.get_orders_by_status(STATUS_PROCESSING):
        await message.answer(
            f"🆔 #{o['id']} | 💰 {int(o['total']):,} ₽\n🛒 {o['items_text']}",
            reply_markup=kb.admin_order_manage_kb(o["id"]),
        )


@dp.callback_query(F.data.startswith("status_"))
async def status_upd(callback: types.CallbackQuery):
    if not is_admin(callback.from_user):
        return await callback.answer("Нет доступа", show_alert=True)
    parts = callback.data.split("_")
    action, oid = parts[1], int(parts[2])
    order = db.get_order_by_id(oid)
    if not order:
        return await callback.answer("Не найден", show_alert=True)
    tech = STATUS_COMPLETED if action == "done" else STATUS_CANCELLED
    db.update_order_status(oid, tech)
    try:
        await bot.send_message(
            order["user_id"],
            f"🔔 Заказ №{oid}: **{STATUS_LABELS[tech]}**",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("Notify %s: %s", order["user_id"], e)
    await callback.message.edit_text(
        f"{callback.message.text}\n\n{STATUS_LABELS[tech]}\n📊 {int(db.get_total_sales()):,} ₽"
    )
    logger.info("Order #%s -> %s by admin", oid, tech)
    await callback.answer()


@dp.callback_query(F.data == "admin_history_done")
async def admin_history_done(callback: types.CallbackQuery):
    if not is_admin(callback.from_user):
        return
    orders = db.get_orders_by_status(STATUS_COMPLETED)[:20]
    if not orders:
        return await callback.answer("Пусто", show_alert=True)
    await callback.message.answer(
        "✅ Завершённые заказы — нажмите, чтобы открыть состав:",
        reply_markup=kb.admin_orders_archive_kb(orders),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_history_cancel")
async def admin_history_cancel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user):
        return
    orders = db.get_orders_by_status(STATUS_CANCELLED)[:20]
    if not orders:
        return await callback.answer("Пусто", show_alert=True)
    await callback.message.answer(
        "❌ Отменённые заказы — нажмите, чтобы открыть состав:",
        reply_markup=kb.admin_orders_archive_kb(orders),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("admord_"))
async def admin_order_detail(callback: types.CallbackQuery):
    if not is_admin(callback.from_user):
        return await callback.answer("Нет доступа", show_alert=True)
    oid = int(callback.data.split("_")[1])
    order = db.get_order_by_id(oid)
    if not order:
        return await callback.answer("Заказ не найден", show_alert=True)

    status = order.get("status")
    if status == STATUS_COMPLETED:
        back = "admin_history_done"
    elif status == STATUS_CANCELLED:
        back = "admin_history_cancel"
    else:
        back = "admin_dashboard"

    await callback.message.answer(
        format_order_detail(order),
        reply_markup=kb.admin_order_detail_kb(oid, back),
    )
    await callback.answer()


# --- УДАЛЕНИЕ ТОВАРА ---
@dp.callback_query(F.data.startswith("del_prod_"))
async def del_prod_ask(callback: types.CallbackQuery):
    if not is_admin(callback.from_user):
        return
    pid = int(callback.data.split("_")[2])
    await callback.message.answer("Удалить?", reply_markup=kb.delete_confirm_kb(pid))
    await callback.answer()


@dp.callback_query(F.data.startswith("del_confirm_"))
async def del_prod_confirm(callback: types.CallbackQuery):
    if not is_admin(callback.from_user):
        return
    pid = int(callback.data.split("_")[2])
    db.delete_product(pid)
    logger.info("Product #%s deleted", pid)
    await callback.message.edit_text("🗑 Удалён.")
    await callback.answer()


@dp.callback_query(F.data == "del_cancel")
async def del_prod_cancel(callback: types.CallbackQuery):
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@dp.message(StateFilter(None))
async def unknown_message(message: types.Message):
    await message.answer("Используйте меню 👇", reply_markup=await menu_for(message.from_user.id))


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("Укажите BOT_TOKEN в .env")
    if db.faq_count() == 0:
        from seed_faq import FAQ_DATA
        for i, (title, content) in enumerate(FAQ_DATA):
            db.add_faq(title, content, sort_order=i)
        logger.info("FAQ seeded: %s topics", len(FAQ_DATA))
    logger.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
