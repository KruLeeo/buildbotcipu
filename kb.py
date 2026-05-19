from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from db_manager import db
from config import MANAGER_URL

HOME_TEXT = "🏠 В начало"
HOME_CALLBACK = "go_home"


def home_inline_row():
    return [InlineKeyboardButton(text=HOME_TEXT, callback_data=HOME_CALLBACK)]


def _append_home(rows: list) -> list:
    return rows + [home_inline_row()]


def get_main_menu(role, cart_count=0):
    cart_btn = f"🛒 Корзина ({cart_count})" if cart_count > 0 else "🛒 Корзина"
    buttons = [
        [KeyboardButton(text="🏬 Каталог"), KeyboardButton(text=cart_btn)],
        [KeyboardButton(text="🚨 Авария 24/7"), KeyboardButton(text="🔍 Поиск")],
        [KeyboardButton(text="⭐ Избранное"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="💬 Консультация"), KeyboardButton(text="👨‍💻 Менеджер")],
        [KeyboardButton(text=HOME_TEXT)],
    ]
    if role == "admin":
        buttons.append([KeyboardButton(text="📊 Дешборд")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_catalog_kb():
    categories = db.get_categories()
    keyboard = [
        [InlineKeyboardButton(text=cat.upper(), callback_data=f"cat_{cat}")]
        for cat in categories
    ]
    return InlineKeyboardMarkup(inline_keyboard=_append_home(keyboard))


def get_consultation_kb():
    items = db.get_faq_items(active_only=True)
    keyboard = [
        [InlineKeyboardButton(text=item["title"], callback_data=f"faq_{item['id']}")]
        for item in items
    ]
    keyboard.append([InlineKeyboardButton(text="Написать менеджеру", url=MANAGER_URL)])
    return InlineKeyboardMarkup(inline_keyboard=_append_home(keyboard))


def user_profile_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=_append_home([
            [InlineKeyboardButton(text="📝 Изменить данные", callback_data="edit_profile")],
            [InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders_menu")],
            [InlineKeyboardButton(text="🔁 Повторить последний заказ", callback_data="repeat_order")],
        ])
    )


def user_orders_type_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=_append_home([
            [InlineKeyboardButton(text="⏳ В обработке", callback_data="u_history_processing")],
            [
                InlineKeyboardButton(text="✅ Завершённые", callback_data="u_history_done"),
                InlineKeyboardButton(text="❌ Отменённые", callback_data="u_history_cancel"),
            ],
        ])
    )

admin_dashboard_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📦 Управление каталогом", callback_data="admin_catalog")],
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product")],
        [InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_users_0")],
        [InlineKeyboardButton(text="💬 Консультации (FAQ)", callback_data="admin_faq")],
        [
            InlineKeyboardButton(text="✅ Архив завершённых", callback_data="admin_history_done"),
            InlineKeyboardButton(text="❌ Архив отменённых", callback_data="admin_history_cancel"),
        ],
    ]
)


def product_kb(pid, is_admin=False, in_stock=True):
    buttons = []
    if in_stock:
        buttons.append([InlineKeyboardButton(text="В корзину ✅", callback_data=f"buy_{pid}")])
    buttons.append([InlineKeyboardButton(text="⭐ В избранное", callback_data=f"fav_{pid}")])
    if is_admin:
        buttons.append(
            [
                InlineKeyboardButton(text="⚙️ Редактировать", callback_data=f"admin_edit_{pid}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_prod_{pid}"),
            ]
        )
    buttons.append(home_inline_row())
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cart_item_kb(product_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➖", callback_data=f"cart_minus_{product_id}"),
                InlineKeyboardButton(text="➕", callback_data=f"cart_plus_{product_id}"),
                InlineKeyboardButton(text="🗑", callback_data=f"cart_remove_{product_id}"),
            ]
        ]
    )


def cart_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=_append_home([
            [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout_start")],
            [InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")],
        ])
    )


def delivery_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=_append_home([
            [InlineKeyboardButton(text="🏪 Самовывоз", callback_data="delivery_pickup")],
            [InlineKeyboardButton(text="🚚 Доставка", callback_data="delivery_courier")],
        ])
    )


def confirm_order_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=_append_home([
            [InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="checkout_confirm")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="checkout_cancel")],
        ])
    )


def phone_request_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить телефон", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def admin_order_manage_kb(order_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Завершить", callback_data=f"status_done_{order_id}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"status_cancel_{order_id}")],
        ]
    )


