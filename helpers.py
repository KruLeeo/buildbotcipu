from aiogram import Bot, types

from config import ADMIN_ID, ALLOWED_USERNAMES
from db_manager import db
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


async def send_product_card(bot: Bot, chat_id: int, p: dict, is_admin_user: bool):
    caption = format_product_caption(p)
    markup = kb.product_kb(p["id"], is_admin=is_admin_user, in_stock=(p.get("stock") or 0) > 0)
    file_id = p.get("image_file_id")
    if file_id:
        await bot.send_photo(chat_id, file_id, caption=caption, reply_markup=markup, parse_mode="Markdown")
    else:
        await bot.send_message(chat_id, caption, reply_markup=markup, parse_mode="Markdown")


async def menu_for(user_id: int, role: str | None = None):
    role = role or db.get_role(user_id)
    return kb.get_main_menu(role, db.get_cart_count(user_id))


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
