import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from db_manager import db
from helpers import is_admin, menu_for, send_product_card
import kb
from states import AddProductStates, EditProductStates, RenameCategoryStates

router = Router()
log = logging.getLogger("build_bot")


@router.callback_query(F.data == "admin_catalog")
async def admin_catalog(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return
    await callback.message.answer(
        "📦 **Управление каталогом**",
        reply_markup=kb.admin_catalog_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_cat_"))
async def admin_cat_products(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return
    category = callback.data.removeprefix("admin_cat_")
    products = db.get_products(category)
    if not products:
        return await callback.answer("Категория пуста", show_alert=True)
    await callback.message.answer(
        f"Категория **{category.upper()}** — выберите товар:",
        reply_markup=kb.admin_category_products_kb(category),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_product")
async def add_p_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user):
        return
    await state.clear()
    await callback.message.answer(
        "Выберите категорию или создайте новую:",
        reply_markup=kb.admin_add_category_kb(),
    )
    await state.set_state(AddProductStates.category)
    await callback.answer()


@router.callback_query(AddProductStates.category, F.data.startswith("addcat_"))
async def add_p_category(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user):
        return
    val = callback.data.removeprefix("addcat_")
    if val == "new":
        await callback.message.answer("Введите название новой категории:")
        await state.update_data(await_new_cat=True)
    else:
        await state.update_data(category=val)
        await callback.message.answer("Введите название товара:")
        await state.set_state(AddProductStates.name)
    await callback.answer()


@router.message(AddProductStates.category)
async def add_p_category_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user):
        return
    data = await state.get_data()
    if data.get("await_new_cat"):
        await state.update_data(category=message.text.lower().strip(), await_new_cat=False)
    else:
        await state.update_data(category=message.text.lower().strip())
    await message.answer("Введите название товара:")
    await state.set_state(AddProductStates.name)


@router.message(AddProductStates.name)
async def add_p_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Цена (число):")
    await state.set_state(AddProductStates.price)


@router.message(AddProductStates.price)
async def add_p_price(message: Message, state: FSMContext):
    if not message.text.replace(".", "", 1).isdigit():
        return await message.answer("Введите число!")
    await state.update_data(price=float(message.text))
    await message.answer("Бренд (или «Пропустить»):", reply_markup=kb.skip_kb("addprod_skip_brand"))
    await state.set_state(AddProductStates.brand)


@router.callback_query(AddProductStates.brand, F.data == "addprod_skip_brand")
async def add_p_skip_brand(callback: CallbackQuery, state: FSMContext):
    await state.update_data(brand="")
    await callback.message.answer("Артикул (или «Пропустить»):", reply_markup=kb.skip_kb("addprod_skip_article"))
    await state.set_state(AddProductStates.article)
    await callback.answer()


@router.message(AddProductStates.brand)
async def add_p_brand(message: Message, state: FSMContext):
    await state.update_data(brand=message.text.strip())
    await message.answer("Артикул (или кнопка «Пропустить»):", reply_markup=kb.skip_kb("addprod_skip_article"))
    await state.set_state(AddProductStates.article)


@router.callback_query(AddProductStates.article, F.data == "addprod_skip_article")
async def add_p_skip_article(callback: CallbackQuery, state: FSMContext):
    await state.update_data(article="")
    await callback.message.answer("Описание / характеристики:")
    await state.set_state(AddProductStates.specs)
    await callback.answer()


@router.message(AddProductStates.article)
async def add_p_article(message: Message, state: FSMContext):
    await state.update_data(article=message.text.strip())
    await message.answer("Описание / характеристики:")
    await state.set_state(AddProductStates.specs)


@router.message(AddProductStates.specs)
async def add_p_specs(message: Message, state: FSMContext):
    await state.update_data(specs=message.text)
    await message.answer("Остаток на складе (число):")
    await state.set_state(AddProductStates.stock)


@router.message(AddProductStates.stock)
async def add_p_stock(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введите целое число!")
    await state.update_data(stock=int(message.text))
    await message.answer(
        "Добавить в «Авария 24/7»?",
        reply_markup=kb.yes_no_kb("addprod_em_yes", "addprod_em_no"),
    )
    await state.set_state(AddProductStates.emergency)


@router.callback_query(AddProductStates.emergency, F.data.in_({"addprod_em_yes", "addprod_em_no"}))
async def add_p_emergency(callback: CallbackQuery, state: FSMContext):
    await state.update_data(is_emergency=1 if callback.data == "addprod_em_yes" else 0)
    await callback.message.answer(
        "Отправьте фото товара или нажмите «Без фото»:",
        reply_markup=kb.no_photo_kb(),
    )
    await state.set_state(AddProductStates.photo)
    await callback.answer()


@router.callback_query(AddProductStates.photo, F.data == "addprod_nophoto")
async def add_p_no_photo(callback: CallbackQuery, state: FSMContext):
    await state.update_data(image_file_id=None)
    await _add_product_preview(callback.message, state, callback.from_user.id, callback.message.bot)
    await callback.answer()


@router.message(AddProductStates.photo, F.photo)
async def add_p_photo(message: Message, state: FSMContext):
    await state.update_data(image_file_id=message.photo[-1].file_id)
    await _add_product_preview(message, state, message.from_user.id, message.bot)


async def _add_product_preview(message: Message, state: FSMContext, admin_id: int, bot):
    data = await state.get_data()
    preview = (
        f"**Проверьте товар:**\n\n"
        f"📦 {data['name']}\n"
        f"💰 {int(data['price']):,} ₽\n"
        f"📁 {data['category']}\n"
        f"🏷 {data.get('brand') or '—'} | 🔖 {data.get('article') or '—'}\n"
        f"📝 {data['specs']}\n"
        f"📊 Остаток: {data['stock']}\n"
        f"🚨 Авария: {'да' if data.get('is_emergency') else 'нет'}\n"
        f"🖼 Фото: {'да' if data.get('image_file_id') else 'нет'}"
    )
    await state.set_state(AddProductStates.confirm)
    await message.answer(preview, reply_markup=kb.add_product_confirm_kb(), parse_mode="Markdown")


@router.callback_query(AddProductStates.confirm, F.data == "addprod_save")
async def add_p_save(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user):
        return
    data = await state.get_data()
    pid = db.add_product(
        data["name"],
        data["price"],
        data["category"],
        data["specs"],
        stock=data["stock"],
        article=data.get("article", ""),
        brand=data.get("brand", ""),
        image_file_id=data.get("image_file_id"),
        is_emergency=data.get("is_emergency", 0),
    )
    await state.clear()
    await callback.message.edit_text(f"✅ Товар #{pid} добавлен!")
    await callback.message.answer(reply_markup=await menu_for(callback.from_user.id, "admin"))
    log.info("Admin added product #%s", pid)
    await callback.answer()


@router.callback_query(AddProductStates.confirm, F.data == "addprod_cancel")
async def add_p_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Добавление отменено.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_edit_"))
async def admin_edit_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user):
        return
    pid = int(callback.data.split("_")[2])
    p = db.get_product_by_id(pid)
    if not p:
        return await callback.answer("Товар не найден", show_alert=True)
    await state.clear()
    await send_product_card(callback.message.bot, callback.message.chat.id, p, True)
    await callback.message.answer(
        f"Редактирование товара **#{pid}**:",
        reply_markup=kb.admin_edit_product_kb(pid),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edfield_"))
async def edit_field_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user):
        return
    parts = callback.data.split("_")
    pid, field = int(parts[1]), parts[2]
    await state.update_data(edit_pid=pid, edit_field=field)
    if field == "photo":
        await callback.message.answer("Отправьте новое фото товара:")
        await state.set_state(EditProductStates.photo)
    elif field == "emergency":
        p = db.get_product_by_id(pid)
        new_val = 0 if p.get("is_emergency") else 1
        db.update_product_field(pid, "is_emergency", new_val)
        await callback.answer("Обновлено")
        await callback.message.answer(
            f"Авария 24/7: {'включено' if new_val else 'выключено'}",
            reply_markup=kb.admin_edit_product_kb(pid),
        )
    else:
        hints = {
            "name": "Новое название:",
            "price": "Новая цена:",
            "specs": "Новое описание:",
            "stock": "Новый остаток (число):",
            "category": "Новая категория:",
            "brand": "Новый бренд:",
            "article": "Новый артикул:",
        }
        await callback.message.answer(hints.get(field, "Новое значение:"))
        await state.set_state(EditProductStates.value)
    await callback.answer()


@router.message(EditProductStates.value)
async def edit_field_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user):
        return
    data = await state.get_data()
    pid, field = data["edit_pid"], data["edit_field"]
    val = message.text.strip()
    if field == "price":
        if not val.replace(".", "", 1).isdigit():
            return await message.answer("Введите число!")
        val = float(val)
    elif field == "stock":
        if not val.isdigit():
            return await message.answer("Введите целое число!")
        val = int(val)
    elif field == "category":
        val = val.lower()
    db.update_product_field(pid, field, val)
    await state.clear()
    await message.answer("✅ Сохранено.", reply_markup=kb.admin_edit_product_kb(pid))
    log.info("Admin updated product #%s field %s", pid, field)


@router.message(EditProductStates.photo, F.photo)
async def edit_photo_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user):
        return
    data = await state.get_data()
    pid = data["edit_pid"]
    db.update_product_image(pid, message.photo[-1].file_id)
    await state.clear()
    await message.answer("✅ Фото обновлено.", reply_markup=kb.admin_edit_product_kb(pid))


