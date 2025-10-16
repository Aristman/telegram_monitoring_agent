"""
Клиент для работы с Yandex GPT API
"""

import logging
import httpx
from typing import Optional

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
