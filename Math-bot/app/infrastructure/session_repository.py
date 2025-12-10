from __future__ import annotations

from typing import Dict

from app.domain.models import UserSession


class UserSessionRepository:
    """
    Простое in-memory хранилище сессий пользователей.
    Для учебного проекта достаточно.
    """
    def __init__(self) -> None:
        self._sessions: Dict[int, UserSession] = {}

    def get_or_create(self, user_id: int) -> UserSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(user_id=user_id)
        return self._sessions[user_id]

    def save(self, session: UserSession) -> None:
        self._sessions[session.user_id] = session

    def reset(self, user_id: int) -> None:
        session = self.get_or_create(user_id)
        session.reset()
        self.save(session)
