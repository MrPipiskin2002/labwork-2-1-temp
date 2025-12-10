from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from app.domain.models import (
    Task,
    UserSession,
    UserTaskResult,
)
from app.infrastructure.session_repository import UserSessionRepository
from app.infrastructure.task_repositories import (
    EulerTaskRepository,
    LevelTaskRepository,
)
from app.infrastructure.llm_client import LLMClient


def _normalize_answer(value: str) -> str:
    return value.strip().lower().replace(" ", "")


@dataclass
class AnswerResult:
    mode: str                    # "euler" или "level"
    is_correct: bool
    user_answer: str
    correct_answer: str
    task: Task
    next_task: Optional[Task]
    finished_round: bool = False
    gave_up: bool = False        # True, если пользователь нажал "Готовое решение" в режиме уровня


@dataclass
class LevelRoundSummary:
    level: str
    total: int
    correct_count: int
    results: List[UserTaskResult]


class MathTaskService:
    """
    Бизнес-логика бота: выбор задач, проверка ответов, подсказки, решения.
    """

    def __init__(
        self,
        euler_repo: EulerTaskRepository,
        level_repo: LevelTaskRepository,
        session_repo: UserSessionRepository,
        llm_client: LLMClient,
    ) -> None:
        self.euler_repo = euler_repo
        self.level_repo = level_repo
        self.session_repo = session_repo
        self.llm_client = llm_client

    # -------- Общие методы работы с сессией --------

    def _get_session(self, user_id: int) -> UserSession:
        return self.session_repo.get_or_create(user_id)

    def reset_session(self, user_id: int) -> None:
        self.session_repo.reset(user_id)

    def is_waiting_for_answer(self, user_id: int) -> bool:
        session = self._get_session(user_id)
        return session.waiting_for_answer and session.expected_task_id is not None

    # -------- Project Euler --------

    def start_euler_session(self, user_id: int, num_tasks: int = 10) -> Optional[Task]:
        session = self._get_session(user_id)
        session.reset()
        session.mode = "euler"

        tasks = self.euler_repo.get_random_tasks(num_tasks)
        session.current_task_ids = [t.id for t in tasks]
        session.current_index = 0
        session.waiting_for_answer = False
        session.expected_task_id = None

        self.session_repo.save(session)

        return tasks[0] if tasks else None

    def get_current_task(self, user_id: int) -> Optional[Task]:
        session = self._get_session(user_id)
        task_id = session.get_current_task_id()
        if task_id is None:
            return None

        if session.mode == "euler":
            return self.euler_repo.get_task_by_id(task_id)
        elif session.mode == "level":
            return self.level_repo.get_task_by_id(task_id)
        return None

    def _goto_next_task(self, session: UserSession) -> Optional[Task]:
        session.current_index += 1
        if session.current_index >= len(session.current_task_ids):
            return None

        if session.mode == "euler":
            return self.euler_repo.get_task_by_id(session.current_task_ids[session.current_index])
        elif session.mode == "level":
            return self.level_repo.get_task_by_id(session.current_task_ids[session.current_index])
        return None

    def request_answer_for_current_task(self, user_id: int) -> Optional[Task]:
        session = self._get_session(user_id)
        task = self.get_current_task(user_id)
        if task is None:
            return None
        session.waiting_for_answer = True
        session.expected_task_id = task.id
        self.session_repo.save(session)
        return task

    def submit_answer(self, user_id: int, user_answer: str) -> Optional[AnswerResult]:
        """
        Обработка текстового ответа пользователя.
        Внутри смотрим, в каком режиме находится пользователь.
        """
        session = self._get_session(user_id)
        if not session.waiting_for_answer or session.expected_task_id is None:
            return None

        task = self.get_current_task(user_id)
        if task is None or task.id != session.expected_task_id:
            # На всякий случай перестрахуемся
            session.waiting_for_answer = False
            session.expected_task_id = None
            self.session_repo.save(session)
            return None

        mode = session.mode
        session.waiting_for_answer = False
        session.expected_task_id = None

        if mode == "euler":
            result = self._submit_answer_euler(session, task, user_answer)
        elif mode == "level":
            result = self._submit_answer_level(session, task, user_answer)
        else:
            result = None

        self.session_repo.save(session)
        return result

    def _submit_answer_euler(
        self,
        session: UserSession,
        task: Task,
        user_answer: str,
    ) -> AnswerResult:
        # Получаем правильный ответ от нейросети
        correct_answer = self.llm_client.get_short_answer(task)
        is_correct = _normalize_answer(user_answer) == _normalize_answer(correct_answer)

        # После ответа переходим к следующей задаче
        next_task = self._goto_next_task(session)
        finished_round = next_task is None

        return AnswerResult(
            mode="euler",
            is_correct=is_correct,
            user_answer=user_answer,
            correct_answer=correct_answer,
            task=task,
            next_task=next_task,
            finished_round=finished_round,
            gave_up=False,
        )

    # -------- Режим задач по уровню --------

    def start_level_round(self, user_id: int, level: str, num_tasks: int = 5) -> Optional[Task]:
        session = self._get_session(user_id)
        session.reset()
        session.mode = "level"
        session.level = level

        tasks = self.level_repo.get_random_tasks_for_level(level, num_tasks)
        session.current_task_ids = [t.id for t in tasks]
        session.current_index = 0
        session.results.clear()
        session.waiting_for_answer = False
        session.expected_task_id = None

        self.session_repo.save(session)

        return tasks[0] if tasks else None

    def _submit_answer_level(
        self,
        session: UserSession,
        task: Task,
        user_answer: str,
    ) -> AnswerResult:
        correct_answer = task.answer or ""
        is_correct = _normalize_answer(user_answer) == _normalize_answer(correct_answer)

        finished_round = False
        next_task: Optional[Task]

        if is_correct:
            # Фиксируем окончательный результат по задаче
            session.results.append(
                UserTaskResult(
                    task_id=task.id,
                    user_answer=user_answer,
                    correct_answer=correct_answer,
                    is_correct=True,
                    gave_up=False,
                )
            )
            next_task = self._goto_next_task(session)
            finished_round = next_task is None
        else:
            # Ответ неверный — остаёмся на той же задаче
            next_task = task

        return AnswerResult(
            mode="level",
            is_correct=is_correct,
            user_answer=user_answer,
            correct_answer=correct_answer,
            task=task,
            next_task=next_task,
            finished_round=finished_round,
            gave_up=False,
        )

    def give_hint_for_current_task(self, user_id: int) -> Optional[str]:
        task = self.get_current_task(user_id)
        if task is None:
            return None
        return self.llm_client.get_hint(task)

    def give_solution_for_current_task_euler(self, user_id: int) -> Optional[str]:
        """
        Готовое решение в режиме Project Euler.
        Пользователь может всё равно потом ответить (отдельной кнопкой).
        """
        task = self.get_current_task(user_id)
        if task is None:
            return None
        return self.llm_client.get_solution(task)

    def give_up_and_get_solution_level(self, user_id: int) -> Optional[AnswerResult]:
        """
        В режиме 'уровень': пользователь нажал 'Готовое решение' = сдаться.
        """
        session = self._get_session(user_id)
        if session.mode != "level":
            return None

        task = self.get_current_task(user_id)
        if task is None:
            return None

        solution_text = self.llm_client.get_solution(task)
        correct_answer = task.answer or ""

        # Фиксируем результат как "сдался"
        session.results.append(
            UserTaskResult(
                task_id=task.id,
                user_answer="",
                correct_answer=correct_answer,
                is_correct=False,
                gave_up=True,
            )
        )

        next_task = self._goto_next_task(session)
        finished_round = next_task is None

        self.session_repo.save(session)

        # Возвращаем AnswerResult, где user_answer пустой, gave_up=True
        return AnswerResult(
            mode="level",
            is_correct=False,
            user_answer="",
            correct_answer=correct_answer,
            task=task,
            next_task=next_task,
            finished_round=finished_round,
            gave_up=True,
        ), solution_text

    def get_level_round_summary(self, user_id: int) -> Optional[LevelRoundSummary]:
        session = self._get_session(user_id)
        if session.mode != "level" or not session.level:
            return None

        total = len(session.results)
        correct_count = sum(1 for r in session.results if r.is_correct)

        return LevelRoundSummary(
            level=session.level,
            total=total,
            correct_count=correct_count,
            results=list(session.results),
        )
