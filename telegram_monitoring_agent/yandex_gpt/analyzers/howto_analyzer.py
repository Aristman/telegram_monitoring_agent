"""
Анализатор HowTo контента
"""

import logging
from typing import Dict, Any, List, Optional

from ..base_analyzer import BaseMessageAnalyzer

logger = logging.getLogger(__name__)


class HowToAnalyzer(BaseMessageAnalyzer):
    """Анализатор для HowTo контента и практических советов"""

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
