from aiogram import Bot, types

from config import ADMIN_ID, ALLOWED_USERNAMES
from db_manager import STATUS_LABELS, db
import kb

log = __import__("logging").getLogger("build_bot")

WELCOME_TEXT = (
    "🚿 **Магазин сантехники 24/7**\n\n"
    "Каталог, корзина, оформление заказа и консультации — всё в одном боте.\n"
    "Для срочных случаев нажмите **Авария 24/7**."
)


def is_admin(user: types.User) -> bool:
    return user.id == ADMIN_ID or (user.username and user.username in ALLOWED_USERNAMES)


def format_product_caption(p: dict) -> str:
    stock = p.get("stock") or 0
    stock_line = f"✅ В наличии: {stock} шт." if stock > 0 else "❌ Нет в наличии"
    lines = [f"📦 **{p['name']}**"]
    if p.get("brand"):
        lines.append(f"🏷 {p['brand']}")
    if p.get("article"):
        lines.append(f"🔖 Артикул: `{p['article']}`")
    lines.append(f"📝 {p.get('specs') or '—'}")
    lines.append(f"💰 **{int(p['price']):,} ₽**")
    lines.append(stock_line)
    return "\n".join(lines)


async def send_product_card(
    bot: Bot,
    chat_id: int,
    p: dict,
    is_admin_user: bool,
    user_id: int | None = None,
    in_favorites: bool | None = None,
):
    caption = format_product_caption(p)
    if in_favorites is None and user_id is not None:
        in_favorites = db.is_favorite(user_id, p["id"])
    elif in_favorites is None:
        in_favorites = False
    markup = kb.product_kb(
        p["id"],
        is_admin=is_admin_user,
        in_stock=(p.get("stock") or 0) > 0,
        in_favorites=in_favorites,
    )
    file_id = p.get("image_file_id")
    if file_id:
        await bot.send_photo(chat_id, file_id, caption=caption, reply_markup=markup, parse_mode="Markdown")
    else:
        await bot.send_message(chat_id, caption, reply_markup=markup, parse_mode="Markdown")


async def menu_for(user_id: int, role: str | None = None):
    role = role or db.get_role(user_id)
    return kb.get_main_menu(role, db.get_cart_count(user_id))


def format_order_detail(order: dict) -> str:
    profile = db.get_profile(order["user_id"])
    status = STATUS_LABELS.get(order.get("status"), order.get("status", "—"))
    delivery = "Самовывоз" if order.get("delivery_type") == "pickup" else "Доставка"
    if not order.get("delivery_type"):
        delivery = "—"

    lines = [
        f"🆔 Заказ №{order['id']}",
        f"📋 Статус: {status}",
        f"👤 Клиент ID: {order['user_id']}",
    ]
    if profile:
        lines.append(f"   ФИО: {profile[0]}")
        lines.append(f"   Тел: {profile[1]}")
        lines.append(f"   Город: {profile[2]}")
    lines.extend([
        "",
        f"🛒 Состав:\n{order.get('items_text') or '—'}",
        "",
        f"💰 Сумма: {int(order['total']):,} ₽",
    ])
    discount = order.get("discount") or 0
    if discount > 0:
        lines.append(f"🏷 Скидка: −{int(discount):,} ₽")
    lines.extend([
        f"📞 Телефон заказа: {order.get('phone') or '—'}",
        f"📍 Адрес: {order.get('address') or '—'}",
        f"🚚 Способ: {delivery}",
    ])
    return "\n".join(lines)


def format_dashboard_text() -> str:
    m = db.get_metrics_summary()
    return (
        "📈 **Дешборд**\n\n"
        "**Нагрузка:**\n"
        f"• Пользователей всего: {m['total_users']}\n"
        f"• Активных за 24 ч: {m['active_24h']}\n"
        f"• Новых сегодня: {m['new_today']}\n"
        f"• Событий за час: {m['events_1h']}\n"
        f"• Заказов в обработке: {m['pending_orders']}\n"
        f"• Корзин с товарами: {m['carts_with_items']}\n\n"
        f"**Выручка (завершённые):** {int(m['total_sales']):,} ₽"
    )
