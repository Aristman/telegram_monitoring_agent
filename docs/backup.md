# Резервное копирование базы данных

## Обзор

Telegram Monitoring Agent использует SQLite базу данных для хранения сообщений и метаданных. Регулярное резервное копирование критически важно для сохранения данных.

## Структура данных

### Файлы для резервного копирования

```
/opt/telegram-agent/
├── telegram_monitoring_agent/
│   ├── telegram_messages.db          # Основная БД
│   ├── telegram_monitor.log          # Логи приложения
│   └── config/
│       ├── settings.yaml             # Runtime конфигурация
│       └── base_config.py            # Базовая конфигурация
├── logs/                             # Дополнительные логи
└── backups/                          # Папка для бэкапов
```

### Таблицы в БД

- `messages` - Сообщения из Telegram
- `chat_info` - Информация о чатах
- `reports` - Сгенерированные отчеты
- `logs` - Системные логи
- `last_sent_message` - Отслеживание обработанных сообщений

## Автоматическое резервное копирование

### 1. Создание скрипта бэкапа

```bash
#!/bin/bash
# /opt/telegram-agent/scripts/backup.sh

set -e

# Переменные
BACKUP_DIR="/opt/telegram-agent/backups"
DB_PATH="/opt/telegram-agent/telegram_monitoring_agent/telegram_messages.db"
CONFIG_DIR="/opt/telegram-agent/telegram_monitoring_agent/config"
LOG_DIR="/opt/telegram-agent/logs"
DATE=$(date +%Y-%m-%d_%H-%M-%S)
RETENTION_DAYS=30

# Создание директории для бэкапов
mkdir -p "$BACKUP_DIR"

echo "Начало резервного копирования: $DATE"

# 1. Бэкап базы данных SQLite
echo "Создание бэкапа базы данных..."
sqlite3 "$DB_PATH" ".backup $BACKUP_DIR/telegram_messages_$DATE.db"

# 2. Бэкап конфигурации
echo "Создание бэкапа конфигурации..."
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" -C "$CONFIG_DIR" .

# 3. Бэкап логов (за последние 7 дней)
echo "Создание бэкапа логов..."
find "$LOG_DIR" -name "*.log" -mtime -7 -print0 | tar -czf "$BACKUP_DIR/logs_$DATE.tar.gz" --null -T -

# 4. Создание полного бэкапа
echo "Создание полного архива..."
tar -czf "$BACKUP_DIR/full_backup_$DATE.tar.gz" \
    -C /opt/telegram-agent \
    telegram_monitoring_agent/telegram_messages.db \
    telegram_monitoring_agent/config/ \
    logs/

# 5. Очистка старых бэкапов
echo "Очистка бэкапов старше $RETENTION_DAYS дней..."
find "$BACKUP_DIR" -name "*.db" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

# 6. Проверка целостности бэкапа
echo "Проверка целостности бэкапа..."
if [ -f "$BACKUP_DIR/telegram_messages_$DATE.db" ]; then
    sqlite3 "$BACKUP_DIR/telegram_messages_$DATE.db" "PRAGMA integrity_check;"
    echo "Бэкап базы данных успешно проверен"
else
    echo "ОШИБКА: Бэкап базы данных не создан"
    exit 1
fi

echo "Резервное копирование завершено: $DATE"
echo "Свободное место: $(df -h /opt/telegram-agent | tail -1 | awk '{print $4}')"

# 7. Отправка уведомления (опционально)
if command -v mail &> /dev/null; then
    echo "Резервное копирование Telegram Agent завершено успешно" | \
    mail -s "Backup completed: $DATE" admin@example.com
fi
```

### 2. Создание скрипта восстановления

```bash
#!/bin/bash
# /opt/telegram-agent/scripts/restore.sh

set -e

if [ $# -eq 0 ]; then
    echo "Использование: $0 <backup_file>"
    echo "Пример: $0 /opt/telegram-agent/backups/telegram_messages_2024-01-15_14-30-00.db"
    exit 1
fi

BACKUP_FILE="$1"
DB_PATH="/opt/telegram-agent/telegram_monitoring_agent/telegram_messages.db"
CONFIG_DIR="/opt/telegram-agent/telegram_monitoring_agent/config"

echo "Восстановление из бэкапа: $BACKUP_FILE"

# Остановка службы
echo "Остановка Telegram Agent..."
sudo systemctl stop telegram-agent.service

# Резервное копирование текущей БД
if [ -f "$DB_PATH" ]; then
    echo "Создание резервной копии текущей БД..."
    cp "$DB_PATH" "$DB_PATH.backup.$(date +%s)"
fi

# Восстановление БД
if [[ "$BACKUP_FILE" == *.db ]]; then
    echo "Восстановление базы данных..."
    cp "$BACKUP_FILE" "$DB_PATH"
elif [[ "$BACKUP_FILE" == *full_backup*.tar.gz ]]; then
    echo "Восстановление полного бэкапа..."
    cd /opt/telegram-agent
    tar -xzf "$BACKUP_FILE"
else
    echo "Ошибка: Неподдерживаемый формат бэкапа"
    exit 1
fi

# Восстановление прав доступа
chown telegram-agent:telegram-agent "$DB_PATH"
chmod 644 "$DB_PATH"

# Проверка целостности восстановленной БД
echo "Проверка целостности БД..."
sqlite3 "$DB_PATH" "PRAGMA integrity_check;"

# Запуск службы
echo "Запуск Telegram Agent..."
sudo systemctl start telegram-agent.service

echo "Восстановление завершено"
```

