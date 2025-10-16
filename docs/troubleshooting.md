# Поиск неисправностей

## Общие проблемы

### Приложение не запускается

#### 1. Ошибка импорта модулей

**Проблема:**
```
ModuleNotFoundError: No module named 'watchdog'
ImportError: cannot import name 'AppConfig'
```

**Решение:**
```bash
# Проверка установки зависимостей
pip install -r requirements.txt

# Проверка структуры проекта
ls -la telegram_monitoring_agent/config/

# Переустановка проблемных пакетов
pip uninstall watchdog PyYAML
pip install watchdog PyYAML
```

#### 2. Ошибка конфигурации

**Проблема:**
```
Configuration validation failed:
  - MONITORED_CHATS не указаны
  - YANDEX_API_KEY не указан
```

**Решение:**
```bash
# Проверка .env файла
cat telegram_monitoring_agent/.env

# Проверка runtime конфигурации
cat telegram_monitoring_agent/config/settings.yaml

# Тест конфигурации
python -c "
from config import AppConfig, RuntimeConfigManager
config = AppConfig()
runtime = RuntimeConfigManager()
print('Config validation:', runtime.is_loaded())
print('Chats:', runtime.get('telegram.monitored_chats'))
"
```

#### 3. Проблемы с правами доступа

**Проблема:**
```
Permission denied: '/opt/telegram-agent/telegram_messages.db'
```

**Решение:**
```bash
# Проверка владельца файлов
ls -la telegram_monitoring_agent/telegram_messages.db

# Установка правильных прав
sudo chown -R telegram-agent:telegram-agent /opt/telegram-agent/
chmod 644 telegram_monitoring_agent/telegram_messages.db
chmod +x /opt/telegram-agent/scripts/*.sh
```

### Проблемы с подключением

#### 1. Ошибка подключения к Telegram API

**Проблема:**
```
Error starting Telegram MCP server
Failed to resolve chat
```

**Решение:**
```bash
# Проверка конфигурации Telegram
python -c "
from config import AppConfig
config = AppConfig()
print('Telegram MCP URL:', config.telegram_mcp_url)
print('Monitored chats:', config.monitored_chats_list)
"

# Тест подключения к MCP серверу
python -c "
from telegram_collector import TelegramMCPClient
from config import TelegramConfig
config = TelegramConfig(telegram_mcp_url='stdio')
client = TelegramMCPClient(config)
print('MCP client created successfully')
"
```

#### 2. Ошибка подключения к Yandex API

**Проблема:**
```
Failed to connect to Yandex GPT
HTTP/1.1 401 Unauthorized
```

**Решение:**
```bash
# Проверка API ключей
grep -E "YANDEX_API_KEY|YANDEX_FOLDER_ID" telegram_monitoring_agent/.env

# Тест API подключения
python -c "
from yandex_gpt import YandexGPTClient
from config import AppConfig
config = AppConfig()
client = YandexGPTClient(config.get_gpt_config())
result = asyncio.run(client.test_connection())
print('Yandex API connection:', result)
"
```

### Проблемы с runtime конфигурацией

#### 1. Файл settings.yaml не загружается

**Проблема:**
```
Runtime config not loaded, skipping reconfiguration
```

**Решение:**
```bash
# Проверка существования файла
ls -la telegram_monitoring_agent/config/settings.yaml

# Проверка синтаксиса YAML
python -c "import yaml; yaml.safe_load(open('telegram_monitoring_agent/config/settings.yaml'))"

# Проверка прав доступа
ls -la telegram_monitoring_agent/config/
chmod 644 telegram_monitoring_agent/config/settings.yaml
```

#### 2. Изменения в settings.yaml не применяются

**Проблема:**
```
File watcher failed
RuntimeError: no running event loop
```

**Решение:**
```bash
# Проверка работы watchdog
python -c "
from config.runtime_config import RuntimeConfigManager
import asyncio
async def test():
    rc = RuntimeConfigManager()
    await rc.start()
    print('Runtime config test:', rc.is_loaded())

asyncio.run(test())
"
```

## Проблемы с производительностью

### Медленный сбор сообщений

