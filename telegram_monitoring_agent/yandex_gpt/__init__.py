"""
Yandex GPT клиент и анализаторы сообщений
"""

from .client import YandexGPTClient
from .base_analyzer import BaseMessageAnalyzer
from .analyzers import (
    SummaryAnalyzer,
    InformationalAnalyzer,
    DiscussionAnalyzer,
    HowToAnalyzer,
)


class MessageSummarizer:
    """
    Класс-обёртка для обратной совместимости.
    Объединяет все анализаторы в один интерфейс.
    """

    def __init__(self, gpt_client: YandexGPTClient):
        self.gpt_client = gpt_client
        
        # Инициализируем все анализаторы
        self._summary_analyzer = SummaryAnalyzer(gpt_client)
        self._informational_analyzer = InformationalAnalyzer(gpt_client)
        self._discussion_analyzer = DiscussionAnalyzer(gpt_client)
        self._howto_analyzer = HowToAnalyzer(gpt_client)

    # Методы из SummaryAnalyzer
    async def summarize_daily_messages(self, chat_title: str, messages):
        """Суммаризация дневных сообщений"""
        return await self._summary_analyzer.summarize_daily_messages(chat_title, messages)

    async def create_thread_summary(self, chat_title: str, messages, thread_topic: str):
        """Создание сводки для тематической цепочки сообщений"""
        return await self._summary_analyzer.create_thread_summary(chat_title, messages, thread_topic)

    async def extract_topics(self, messages):
        """Извлечение тем из сообщений"""
        return await self._summary_analyzer.extract_topics(messages)

    # Методы из InformationalAnalyzer
    async def summarize_informational_messages(self, chat_title: str, messages):
        """Анализ и суммаризация информационных сообщений"""
        return await self._informational_analyzer.summarize_informational_messages(chat_title, messages)

    # Методы из DiscussionAnalyzer
    async def analyze_discussions_detailed(self, chat_title: str, messages):
        """Детальный анализ обсуждений"""
        return await self._discussion_analyzer.analyze_discussions_detailed(chat_title, messages)

    # Методы из HowToAnalyzer
    async def summarize_howto_content(self, chat_title: str, messages):
        """Анализ и суммаризация HowTo контента"""
        return await self._howto_analyzer.summarize_howto_content(chat_title, messages)


__all__ = [
    'YandexGPTClient',
    'MessageSummarizer',
    'BaseMessageAnalyzer',
    'SummaryAnalyzer',
    'InformationalAnalyzer',
    'DiscussionAnalyzer',
    'HowToAnalyzer',
]