### 3. Настройка Cron для автоматического бэкапа

```bash
# Редактирование crontab
crontab -e
```

```cron
# Ежедневный бэкап в 2:00 ночи
0 2 * * * /opt/telegram-agent/scripts/backup.sh >> /opt/telegram-agent/logs/backup.log 2>&1

# Еженедельная проверка бэкапов в воскресенье в 3:00
0 3 * * 0 /opt/telegram-agent/scripts/verify-backups.sh >> /opt/telegram-agent/logs/backup.log 2>&1
```

### 4. Скрипт проверки бэкапов

```bash
#!/bin/bash
# /opt/telegram-agent/scripts/verify-backups.sh

BACKUP_DIR="/opt/telegram-agent/backups"
ALERT_EMAIL="admin@example.com"

echo "Проверка бэкапов: $(date)"

# Проверка наличия бэкапов за последние 7 дней
RECENT_BACKUPS=$(find "$BACKUP_DIR" -name "telegram_messages_*.db" -mtime -7 | wc -l)

if [ "$RECENT_BACKUPS" -eq 0 ]; then
    echo "ОШИБКА: Нет бэкапов за последние 7 дней!"
    echo "Отсутствие бэкапов за последние 7 дней" | mail -s "ALERT: No recent backups" "$ALERT_EMAIL"
    exit 1
fi

# Проверка размера последнего бэкапа
LATEST_BACKUP=$(find "$BACKUP_DIR" -name "telegram_messages_*.db" -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2)
BACKUP_SIZE=$(stat -c%s "$LATEST_BACKUP")

if [ "$BACKUP_SIZE" -lt 1048576 ]; then  # 1MB
    echo "ПРЕДУПРЕЖДЕНИЕ: Последний бэкап слишком маленький ($BACKUP_SIZE байт)"
    echo "Последний бэкап слишком маленький" | mail -s "WARNING: Small backup detected" "$ALERT_EMAIL"
fi

# Проверка свободного места
FREE_SPACE=$(df /opt/telegram-agent | tail -1 | awk '{print $4}')
FREE_SPACE_GB=$((FREE_SPACE / 1024 / 1024))

if [ "$FREE_SPACE_GB" -lt 5 ]; then
    echo "ПРЕДУПРЕЖДЕНИЕ: Мало свободного места ($FREE_SPACE_GB GB)"
    echo "Мало свободного места на диске" | mail -s "WARNING: Low disk space" "$ALERT_EMAIL"
fi

echo "Проверка бэкапов завершена. Найдено бэкапов: $RECENT_BACKUPS"
```

## Ручное резервное копирование

### 1. Бэкап SQLite базы данных

```bash
# Метод 1: Использование команды .backup
sqlite3 /opt/telegram-agent/telegram_monitoring_agent/telegram_messages.db ".backup /path/to/backup/telegram_messages_$(date +%Y%m%d).db"

# Метод 2: Копирование файла (требует остановки службы)
sudo systemctl stop telegram-agent.service
cp /opt/telegram-agent/telegram_monitoring_agent/telegram_messages.db /path/to/backup/telegram_messages_$(date +%Y%m%d).db
sudo systemctl start telegram-agent.service

# Метод 3: Использование.dump
sqlite3 /opt/telegram-agent/telegram_monitoring_agent/telegram_messages.db ".dump" > /path/to/backup/telegram_messages_$(date +%Y%m%d).sql
```

### 2. Бэкап конфигурации

```bash
# Архивация конфигурации
tar -czf /path/to/backup/config_$(date +%Y%m%d).tar.gz \
    -C /opt/telegram-agent/telegram_monitoring_agent \
    config/settings.yaml \
    config/base_config.py
```

### 3. Полный бэкап

```bash
# Создание полного архива
tar -czf /path/to/backup/telegram-agent-full_$(date +%Y%m%d_%H%M%S).tar.gz \
    -C /opt/telegram-agent \
    telegram_monitoring_agent/telegram_messages.db \
    telegram_monitoring_agent/config/ \
    logs/ \
    scripts/
```

