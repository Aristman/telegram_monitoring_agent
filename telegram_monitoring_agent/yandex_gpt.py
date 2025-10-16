"""
Клиент для работы с Yandex GPT
"""

import json
import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime

from config import YandexGPTConfig

logger = logging.getLogger(__name__)


class YandexGPTClient:
    """Клиент для работы с Yandex GPT API"""

    def __init__(self, config: YandexGPTConfig):
        self.config = config
        self.api_url = config.api_url
        self.headers = {
            "Authorization": f"Api-Key {config.api_key}",
            "Content-Type": "application/json"
        }

    async def generate_completion(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Optional[str]:
        """Генерация текста с помощью Yandex GPT"""
        try:
            # Формируем модель URI
            model_uri = f"gpt://{self.config.folder_id}/{self.config.model_id}/latest"

            # Формируем запрос
            request_data = {
                "modelUri": model_uri,
                "completionOptions": {
                    "stream": False,
                    "temperature": temperature or self.config.temperature,
                    "maxTokens": max_tokens or self.config.max_tokens
                },
                "messages": [
                    {
                        "role": "system",
                        "text": system_prompt
                    },
                    {
                        "role": "user",
                        "text": user_message
                    }
                ]
            }

            # Отправляем запрос
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    json=request_data,
                    headers=self.headers
                )
                response.raise_for_status()

                # Парсим ответ
                result = response.json()

                if "result" in result and "alternatives" in result["result"]:
                    alternative = result["result"]["alternatives"][0]
                    if "message" in alternative and "text" in alternative["message"]:
                        return alternative["message"]["text"]

                logger.error(f"Invalid response format from Yandex GPT: {result}")
                return None

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error in Yandex GPT request: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error generating completion with Yandex GPT: {e}")
            return None

    async def test_connection(self) -> bool:
        """Проверка соединения с API"""
        try:
            test_response = await self.generate_completion(
                system_prompt="Ты тестовый ассистент.",
                user_message="Ответь одним словом: Да",
                max_tokens=10
            )
            return test_response is not None

        except Exception as e:
            logger.error(f"Yandex GPT connection test failed: {e}")
            return False


