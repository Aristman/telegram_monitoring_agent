# Telegram Monitoring Agent - Документация по развертыванию

## Обзор

Telegram Monitoring Agent - это система для мониторинга Telegram чатов с автоматической генерацией отчетов и анализом контента.

**Компоненты:**
- `telegram_monitoring_agent/` - Основной агент мониторинга
- `telegram_mcp_server_py/` - MCP сервер для Telegram
- `yandex_wiki_mcp/` - MCP сервер для Yandex Wiki

**Требования:**
- Python 3.11+
- Linux/Windows/macOS
- Yandex Cloud API ключи
- Доступ к Telegram API

## Структура документации

1. [Развертывание на виртуальной машине](./deployment.md)
2. [Запуск в фоновом режиме](./background-services.md)
3. [Резервное копирование БД](./backup.md)

## Быстрый старт

```bash
# 1. Клонирование репозитория
git clone <repository-url>
cd telegram_monitoring_agent

# 2. Настройка окружения
cd telegram_monitoring_agent
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или venv\Scripts\activate  # Windows

# 3. Установка зависимостей
pip install -r requirements.txt

# 4. Настройка конфигурации
cp .env.example .env
# Отредактировать .env и config/settings.yaml

# 5. Запуск
python -m main
```

## Конфигурация

### Критичные настройки (.env):
```bash
YANDEX_API_KEY=your_api_key
YANDEX_FOLDER_ID=your_folder_id
```

### Операционные настройки (config/settings.yaml):
- Список чатов для мониторинга
- Интервалы сбора сообщений
- Время выполнения задач
- Настройки логирования

## Архитектура

```
┌─────────────────┐    ┌──────────────────────┐
│  Main Agent     │    │   Runtime Config     │
│                 │◄──►│  (hot reload)         │
└─────────┬───────┘    └──────────────────────┘
          │
          ├──► Telegram Collector
          ├──► Summary Service
          ├──► Scheduler
          └──► Wiki Client
```

## Поддержка

Для получения помощи:
1. Проверьте логи приложения
2. Убедитесь, что все зависимости установлены
3. Проверьте конфигурацию в .env и settings.yaml