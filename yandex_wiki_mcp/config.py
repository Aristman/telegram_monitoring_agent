"""
Конфигурация Yandex Wiki MCP сервера
"""

import os
import sys
from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


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

        print(f"🔧 Using env file: {env_file} (exists: {env_file.exists()})", file=sys.stderr)

        # Обновляем конфигурацию с правильным путем
        super().__init__(env_file=str(env_file), **kwargs)

    # OAuth/IAM токен для аутентификации
    yandex_token: Optional[str] = None

    # ID организации Yandex 360
    organization_id: Optional[str] = None

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


def validate_config(config: Config) -> None:
    """Валидация конфигурации"""
    print(f"🔧 Debug: yandex_token = {config.yandex_token}", file=sys.stderr)
    print(f"🔧 Debug: organization_id = {config.organization_id}", file=sys.stderr)
    print(f"🔧 Debug: .env file exists: {Path('.env').exists()}", file=sys.stderr)

    if not config.yandex_token:
        raise ValueError(
            "YANDEX_TOKEN не найден. Установите переменную окружения или добавьте в .env файл. "
            "Используйте OAuth токен (начинается с y0_), IAM токен будет получен автоматически."
        )

    if not config.organization_id:
        raise ValueError(
            "YANDEX_ORGANIZATION_ID не найден. Установите ID вашей организации Yandex 360."
        )