"""
Конфигурация Yandex Wiki MCP сервера
"""

import os
from typing import Optional
from pathlib import Path
from pydantic import BaseSettings


class Config(BaseSettings):
    """Конфигурация сервера"""

    # OAuth/IAM токен для аутентификации
    yandex_token: Optional[str] = os.getenv("YANDEX_TOKEN")

    # ID организации Yandex 360
    organization_id: Optional[str] = os.getenv("YANDEX_ORGANIZATION_ID")

    # Базовый URL API Yandex Wiki
    wiki_api_url: str = "https://wiki.yandex.ru/api/v1"

    # URL для OAuth токена
    oauth_url: str = "https://oauth.yandex.ru/token"

    # Настройки HTTP клиента
    timeout: int = 30
    max_retries: int = 3

    # Настройки сервера
    host: str = "127.0.0.1"
    port: int = 8080

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def validate_config(config: Config) -> None:
    """Валидация конфигурации"""
    if not config.yandex_token:
        raise ValueError(
            "YANDEX_TOKEN не найден. Установите переменную окружения или добавьте в .env файл. "
            "Токен можно получить через Yandex Cloud CLI или OAuth."
        )

    if not config.organization_id:
        raise ValueError(
            "YANDEX_ORGANIZATION_ID не найден. Установите ID вашей организации Yandex 360."
        )