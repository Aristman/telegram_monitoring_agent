# Yandex Wiki MCP Server

MCP (Model Context Protocol) сервер для работы с Yandex Wiki API. Предоставляет инструменты для просмотра, создания и управления страницами Yandex Wiki через HTTP интерфейс.

## Возможности

- Просмотр детальной информации о страницах
- Чтение содержимого страниц
- Поиск страниц по текстовому запросу
- Получение списка страниц и папок
- Создание новых страниц
- Обновление существующих страниц
- Удаление страниц
- Просмотр истории изменений
- Проверка соединения с API

## Установка и настройка

### 1. Клонирование и установка зависимостей

```bash
cd yandex_wiki_mcp
pip install -r requirements.txt
```

### 2. Настройка окружения

Скопируйте файл конфигурации:

```bash
cp .env .env
```

Отредактируйте `.env` файл, добавив ваши учетные данные:

```env
# OAuth или IAM токен для доступа к Yandex API
YANDEX_TOKEN=ваш_токен_здесь

# ID вашей организации Yandex 360
YANDEX_ORGANIZATION_ID=ваш_id_организации_здесь
```

### 3. Получение токена доступа

#### Способ 1: Через Yandex Cloud CLI (рекомендуется)

```bash
# Установите yc CLI, если еще не установлен
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash

# Получите IAM токен
yc iam create-token
```

#### Способ 2: OAuth приложение

1. Создайте OAuth приложение на [Yandex ID](https://oauth.yandex.ru/client/new)
2. Получите токен через OAuth flow
3. Используйте полученный токен в `YANDEX_TOKEN`

### 4. Запуск сервера

```bash
# Базовый запуск
python main.py

# С указанием хоста и порта
python main.py --host 0.0.0.0 --port 8080

# С автоперезагрузкой для разработки
python main.py --reload
```

## MCP инструменты

Сервер предоставляет следующие MCP инструменты:

### Просмотр страниц

- `ywiki.get_page` - Получить детальную информацию о странице
- `ywiki.get_page_content` - Получить содержимое страницы
- `ywiki.search_pages` - Поиск страниц по запросу
- `ywiki.list_pages` - Получить список страниц
- `ywiki.get_page_history` - Получить историю изменений
- `ywiki.get_folders` - Получить список папок

### Управление страницами

- `ywiki.create_page` - Создать новую страницу
- `ywiki.update_page` - Обновить существующую страницу
- `ywiki.delete_page` - Удалить страницу

### Утилиты

- `ywiki.test_connection` - Проверить соединение с API

## Примеры использования

### Просмотр содержимого страницы

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "ywiki.get_page_content",
    "arguments": {
      "page_id": "12345"
    }
  }
}
```

### Создание новой страницы

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "ywiki.create_page",
    "arguments": {
      "title": "Новая страница",
      "content": "# Заголовок\n\nСодержимое страницы в **Markdown** формате.",
      "folder_id": "folder123"
    }
  }
}
```

### Поиск страниц

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "ywiki.search_pages",
    "arguments": {
      "query": "документация API",
      "limit": 10
    }
  }
}
```

## API эндпоинты

- `POST /` - Основной MCP эндпоинт для JSON-RPC запросов
- `GET /health` - Проверка здоровья сервера
- `GET /` - Информация о сервере

## Структура проекта

```
yandex_wiki_mcp/
├── main.py              # Основной файл сервера FastAPI
├── config.py            # Конфигурация и переменные окружения
├── wiki_client.py       # HTTP клиент для Yandex Wiki API
├── tools.py             # MCP инструменты
├── requirements.txt     # Зависимости Python
├── .env.example         # Пример конфигурации
└── README.md           # Документация
```

## Требования

- Python 3.8+
- Yandex Cloud CLI (для получения токена) или OAuth приложение
- Доступ к Yandex Wiki API
- Права на чтение/запись в вашей организации Yandex 360

## Лицензия

Этот проект следует лицензии основного репозитория.

## Поддержка

При возникновении проблем:

1. Проверьте правильность токена и ID организации
2. Убедитесь, что у вас есть необходимые права доступа
3. Проверьте журнал ошибок сервера
4. Используйте инструмент `ywiki.test_connection` для диагностики