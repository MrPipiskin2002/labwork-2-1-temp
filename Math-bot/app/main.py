from __future__ import annotations

from app.config import (
    TELEGRAM_BOT_TOKEN,
    EULER_TASKS_PATH,
    LEVEL_TASKS_PATH,
    GIGACHAT_CREDENTIALS,
    GIGACHAT_SCOPE,
    GIGACHAT_MODEL,
    GIGACHAT_VERIFY_SSL_CERTS,
    LEVELS,
)
from app.infrastructure.task_repositories import (
    JsonEulerTaskRepository,
    JsonLevelTaskRepository,
)
from app.infrastructure.session_repository import UserSessionRepository
from app.infrastructure.llm_client import DummyLLMClient, GigaChatLLMClient
from app.services.math_task_service import MathTaskService
from app.presentation.telegram_bot import TelegramMathBot


def main() -> None:
    # Репозитории задач
    euler_repo = JsonEulerTaskRepository(EULER_TASKS_PATH)
    level_repo = JsonLevelTaskRepository(LEVEL_TASKS_PATH)

    # Хранилище сессий
    session_repo = UserSessionRepository()

    # --- Клиент LLM ---

    # Вариант 1: реальная нейросеть GigaChat (то, что тебе нужно)
    llm_client = GigaChatLLMClient(
        credentials=GIGACHAT_CREDENTIALS,
        scope=GIGACHAT_SCOPE,
        model=GIGACHAT_MODEL,
        verify_ssl_certs=GIGACHAT_VERIFY_SSL_CERTS,
    )

    # Вариант 2: заглушка (на случай, если хочешь отключить нейросеть для отладки)
    # llm_client = DummyLLMClient()

    # Сервис бизнес-логики
    service = MathTaskService(euler_repo, level_repo, session_repo, llm_client)

    # Telegram-бот
    bot = TelegramMathBot(TELEGRAM_BOT_TOKEN, service, levels=LEVELS)
    bot.run()


if __name__ == "__main__":
    main()
