import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from db_manager import db
from helpers import is_admin
import kb
from states import FaqEditStates

router = Router()
log = logging.getLogger("build_bot")


@router.callback_query(F.data == "admin_faq")
async def admin_faq_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return
    await callback.message.answer(
        "💬 **Управление консультациями (FAQ)**",
        reply_markup=kb.admin_faq_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "faq_list")
async def faq_list(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return
    items = db.get_faq_items(active_only=False)
    if not items:
        return await callback.answer("Тем пока нет", show_alert=True)
    await callback.message.answer(
        "Выберите тему для редактирования:",
        reply_markup=kb.admin_faq_list_kb(items),
    )
    await callback.answer()


@router.callback_query(F.data == "faq_add")
async def faq_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user):
        return
    await callback.message.answer("Введите заголовок кнопки (кратко):")
    await state.set_state(FaqEditStates.title)
    await state.update_data(faq_mode="add")
    await callback.answer()


@router.message(FaqEditStates.title)
async def faq_add_title(message: Message, state: FSMContext):
    if not is_admin(message.from_user):
        return
    await state.update_data(title=message.text.strip())
    await message.answer("Введите текст ответа (можно с **жирным** Markdown):")
    await state.set_state(FaqEditStates.content)


@router.message(FaqEditStates.content)
async def faq_add_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user):
        return
    data = await state.get_data()
    fid = db.add_faq(data["title"], message.text)
    await state.clear()
    await message.answer(f"✅ Тема FAQ #{fid} добавлена.")
    log.info("Admin added FAQ #%s", fid)


@router.callback_query(F.data.startswith("faq_edit_"))
async def faq_edit_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return
    faq_id = int(callback.data.split("_")[2])
    item = db.get_faq_by_id(faq_id)
    if not item:
        return await callback.answer("Не найдено", show_alert=True)
    preview = item["content"][:200] + ("..." if len(item["content"]) > 200 else "")
    await callback.message.answer(
        f"**{item['title']}**\n\n{preview}",
        reply_markup=kb.admin_faq_item_kb(faq_id, item["is_active"]),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faqetitle_"))
async def faq_edit_title_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user):
        return
    faq_id = int(callback.data.split("_")[1])
    await state.update_data(edit_id=faq_id)
    await state.set_state(FaqEditStates.edit_field)
    await state.update_data(field="title")
    await callback.message.answer("Новый заголовок:")
    await callback.answer()


@router.callback_query(F.data.startswith("faqetext_"))
async def faq_edit_text_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user):
        return
    faq_id = int(callback.data.split("_")[1])
    await state.update_data(edit_id=faq_id, field="content")
    await state.set_state(FaqEditStates.edit_field)
    await callback.message.answer("Новый текст ответа:")
    await callback.answer()


@router.message(FaqEditStates.edit_field)
async def faq_edit_field_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user):
        return
    data = await state.get_data()
    faq_id = data["edit_id"]
    field = data["field"]
    if field == "title":
        db.update_faq(faq_id, title=message.text.strip())
    else:
        db.update_faq(faq_id, content=message.text)
    await state.clear()
    await message.answer("✅ Сохранено.")


@router.callback_query(F.data.startswith("faqtoggle_"))
async def faq_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return
    faq_id = int(callback.data.split("_")[1])
    item = db.get_faq_by_id(faq_id)
    if not item:
        return await callback.answer("Не найдено", show_alert=True)
    db.update_faq(faq_id, is_active=0 if item["is_active"] else 1)
    await callback.answer("Статус изменён")
    item = db.get_faq_by_id(faq_id)
    await callback.message.edit_reply_markup(
        reply_markup=kb.admin_faq_item_kb(faq_id, item["is_active"])
    )


@router.callback_query(F.data.startswith("faqdel_"))
async def faq_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return
    faq_id = int(callback.data.split("_")[1])
    db.delete_faq(faq_id)
    await callback.message.edit_text("🗑 Тема удалена.")
    await callback.answer()
    log.info("Admin deleted FAQ #%s", faq_id)
