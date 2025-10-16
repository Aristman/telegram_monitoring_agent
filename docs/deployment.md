# Развертывание на виртуальной машине

## Подготовка виртуальной машины

### Системные требования

- **ОС**: Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **CPU**: 2+ cores
- **RAM**: 4GB+ (рекомендуется 8GB)
- **Диск**: 20GB+ SSD
- **Сеть**: Доступ к API Telegram и Yandex Cloud

### Установка зависимостей

#### Ubuntu/Debian:
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Python и зависимостей
sudo apt install -y python3 python3-pip python3-venv git sqlite3 nginx

# Установка дополнительных пакетов
sudo apt install -y build-essential python3-dev
```

#### CentOS/RHEL:
```bash
# Обновление системы
sudo yum update -y

# Установка EPEL и Python
sudo yum install -y epel-release
sudo yum install -y python3 python3-pip git sqlite3 nginx
sudo yum groupinstall -y "Development Tools"
sudo yum install -y python3-devel
```

## Создание пользователя приложения

```bash
# Создание пользователя
sudo useradd -m -s /bin/bash telegram-agent
sudo usermod -aG sudo telegram-agent

# Переключение на пользователя
sudo su - telegram-agent
```

## Развертывание приложения

### 1. Клонирование репозитория

```bash
# Клонирование из Git
git clone <repository-url> /opt/telegram-agent
cd /opt/telegram-agent

# Установка прав доступа
sudo chown -R telegram-agent:telegram-agent /opt/telegram-agent
```

### 2. Настройка Python окружения

```bash
# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r telegram_monitoring_agent/requirements.txt
```

### 3. Настройка конфигурации

```bash
# Создание .env файла
cp telegram_monitoring_agent/.env.example telegram_monitoring_agent/.env
nano telegram_monitoring_agent/.env
```

**Минимальный .env:**
```bash
YANDEX_API_KEY=your_api_key_here
YANDEX_FOLDER_ID=your_folder_id_here
DEBUG=false
```

**Настройка config/settings.yaml:**
```bash
nano telegram_monitoring_agent/config/settings.yaml
```

Пример конфигурации:
```yaml
telegram:
  monitored_chats:
    - "chat_name_or_id"
  collection:
    interval_seconds: 1800
    max_messages_per_fetch: 100

scheduler:
  timezone: "Europe/Moscow"
  tasks:
    daily_summary:
      enabled: true
      time: "21:00"
```

### 4. Первоначальный запуск и тестирование

```bash
cd /opt/telegram-agent/telegram_monitoring_agent

# Запуск в консоли для проверки
source ../venv/bin/activate
python -m main
```

Проверьте, что приложение запускается без ошибок и видит настроенные чаты.

## Настройка systemd для автоматического запуска

### 1. Создание службы для основного агента

```bash
sudo nano /etc/systemd/system/telegram-agent.service
```

**Содержимое файла:**
```ini
[Unit]
Description=Telegram Monitoring Agent
After=network.target
Wants=network.target

[Service]
Type=simple
User=telegram-agent
Group=telegram-agent
WorkingDirectory=/opt/telegram-agent/telegram_monitoring_agent
Environment=PATH=/opt/telegram-agent/venv/bin
ExecStart=/opt/telegram-agent/venv/bin/python -m main
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Включение и запуск службы

```bash
# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable telegram-agent.service

# Запуск службы
sudo systemctl start telegram-agent.service

# Проверка статуса
sudo systemctl status telegram-agent.service
```

### 3. Создание службы для MCP серверов (опционально)

Если нужно запускать MCP серверы отдельно:

```bash
sudo nano /etc/systemd/system/telegram-mcp.service
```

