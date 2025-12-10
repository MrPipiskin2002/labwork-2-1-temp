from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from app.utils.text_normalizer import extract_plain_answer

from gigachat import GigaChat

from app.domain.models import Task
from app.config import (
    GIGACHAT_CREDENTIALS,
    GIGACHAT_SCOPE,
    GIGACHAT_MODEL,
    GIGACHAT_VERIFY_SSL_CERTS,
)


class LLMClient(ABC):
    """
    Интерфейс клиента к нейросети.
    """

    @abstractmethod
    def get_hint(self, task: Task) -> str:
        """
        Краткая подсказка без раскрытия полного решения.
        """
        ...

    @abstractmethod
    def get_solution(self, task: Task) -> str:
        """
        Полное решение с объяснением (для показа пользователю).
        """
        ...

    @abstractmethod
    def get_short_answer(self, task: Task) -> str:
        """
        Краткий окончательный ответ (например, число или выражение),
        без пояснений. Используется для проверки ответа (режим Euler).
        """
        ...


class DummyLLMClient(LLMClient):
    """
    Заглушка для разработки без реальной нейросети.
    Можно оставить на всякий случай.
    """

    def get_hint(self, task: Task) -> str:
        return "Здесь могла быть подсказка от GigaChat 🙂."

    def get_solution(self, task: Task) -> str:
        return (
            "Здесь могло быть подробное решение от GigaChat.\n\n"
            "Сейчас используется заглушка."
        )

    def get_short_answer(self, task: Task) -> str:
        # Для отладки просто возвращаем фиктивный ответ
        return "42"


class GigaChatLLMClient(LLMClient):
    """
    Реализация клиента LLM через Sber GigaChat (через Python SDK `gigachat`).
    Используем Authorization Key (credentials) и Freemium-режим.
    """

    def __init__(
        self,
        credentials: str | None = None,
        scope: str | None = None,
        model: str | None = None,
        verify_ssl_certs: bool = False,
    ) -> None:
        # Если параметры не переданы явно, берём из config/env
        self.credentials = credentials or GIGACHAT_CREDENTIALS
        self.scope = scope or GIGACHAT_SCOPE
        self.model = model or GIGACHAT_MODEL
        self.verify_ssl_certs = verify_ssl_certs or GIGACHAT_VERIFY_SSL_CERTS

    # -------- Внутренний метод обращения к GigaChat --------

    def _chat(self, prompt: str) -> str:
        """
        Делает один запрос к GigaChat с указанным промптом и возвращает text-ответ модели.
        """
        if not self.credentials or self.credentials.startswith("PUT_YOUR_GIGACHAT"):
            raise RuntimeError(
                "GigaChat credentials не заданы. "
                "Заполни GIGACHAT_CREDENTIALS в .env или app/config.py."
            )

        kwargs: dict[str, Any] = {
            "credentials": self.credentials,
            "verify_ssl_certs": self.verify_ssl_certs,
        }
        if self.scope:
            kwargs["scope"] = self.scope
        if self.model:
            kwargs["model"] = self.model

        # SDK сам получит access_token по Authorization Key и переиспользует его
        with GigaChat(**kwargs) as giga:
            response = giga.chat(prompt)
        # Ответ в стиле OpenAI: choices[0].message.content
        return response.choices[0].message.content

    # -------- Публичные методы, используемые сервисом бота --------

    def get_hint(self, task: Task) -> str:
        prompt = f"""Ты — доброжелательный репетитор по математике.

Задача:
{task.text}

Сгенерируй ОДНУ краткую подсказку (1–3 предложения), которая помогает продвинуться к решению,
но НЕ раскрывает полный ход решения и НЕ содержит окончательного числового ответа."""
        return self._chat(prompt).strip()

    def get_solution(self, task: Task) -> str:
        """
        Подробное решение для вывода пользователю.
        Специально не жёстко форматируем ответ — просто просим «решить подробно».
        """
        prompt = f"""Ты — строгий, но понятный преподаватель математики.

Задача:
{task.text}

Реши задачу подробно, шаг за шагом.
Объясняй логику так, чтобы это понял студент соответствующего уровня.
В конце можно явно выделить строку с окончательным ответом в формате
"Ответ: ...", но это не обязательно."""
        return self._chat(prompt).strip()

    def get_short_answer(self, task: Task) -> str:
        """
        Просим GigaChat вернуть только конечный ответ, без текста.
        Используется в режиме Project Euler для автоматической проверки.
        """
        prompt = f"""Дана задача по математике.

        Задача:
        {task.text}

        Найди ЕДИНСТВЕННЫЙ окончательный ответ задачи.

        ТОЛЬКО ответ:
        - без пояснений;
        - без текста до или после;
        - без слова "Ответ";
        - без TeX / LaTeX (не используй $, \\, \\frac, \\sqrt и т.п.);
        - только одно число (если ответ числовой) или короткое выражение.

        Не добавляй ничего, кроме самого ответа."""

        raw = self._chat(prompt)
        return extract_plain_answer(raw)

