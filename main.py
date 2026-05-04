import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import BOT_TOKEN, ADMIN_ID, ALLOWED_USERNAMES
from db_manager import db
import kb

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_carts = {}

# Состояния
class ProfileStates(StatesGroup):
    name, phone, city = State(), State(), State()

class AddProductStates(StatesGroup):
    name, price, category, specs = State(), State(), State(), State()

class EditProductStates(StatesGroup):
    pid = State()
    name = State()
    price = State()
    specs = State()

def is_admin(user: types.User):
    return user.id == ADMIN_ID or user.username in ALLOWED_USERNAMES

@dp.message(Command("start"))
async def start(message: types.Message):
    role = 'admin' if is_admin(message.from_user) else db.get_role(message.from_user.id)
    if role == 'admin': db.set_role(message.from_user.id, 'admin')
    count = len(user_carts.get(message.from_user.id, []))
    await message.answer("🛠 **Строительный Магазин**\nДобро пожаловать!", reply_markup=kb.get_main_menu(role, count))

# --- КАТАЛОГ ---
@dp.message(F.text == "🏬 Каталог")
async def show_catalog(message: types.Message):
    await message.answer("Выберите раздел:", reply_markup=kb.get_catalog_kb())

@dp.callback_query(F.data.startswith("cat_"))
async def show_items(callback: types.CallbackQuery):
    category = callback.data.split("_")[1]
    items = db.get_products(category)
    admin_status = is_admin(callback.from_user) # Проверяем, админ ли это
    
    for item in items:
        await callback.message.answer(
            f"📦 **{item[1]}**\n📝 {item[4]}\n💰 {int(item[2]):,} руб.",
            # В функцию buy_kb нужно будет добавить передачу аргумента is_admin
            reply_markup=kb.buy_kb(item[0], is_admin=admin_status), 
            parse_mode="Markdown"
        )
    await callback.answer()

# --- РЕДАКТИРОВАНИЕ ТОВАРА (АДМИН) ---

@dp.callback_query(F.data.startswith("edit_prod_"))
async def edit_p_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user): return
    
    pid = int(callback.data.split("_")[2])
    await state.update_data(edit_pid=pid)
    
    await callback.message.answer("Введите НОВОЕ название товара (или '-' чтобы оставить прежним):")
    await state.set_state(EditProductStates.name)
    await callback.answer()

@dp.message(EditProductStates.name)
async def edit_p_name(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Введите НОВУЮ цену (или '-' чтобы оставить):")
    await state.set_state(EditProductStates.price)

@dp.message(EditProductStates.price)
async def edit_p_price(m: types.Message, state: FSMContext):
    if m.text != "-" and not m.text.isdigit():
        return await m.answer("Введите число или '-'!")
    
    await state.update_data(price=m.text)
    await m.answer("Введите НОВОЕ описание (или '-' чтобы оставить):")
    await state.set_state(EditProductStates.specs)

@dp.message(EditProductStates.specs)
async def edit_p_final(m: types.Message, state: FSMContext):
    data = await state.get_data()
    pid = data['edit_pid']
    
    # Получаем старые данные из базы, чтобы сохранить их, если введен "-"
    old_p = db.get_product_by_id(pid)
    
    new_name = data['name'] if data['name'] != "-" else old_p[1]
    new_price = float(data['price']) if data['price'] != "-" else old_p[2]
    new_specs = m.text if m.text != "-" else old_p[4]
    
    # Вызываем метод обновления в БД
    db.update_product(pid, new_name, new_price, new_specs)
    
    await state.clear()
    await m.answer("✅ Товар успешно обновлен!")

# --- ИСТОРИЯ ЗАКАЗОВ (ПОЛЬЗОВАТЕЛЬ) ---

@dp.callback_query(F.data == "my_orders_menu")
async def my_orders_menu(callback: types.CallbackQuery):
    await callback.message.answer("Выберите категорию заказов:", reply_markup=kb.user_orders_type_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("u_history_"))
async def show_user_history(callback: types.CallbackQuery):
    # Извлекаем ключ (processing, done или cancel)
    status_key = callback.data.split("_")[2]
    
    # Тот самый словарь-переводчик
    status_map = {
        "processing": "В обработке", 
        "done": "completed", 
        "cancel": "cancelled"
    }
    
    target_status = status_map.get(status_key)
    orders = db.get_user_orders(callback.from_user.id, target_status)
    
    if not orders:
        return await callback.answer("Заказов не найдено", show_alert=True)

    await callback.message.answer(f"📜 **История ваших заказов ({target_status}):**", parse_mode="Markdown")
    for o in orders:
        # o[0] - ID, o[1] - товары, o[2] - сумма
        await callback.message.answer(f"🆔 Заказ **#{o[0]}**\n🛒 {o[1]}\n💰 {int(o[2]):,} р.", parse_mode="Markdown")
    await callback.answer()

# --- ДОБАВЛЕНИЕ ТОВАРА (АДМИН) ---
@dp.callback_query(F.data == "admin_add_product")
async def add_p_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user): return
    await callback.message.answer("Название товара:")
    await state.set_state(AddProductStates.name)
    await callback.answer()

