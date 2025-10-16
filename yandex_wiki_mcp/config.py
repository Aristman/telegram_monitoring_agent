"""
Конфигурация Yandex Wiki MCP сервера
"""

import os
import sys
from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field


class Config(BaseSettings):
    """Конфигурация сервера"""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow"  # Разрешаем дополнительные поля
    )

    def __init__(self, **kwargs):
        # Получаем абсолютный путь к .env файлу
        script_dir = Path(__file__).parent
        env_file = script_dir / ".env"

        # Если .env не существует в текущей директории, ищем в родительских
        if not env_file.exists():
            parent_env = script_dir.parent / ".env"
            if parent_env.exists():
                env_file = parent_env

        # Обновляем конфигурацию с правильным путем
        super().__init__(env_file=str(env_file), **kwargs)

    # OAuth/IAM токен для аутентификации
    yandex_token: Optional[str] = Field(default=None, alias="YANDEX_TOKEN")

    # ID организации Yandex Cloud Organization
    organization_id: Optional[str] = Field(default=None, alias="YANDEX_ORGANIZATION_ID")

    # Базовый URL API Yandex Wiki
    wiki_api_url: str = "https://api.wiki.yandex.net/v1"

    # URL для OAuth токена
    oauth_url: str = "https://oauth.yandex.ru/token"

    # Настройки HTTP клиента
    timeout: int = 30
    max_retries: int = 3

    # Настройки сервера
    host: str = "127.0.0.1"
    port: int = 8080


def validate_config(config: Config) -> None:
    """Валидация конфигурации"""
    if not config.yandex_token:
        raise ValueError(
            "YANDEX_TOKEN не найден. Установите переменную окружения или добавьте в .env файл. "
            "Используйте OAuth токен (начинается с y0_), IAM токен будет получен автоматически."
        )

    if not config.organization_id:
        raise ValueError(
            "YANDEX_ORGANIZATION_ID не найден. Установите ID вашей организации Yandex Cloud Organization."
        )