**Проблема:**
- Сбор сообщений занимает много времени
- Большое количество ошибок timeout

**Диагностика:**
```bash
# Проверка настроек интервала
grep -n "interval_seconds" telegram_monitoring_agent/config/settings.yaml

# Проверка количества сообщений
sqlite3 telegram_monitoring_agent/telegram_messages.db "SELECT COUNT(*) FROM messages;"

# Проверка логов на ошибки
grep ERROR telegram_monitoring_agent/telegram_monitor.log | tail -20
```

**Решение:**
```yaml
# Оптимизация settings.yaml
telegram:
  collection:
    interval_seconds: 3600      # Увеличить интервал
    max_messages_per_fetch: 50   # Уменьшить количество за раз
```

### Большое потребление памяти

**Проблема:**
- Приложение потребляет много RAM
- Периодические падения производительности

**Диагностика:**
```bash
# Мониторинг памяти
top -p $(pgrep -f "python -m main")

# Проверка размера БД
ls -lh telegram_monitoring_agent/telegram_messages.db

# Анализ таблиц БД
sqlite3 telegram_monitoring_agent/telegram_messages.db ".tables"
sqlite3 telegram_monitoring_agent/telegram_messages.db "SELECT COUNT(*) FROM messages;"
sqlite3 telegram_monitoring_agent/telegram_messages.db "PRAGMA table_info(messages);"
```

**Решение:**
```bash
# Настройка очистки старых данных
python -c "
from database import Database
from config import DatabaseConfig
db = Database(DatabaseConfig())
deleted = db.cleanup_old_messages(days_to_keep=7)
print(f'Удалено старых сообщений: {deleted}')
"
```

## Проблемы с базой данных

### База данных заблокирована

**Проблема:**
```
sqlite3.OperationalError: database is locked
```

**Решение:**
```bash
# Проверка процессов использующих БД
lsof telegram_monitoring_agent/telegram_messages.db

# Остановка приложения
sudo systemctl stop telegram-agent.service

# Проверка целостности БД
sqlite3 telegram_monitoring_agent/telegram_messages.db "PRAGMA integrity_check;"

# Перезапуск приложения
sudo systemctl start telegram-agent.service
```

### Коррупция базы данных

**Проблема:**
```
sqlite3.DatabaseError: database disk image is malformed
```

**Решение:**
```bash
# Создание бэкапа
cp telegram_monitoring_agent/telegram_messages.db telegram_monitoring_agent/telegram_messages.db.corrupted

# Восстановление из бэкапа
sudo systemctl stop telegram-agent.service
cp backups/telegram_messages_2024-01-15.db telegram_monitoring_agent/telegram_messages.db
sudo systemctl start telegram-agent.service

# Если бэкапа нет, попытка восстановления
sqlite3 telegram_monitoring_agent/telegram_messages.db ".recover"
```

## Проблемы с планировщиком

### Задачи не выполняются

**Проблема:**
```
Scheduled task failed to run
Task not found
```

**Диагностика:**
```bash
# Проверка статуса планировщика
python -c "
from config import RuntimeConfigManager
import asyncio
async def test():
    rc = RuntimeConfigManager()
    await rc.start()
    scheduler_config = rc.get_scheduler_config()
    print('Scheduler config:', scheduler_config)

asyncio.run(test())
"

# Проверка логов планировщика
grep -n "scheduler" telegram_monitoring_agent/telegram_monitor.log | tail -10
```

**Решение:**
```bash
# Перезапуск службы
sudo systemctl restart telegram-agent.service

# Ручная проверка задачи
python -c "
from scheduler import TaskScheduler
from config import SchedulerConfig
scheduler = TaskScheduler(SchedulerConfig())
print('Scheduler tasks:', scheduler.tasks.keys())
"
```

## Логирование и отладка

### Включение отладочного режима

```bash
# Редактирование .env
echo "DEBUG=true" >> telegram_monitoring_agent/.env

# Или редактирование settings.yaml
sed -i 's/level: "INFO"/level: "DEBUG"/' telegram_monitoring_agent/config/settings.yaml
```

### Просмотр логов в реальном времени

