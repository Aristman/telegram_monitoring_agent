"""
Базовый класс для анализаторов сообщений
"""

import logging
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
            timestamp = msg['timestamp'].strftime("%H:%M")
            sender = msg['sender_name']
            text = msg['text']

            formatted_messages.append(f"[{timestamp}] {sender}: {text}")

        return "\n".join(formatted_messages)
