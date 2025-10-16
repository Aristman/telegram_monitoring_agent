"""
Анализатор для общей суммаризации сообщений
"""

import logging
from typing import Dict, Any, List, Optional

from ..base_analyzer import BaseMessageAnalyzer

logger = logging.getLogger(__name__)


class SummaryAnalyzer(BaseMessageAnalyzer):
    """Анализатор для общей суммаризации сообщений"""

    async def summarize_daily_messages(
        self,
        chat_title: str,
        messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Суммаризация дневных сообщений"""
        try:
            if not messages:
                return "За день не было сообщений."

            # Форматируем сообщения
            formatted_messages = self._format_messages_for_summary(messages)

            # Формируем системный промпт
            system_prompt = """Ты - аналитик, который создает краткие и полезные сводки сообщений из Telegram чатов.

Твоя задача:
1. Проанализировать сообщения за день
2. Сгруппировать по темам и обсуждениям
3. Выделить ключевых участников и их вклад
4. Создать структурированную сводку
5. Приложить ссылки на сообщения, которые были использованы для суммаризации
6. В конце вывести ключевые ссылки из сообщений, которые были использованы для суммаризации

Формат вывода:
## 📊 Общая статистика
- Количество сообщений
- Активные участники
- Время активности

## 🎯 Основные темы
1. **Тема 1** - краткое описание
2. **Тема 2** - краткое описание

## 💬 Тематические обсуждения
- **Обсуждение 1**: описание и участники
- **Обсуждение 2**: описание и участники

## 📋 Важные моменты
- Ключевые решения
- Вопросы, требующие внимания
- Задачи и действия

Будь краток, но информативен. Используй Markdown форматирование."""

            # Формируем пользовательский промпт
            user_prompt = f"""Проанализируй сообщения из чата "{chat_title}" за день и создай сводку:

{formatted_messages}

Создай структурированную сводку согласно инструкциям выше."""

            # Генерируем сводку
            summary = await self.gpt_client.generate_completion(
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.3,
                max_tokens=2000
            )

            if summary:
                logger.info(f"Generated summary for chat '{chat_title}' with {len(messages)} messages")
                return summary
            else:
                logger.error(f"Failed to generate summary for chat '{chat_title}'")
                return None

        except Exception as e:
            logger.error(f"Error summarizing messages for chat '{chat_title}': {e}")
            return None

    async def create_thread_summary(
        self,
        chat_title: str,
        messages: List[Dict[str, Any]],
        thread_topic: str
    ) -> Optional[str]:
        """Создание сводки для тематической цепочки сообщений"""
        try:
            if not messages:
                return None

            # Форматируем сообщения
            formatted_messages = self._format_messages_for_summary(messages)

            # Формируем системный промпт
            system_prompt = """Ты - аналитик, который создает краткие сводки для тематических обсуждений в Telegram.

Твоя задача:
1. Проанализировать цепочку сообщений по конкретной теме
2. Выделить ключевые моменты и аргументы
3. Определить позиции участников
4. Создать краткую, но исчерпывающую сводку

Формат вывода:
## 🔗 Тема: [название темы]

**Участники:** список участников
**Длительность:** время обсуждения

### 📝 Суть обсуждения
Краткое описание основной темы

### 💬 Основные позиции
- **Участник 1**: позиция/аргумент
- **Участник 2**: позиция/аргумент

### 🎯 Ключевые моменты
- Важные выводы
- Решения
- Открытые вопросы

Будь объективен и лаконичен."""

            # Формируем пользовательский промпт
            user_prompt = f"""Проанализируй обсуждение на тему "{thread_topic}" в чате "{chat_title}":

{formatted_messages}

Создай сводку обсуждения согласно инструкциям выше."""

            # Генерируем сводку
            summary = await self.gpt_client.generate_completion(
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.2,
                max_tokens=1500
            )

            if summary:
                logger.info(f"Generated thread summary for '{thread_topic}' with {len(messages)} messages")
                return summary
            else:
                logger.error(f"Failed to generate thread summary for '{thread_topic}'")
                return None

        except Exception as e:
            logger.error(f"Error creating thread summary for '{thread_topic}': {e}")
            return None

    async def extract_topics(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Извлечение тем из сообщений"""
        try:
            if not messages:
                return []

            # Берем последнее сообщение для определения тем
            recent_messages = messages[-20:]  # Последние 20 сообщений
            formatted_messages = self._format_messages_for_summary(recent_messages)

            # Формируем системный промпт
            system_prompt = """Ты - аналитик, который определяет основные темы обсуждения в чате.

Твоя задача:
1. Проанализировать сообщения
2. Выделить основные темы
3. Кратко сформулировать каждую тему

Формат вывода:
Выведи только список тем, каждая с новой строки, без нумерации и дополнительных комментариев."""

            # Формируем пользовательский промпт
            user_prompt = f"""Определи основные темы в этих сообщениях:

{formatted_messages}

Выведи список основных тем обсуждения."""

            # Генерируем темы
            topics_text = await self.gpt_client.generate_completion(
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.1,
                max_tokens=200
            )

            if topics_text:
                # Парсим темы
                topics = []
                for line in topics_text.strip().split('\n'):
                    topic = line.strip().lstrip('-*•').strip()
                    if topic and len(topic) > 3:
                        topics.append(topic)

                logger.info(f"Extracted {len(topics)} topics from messages")
                return topics[:5]  # Возвращаем не более 5 тем

            return []

        except Exception as e:
            logger.error(f"Error extracting topics from messages: {e}")
            return []