## Восстановление из бэкапа

### 1. Восстановление базы данных

```bash
# Из .db файла
sudo systemctl stop telegram-agent.service
cp /path/to/backup/telegram_messages_20240115.db /opt/telegram-agent/telegram_monitoring_agent/telegram_messages.db
sudo systemctl start telegram-agent.service

# Из .sql файла
sudo systemctl stop telegram-agent.service
sqlite3 /opt/telegram-agent/telegram_monitoring_agent/telegram_messages.db < /path/to/backup/telegram_messages_20240115.sql
sudo systemctl start telegram-agent.service
```

### 2. Восстановление конфигурации

```bash
# Распаковка архива конфигурации
tar -xzf /path/to/backup/config_20240115.tar.gz -C /opt/telegram-agent/telegram_monitoring_agent/
```

## Удаленное резервное копирование

### 1. Настройка SSH ключей

```bash
# Генерация SSH ключей (на сервере)
ssh-keygen -t rsa -b 4096 -C "backup@telegram-agent"

# Копирование публичного ключа на удаленный сервер
ssh-copy-id user@backup-server.com
```

### 2. Скрипт удаленного бэкапа

```bash
#!/bin/bash
# /opt/telegram-agent/scripts/remote-backup.sh

REMOTE_SERVER="user@backup-server.com"
REMOTE_DIR="/backup/telegram-agent"
LOCAL_BACKUP_DIR="/opt/telegram-agent/backups"
DATE=$(date +%Y-%m-%d_%H-%M-%S)

# Создание локального бэкапа
/opt/telegram-agent/scripts/backup.sh

# Копирование на удаленный сервер
echo "Копирование бэкапа на удаленный сервер..."
ssh "$REMOTE_SERVER" "mkdir -p $REMOTE_DIR/$(date +%Y-%m-%d)"

scp "$LOCAL_BACKUP_DIR/telegram_messages_$DATE.db" "$REMOTE_SERVER:$REMOTE_DIR/$(date +%Y-%m-%d)/"
scp "$LOCAL_BACKUP_DIR/full_backup_$DATE.tar.gz" "$REMOTE_SERVER:$REMOTE_DIR/$(date +%Y-%m-%d)/"

echo "Удаленное резервное копирование завершено"
```

### 3. Использование Rsync для инкрементальных бэкапов

```bash
#!/bin/bash
# /opt/telegram-agent/scripts/rsync-backup.sh

REMOTE_SERVER="user@backup-server.com"
REMOTE_DIR="/backup/telegram-agent"
LOCAL_DIR="/opt/telegram-agent"

# Инкрементальное копирование
rsync -avz --delete \
    --exclude="*.pyc" \
    --exclude="__pycache__" \
    --exclude="venv" \
    --exclude="logs/*.log" \
    "$LOCAL_DIR/telegram_monitoring_agent/telegram_messages.db" \
    "$REMOTE_SERVER:$REMOTE_DIR/database/"

rsync -avz \
    "$LOCAL_DIR/telegram_monitoring_agent/config/" \
    "$REMOTE_SERVER:$REMOTE_DIR/config/"

echo "Rsync бэкап завершен"
```

## Мониторинг бэкапов

### 1. Проверка состояния бэкапов

```bash
#!/bin/bash
# /opt/telegram-agent/scripts/check-backup-status.sh

BACKUP_DIR="/opt/telegram-agent/backups"
TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)

echo "Проверка статуса бэкапов от $YESTERDAY"

# Проверка наличия бэкапа
if [ -f "$BACKUP_DIR/telegram_messages_$YESTERDAY*.db" ]; then
    echo "✅ Бэкап БД за $YESTERDAY найден"
else
    echo "❌ Бэкап БД за $YESTERDAY НЕ найден"
fi

# Проверка размера
if [ -f "$BACKUP_DIR/telegram_messages_$YESTERDAY*.db" ]; then
    SIZE=$(stat -c%s "$BACKUP_DIR/telegram_messages_$YESTERDAY*.db")
    SIZE_MB=$((SIZE / 1024 / 1024))
    echo "📊 Размер бэкапа: $SIZE_MB MB"
fi

# Проверка целостности
if [ -f "$BACKUP_DIR/telegram_messages_$YESTERDAY*.db" ]; then
    sqlite3 "$BACKUP_DIR/telegram_messages_$YESTERDAY*.db" "PRAGMA integrity_check;" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ Целостность бэкапа в порядке"
    else
        echo "❌ Ошибка целостности бэкапа"
    fi
fi
```

### 2. Создание отчета о бэкапах