def delete_confirm_kb(pid):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, удалить", callback_data=f"del_confirm_{pid}"),
                InlineKeyboardButton(text="Отмена", callback_data="del_cancel"),
            ]
        ]
    )


def admin_catalog_kb():
    stats = db.get_category_stats()
    keyboard = []
    for row in stats:
        cat = row["category"]
        cnt = row["cnt"]
        keyboard.append([
            InlineKeyboardButton(
                text=f"{cat.upper()} ({cnt})",
                callback_data=f"admin_cat_{cat}",
            )
        ])
    keyboard.append([InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product")])
    keyboard.append([InlineKeyboardButton(text="✏️ Переименовать категорию", callback_data="admin_rename_cat")])
    keyboard.append([InlineKeyboardButton(text="◀ В дешборд", callback_data="admin_dashboard")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_category_products_kb(category):
    products = db.get_products(category)
    keyboard = []
    for p in products:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{p['name'][:30]} — {int(p['price']):,} ₽",
                callback_data=f"admin_edit_{p['id']}",
            )
        ])
    keyboard.append([InlineKeyboardButton(text="◀ К каталогам", callback_data="admin_catalog")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_add_category_kb():
    cats = db.get_categories()
    keyboard = [[InlineKeyboardButton(text=c.upper(), callback_data=f"addcat_{c}")] for c in cats]
    keyboard.append([InlineKeyboardButton(text="➕ Новая категория", callback_data="addcat_new")])
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_catalog")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def skip_kb(callback_data):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data=callback_data)]]
    )


def yes_no_kb(yes_cb, no_cb):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data=yes_cb),
                InlineKeyboardButton(text="Нет", callback_data=no_cb),
            ]
        ]
    )


def add_product_confirm_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сохранить", callback_data="addprod_save")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="addprod_cancel")],
        ]
    )


def no_photo_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Без фото", callback_data="addprod_nophoto")]]
    )


def admin_edit_product_kb(pid):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Название", callback_data=f"edfield_{pid}_name"),
                InlineKeyboardButton(text="Цена", callback_data=f"edfield_{pid}_price"),
            ],
            [
                InlineKeyboardButton(text="Описание", callback_data=f"edfield_{pid}_specs"),
                InlineKeyboardButton(text="Остаток", callback_data=f"edfield_{pid}_stock"),
            ],
            [
                InlineKeyboardButton(text="Категория", callback_data=f"edfield_{pid}_category"),
                InlineKeyboardButton(text="Бренд", callback_data=f"edfield_{pid}_brand"),
            ],
            [
                InlineKeyboardButton(text="Артикул", callback_data=f"edfield_{pid}_article"),
                InlineKeyboardButton(text="Фото", callback_data=f"edfield_{pid}_photo"),
            ],
            [InlineKeyboardButton(text="Авария 24/7", callback_data=f"edfield_{pid}_emergency")],
            [
                InlineKeyboardButton(text="🗑 Удалить фото", callback_data=f"edclrphoto_{pid}"),
                InlineKeyboardButton(text="🗑 Удалить товар", callback_data=f"del_prod_{pid}"),
            ],
            [InlineKeyboardButton(text="◀ Назад", callback_data="admin_catalog")],
        ]
    )


def admin_users_kb(page, has_next):
    buttons = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"admin_users_{page - 1}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="Вперёд ▶", callback_data=f"admin_users_{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="◀ В дешборд", callback_data="admin_dashboard")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_faq_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить тему", callback_data="faq_add")],
            [InlineKeyboardButton(text="📋 Все темы (редакт.)", callback_data="faq_list")],
            [InlineKeyboardButton(text="◀ В дешборд", callback_data="admin_dashboard")],
        ]
    )


def admin_faq_list_kb(items):
    keyboard = []
    for item in items:
        status = "✅" if item["is_active"] else "🚫"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {item['title'][:35]}",
                callback_data=f"faq_edit_{item['id']}",
            )
        ])
    keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data="admin_faq")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_faq_item_kb(faq_id, is_active):
    toggle = "Скрыть" if is_active else "Показать"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Заголовок", callback_data=f"faqetitle_{faq_id}")],
            [InlineKeyboardButton(text="✏️ Текст", callback_data=f"faqetext_{faq_id}")],
            [InlineKeyboardButton(text=toggle, callback_data=f"faqtoggle_{faq_id}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"faqdel_{faq_id}")],
            [InlineKeyboardButton(text="◀ К списку", callback_data="faq_list")],
        ]
    )


def manager_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=_append_home([
            [InlineKeyboardButton(text="Написать менеджеру 💬", url=MANAGER_URL)],
        ])
    )
