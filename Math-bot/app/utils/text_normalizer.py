from __future__ import annotations

import re


def escape_html(text: str) -> str:
    """
    Экранируем <, >, &, чтобы Telegram в режиме HTML не думал,
    что это теги.
    """
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


# Простейшие замены TeX → понятные символы
_TEX_REPLACEMENTS: list[tuple[str, str]] = [
    # корни
    (r"\\sqrt\s*\{([^}]+)\}", r"√(\1)"),
    (r"\\sqrt\s+([^\s,.;:]+)", r"√\1"),

    # дроби
    (r"\\frac\{([^}]+)\}\{([^}]+)\}", r"(\1)/(\2)"),

    # интегралы и прочее
    (r"\\int", "∫"),
    (r"\\sum", "∑"),
    (r"\\infty", "∞"),

    # действия/операторы
    (r"\\cdot", "·"),
    (r"\\times", "×"),
    (r"\\div", "÷"),
    (r"\\pm", "±"),

    # сравнения
    (r"\\leq?", "≤"),
    (r"\\geq?", "≥"),
    (r"\\neq", "≠"),

    # разное
    (r"\\vert", "|"),
    (r"\\ldots", "..."),
    (r"\\dots", "..."),

    # служебные
    (r"\\displaystyle", ""),
    (r"\\left", ""),
    (r"\\right", ""),
    (r"\\,", " "),
]

_DOLLAR_RE = re.compile(r"\$+")
_DISPLAY_MATH_RE = re.compile(r"\\\[|\\\]|\\\(|\\\)")


def latex_to_plain(text: str) -> str:
    """
    Грубо приводим TeX-текст к нормальному виду:
    убираем $, \(...\), \[...\], частые команды и
    нормализуем разрывы строк.
    """
    # нормализуем перевод строк
    s = text.replace("\r\n", "\n")

    # убираем разделители формул $ ... $, \( ... \), \[ ... \]
    s = _DOLLAR_RE.sub("", s)
    s = _DISPLAY_MATH_RE.sub("", s)

    # применяем замены TeX-команд
    for pattern, repl in _TEX_REPLACEMENTS:
        s = re.sub(pattern, repl, s)

    # упрощаем индексы/степени: _{k} -> _k, ^{2} -> ^2
    s = re.sub(r"_\{([^{}]+)\}", r"_\1", s)
    s = re.sub(r"\^\{([^{}]+)\}", r"^\1", s)
    # убираем обратный слэш перед оставшимися буквенными командами: \alpha -> alpha
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)

    # схлопываем последовательности пробелов
    s = re.sub(r"[ \t]{2,}", " ", s)

    # ---- НОРМАЛИЗАЦИЯ ПЕРЕНОСОВ СТРОК ----
    # делим на абзацы по пустым строкам
    paragraphs = re.split(r"\n\s*\n", s)
    cleaned_paragraphs: list[str] = []
    for p in paragraphs:
        # внутри абзаца все переводы строк -> пробелы
        p = re.sub(r"\s*\n\s*", " ", p)
        p = p.strip()
        if p:
            cleaned_paragraphs.append(p)

    # абзацы соединяем двойным переводом
    s = "\n\n".join(cleaned_paragraphs)

    return s


def normalize_for_telegram_math(text: str) -> str:
    """
    Полный конвейер:
    TeX → понятный текст/символы → безопасный HTML-текст.
    """
    s = latex_to_plain(text)
    s = escape_html(s)
    return s.strip()


# --- Вытаскивание числового ответа из нейросети ---


_ANSWER_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def extract_plain_answer(raw: str) -> str:
    """
    Пытаемся превратить произвольный ответ нейросети в "голый" ответ:
    число / короткое выражение без TeX и слов "Ответ".
    """
    s = raw.strip()

    # Берём первую непустую строку — чаще всего ответ сидит в ней
    for line in s.splitlines():
        line = line.strip()
        if line:
            s = line
            break

    # Срезаем типичные оболочки
    s = re.sub(r"^\$+(.+?)\$+$", r"\1", s)           # $123$, $$123$$
    s = re.sub(r"\\boxed\{(.+?)\}", r"\1", s)        # \boxed{123}
    s = re.sub(r"^[Оо]твет[:\s-]*", "", s)           # Ответ: 123
    s = re.sub(r"^[Aa]nswer[:\s-]*", "", s)

    # Если внутри есть числа — забираем последнее
    nums = _ANSWER_NUMBER_RE.findall(s)
    if nums:
        return nums[-1].replace(",", ".").strip()

    # Фоллбек — вернём очищенную строку как есть
    return s.strip()