**Содержимое файла:**
```ini
[Unit]
Description=Telegram MCP Server
After=network.target

[Service]
Type=simple
User=telegram-agent
WorkingDirectory=/opt/telegram-agent/telegram_mcp_server_py
Environment=PATH=/opt/telegram-agent/venv/bin
ExecStart=/opt/telegram-agent/venv/bin/python -m main
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Настройка Nginx (опционально)

Если нужно веб-интерфейс или API:

```bash
sudo nano /etc/nginx/sites-available/telegram-agent
```

**Конфигурация Nginx:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/telegram-agent/static/;
    }
}
```

```bash
# Включение сайта
sudo ln -s /etc/nginx/sites-available/telegram-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Обновление приложения

### Автоматическое обновление через Git

```bash
# Создание скрипта обновления
sudo nano /opt/telegram-agent/update.sh
```

**Содержимое скрипта:**
```bash
#!/bin/bash

cd /opt/telegram-agent

# Остановка службы
sudo systemctl stop telegram-agent.service

# Обновление кода
git pull origin main

# Обновление зависимостей
source venv/bin/activate
pip install -r telegram_monitoring_agent/requirements.txt

# Запуск службы
sudo systemctl start telegram-agent.service

echo "Обновление завершено"
```

```bash
# Права на выполнение
sudo chmod +x /opt/telegram-agent/update.sh
```

### Обновление вручную

```bash
# 1. Остановка службы
sudo systemctl stop telegram-agent.service

# 2. Обновление кода
cd /opt/telegram-agent
git pull origin main

# 3. Обновление зависимостей
source venv/bin/activate
pip install -r telegram_monitoring_agent/requirements.txt

# 4. Запуск службы
sudo systemctl start telegram-agent.service

# 5. Проверка статуса
sudo systemctl status telegram-agent.service
```

## Мониторинг и логирование

### Просмотр логов

```bash
# Логи systemd
sudo journalctl -u telegram-agent.service -f

# Логи приложения
tail -f /opt/telegram-agent/telegram_monitoring_agent/telegram_monitor.log
```

### Настройка ротации логов

```bash
sudo nano /etc/logrotate.d/telegram-agent
```

**Конфигурация logrotate:**
```
/opt/telegram-agent/telegram_monitoring_agent/telegram_monitor.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 telegram-agent telegram-agent
    postrotate
        systemctl reload telegram-agent.service
    endscript
}
```

## Безопасность

### 1. Настройка файрвола

```bash
# Ubuntu/Debian
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# CentOS/RHEL
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 2. Ограничение доступа к файлам

```bash
# Права на конфигурационные файлы
chmod 600 /opt/telegram-agent/telegram_monitoring_agent/.env
chmod 644 /opt/telegram-agent/telegram_monitoring_agent/config/settings.yaml

# Владелец файлов
sudo chown -R telegram-agent:telegram-agent /opt/telegram-agent
```

## Поиск неисправностей

### Проверка статуса службы

```bash
# Статус службы
sudo systemctl status telegram-agent.service

# Последние логи
sudo journalctl -u telegram-agent.service --no-pager -l

# Логи в реальном времени
sudo journalctl -u telegram-agent.service -f
```

### Проверка конфигурации

```bash
# Проверка .env файла
cd /opt/telegram-agent/telegram_monitoring_agent
source ../venv/bin/activate
python -c "from config import AppConfig; print('Config OK')"

# Проверка runtime конфигурации
python -c "from config import RuntimeConfigManager; rc = RuntimeConfigManager(); print('Runtime config OK')"
```

### Тестирование компонентов

```bash
# Тест подключения к Telegram API
python -c "
from telegram_collector import TelegramCollector
from database import Database
from config import AppConfig
config = AppConfig()
db = Database(config.get_database_config())
collector = TelegramCollector(config.get_telegram_config(), db)
print('Telegram collector OK')
"

# Тест подключения к Yandex API
python -c "
from yandex_gpt import YandexGPTClient
from config import AppConfig
config = AppConfig()
client = YandexGPTClient(config.get_gpt_config())
print('Yandex GPT client OK')
"
```