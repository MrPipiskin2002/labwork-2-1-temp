from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, List

TaskSource = Literal["euler", "level"]
ModeType = Literal["euler", "level"]


@dataclass
class Task:
    """
    Универсальная модель задачи (Project Euler или по уровню).
    """
    id: int
    title: str
    text: str
    lang: str = "ru"
    level: Optional[str] = None          # "5 класс", "1 курс" и т.п.
    answer: Optional[str] = None         # для level-задач
    source: TaskSource = "level"         # "euler" или "level"
    url: Optional[str] = None            # для Project Euler
    original_url: Optional[str] = None   # для Project Euler


@dataclass
class UserTaskResult:
    """
    Результат по одной задаче в режиме 'уровень'.
    """
    task_id: int
    user_answer: str
    correct_answer: str
    is_correct: bool
    gave_up: bool


@dataclass
class UserSession:
    """
    Состояние пользователя в боте.
    """
    user_id: int

    # Текущий режим: Project Euler или задачи по уровню
    mode: Optional[ModeType] = None

    # Для режима "уровень"
    level: Optional[str] = None

    # Текущий набор задач (список id) и индекс текущей задачи
    current_task_ids: List[int] = field(default_factory=list)
    current_index: int = 0

    # Ожидаем ли текстовый ответ от пользователя
    waiting_for_answer: bool = False
    expected_task_id: Optional[int] = None

    # Результаты для текущего "захода" в режиме уровня
    results: List[UserTaskResult] = field(default_factory=list)

    def reset(self) -> None:
        """
        Полный сброс сессии.
        """
        self.mode = None
        self.level = None
        self.current_task_ids.clear()
        self.current_index = 0
        self.waiting_for_answer = False
        self.expected_task_id = None
        self.results.clear()

    def has_active_tasks(self) -> bool:
        return 0 <= self.current_index < len(self.current_task_ids)

    def get_current_task_id(self) -> Optional[int]:
        if self.has_active_tasks():
            return self.current_task_ids[self.current_index]
        return None
