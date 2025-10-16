"""
Конфигурация агента мониторинга Telegram
"""

import os
from typing import List, Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field, field_validator


class TelegramConfig(BaseSettings):
    """Конфигурация Telegram"""
    model_config = ConfigDict(extra="allow")

    # Список ID чатов для мониторинга
    monitored_chats: List[str] = Field(default_factory=list)

    # URL Telegram MCP сервера
    telegram_mcp_url: str = Field(default="stdio")

    # Интервал сбора сообщений в секундах (по умолчанию 5 минут)
    message_collection_interval: int = Field(default=600)

    # Максимальное количество сообщений за один сбор
    max_messages_per_fetch: int = Field(default=100)

    @field_validator('monitored_chats', mode='before')
    @classmethod
    def parse_monitored_chats(cls, v):
        if isinstance(v, str):
            # Разделяем по запятой и убираем пустые значения
            return [chat_id.strip() for chat_id in v.split(',') if chat_id.strip()]
        return v

    @field_validator('message_collection_interval', mode='before')
    @classmethod
    def parse_interval(cls, v):
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 300
        return v

    @field_validator('max_messages_per_fetch', mode='before')
    @classmethod
    def parse_max_messages(cls, v):
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 100
        return v


class YandexWikiConfig(BaseSettings):
    """Конфигурация Yandex Wiki"""
    model_config = ConfigDict(extra="allow")

    # Базовый URL Wiki MCP сервера
    wiki_mcp_url: str = Field(default="http://127.0.0.1:8080")

    # Базовая папка для отчетов
    wiki_base_folder: str = Field(default="telegram_report")


class YandexGPTConfig(BaseSettings):
    """Конфигурация Yandex GPT"""
    model_config = ConfigDict(
        extra="allow",
        protected_namespaces=('settings_',)  # Fix warning for model_id
    )

    # API ключ для Yandex Cloud
    api_key: str = Field(default="")

    # ID папки Yandex Cloud
    folder_id: str = Field(default="")

    # ID модели (yandexgpt-lite или yandexgpt)
    model_id: str = Field(default="yandexgpt-lite")

    # URL API
    api_url: str = Field(default="https://llm.api.cloud.yandex.net/foundationModels/v1/completion")

    # Температура генерации
    temperature: float = Field(default=0.3)

    # Максимальное количество токенов
    max_tokens: int = Field(default=4000)

    @field_validator('temperature', mode='before')
    @classmethod
    def parse_temperature(cls, v):
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return 0.3
        return v

    @field_validator('max_tokens', mode='before')
    @classmethod
    def parse_max_tokens(cls, v):
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 4000
        return v


class DatabaseConfig(BaseSettings):
    """Конфигурация базы данных"""
    model_config = ConfigDict(extra="allow")

    # Путь к файлу базы данных SQLite
    db_path: str = Field(default="telegram_messages.db")

    # URL для подключения (если используется другая БД)
    db_url: Optional[str] = Field(default=None)


class SchedulerConfig(BaseSettings):
    """Конфигурация планировщика"""
    model_config = ConfigDict(extra="allow")

    # Время ежедневной суммаризации в формате HH:MM
    daily_summary_time: str = Field(default="21:00")

    # Часовой пояс
    timezone: str = Field(default="Europe/Moscow")


class AppConfig(BaseSettings):
    """Общая конфигурация приложения"""
    model_config = ConfigDict(
        extra="allow",
        env_file=".env",
        env_file_encoding="utf-8",
        env_parse_none_str_as_empty=True
    )

    # Уровень логирования
    log_level: str = Field(default="INFO")

    # Путь к файлу логов
    log_file: str = Field(default="telegram_monitor.log")

    # Директория для временных файлов
    temp_dir: str = Field(default="./temp")

    # Включить/выключить отладочный режим
    debug: bool = Field(default=False)

    # Telegram настройки
    monitored_chats: str = Field(default="")
    telegram_mcp_url: str = Field(default="stdio")
    message_collection_interval: int = Field(default=300)
    max_messages_per_fetch: int = Field(default=100)

    # Wiki настройки
    wiki_mcp_url: str = Field(default="http://127.0.0.1:8080")
    wiki_base_folder: str = Field(default="telegram_report")

    # Yandex GPT настройки
    yandex_api_key: str = Field(default="")
    yandex_folder_id: str = Field(default="")
    yandex_model_id: str = Field(default="yandexgpt-lite")
    yandex_gpt_url: str = Field(default="https://llm.api.cloud.yandex.net/foundationModels/v1/completion")
    yandex_gpt_temperature: float = Field(default=0.3)
    yandex_gpt_max_tokens: int = Field(default=4000)

    # База данных
    db_path: str = Field(default="telegram_messages.db")

    # Планировщик
    daily_summary_time: str = Field(default="21:00")
    timezone: str = Field(default="Europe/Moscow")

    @property
    def monitored_chats_list(self) -> List[str]:
        """Get monitored chats as a list"""
        if not self.monitored_chats:
            return []
        return [chat_id.strip() for chat_id in self.monitored_chats.split(',') if chat_id.strip()]

    @field_validator('message_collection_interval', mode='before')
    @classmethod
    def parse_interval(cls, v):
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 300
        return v

    @field_validator('max_messages_per_fetch', mode='before')
    @classmethod
    def parse_max_messages(cls, v):
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 100
        return v

    @field_validator('yandex_gpt_temperature', mode='before')
    @classmethod
    def parse_temperature(cls, v):
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return 0.3
        return v

    @field_validator('yandex_gpt_max_tokens', mode='before')
    @classmethod
    def parse_max_tokens(cls, v):
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 8000
        return v

    @field_validator('debug', mode='before')
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on')
        return v

    def get_telegram_config(self) -> TelegramConfig:
        """Получить Telegram конфигурацию"""
        return TelegramConfig(
            monitored_chats=self.monitored_chats_list,
            telegram_mcp_url=self.telegram_mcp_url,
            message_collection_interval=self.message_collection_interval,
            max_messages_per_fetch=self.max_messages_per_fetch
        )

    def get_wiki_config(self) -> YandexWikiConfig:
        """Получить Wiki конфигурацию"""
        return YandexWikiConfig(
            wiki_mcp_url=self.wiki_mcp_url,
            base_folder=self.wiki_base_folder
        )

    def get_gpt_config(self) -> YandexGPTConfig:
        """Получить GPT конфигурацию"""
        return YandexGPTConfig(
            api_key=self.yandex_api_key,
            folder_id=self.yandex_folder_id,
            model_id=self.yandex_model_id,
            api_url=self.yandex_gpt_url,
            temperature=self.yandex_gpt_temperature,
            max_tokens=self.yandex_gpt_max_tokens
        )

    def get_database_config(self) -> DatabaseConfig:
        """Получить конфигурацию базы данных"""
        return DatabaseConfig(
            db_path=self.db_path
        )

    def get_scheduler_config(self) -> SchedulerConfig:
        """Получить конфигурацию планировщика"""
        return SchedulerConfig(
            daily_summary_time=self.daily_summary_time,
            timezone=self.timezone
        )


def validate_config(config: AppConfig) -> List[str]:
    """Валидация конфигурации и возврат списка ошибок"""
    errors = []

    # Проверка Telegram конфигурации
    if not config.monitored_chats_list:
        errors.append("MONITORED_CHATS не указаны")

    # Проверка Yandex GPT конфигурации
    if not config.yandex_api_key:
        errors.append("YANDEX_API_KEY не указан")

    if not config.yandex_folder_id:
        errors.append("YANDEX_FOLDER_ID не указан")

    return errors