```bash
#!/bin/bash
# /opt/telegram-agent/scripts/backup-report.sh

BACKUP_DIR="/opt/telegram-agent/backups"
REPORT_FILE="/opt/telegram-agent/logs/backup-report-$(date +%Y-%m-%d).txt"

echo "Отчет о резервном копировании - $(date)" > "$REPORT_FILE"
echo "=========================================" >> "$REPORT_FILE"

# Статистика по бэкапам
echo "" >> "$REPORT_FILE"
echo "Общее количество бэкапов БД:" >> "$REPORT_FILE"
find "$BACKUP_DIR" -name "telegram_messages_*.db" | wc -l >> "$REPORT_FILE"

echo "" >> "$REPORT_FILE"
echo "Последние 5 бэкапов:" >> "$REPORT_FILE"
find "$BACKUP_DIR" -name "telegram_messages_*.db" -printf "%T@ %p\n" | sort -n | tail -5 | while read timestamp file; do
    date -d "@$timestamp" "+%Y-%m-%d %H:%M:%S" >> "$REPORT_FILE"
    stat -c "Размер: %s байт" "$file" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
done

echo "" >> "$REPORT_FILE"
echo "Использование диска:" >> "$REPORT_FILE"
df -h /opt/telegram-agent >> "$REPORT_FILE"

# Отправка отчета по email (опционально)
if command -v mail &> /dev/null; then
    mail -s "Backup Report - $(date)" admin@example.com < "$REPORT_FILE"
fi

echo "Отчет создан: $REPORT_FILE"
```

## Восстановление после сбоя

### 1. Процедура полного восстановления

```bash
#!/bin/bash
# /opt/telegram-agent/scripts/disaster-recovery.sh

BACKUP_DIR="/opt/telegram-agent/backups"
LATEST_BACKUP=$(find "$BACKUP_DIR" -name "full_backup_*.tar.gz" -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2)

echo "Катастрофическое восстановление из бэкапа: $LATEST_BACKUP"

# Остановка всех служб
sudo systemctl stop telegram-agent.service
sudo systemctl stop telegram-mcp.service 2>/dev/null || true
sudo systemctl stop wiki-mcp.service 2>/dev/null || true

# Создание резервной копии текущего состояния
echo "Создание резервной копии текущего состояния..."
tar -czf "$BACKUP_DIR/disaster_backup_$(date +%Y%m%d_%H%M%S).tar.gz" \
    -C /opt/telegram-agent \
    telegram_monitoring_agent/ \
    logs/ 2>/dev/null || true

# Восстановление из бэкапа
echo "Восстановление из полного бэкапа..."
cd /opt/telegram-agent
tar -xzf "$LATEST_BACKUP"

# Восстановление прав доступа
sudo chown -R telegram-agent:telegram-agent /opt/telegram-agent
sudo chmod 755 /opt/telegram-agent

# Проверка целостности БД
echo "Проверка целостности БД..."
sqlite3 /opt/telegram-agent/telegram_monitoring_agent/telegram_messages.db "PRAGMA integrity_check;"

# Запуск служб
echo "Запуск служб..."
sudo systemctl start telegram-agent.service

echo "Восстановление завершено. Проверьте статус служб:"
sudo systemctl status telegram-agent.service
```

## Оптимизация бэкапов

### 1. Сжатие старых бэкапов

```bash
#!/bin/bash
# /opt/telegram-agent/scripts/compress-old-backups.sh

BACKUP_DIR="/opt/telegram-agent/backups"
DAYS_TO_COMPRESS=7
DAYS_TO_DELETE=30

# Сжатие бэкапов старше N дней
find "$BACKUP_DIR" -name "telegram_messages_*.db" -mtime +$DAYS_TO_COMPRESS -exec gzip {} \;

# Удаление очень старых бэкапов
find "$BACKUP_DIR" -name "*.gz" -mtime +$DAYS_TO_DELETE -delete

echo "Оптимизация бэкапов завершена"
```

### 2. Дедупликация бэкапов

```bash
#!/bin/bash
# /opt/telegram-agent/scripts/deduplicate-backups.sh

BACKUP_DIR="/opt/telegram-agent/backups"

# Использование fdupes для поиска дубликатов
if command -v fdupes &> /dev/null; then
    echo "Поиск дубликатов в бэкапах..."
    fdupes -r "$BACKUP_DIR" | while read -r line; do
        if [[ $line == *.db* ]]; then
            files=($line)
            if [ ${#files[@]} -gt 1 ]; then
                echo "Найдены дубликаты: ${files[*]}"
                # Удаление дубликатов, оставляя самый новый
                for ((i=1; i<${#files[@]}; i++)); do
                    rm "${files[$i]}"
                    echo "Удален дубликат: ${files[$i]}"
                done
            fi
        fi
    done
fi

echo "Дедупликация завершена"
```

Эта документация предоставляет полный набор инструкций для резервного копирования и восстановления Telegram Monitoring Agent в различных сценариях.