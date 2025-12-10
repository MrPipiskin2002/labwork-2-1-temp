import json
import re
import time
from typing import Optional, Dict, List

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://euler.jakumo.org"
PROBLEMS_LIST_URL = f"{BASE_URL}/problems"

HEADERS = {
    # желательно подставь сюда свой GitHub / почту
    "User-Agent": "EulerParser/1.0 (+https://github.com/yourname)"
}


def get_total_problems(session: requests.Session) -> int:
    """
    Определяет общее количество задач по странице /problems.
    Если по какой-то причине не удалось — возвращает 851 как fallback.
    """
    try:
        resp = session.get(PROBLEMS_LIST_URL, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"[WARN] Не удалось получить {PROBLEMS_LIST_URL}: {e}")
        print("[WARN] Использую значение по умолчанию: 851")
        return 851

    m = re.search(r"Всего переведено задач:\s*(\d+)", resp.text)
    if m:
        total = int(m.group(1))
        print(f"[INFO] Найдено задач: {total}")
        return total

    print("[WARN] Не удалось найти строку 'Всего переведено задач', используем 851")
    return 851


def extract_title(soup: BeautifulSoup, text_lines: List[str]) -> Optional[str]:
    """
    Пытается вытащить заголовок задачи.
    Сначала через <h2>, если не нашли — ищем строку, начинающуюся с '## ' во всём тексте.
    """
    h2 = soup.find("h2")
    if h2 and h2.get_text(strip=True):
        return h2.get_text(strip=True)

    # fallback по текстовым строкам
    for line in text_lines:
        line = line.strip()
        if line.startswith("## "):
            return line[3:].strip()

    return None


def extract_original_url(soup: BeautifulSoup) -> Optional[str]:
    """
    Находит ссылку 'Оригинал' и возвращает href.
    """
    link = soup.find("a", string=lambda s: s and "Оригинал" in s)
    if link:
        return link.get("href")
    return None


def extract_problem_text(soup: BeautifulSoup) -> str:
    """
    Вытаскивает основной текст задачи из полной текстовой версии страницы.

    Алгоритм:
    - Берём весь текст страницы через soup.get_text("\n").
    - Режем по строкам.
    - Ищем строку с 'Оригинал' -> это около начала задачи.
    - Ищем строку с 'Dark Mode' -> это начало футера.
    - Берём всё между ними, выкидываем 'Предыдущая'/'Следующая', обрезаем пустые строки по краям.
    """
    full_text = soup.get_text("\n")
    # разрезаем на строки и очищаем неразрывные пробелы и т.п.
    lines = [line.replace("\u00a0", " ").strip() for line in full_text.splitlines()]

    start_idx = None
    end_idx = None

    for i, line in enumerate(lines):
        if "Оригинал" in line:
            start_idx = i
        if "Dark Mode" in line:
            end_idx = i
            break

    if start_idx is None or end_idx is None or start_idx >= end_idx:
        # fallback: просто возвращаем всё, что есть (на всякий случай)
        print("[WARN] Не удалось аккуратно выделить текст задачи, возвращаю весь текст страницы целиком")
        return full_text.strip()

    # Берём строки между 'Оригинал' и 'Dark Mode'
    content_lines: List[str] = []
    for line in lines[start_idx + 1 : end_idx]:
        stripped = line.strip()
        # пропускаем навигацию
        if stripped in ("Предыдущая", "Следующая", ""):
            # пустые строки можно оставить, но мы их потом аккуратно почистим
            if stripped == "":
                content_lines.append("")
            continue
        content_lines.append(stripped)

    # убираем пустые строки в начале и в конце
    while content_lines and content_lines[0] == "":
        content_lines.pop(0)
    while content_lines and content_lines[-1] == "":
        content_lines.pop()

    return "\n".join(content_lines)


def fetch_problem(session: requests.Session, problem_id: int) -> Optional[Dict]:
    """
    Загружает одну задачу с /problem/<id> и возвращает dict формата:
    {
        "id": int,
        "title": str,
        "url": str,
        "original_url": str | None,
        "lang": "ru",
        "text": str
    }
    """
    url = f"{BASE_URL}/problem/{problem_id}"
    try:
        resp = session.get(url, headers=HEADERS, timeout=10)
    except Exception as e:
        print(f"[ERROR] Не удалось запросить {url}: {e}")
        return None

    if resp.status_code == 404:
        print(f"[WARN] {url} -> 404, пропускаю (перевода, возможно, нет)")
        return None

    if resp.status_code != 200:
        print(f"[WARN] {url} -> HTTP {resp.status_code}, пропускаю")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Для извлечения title и text нам пригодится список текстовых строк
    full_text = soup.get_text("\n")
    text_lines = [line.replace("\u00a0", " ").strip() for line in full_text.splitlines()]

    title = extract_title(soup, text_lines)
    original_url = extract_original_url(soup)
    text = extract_problem_text(soup)

    if not title:
        print(f"[WARN] Не удалось вытащить title для задачи {problem_id}, ставлю пустую строку")
        title = ""

    problem_data = {
        "id": problem_id,
        "title": title,
        "url": url,
        "original_url": original_url,
        "lang": "ru",
        "text": text,
    }

    print(f"[OK] Задача {problem_id}: {title}")
    return problem_data


def main():
    session = requests.Session()

    total = get_total_problems(session)  # например, 851
    print(f"[INFO] Буду парсить задачи с 1 по {total}")

    problems: List[Dict] = []

    for problem_id in range(1, total + 1):
        data = fetch_problem(session, problem_id)
        if data is not None:
            problems.append(data)
        # маленькая пауза, чтобы не долбить сайт слишком агрессивно
        time.sleep(0.2)

    output_file = "euler_ru.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Сохранено задач: {len(problems)} в файл {output_file}")


if __name__ == "__main__":
    main()