class MessageSummarizer:
    """Класс для суммаризации сообщений с помощью Yandex GPT"""

    def __init__(self, gpt_client: YandexGPTClient):
        self.gpt_client = gpt_client

    def _format_messages_for_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Форматирование сообщений для суммаризации"""
        formatted_messages = []

        for msg in messages:
            timestamp = msg['timestamp'].strftime("%H:%M")
            sender = msg['sender_name']
            text = msg['text']

            formatted_messages.append(f"[{timestamp}] {sender}: {text}")

        return "\n".join(formatted_messages)

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

    async def summarize_informational_messages(
        self,
        chat_title: str,
        messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Анализ и суммаризация информационных сообщений.
        
        Информационные сообщения включают:
        - Сообщения со ссылками и документами
        - Факты и обучающие материалы
        - Новости и объявления
        - Полезный контент для изучения
        """
        try:
            if not messages:
                return "Информационных сообщений не обнаружено."

            # Форматируем сообщения
            formatted_messages = self._format_messages_for_summary(messages)

            # Формируем системный промпт
            system_prompt = """Ты - аналитик информационного контента в Telegram чатах.

Твоя задача:
1. Проанализировать все сообщения и выделить информационные
2. Информационные сообщения - это:
   - Сообщения со ссылками на статьи, видео, документы
   - Факты, статистика, данные
   - Обучающие материалы и туториалы
   - Новости, анонсы, объявления
   - Полезный контент для изучения
3. Суммаризировать информационные сообщения по категориям
4. ОБЯЗАТЕЛЬНО сохранить все ссылки из сообщений для последующего перехода
5. Указать автора каждого информационного сообщения

Формат вывода:
## 📚 Информационные сообщения

### 📰 Новости и объявления
- **[Автор]**: краткое описание
  - Ссылка: [URL если есть]

### 🔗 Полезные ссылки и материалы
- **[Автор]**: описание материала
  - Ссылка: [URL]

### 📊 Факты и данные
- **[Автор]**: описание факта/данных
  - Источник: [URL если есть]

### 📖 Обучающие материалы
- **[Автор]**: описание материала
  - Ссылка: [URL если есть]

### 🔗 Все ссылки для изучения
- [URL 1] - краткое описание
- [URL 2] - краткое описание

## 📝 Краткая сводка
2-3 предложения о самых важных информационных сообщениях.

ВАЖНО: Сохраняй все URL-ссылки из сообщений полностью и точно."""

            # Формируем пользовательский промпт
            user_prompt = f"""Проанализируй сообщения из чата "{chat_title}" и выдели информационные:

{formatted_messages}

Создай структурированную сводку информационных сообщений согласно инструкциям выше.
ОБЯЗАТЕЛЬНО сохрани все ссылки из сообщений."""

            # Генерируем сводку
            summary = await self.gpt_client.generate_completion(
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.2,
                max_tokens=2500
            )

            if summary:
                logger.info(f"Generated informational summary for chat '{chat_title}' with {len(messages)} messages")
                return summary
            else:
                logger.error(f"Failed to generate informational summary for chat '{chat_title}'")
                return None

        except Exception as e:
            logger.error(f"Error summarizing informational messages for chat '{chat_title}': {e}")
            return None

    async def analyze_discussions_detailed(
        self,
        chat_title: str,
        messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Детальный анализ обсуждений с выделением тем, решений, action items и разногласий.
        
        Возвращает:
        - Markdown-таблицы с темами, решениями, action items
        - Выделенные разногласия
        - Краткий вывод на 5-7 предложений
        """
        try:
            if not messages:
                return "Сообщений для анализа не обнаружено."

            # Форматируем сообщения
            formatted_messages = self._format_messages_for_summary(messages)

            # Формируем системный промпт
            system_prompt = """Ты - бизнес-аналитик, который анализирует обсуждения в Telegram чатах.

Твоя задача:
1. Суммаризировать ключевые темы обсуждений
2. Выделить принятые решения
3. Найти action items (задачи к выполнению) с дедлайнами и ответственными
4. Выделить основные разногласия между участниками
5. ОБЯЗАТЕЛЬНО сохранить все ссылки из сообщений

Ключевые слова для поиска action items:
- "нужно сделать", "необходимо", "надо"
- "кто сделает", "возьмусь", "сделаю"
- "до [дата]", "к [дата]", "deadline"
- "задача", "todo", "action"

Формат вывода:

## 🎯 Ключевые темы

| Тема | Описание | Участники |
|------|----------|-----------|
| Тема 1 | Краткое описание | Имена участников |
| Тема 2 | Краткое описание | Имена участников |

## ✅ Принятые решения

| Решение | Контекст | Кто принял |
|---------|----------|------------|
| Решение 1 | Краткий контекст | Имя |
| Решение 2 | Краткий контекст | Имя |

## 📋 Action Items

| Задача | Ответственный | Дедлайн | Статус |
|--------|---------------|---------|--------|
| Описание задачи 1 | Имя | Дата или "не указан" | Назначена/В работе |
| Описание задачи 2 | Имя | Дата или "не указан" | Назначена/В работе |

## ⚠️ Разногласия

| Вопрос | Позиции | Участники |
|--------|---------|-----------|
| Спорный вопрос | Краткое описание позиций | Имена |

## 🔗 Важные ссылки из обсуждения
- [URL 1] - описание
- [URL 2] - описание

## 📝 Краткий вывод

5-7 предложений с основными выводами по обсуждению:
- Что обсуждалось
- Какие решения приняты
- Что нужно сделать
- Есть ли нерешенные вопросы

ВАЖНО: 
- Если данных для таблицы нет, напиши "Не обнаружено"
- Сохраняй все URL-ссылки полностью
- Будь конкретен в формулировках"""

            # Формируем пользовательский промпт
            user_prompt = f"""Проведи детальный анализ обсуждений в чате "{chat_title}":

{formatted_messages}

Создай структурированный анализ с таблицами согласно инструкциям выше.
ОБЯЗАТЕЛЬНО сохрани все ссылки из сообщений."""

            # Генерируем анализ
            analysis = await self.gpt_client.generate_completion(
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.2,
                max_tokens=3000
            )

            if analysis:
                logger.info(f"Generated detailed analysis for chat '{chat_title}' with {len(messages)} messages")
                return analysis
            else:
                logger.error(f"Failed to generate detailed analysis for chat '{chat_title}'")
                return None

        except Exception as e:
            logger.error(f"Error analyzing discussions for chat '{chat_title}': {e}")
            return None

    async def summarize_howto_content(
        self,
        chat_title: str,
        messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Анализ и суммаризация HowTo контента из сообщений.
        
        HowTo контент включает:
        - Советы и рекомендации
        - Инструкции и гайды
        - Лайфхаки и приемы
        - Best practices
        - Решения проблем
        
        Возвращает None если HowTo контента не обнаружено.
        """
        try:
            if not messages:
                return None

            # Форматируем сообщения
            formatted_messages = self._format_messages_for_summary(messages)

            # Формируем системный промпт
            system_prompt = """Ты - аналитик практического контента в Telegram чатах.

Твоя задача:
1. Проанализировать все сообщения и выделить HowTo контент
2. HowTo контент - это:
   - Советы и рекомендации ("советую", "рекомендую", "лучше сделать так")
   - Инструкции и пошаговые гайды ("как сделать", "шаги", "инструкция")
   - Лайфхаки и приемы ("трюк", "прием", "способ")
   - Best practices ("лучшая практика", "правильный подход")
   - Решения конкретных проблем ("вот как решить", "помогло мне")
3. Суммаризировать HowTo контент по категориям
4. ОБЯЗАТЕЛЬНО сохранить все ссылки из сообщений
5. Указать автора каждого совета/приема

ВАЖНО: Если в сообщениях НЕТ HowTo контента, верни ТОЛЬКО слово "NONE" без дополнительных пояснений.

Формат вывода (только если есть HowTo контент):
## 🎓 HowTo и практические советы

### 💡 Советы и рекомендации
- **[Автор]**: краткое описание совета
  - Ссылка: [URL если есть]

### 📝 Инструкции и гайды
- **[Автор]**: описание инструкции
  - Ссылка: [URL если есть]

### ⚡ Лайфхаки и приемы
- **[Автор]**: описание приема
  - Ссылка: [URL если есть]

### ✅ Best Practices
- **[Автор]**: описание практики
  - Ссылка: [URL если есть]

### 🔧 Решения проблем
- **Проблема**: краткое описание
- **Решение от [Автор]**: описание решения
  - Ссылка: [URL если есть]

### 🔗 Полезные ссылки по теме
- [URL 1] - краткое описание
- [URL 2] - краткое описание

## 📝 Краткая сводка
2-3 предложения о самых полезных советах и приемах.

ВАЖНО: Сохраняй все URL-ссылки из сообщений полностью и точно."""

            # Формируем пользовательский промпт
            user_prompt = f"""Проанализируй сообщения из чата "{chat_title}" и выдели HowTo контент:

{formatted_messages}

Если есть HowTo контент - создай структурированную сводку согласно инструкциям выше.
Если HowTo контента НЕТ - верни только "NONE".
ОБЯЗАТЕЛЬНО сохрани все ссылки из сообщений."""

            # Генерируем сводку
            summary = await self.gpt_client.generate_completion(
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.2,
                max_tokens=2500
            )

            if summary:
                # Проверяем, есть ли контент
                if summary.strip().upper() == "NONE":
                    logger.info(f"No HowTo content found in chat '{chat_title}'")
                    return None
                
                logger.info(f"Generated HowTo summary for chat '{chat_title}' with {len(messages)} messages")
                return summary
            else:
                logger.error(f"Failed to generate HowTo summary for chat '{chat_title}'")
                return None

        except Exception as e:
            logger.error(f"Error summarizing HowTo content for chat '{chat_title}': {e}")
            return None