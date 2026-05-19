from aiogram.fsm.state import State, StatesGroup


class ProfileStates(StatesGroup):
    name = State()
    phone = State()
    city = State()


class AddProductStates(StatesGroup):
    category = State()
    name = State()
    price = State()
    brand = State()
    article = State()
    specs = State()
    stock = State()
    emergency = State()
    photo = State()
    confirm = State()


class EditProductStates(StatesGroup):
    pid = State()
    field = State()
    value = State()
    photo = State()


class RenameCategoryStates(StatesGroup):
    old_category = State()
    new_name = State()


class CheckoutStates(StatesGroup):
    delivery_type = State()
    phone = State()
    address = State()
    confirm = State()


class SearchStates(StatesGroup):
    query = State()


class CartQtyStates(StatesGroup):
    qty = State()


class FaqEditStates(StatesGroup):
    title = State()
    content = State()
    edit_id = State()
    edit_field = State()
