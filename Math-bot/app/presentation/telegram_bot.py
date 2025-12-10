from __future__ import annotations

from typing import List, Optional

import telebot
from telebot import types

from app.domain.models import Task
from app.services.math_task_service import MathTaskService, AnswerResult, LevelRoundSummary
from app.config import LEVELS
from app.utils.text_normalizer import normalize_for_telegram_math


class TelegramMathBot:
    def __init__(self, tg_token: str, service: MathTaskService, levels: List[str]) -> None:
        self.bot = telebot.TeleBot(tg_token, parse_mode="HTML")
        self.service = service
        self.levels = levels

        self._register_handlers()

    # ---------- Клавиатуры ----------

    def _main_menu_keyboard(self) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(types.KeyboardButton("Задачи Project Euler"))
        kb.row(types.KeyboardButton("Задачи по уровню"))
        kb.row(types.KeyboardButton("Остановить"))
        return kb

    def _levels_keyboard(self) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        row: List[types.KeyboardButton] = []
        for level in self.levels:
            row.append(types.KeyboardButton(level))
            if len(row) == 2:
                kb.row(*row)
                row = []
        if row:
            kb.row(*row)
        kb.row(types.KeyboardButton("Остановить"))
        return kb

    def _task_inline_keyboard(self, mode: str, task_id: int) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup()
        prefix = "euler" if mode == "euler" else "level"

        kb.row(
            types.InlineKeyboardButton("Ответить", callback_data=f"{prefix}_answer:{task_id}"),
            types.InlineKeyboardButton("Подсказка", callback_data=f"{prefix}_hint:{task_id}"),
        )
        kb.row(
            types.InlineKeyboardButton("Готовое решение", callback_data=f"{prefix}_solution:{task_id}")
        )
        kb.row(
            types.InlineKeyboardButton("Остановить", callback_data="stop")
        )
        return kb

    def _after_level_round_keyboard(self, can_go_next: bool) -> types.InlineKeyboardMarkup:
        kb = types.InlineKeyboardMarkup()
        if can_go_next:
            kb.row(types.InlineKeyboardButton("Следующий уровень", callback_data="level_next"))
        kb.row(types.InlineKeyboardButton("Повторить уровень", callback_data="level_retry"))
        kb.row(types.InlineKeyboardButton("Выход в меню", callback_data="to_menu"))
        return kb

    # ---------- Отправка задач ----------

    def _format_task_text(self, task: Task, idx: int, total: int, source: str) -> str:
        header = (
            f"[{source}] Задача {idx} из {total}\n"
            f"ID: {task.id}\n"
            f"{task.title}\n\n"
        )
        body = normalize_for_telegram_math(task.text)
        return header + body

    def _format_euler_task(self, task: Task, position: int, total: int) -> str:
        title = normalize_for_telegram_math(task.title)
        body = normalize_for_telegram_math(task.text)
        url = normalize_for_telegram_math(task.url) if task.url else None

        parts = [
            f"<b>[Project Euler] Задача {position} из {total}</b>",
            f"ID: {task.id}",
            f"<b>{title}</b>",
            "",
            body,
        ]
        if url:
            parts.append(f"\nСайт: {url}")
        return "\n".join(parts)

    def _format_level_task(self, task: Task, position: int, total: int, level: str) -> str:
        title = normalize_for_telegram_math(task.title)
        body = normalize_for_telegram_math(task.text)

        parts = [
            f"<b>[Уровень: {level}] Задача {position} из {total}</b>",
            f"ID: {task.id}",
            f"<b>{title}</b>",
            "",
            body,
        ]
        return "\n".join(parts)

    def _send_euler_task(self, chat_id: int, task: Task, index: int, total: int) -> None:
        text = self._format_euler_task(task, index + 1, total)
        kb = self._task_inline_keyboard("euler", task.id)
        self.bot.send_message(chat_id, text, reply_markup=kb)

    def _send_level_task(self, chat_id: int, task: Task, index: int, total: int, level: str) -> None:
        text = self._format_level_task(task, index + 1, total, level)
        kb = self._task_inline_keyboard("level", task.id)
        self.bot.send_message(chat_id, text, reply_markup=kb)

    # ---------- Регистрация хэндлеров ----------

    def _register_handlers(self) -> None:
        @self.bot.message_handler(commands=["start"])
        def handle_start(message: types.Message) -> None:
            self.service.reset_session(message.from_user.id)
            self.bot.send_message(
                message.chat.id,
                "Привет! Я бот для тренировки по математике.\n\n"
                "Доступные режимы:\n"
                "• Задачи Project Euler (10 случайных задач)\n"
                "• Задачи по уровню (5 задач с выбранного уровня)\n\n"
                "В любой момент ты можешь нажать «Остановить», чтобы завершить сессию.",
                reply_markup=self._main_menu_keyboard(),
            )

        @self.bot.message_handler(commands=["stop"])
        @self.bot.message_handler(func=lambda m: m.text == "Остановить")
        def handle_stop(message: types.Message) -> None:
            self.service.reset_session(message.from_user.id)
            self.bot.send_message(
                message.chat.id,
                "Сессия завершена. Можешь начать заново, выбрав режим.",
                reply_markup=self._main_menu_keyboard(),
            )

        @self.bot.message_handler(func=lambda m: m.text == "Задачи Project Euler")
        def handle_euler_entry(message: types.Message) -> None:
            user_id = message.from_user.id
            first_task = self.service.start_euler_session(user_id, num_tasks=10)
            if first_task is None:
                self.bot.send_message(
                    message.chat.id,
                    "Не удалось загрузить задачи Project Euler.",
                    reply_markup=self._main_menu_keyboard(),
                )
                return

            total = 10  # мы запрашивали 10 задач
            self.bot.send_message(
                message.chat.id,
                "Начинаем сессию Project Euler: 10 случайных задач.\n"
                "Для каждой задачи доступны действия: Ответить, Подсказка, Готовое решение.",
            )
            self._send_euler_task(message.chat.id, first_task, 0, total)

        @self.bot.message_handler(func=lambda m: m.text == "Задачи по уровню")
        def handle_level_entry(message: types.Message) -> None:
            user_id = message.from_user.id
            self.service.reset_session(user_id)
            self.bot.send_message(
                message.chat.id,
                "Выбери уровень (класс/курс). После выбора ты получишь 5 задач.",
                reply_markup=self._levels_keyboard(),
            )

        @self.bot.message_handler(func=lambda m: m.text in LEVELS)
        def handle_level_choice(message: types.Message) -> None:
            user_id = message.from_user.id
            level = message.text
            first_task = self.service.start_level_round(user_id, level=level, num_tasks=5)
            if first_task is None:
                self.bot.send_message(
                    message.chat.id,
                    f"Для уровня {level} пока нет задач.",
                    reply_markup=self._main_menu_keyboard(),
                )
                return

            self.bot.send_message(
                message.chat.id,
                f"Уровень установлен: {level}. "
                f"Сейчас ты получишь 5 задач одну за другой.",
                reply_markup=self._main_menu_keyboard(),
            )
            self._send_level_task(message.chat.id, first_task, 0, 5, level)

        # ----- CallbackQuery: действия по задачам -----

        @self.bot.callback_query_handler(func=lambda c: c.data == "stop")
        def handle_stop_callback(call: types.CallbackQuery) -> None:
            user_id = call.from_user.id
            self.service.reset_session(user_id)
            self.bot.answer_callback_query(call.id, "Сессия остановлена.")
            self.bot.send_message(
                call.message.chat.id,
                "Сессия завершена. Можешь начать заново, выбрав режим.",
                reply_markup=self._main_menu_keyboard(),
            )

        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("euler_"))
        def handle_euler_callbacks(call: types.CallbackQuery) -> None:
            user_id = call.from_user.id
            data = call.data  # euler_answer:ID / euler_hint:ID / euler_solution:ID
            action, raw_id = data.split(":")
            task_id = int(raw_id)

            if action == "euler_answer":
                task = self.service.request_answer_for_current_task(user_id)
                if task is None:
                    self.bot.answer_callback_query(call.id, "Нет активной задачи.")
                    return
                self.bot.answer_callback_query(call.id)
                self.bot.send_message(
                    call.message.chat.id,
                    f"Напиши свой ответ на задачу #{task.id} одним сообщением.",
                )


            elif action == "euler_hint":
                hint = self.service.give_hint_for_current_task(user_id)
                self.bot.answer_callback_query(call.id)
                if hint is None:
                    self.bot.send_message(call.message.chat.id, "Нет активной задачи.")
                else:
                    hint_text = normalize_for_telegram_math(hint)
                    self.bot.send_message(call.message.chat.id, f"<b>Подсказка:</b>\n{hint_text}")

            elif action == "euler_solution":
                solution = self.service.give_solution_for_current_task_euler(user_id)
                self.bot.answer_callback_query(call.id)
                if solution is None:
                    self.bot.send_message(call.message.chat.id, "Нет активной задачи.")
                else:
                    solution_text = normalize_for_telegram_math(solution)
                    self.bot.send_message(call.message.chat.id, f"<b>Решение:</b>\n{solution_text}")

        @self.bot.callback_query_handler(func=lambda c: c.data.startswith("level_"))
        def handle_level_callbacks(call: types.CallbackQuery) -> None:
            user_id = call.from_user.id
            data = call.data  # level_answer:ID / level_hint:ID / level_solution:ID
            action, raw_id = data.split(":")
            task_id = int(raw_id)

            if action == "level_answer":
                task = self.service.request_answer_for_current_task(user_id)
                if task is None:
                    self.bot.answer_callback_query(call.id, "Нет активной задачи.")
                    return
                self.bot.answer_callback_query(call.id)
                self.bot.send_message(
                    call.message.chat.id,
                    f"Напиши свой ответ на задачу #{task.id} одним сообщением.",
                )


            elif action == "level_hint":
                hint = self.service.give_hint_for_current_task(user_id)
                self.bot.answer_callback_query(call.id)
                if hint is None:
                    self.bot.send_message(call.message.chat.id, "Нет активной задачи.")
                else:
                    hint_text = normalize_for_telegram_math(hint)
                    self.bot.send_message(call.message.chat.id, f"<b>Подсказка:</b>\n{hint_text}")


            elif action == "level_solution":
                result_and_solution = self.service.give_up_and_get_solution_level(user_id)
                self.bot.answer_callback_query(call.id)
                if result_and_solution is None:
                    self.bot.send_message(call.message.chat.id, "Нет активной задачи.")
                    return
                result, solution = result_and_solution
                solution_text = normalize_for_telegram_math(solution)
                self.bot.send_message(
                    call.message.chat.id,
                    f"<b>Решение:</b>\n{solution_text}\n\n"
                    "Эта задача засчитана как 'сдача' (балл не начисляется).",
                )

                if result.next_task is not None:
                    # Переходим к следующей задаче
                    # Здесь мы не знаем индекс напрямую, поэтому при выводе просто выводим "следующая"
                    # Для простоты считаем, что всегда 5 задач.
                    level = "текущий уровень"
                    self._send_level_task(
                        call.message.chat.id,
                        result.next_task,
                        index=0,  # позицию можно не указывать точно, если не важно
                        total=5,
                        level=level,
                    )
                else:
                    # Раунд завершён — покажем результаты
                    summary = self.service.get_level_round_summary(user_id)
                    if summary is not None:
                        self._send_level_summary(call.message.chat.id, summary)

        @self.bot.callback_query_handler(func=lambda c: c.data in {"level_next", "level_retry", "to_menu"})
        def handle_level_after_round(call: types.CallbackQuery) -> None:
            user_id = call.from_user.id
            data = call.data
            session_summary = self.service.get_level_round_summary(user_id)

            if data == "to_menu":
                self.service.reset_session(user_id)
                self.bot.answer_callback_query(call.id)
                self.bot.send_message(
                    call.message.chat.id,
                    "Возвращаемся в главное меню.",
                    reply_markup=self._main_menu_keyboard(),
                )
                return

            if session_summary is None:
                self.bot.answer_callback_query(call.id, "Нет активного результата уровня.")
                return

            current_level = session_summary.level
            self.bot.answer_callback_query(call.id)

            if data == "level_retry":
                # Повторить тот же уровень
                first_task = self.service.start_level_round(user_id, level=current_level, num_tasks=5)
                if first_task is None:
                    self.bot.send_message(call.message.chat.id, f"Для уровня {current_level} нет задач.")
                    return
                self.bot.send_message(
                    call.message.chat.id,
                    f"Повторяем уровень {current_level}: новые 5 задач.",
                    reply_markup=self._main_menu_keyboard(),
                )
                self._send_level_task(call.message.chat.id, first_task, 0, 5, current_level)
            elif data == "level_next":
                # Переходим на следующий уровень, если он есть
                if current_level not in LEVELS:
                    self.bot.send_message(
                        call.message.chat.id,
                        "Не удалось определить следующий уровень.",
                        reply_markup=self._main_menu_keyboard(),
                    )
                    return
                idx = LEVELS.index(current_level)
                if idx + 1 >= len(LEVELS):
                    self.bot.send_message(
                        call.message.chat.id,
                        "Следующего уровня нет. Это был максимальный уровень.",
                        reply_markup=self._main_menu_keyboard(),
                    )
                    return
                next_level = LEVELS[idx + 1]
                first_task = self.service.start_level_round(user_id, level=next_level, num_tasks=5)
                if first_task is None:
                    self.bot.send_message(
                        call.message.chat.id,
                        f"Для уровня {next_level} пока нет задач.",
                        reply_markup=self._main_menu_keyboard(),
                    )
                    return
                self.bot.send_message(
                    call.message.chat.id,
                    f"Переходим на следующий уровень: {next_level}.",
                    reply_markup=self._main_menu_keyboard(),
                )
                self._send_level_task(call.message.chat.id, first_task, 0, 5, next_level)

        # ----- Обработка текстовых ответов -----

        @self.bot.message_handler(func=lambda m: True)
        def handle_free_text(message: types.Message) -> None:
            user_id = message.from_user.id

            # Если ждём ответ на задачу
            if self.service.is_waiting_for_answer(user_id):
                result = self.service.submit_answer(user_id, message.text)
                if result is None:
                    self.bot.send_message(
                        message.chat.id,
                        "Не удалось обработать ответ. Попробуй ещё раз.",
                    )
                    return
                self._process_answer_result(message.chat.id, result)
            else:
                # Любой другой текст вне контекста — мягко отправим в меню
                if message.text not in {
                    "Задачи Project Euler",
                    "Задачи по уровню",
                    "Остановить",
                } and not message.text.startswith("/"):
                    self.bot.send_message(
                        message.chat.id,
                        "Я тебя не понял. Используй кнопки меню или команды /start /stop.",
                    )

    # ---------- Обработка результатов ответов ----------

    def _process_answer_result(self, chat_id: int, result: AnswerResult) -> None:
        if result.mode == "euler":
            status = "✅ Верно!" if result.is_correct else "❌ Неверно."
            text = (
                f"{status}\n\n"
                f"Твой ответ: {result.user_answer}\n"
                f"Ответ нейросети: {result.correct_answer}"
            )
            self.bot.send_message(chat_id, text)

            if result.next_task is not None:
                # Для простоты считаем, что всегда 10 задач
                self._send_euler_task(chat_id, result.next_task, index=0, total=10)
            else:
                self.bot.send_message(
                    chat_id,
                    "Это была последняя задача из набора.",
                    reply_markup=self._main_menu_keyboard(),
                )

        elif result.mode == "level":
            if result.is_correct:
                status = "✅ Верно!"
                text = (
                    f"{status}\n\n"
                    f"Твой ответ: {result.user_answer}\n"
                    f"Правильный ответ: {result.correct_answer}"
                )
                self.bot.send_message(chat_id, text)
                if result.next_task is not None:
                    # Здесь мы знаем, что задач всего 5
                    self._send_level_task(chat_id, result.next_task, index=0, total=5, level="текущий уровень")
                else:
                    # Раунд завершён, покажем результаты
                    summary = self.service.get_level_round_summary(chat_id)
                    if summary is not None:
                        self._send_level_summary(chat_id, summary)
            else:
                # Неверный ответ: остаёмся на той же задаче
                text = (
                    "❌ Неверно.\n"
                    "Попробуй ещё раз или воспользуйся подсказкой / готовым решением."
                )
                self.bot.send_message(chat_id, text)

    def _send_level_summary(self, chat_id: int, summary: LevelRoundSummary) -> None:
        lines = [
            f"<b>Результаты по уровню \"{summary.level}\":</b>",
            "",
            f"Всего задач: {summary.total}",
            f"Правильных ответов: {summary.correct_count} из {summary.total}",
            "",
        ]
        for res in summary.results:
            mark = "✅" if res.is_correct else "❌"
            user_ans = res.user_answer if res.user_answer else "(пользователь сдался)"
            lines.append(
                f"Задача #{res.task_id}: {mark}\n"
                f"  Правильный ответ: {res.correct_answer}\n"
                f"  Твой ответ: {user_ans}\n"
            )

        text = "\n".join(lines)

        can_go_next = summary.correct_count == summary.total and summary.level in LEVELS
        kb = self._after_level_round_keyboard(can_go_next=can_go_next)
        self.bot.send_message(chat_id, text, reply_markup=kb)

    # ---------- Запуск ----------

    def run(self) -> None:
        self.bot.infinity_polling()
