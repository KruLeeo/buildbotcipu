# admin_handlers.py
from aiogram import Router, F, types
from db_manager import db
import kb

router = Router()

@router.message(F.text == "📊 Дешборд")
async def dashboard(message: types.Message):
    role = db.get_role(message.from_user.id)
    if role not in ['admin', 'seller']:
        return await message.answer("У вас нет доступа к этому модулю.")
    
    await message.answer(f"🔒 **Авторизован как: {role.upper()}**\nВыберите действие:", 
                         reply_markup=kb.admin_kb)

@router.callback_query(F.data == "adm_orders")
async def view_orders(callback: types.CallbackQuery):
    orders = db.get_all_orders()
    if not orders:
        return await callback.answer("Заказов пока нет", show_alert=True)
    
    report = "📋 **Последние заказы:**\n\n"
    for order in orders[:10]:
        report += f"ID: {order[0]} | Юзер: {order[1]} | Сумма: {order[3]:,} руб.\nСтатус: {order[4]}\n---\n"
    
    await callback.message.answer(report)
    await callback.answer()