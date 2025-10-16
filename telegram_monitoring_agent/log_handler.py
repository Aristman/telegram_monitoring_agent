"""
Кастомный обработчик логов для записи в базу данных
"""

import logging
from datetime import datetime
from typing import Optional


class DatabaseLogHandler(logging.Handler):
    """Обработчик логов для записи в базу данных"""

    def __init__(self, database=None):
        super().__init__()
        self.database = database
        self._enabled = False

    def set_database(self, database):
        """Установка экземпляра базы данных"""
        self.database = database
        self._enabled = True

    def emit(self, record: logging.LogRecord):
        """Обработка записи лога"""
        if not self._enabled or not self.database:
            return

        try:
            # Форматируем сообщение
            message = self.format(record)
            
            # Сохраняем в БД
            timestamp = datetime.fromtimestamp(record.created)
            self.database.save_log(
                timestamp=timestamp,
                level=record.levelname,
                logger_name=record.name,
                message=message
            )

        except Exception:
            # Не вызываем handleError чтобы избежать рекурсии
            pass
