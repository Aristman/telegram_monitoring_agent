"""
Базовый класс для анализаторов сообщений
"""

import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class BaseMessageAnalyzer:
    """Базовый класс для анализаторов сообщений с помощью Yandex GPT"""

    def __init__(self, gpt_client):
        """
        Args:
            gpt_client: Экземпляр YandexGPTClient
        """
        self.gpt_client = gpt_client

    def _format_messages_for_summary(self, messages: List[Dict[str, Any]]) -> str:
        """
        Форматирование сообщений для суммаризации
        
        Args:
            messages: Список сообщений с полями timestamp, sender_name, text
            
        Returns:
            Отформатированная строка сообщений
        """
        formatted_messages = []

        for msg in messages:
            # Обрабатываем timestamp как строку или datetime объект
            timestamp_value = msg['timestamp']
            if isinstance(timestamp_value, str):
                # Парсим ISO формат строки в datetime
                try:
                    timestamp_obj = datetime.fromisoformat(timestamp_value)
                    timestamp = timestamp_obj.strftime("%H:%M")
                except (ValueError, AttributeError):
                    # Если не удалось распарсить, используем строку как есть
                    timestamp = timestamp_value[:5] if len(timestamp_value) >= 5 else timestamp_value
            elif isinstance(timestamp_value, datetime):
                timestamp = timestamp_value.strftime("%H:%M")
            else:
                timestamp = str(timestamp_value)
            
            sender = msg['sender_name']
            text = msg['text']

            formatted_messages.append(f"[{timestamp}] {sender}: {text}")

        return "\n".join(formatted_messages)
