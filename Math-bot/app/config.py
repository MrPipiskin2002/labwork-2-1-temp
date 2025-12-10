from __future__ import annotations

from pathlib import Path
import os

# Корень проекта: math_bot/
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Пути к JSON-файлам с задачами
EULER_TASKS_PATH = DATA_DIR / "euler_ru.json"
LEVEL_TASKS_PATH = DATA_DIR / "level_tasks_ru.json"

# Уровни сложности для задач по уровню
LEVELS = [
    "5 класс",
    "6 класс",
    "7 класс",
    "8 класс",
    "9 класс",
    "10 класс",
    "11 класс",
    "1 курс",
    "2 курс",
]

# --- Telegram токен ---

TELEGRAM_BOT_TOKEN = ""

# --- GigaChat (Freemium, физлицо) ---

# Authorization Key из личного кабинета GigaChat API (поле Authorization Key)
GIGACHAT_CREDENTIALS = ""

# Версия API. Для физлица и Freemium — GIGACHAT_API_PERS
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")

# Модель. Можно оставить пустым (None), тогда возьмется дефолтная для твоего тарифа.
# Или явно указать, например: "GigaChat", "GigaChat-Pro", "GigaChat 2 Pro" — по тому,
# что тебе доступно в кабинете/доке.
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL") or None

# Ты НЕ хочешь устанавливать сертификат НУЦ Минцифры -> выключаем проверку SSL.
# Если когда-нибудь захочешь включить — поставь переменную окружения GIGACHAT_VERIFY_SSL_CERTS=True
GIGACHAT_VERIFY_SSL_CERTS = os.getenv("GIGACHAT_VERIFY_SSL_CERTS", "False").lower() == "true"
