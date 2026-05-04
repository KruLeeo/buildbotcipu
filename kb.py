from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from db_manager import db

def get_main_menu(role, cart_count=0):
    cart_btn = f"🛒 Корзина ({cart_count})" if cart_count > 0 else "🛒 Корзина"
    buttons = [
        [KeyboardButton(text="🏬 Каталог"), KeyboardButton(text=cart_btn)],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="👨‍💻 Менеджер")]
    ]
    if role == 'admin':
        buttons.append([KeyboardButton(text="📊 Дешборд")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_catalog_kb():
    categories = db.get_categories()
    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(text=cat.upper(), callback_data=f"cat_{cat}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

user_profile_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📝 Изменить данные", callback_data="edit_profile")],
    [InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders_menu")]
])

user_orders_type_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⏳ В обработке", callback_data="u_history_processing")],
    [InlineKeyboardButton(text="✅ Завершенные", callback_data="u_history_done"),
     InlineKeyboardButton(text="❌ Отмененные", callback_data="u_history_cancel")]
])

admin_dashboard_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product")],
    [InlineKeyboardButton(text="✅ Архив завершенных", callback_data="admin_history_done")],
    [InlineKeyboardButton(text="❌ Архив отмененных", callback_data="admin_history_cancel")]
])



def buy_kb(pid, is_admin=False):
    buttons = [[InlineKeyboardButton(text="В корзину ✅", callback_data=f"buy_{pid}")]]
    
    # Если зашел админ, добавляем кнопку редактирования
    if is_admin:
        buttons.append([InlineKeyboardButton(text="⚙️ Редактировать", callback_data=f"edit_prod_{pid}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def cart_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton(text="🗑 Очистить", callback_data="clear_cart")]
    ])

def admin_order_manage_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить", callback_data=f"status_done_{order_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"status_cancel_{order_id}")]
    ])

manager_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Написать менеджеру 💬", url="https://t.me/kruleeo")]
])