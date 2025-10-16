"""
Анализатор информационного контента
"""

import logging
from typing import Dict, Any, List, Optional

from ..base_analyzer import BaseMessageAnalyzer

logger = logging.getLogger(__name__)


class InformationalAnalyzer(BaseMessageAnalyzer):
    """Анализатор для информационных сообщений"""

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
  - Ссылка: <URL> (если есть)

### 🔗 Полезные ссылки и материалы
- **[Автор]**: описание материала
  - Ссылка: <URL>

### 📊 Факты и данные
- **[Автор]**: описание факта/данных
  - Источник: <URL> (если есть)

### 📖 Обучающие материалы
- **[Автор]**: описание материала
  - Ссылка: <URL> (если есть)

### 🔗 Все ссылки для изучения
- <URL> - краткое описание
- <URL> - краткое описание

## 📝 Краткая сводка
2-3 предложения о самых важных информационных сообщениях.

ВАЖНО: 
- Сохраняй все URL-ссылки из сообщений полностью и точно
- Если ссылок НЕТ - НЕ выводи раздел "🔗 Все ссылки для изучения"
- НЕ пиши "Ссылка: NONE" или "Источник: NONE" - просто пропускай строку со ссылкой
- Если в категории нет данных, не выводи эту категорию"""

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