@dp.message(AddProductStates.name)
async def add_p_name(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text); await m.answer("Цена (число):"); await state.set_state(AddProductStates.price)

@dp.message(AddProductStates.price)
async def add_p_price(m: types.Message, state: FSMContext):
    if not m.text.isdigit(): return await m.answer("Введите число!")
    await state.update_data(price=float(m.text)); await m.answer("Категория:"); await state.set_state(AddProductStates.category)

@dp.message(AddProductStates.category)
async def add_p_cat(m: types.Message, state: FSMContext):
    await state.update_data(category=m.text.lower()); await m.answer("Описание:"); await state.set_state(AddProductStates.specs)

@dp.message(AddProductStates.specs)
async def add_p_final(m: types.Message, state: FSMContext):
    d = await state.get_data()
    db.add_product(d['name'], d['price'], d['category'], m.text)
    await state.clear()
    await m.answer("✅ Товар добавлен!", reply_markup=kb.get_main_menu('admin'))

# --- КОРЗИНА И ЗАКАЗ ---
@dp.callback_query(F.data.startswith("buy_"))
async def buy(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user_carts.setdefault(uid, []).append(int(callback.data.split("_")[1]))
    await callback.message.answer(f"✅ Добавлено! В корзине: {len(user_carts[uid])}", reply_markup=kb.get_main_menu(db.get_role(uid), len(user_carts[uid])))
    await callback.answer()

@dp.message(F.text.startswith("🛒 Корзина"))
async def cart(m: types.Message):
    items = user_carts.get(m.from_user.id, [])
    if not items: return await m.answer("Пусто")
    total = 0
    res = "📦 **Ваша корзина:**\n\n"
    for pid in items:
        p = db.get_product_by_id(pid)
        res += f"• {p[1]} — {int(p[2]):,} р.\n"
        total += p[2]
    await m.answer(f"{res}\nИТОГО: {int(total):,} р.", reply_markup=kb.cart_kb(), parse_mode="Markdown")

@dp.callback_query(F.data == "checkout")
async def checkout(callback: types.CallbackQuery):
    uid = callback.from_user.id
    items = user_carts.get(uid, [])
    if not items: 
        return await callback.answer("Ваша корзина пуста!")
        
    p_info = db.get_profile(uid)
    client = f"@{callback.from_user.username}" if callback.from_user.username else f"ID: {uid}"
    if p_info: 
        client += f"\n👤 {p_info[0]} | 📞 {p_info[1]}"
    
    # Формируем данные заказа
    txt = ", ".join([db.get_product_by_id(pid)[1] for pid in items])
    total = sum(db.get_product_by_id(pid)[2] for pid in items)
    
    # Сохраняем в БД
    db.add_order(uid, txt, total)
    
    # ОЧИЩАЕМ КОРЗИНУ
    user_carts[uid] = []
    
    # Удаляем инлайн-кнопки из текущего сообщения
    await callback.message.edit_text(f"✅ **Заказ оформлен!**\nСостав: {txt}\nСумма: {int(total):,} р.", parse_mode="Markdown")
    
    # ОТПРАВЛЯЕМ НОВОЕ СООБЩЕНИЕ С ОБНОВЛЕННОЙ КЛАВИАТУРОЙ (где Корзина будет (0))
    role = db.get_role(uid)
    await callback.message.answer(
        "Менеджер скоро свяжется с вами. Корзина очищена.", 
        reply_markup=kb.get_main_menu(role, 0)
    )
    
    # Уведомляем админа
    await bot.send_message(ADMIN_ID, f"🔔 **НОВЫЙ ЗАКАЗ**\n{client}\n🛒 {txt}\n💰 {int(total):,} р.")
    await callback.answer()
    
@dp.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: types.CallbackQuery):
    uid = callback.from_user.id
    
    # Проверяем, есть ли что-то в корзине
    if uid not in user_carts or not user_carts[uid]:
        return await callback.answer("Корзина и так пуста!", show_alert=True)
    
    # 1. Очищаем список в памяти
    user_carts[uid] = []
    
    # 2. Обновляем текущее сообщение (убираем список товаров)
    await callback.message.edit_text("🗑 **Корзина очищена.**", parse_mode="Markdown")
    
    # 3. Отправляем новое сообщение, чтобы обновить Reply-кнопки (убрать цифру с кнопки)
    role = db.get_role(uid)
    await callback.message.answer(
        "Вы можете выбрать новые товары в каталоге.",
        reply_markup=kb.get_main_menu(role, 0) # Явно передаем 0
    )
    
    await callback.answer("Корзина очищена")

