import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ALLOWED_USERNAMES = [
    u.strip() for u in os.getenv("ALLOWED_USERNAMES", "kruleeo").split(",") if u.strip()
]
MANAGER_URL = os.getenv("MANAGER_URL", "https://t.me/kruleeo")
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Скидки от суммы заказа (сантехника)
DISCOUNT_TIERS = [
    (100_000, 0.10),
    (50_000, 0.05),
]