@router.callback_query(F.data.startswith("edclrphoto_"))
async def edit_clear_photo(callback: CallbackQuery):
    if not is_admin(callback.from_user):
        return
    pid = int(callback.data.split("_")[1])
    db.update_product_image(pid, None)
    await callback.answer("Фото удалено")


@router.callback_query(F.data == "admin_rename_cat")
async def rename_cat_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user):
        return
    cats = db.get_categories()
    if not cats:
        return await callback.answer("Нет категорий", show_alert=True)
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [[InlineKeyboardButton(text=c.upper(), callback_data=f"rencat_{c}")] for c in cats]
    keyboard.append([InlineKeyboardButton(text="◀ Отмена", callback_data="admin_catalog")])
    await callback.message.answer(
        "Выберите категорию для переименования:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rencat_"))
async def rename_cat_pick(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user):
        return
    cat = callback.data.removeprefix("rencat_")
    await state.update_data(old_category=cat)
    await state.set_state(RenameCategoryStates.new_name)
    await callback.message.answer(f"Новое имя для категории «{cat}»:")
    await callback.answer()


@router.message(RenameCategoryStates.new_name)
async def rename_cat_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user):
        return
    data = await state.get_data()
    db.rename_category(data["old_category"], message.text.strip())
    await state.clear()
    await message.answer("✅ Категория переименована.")
    log.info("Category renamed %s -> %s", data["old_category"], message.text)