# --- ПРОФИЛЬ И ДЕШБОРД ---
@dp.message(F.text == "👤 Профиль")
async def profile(m: types.Message):
    p = db.get_profile(m.from_user.id)
    text = f"👤 **Профиль**\n\nФИО: {p[0]}\nТел: {p[1]}\nГород: {p[2]}" if p else "⚙️ Профиль не заполнен."
    await m.answer(text, reply_markup=kb.user_profile_kb, parse_mode="Markdown")

@dp.message(F.text == "📊 Дешборд")
async def dashboard(m: types.Message):
    if not is_admin(m.from_user): return
    orders = db.get_orders_by_status("В обработке")
    await m.answer(f"📈 **ДЕШБОРД**\nВыручка: {int(db.get_total_sales()):,} р.", reply_markup=kb.admin_dashboard_kb)
    for o in orders:
        await m.answer(f"🆔 #{o[0]} | 💰 {int(o[3]):,} р.\n🛒 {o[2]}", reply_markup=kb.admin_order_manage_kb(o[0]))

@dp.callback_query(F.data.startswith("status_"))
async def status_upd(callback: types.CallbackQuery):
    _, action, oid = callback.data.split("_")
    
    # 1. Получаем данные заказа, чтобы узнать ID пользователя (uid)
    # Предположим, db.get_order_by_id возвращает (id, user_id, items, total, status)
    order_data = db.get_order_by_id(int(oid))
    customer_id = order_data[1] 
    
    tech_status = "completed" if action == "done" else "cancelled"
    display_status = "✅ Завершен" if action == "done" else "❌ Отменен"
    
    # 2. Обновляем в базе
    db.update_order_status(int(oid), tech_status)
    
    # 3. УВЕДОМЛЯЕМ ПОЛЬЗОВАТЕЛЯ
    try:
        status_msg = (
            f"🔔 **Обновление по вашему заказу #{oid}**\n"
            f"Статус изменен на: **{display_status}**"
        )
        await bot.send_message(customer_id, status_msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление пользователю {customer_id}: {e}")

    # 4. Обновляем дешборд админа (твой текущий код)
    current_sales = db.get_total_sales()
    await callback.message.edit_text(
        f"{callback.message.text}\n\n"
        f"Статус: {display_status}\n"
        f"📊 Актуальная выручка: {int(current_sales):,} р."
    )
    await callback.answer(f"Статус изменен")

@dp.message(F.text == "👨‍💻 Менеджер")
async def manager(m: types.Message):
    await m.answer("Связь с менеджером:", reply_markup=kb.manager_kb)

# --- АНКЕТА (FSM) ---
@dp.callback_query(F.data == "edit_profile")
async def profile_edit(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("Введите ФИО:"); await state.set_state(ProfileStates.name); await c.answer()

@dp.message(ProfileStates.name)
async def p_name(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text); await m.answer("Телефон:"); await state.set_state(ProfileStates.phone)

@dp.message(ProfileStates.phone)
async def p_phone(m: types.Message, state: FSMContext):
    await state.update_data(phone=m.text); await m.answer("Город:"); await state.set_state(ProfileStates.city)

@dp.message(ProfileStates.city)
async def p_city(m: types.Message, state: FSMContext):
    d = await state.get_data(); db.save_profile(m.from_user.id, d['name'], d['phone'], m.text); await state.clear()
    await m.answer("✅ Сохранено!", reply_markup=kb.get_main_menu(db.get_role(m.from_user.id)))

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())