import logging

from aiogram import F, Router, types
from aiogram.types import CallbackQuery

from db_manager import db
from helpers import format_dashboard_text, is_admin
import kb

router = Router()
log = logging.getLogger("build_bot")


@router.callback_query(F.data == "admin_dashboard")
async def admin_dashboard_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return
    await callback.message.answer(
        format_dashboard_text(),
        reply_markup=kb.admin_dashboard_kb,
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin_users_\d+$"))
async def admin_users_list(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return await callback.answer("Нет доступа", show_alert=True)
    page = int(callback.data.split("_")[-1])
    users, has_next = db.get_users_paginated(page)
    if not users and page > 0:
        return await callback.answer("Больше нет записей", show_alert=True)
    lines = [f"👥 **Пользователи** (стр. {page + 1})\n"]
    for u in users:
        uname = f"@{u['username']}" if u.get("username") else "—"
        fname = u.get("full_name") or u.get("first_name") or "—"
        seen = (u.get("last_seen") or "")[:16]
        lines.append(
            f"• `{u['user_id']}` {uname}\n  {fname} | заказов: {u['orders_count']} | {seen}"
        )
    await callback.message.answer(
        "\n".join(lines),
        reply_markup=kb.admin_users_kb(page, has_next),
        parse_mode="Markdown",
    )
    await callback.answer()
    log.info("Admin %s viewed users page %s", callback.from_user.id, page)
