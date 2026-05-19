import re

_FIO_RE = re.compile(r"^[a-zA-Zа-яА-ЯёЁ\-]+(?:\s+[a-zA-Zа-яА-ЯёЁ\-]+){1,3}$")
_PHONE_DIGITS = re.compile(r"\D")


def validate_fio(text: str) -> tuple[bool, str]:
    text = text.strip()
    if len(text) < 5 or len(text) > 100:
        return False, "ФИО: от 5 до 100 символов, 2–4 слова (например: Иванов Иван Иванович)."
    if not _FIO_RE.match(text):
        return False, "ФИО: только буквы и дефис, минимум 2 слова, без цифр."
    return True, text


def normalize_phone(text: str) -> tuple[bool, str]:
    digits = _PHONE_DIGITS.sub("", text.strip())
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) != 11 or not digits.startswith("7"):
        return False, "Телефон: введите 10 цифр или номер в формате +7..."
    return True, f"+{digits}"


def validate_city(text: str) -> tuple[bool, str]:
    text = text.strip()
    if len(text) < 2:
        return False, "Город: минимум 2 символа."
    if text.isdigit():
        return False, "Город не может состоять только из цифр."
    return True, text
