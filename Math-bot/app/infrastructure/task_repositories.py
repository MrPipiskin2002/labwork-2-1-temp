from __future__ import annotations

import json
import random
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict

from app.domain.models import Task


class BaseTaskRepository(ABC):
    @abstractmethod
    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        ...


class EulerTaskRepository(BaseTaskRepository, ABC):
    @abstractmethod
    def get_random_tasks(self, n: int) -> List[Task]:
        ...


class LevelTaskRepository(BaseTaskRepository, ABC):
    @abstractmethod
    def get_random_tasks_for_level(self, level: str, n: int) -> List[Task]:
        ...


class JsonEulerTaskRepository(EulerTaskRepository):
    """
    Репозиторий задач Project Euler из euler_ru.json
    Структура файла (пример):
    [
      {
        "id": 1,
        "title": "...",
        "url": "...",
        "original_url": "...",
        "lang": "ru",
        "text": "..."
      },
      ...
    ]
    """

    def __init__(self, json_path: Path) -> None:
        self._tasks_by_id: Dict[int, Task] = {}
        self._load(json_path)

    def _load(self, json_path: Path) -> None:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            task = Task(
                id=item["id"],
                title=item.get("title", f"Euler #{item['id']}"),
                text=item.get("text", ""),
                lang=item.get("lang", "ru"),
                level=None,
                answer=None,
                source="euler",
                url=item.get("url"),
                original_url=item.get("original_url"),
            )
            self._tasks_by_id[task.id] = task

    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        return self._tasks_by_id.get(task_id)

    def get_random_tasks(self, n: int) -> List[Task]:
        all_tasks = list(self._tasks_by_id.values())
        if not all_tasks:
            return []
        if n >= len(all_tasks):
            return random.sample(all_tasks, len(all_tasks))
        return random.sample(all_tasks, n)


class JsonLevelTaskRepository(LevelTaskRepository):
    """
    Репозиторий задач по уровням из level_tasks_ru.json
    Структура файла:
    [
      {
        "id": 1,
        "title": "Название задачи",
        "level": "5 класс",
        "lang": "ru",
        "text": "Текст условия...",
        "answer": "42"
      },
      ...
    ]
    """

    def __init__(self, json_path: Path) -> None:
        self._tasks_by_id: Dict[int, Task] = {}
        self._tasks_by_level: Dict[str, List[Task]] = {}
        self._load(json_path)

    def _load(self, json_path: Path) -> None:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            level = item["level"]
            task = Task(
                id=item["id"],
                title=item.get("title", f"Задача #{item['id']}"),
                text=item.get("text", ""),
                lang=item.get("lang", "ru"),
                level=level,
                answer=item.get("answer"),
                source="level",
            )
            self._tasks_by_id[task.id] = task
            self._tasks_by_level.setdefault(level, []).append(task)

    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        return self._tasks_by_id.get(task_id)

    def get_random_tasks_for_level(self, level: str, n: int) -> List[Task]:
        tasks = self._tasks_by_level.get(level, [])
        if not tasks:
            return []
        if n >= len(tasks):
            return random.sample(tasks, len(tasks))
        return random.sample(tasks, n)
