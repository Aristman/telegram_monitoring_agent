# Changelog

## [Unreleased] - 2024-10-16

### Fixed
- **Метод create_page**: Исправлена структура запроса согласно официальной документации Yandex Wiki API
  - Параметр `slug` теперь передается в body запроса вместо query параметров
  - Добавлен обязательный параметр `page_type` (по умолчанию "page")
  - Параметр `content` теперь передается как строка, а не как объект с полями `body` и `format`
  - Обновлена схема MCP инструмента `ywiki.create_page` с добавлением параметра `page_type`

- **Методы get_folders и test_connection**: Исправлено использование несуществующего эндпоинта
  - Эндпоинт `/folders` не существует в текущей версии Yandex Wiki API
  - Оба метода теперь используют эндпоинт `/pages` для проверки доступа и получения структуры
  - Исправлена ошибка 404 при тестировании соединения

### Документация
- Согласно [официальной документации Yandex Wiki API](https://yandex.ru/support/wiki/ru/api-ref/pages/pages__create_public_page):
  - Обязательные параметры в body: `slug`, `title`, `page_type`, `content`
  - Поддерживаемые типы страниц: `page`, `grid`, `cloud_page`, `wysiwyg`, `template`
  - Параметр `content` должен быть строкой в формате markdown

### Примечания
- Другие методы API (get_page, update_page, delete_page и т.д.) проверены и работают корректно
- Метод `get_page_list` правильно использует `slug` как query параметр для GET запросов
