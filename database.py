# database.py
PRODUCTS = {
    "excavators": [
        {"id": 1, "name": "Экскаватор Caterpillar 320", "price": 15000000, "desc": "Мощный, надежный, желтый."},
        {"id": 2, "name": "Экскаватор JCB JS205", "price": 12000000, "desc": "Лучший для городских работ."}
    ],
    "loaders": [
        {"id": 3, "name": "Погрузчик Bobcat S530", "price": 4500000, "desc": "Маневренный мини-погрузчик."},
    ]
}

def get_discount(total_sum):
    """Фишка: прогрессивная скидка"""
    if total_sum > 20000000:
        return 0.10  # 10%
    if total_sum > 10000000:
        return 0.05  # 5%
    return 0