```bash
# Основные логи
tail -f telegram_monitoring_agent/telegram_monitor.log

# Системные логи (systemd)
sudo journalctl -u telegram-agent.service -f

# Фильтрация по ошибкам
grep -n "ERROR\|CRITICAL" telegram_monitoring_agent/telegram_monitor.log | tail -20
```

### Создание детальных логов

```python
# Добавление в начало main.py
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)
```

## Проверка работоспособности

### Комплексная проверка

```bash
#!/bin/bash
# /opt/telegram-agent/scripts/health-check.sh

echo "=== Health Check Telegram Agent ===" $(date)

# 1. Проверка процесса
if pgrep -f "python -m main" > /dev/null; then
    echo "✅ Процесс запущен"
else
    echo "❌ Процесс не найден"
fi

# 2. Проверка конфигурации
if [ -f "telegram_monitoring_agent/.env" ] && [ -f "telegram_monitoring_agent/config/settings.yaml" ]; then
    echo "✅ Файлы конфигурации существуют"
else
    echo "❌ Отсутствуют файлы конфигурации"
fi

# 3. Проверка БД
if sqlite3 telegram_monitoring_agent/telegram_messages.db "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ База данных доступна"
    MSG_COUNT=$(sqlite3 telegram_monitoring_agent/telegram_messages.db "SELECT COUNT(*) FROM messages;")
    echo "📊 Сообщений в БД: $MSG_COUNT"
else
    echo "❌ База данных недоступна"
fi

# 4. Проверка зависимостей
python -c "
try:
    from config import AppConfig, RuntimeConfigManager
    from telegram_collector import TelegramCollector
    print('✅ Все зависимости доступны')
except Exception as e:
    print(f'❌ Ошибка зависимостей: {e}')
"

# 5. Проверка системных ресурсов
echo "💾 Свободное место: $(df -h . | tail -1 | awk '{print $4}')"
echo "🖥  Нагрузка CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')"
echo "🧠 Использование RAM: $(free -h | grep Mem | awk '{print $3}')"

echo "=== Health Check завершен ==="
```

### Автоматические тесты

```python
# /opt/telegram-agent/tests/test_config.py
import unittest
from config import AppConfig, RuntimeConfigManager

class TestConfig(unittest.TestCase):
    def test_app_config(self):
        config = AppConfig()
        self.assertIsNotNone(config.yandex_api_key)
        self.assertIsNotNone(config.yandex_folder_id)

    def test_runtime_config(self):
        rc = RuntimeConfigManager()
        self.assertTrue(rc.config_path.exists())

    def test_telegram_chats(self):
        rc = RuntimeConfigManager()
        chats = rc.get('telegram.monitored_chats')
        self.assertIsNotNone(chats)
        self.assertGreater(len(chats), 0)

if __name__ == '__main__':
    unittest.main()
```

## Частые вопросы и ответы

### Q: Почему приложение не видит сообщения из новых чатов?

A: Проверьте список чатов в `config/settings.yaml` и убедитесь, что у бота есть доступ к этим чатам. Попробуйте добавить чат по его ID вместо имени.

### Q: Почему отчеты не создаются в Wiki?

A: Проверьте:
1. Доступность Wiki MCP сервера
2. Настройки Wiki в конфигурации
3. Логи на предмет ошибок подключения

### Q: Как сбросить конфигурацию к значениям по умолчанию?

A: Удалите `config/settings.yaml` и перезапустите приложение - он создаст файл с настройками по умолчанию.

### Q: Почему приложение потребляет много памяти?

A: Возможные причины:
- Большое количество сообщений в БД
- Утечка памяти в циклах сбора
- Неправильная работа с большими объемами данных

Попробуйте очистить старые сообщения и перезапустить приложение.

### Q: Как перенести приложение на другой сервер?

A: Используйте скрипт полного бэкапа:
1. Создайте полный бэкап на текущем сервере
2. Перенесите бэкап на новый сервер
3. Установите зависимости на новом сервере
4. Восстановите из бэкапа
5. Запустите приложение

Эта документация поможет диагностировать и решать наиболее распространенные проблемы при развертывании и эксплуатации Telegram Monitoring Agent.