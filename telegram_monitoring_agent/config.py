"""
Конфигурация агента мониторинга Telegram
"""

import os
from typing import List, Optional
from pathlib import Path
from pydantic_settings import BaseSettings


class TelegramConfig(BaseSettings):
    """Конфигурация Telegram"""
    # Список ID чатов для мониторинга
    monitored_chats: List[str] = os.getenv(
        "MONITORED_CHATS", ""
    ).split(",") if os.getenv("MONITORED_CHATS") else []

    # URL Telegram MCP сервера
    telegram_mcp_url: str = os.getenv("TELEGRAM_MCP_URL", "stdio")

    # Интервал сбора сообщений в секундах (по умолчанию 5 минут)
    message_collection_interval: int = int(os.getenv("MESSAGE_COLLECTION_INTERVAL", "300"))

    # Максимальное количество сообщений за один сбор
    max_messages_per_fetch: int = int(os.getenv("MAX_MESSAGES_PER_FETCH", "100"))


class YandexWikiConfig(BaseSettings):
    """Конфигурация Yandex Wiki"""
    # Базовый URL Wiki MCP сервера
    wiki_mcp_url: str = os.getenv("WIKI_MCP_URL", "http://127.0.0.1:8080")

    # Базовая папка для отчетов
    base_folder: str = os.getenv("WIKI_BASE_FOLDER", "telegram_report")


class YandexGPTConfig(BaseSettings):
    """Конфигурация Yandex GPT"""
    # API ключ для Yandex Cloud
    api_key: str = os.getenv("YANDEX_API_KEY", "")

    # ID папки Yandex Cloud
    folder_id: str = os.getenv("YANDEX_FOLDER_ID", "")

    # ID модели (yandexgpt-lite или yandexgpt)
    model_id: str = os.getenv("YANDEX_MODEL_ID", "yandexgpt-lite")

    # URL API
    api_url: str = os.getenv("YANDEX_GPT_URL", "https://llm.api.cloud.yandex.net/foundationModels/v1/completion")

    # Температура генерации
    temperature: float = float(os.getenv("YANDEX_GPT_TEMPERATURE", "0.3"))

    # Максимальное количество токенов
    max_tokens: int = int(os.getenv("YANDEX_GPT_MAX_TOKENS", "4000"))


class DatabaseConfig(BaseSettings):
    """Конфигурация базы данных"""
    # Путь к файлу базы данных SQLite
    db_path: str = os.getenv("DB_PATH", "telegram_messages.db")

    # URL для подключения (если используется другая БД)
    db_url: Optional[str] = os.getenv("DATABASE_URL")


class SchedulerConfig(BaseSettings):
    """Конфигурация планировщика"""
    # Время ежедневной суммаризации в формате HH:MM
    daily_summary_time: str = os.getenv("DAILY_SUMMARY_TIME", "21:00")

    # Часовой пояс
    timezone: str = os.getenv("TIMEZONE", "Europe/Moscow")


class AppConfig(BaseSettings):
    """Общая конфигурация приложения"""
    # Уровень логирования
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Путь к файлу логов
    log_file: str = os.getenv("LOG_FILE", "telegram_monitor.log")

    # Директория для временных файлов
    temp_dir: str = os.getenv("TEMP_DIR", "./temp")

    # Включить/выключить отладочный режим
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Вложенные конфигурации
    telegram: TelegramConfig = TelegramConfig()
    wiki: YandexWikiConfig = YandexWikiConfig()
    gpt: YandexGPTConfig = YandexGPTConfig()
    database: DatabaseConfig = DatabaseConfig()
    scheduler: SchedulerConfig = SchedulerConfig()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def validate_config(config: AppConfig) -> List[str]:
    """Валидация конфигурации и возврат списка ошибок"""
    errors = []

    # Проверка Telegram конфигурации
    if not config.telegram.monitored_chats:
        errors.append("MONITORED_CHATS не указаны")

    # Проверка Yandex GPT конфигурации
    if not config.gpt.api_key:
        errors.append("YANDEX_API_KEY не указан")

    if not config.gpt.folder_id:
        errors.append("YANDEX_FOLDER_ID не указан")

    return errors