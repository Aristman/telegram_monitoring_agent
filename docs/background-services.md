# Запуск в фоновом режиме

## Обзор

Для запуска Telegram Monitoring Agent в фоновом режиме используются системные службы systemd (Linux) или службы Windows (Windows).

## Linux (systemd)

### 1. Основной агент мониторинга

Создайте файл службы `/etc/systemd/system/telegram-agent.service`:

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
StandardOutput=append:/opt/telegram-agent/telegram_monitoring_agent/telegram_monitor.log
StandardError=append:/opt/telegram-agent/telegram_monitoring_agent/telegram_monitor.log

[Install]
WantedBy=multi-user.target
```

### 2. Telegram MCP сервер (если запускается отдельно)

Создайте файл службы `/etc/systemd/system/telegram-mcp.service`:

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
StandardOutput=append:/opt/telegram-agent/logs/telegram-mcp.log
StandardError=append:/opt/telegram-agent/logs/telegram-mcp.log

[Install]
WantedBy=multi-user.target
```

### 3. Yandex Wiki MCP сервер

Создайте файл службы `/etc/systemd/system/wiki-mcp.service`:

```ini
[Unit]
Description=Yandex Wiki MCP Server
After=network.target

[Service]
Type=simple
User=telegram-agent
WorkingDirectory=/opt/telegram-agent/yandex_wiki_mcp
Environment=PATH=/opt/telegram-agent/venv/bin
ExecStart=/opt/telegram-agent/venv/bin/python -m main
Restart=on-failure
RestartSec=10
StandardOutput=append:/opt/telegram-agent/logs/wiki-mcp.log
StandardError=append:/opt/telegram-agent/logs/wiki-mcp.log

[Install]
WantedBy=multi-user.target
```

### Управление службами

```bash
# Перезагрузка systemd после создания/изменения служб
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable telegram-agent.service
sudo systemctl enable telegram-mcp.service    # если нужно
sudo systemctl enable wiki-mcp.service       # если нужно

# Запуск служб
sudo systemctl start telegram-agent.service
sudo systemctl start telegram-mcp.service    # если нужно
sudo systemctl start wiki-mcp.service       # если нужно

# Проверка статуса
sudo systemctl status telegram-agent.service

# Просмотр логов
sudo journalctl -u telegram-agent.service -f

# Остановка служб
sudo systemctl stop telegram-agent.service
sudo systemctl stop telegram-mcp.service    # если нужно
sudo systemctl stop wiki-mcp.service       # если нужно

# Перезапуск служб
sudo systemctl restart telegram-agent.service
```

### 4. Настройка зависимостей между службами

Если MCP серверы должны запускаться перед основным агентом:

```ini
[Unit]
Description=Telegram Monitoring Agent
After=network.target telegram-mcp.service wiki-mcp.service
Wants=telegram-mcp.service wiki-mcp.service
```

## Windows (сервисы)

### 1. Установка NSSM (Non-Sucking Service Manager)

Скачайте и установите NSSM: https://nssm.cc/download

### 2. Создание службы для основного агента

```cmd
# Установка службы
nssm install TelegramAgent "C:\opt\telegram-agent\venv\Scripts\python.exe"
nssm set TelegramAgent Arguments "-m main"
nssm set TelegramAgent WorkingDirectory "C:\opt\telegram-agent\telegram_monitoring_agent"
nssm set TelegramAgent DisplayName "Telegram Monitoring Agent"
nssm set TelegramAgent Description "Telegram chat monitoring and reporting agent"
nssm set TelegramAgent Start SERVICE_AUTO_START
nssm set TelegramAgent AppEnvironmentExtra "PYTHONPATH=C:\opt\telegram-agent\telegram_monitoring_agent"
nssm set TelegramAgent AppStdout "C:\opt\telegram-agent\logs\telegram-agent.log"
nssm set TelegramAgent AppStderr "C:\opt\telegram-agent\logs\telegram-agent-error.log"
```

### 3. Создание службы для Telegram MCP сервера

```cmd
nssm install TelegramMCP "C:\opt\telegram-agent\venv\Scripts\python.exe"
nssm set TelegramMCP Arguments "-m main"
nssm set TelegramMCP WorkingDirectory "C:\opt\telegram-agent\telegram_mcp_server_py"
nssm set TelegramMCP DisplayName "Telegram MCP Server"
nssm set TelegramMCP Description "Telegram MCP server for agent communication"
nssm set TelegramMCP Start SERVICE_AUTO_START
nssm set TelegramMCP AppStdout "C:\opt\telegram-agent\logs\telegram-mcp.log"
nssm set TelegramMCP AppStderr "C:\opt\telegram-agent\logs\telegram-mcp-error.log"
```

### 4. Управление службами Windows

```cmd
# Запуск службы
nssm start TelegramAgent
nssm start TelegramMCP

# Остановка службы
nssm stop TelegramAgent
nssm stop TelegramMCP

# Проверка статуса
nssm status TelegramAgent
nssm status TelegramMCP

# Удаление службы
nssm remove TelegramAgent
nssm remove TelegramMCP
```

## Docker (альтернативный вариант)

### 1. Создание Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY telegram_monitoring_agent/ ./telegram_monitoring_agent/
COPY telegram_mcp_server_py/ ./telegram_mcp_server_py/
COPY yandex_wiki_mcp/ ./yandex_wiki_mcp/

# Создание пользователя
RUN useradd -m -u 1000 agent
USER agent

# Команда запуска
CMD ["python", "-m", "telegram_monitoring_agent.main"]
```

### 2. Создание docker-compose.yml

```yaml
version: '3.8'

services:
  telegram-agent:
    build: .
    container_name: telegram-agent
    restart: unless-stopped
    environment:
      - YANDEX_API_KEY=${YANDEX_API_KEY}
      - YANDEX_FOLDER_ID=${YANDEX_FOLDER_ID}
    volumes:
      - ./config:/app/telegram_monitoring_agent/config
      - ./logs:/app/logs
      - ./data:/app/data
    networks:
      - telegram-network

  telegram-mcp:
    build:
      context: .
      dockerfile: Dockerfile.mcp
    container_name: telegram-mcp
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
    networks:
      - telegram-network

networks:
  telegram-network:
    driver: bridge
```

### 3. Запуск Docker

```bash
# Сборка и запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f telegram-agent

# Остановка
docker-compose down

# Перезапуск
docker-compose restart telegram-agent
```

## Cron задачи (альтернативный вариант)

### 1. Создание скрипта запуска

```bash
#!/bin/bash
# /opt/telegram-agent/start-agent.sh

cd /opt/telegram-agent/telegram_monitoring_agent
source ../venv/bin/activate

# Проверка, не запущен ли уже процесс
if pgrep -f "python -m main" > /dev/null; then
    echo "Telegram Agent уже запущен"
    exit 0
fi

# Запуск в фоновом режиме
nohup python -m main > /opt/telegram-agent/logs/agent.log 2>&1 &
echo $! > /opt/telegram-agent/agent.pid

echo "Telegram Agent запущен с PID $(cat /opt/telegram-agent/agent.pid)"
```

### 2. Настройка Cron

```bash
# Редактирование crontab
crontab -e
```

```cron
# Запуск при загрузке системы
@reboot /opt/telegram-agent/start-agent.sh

# Проверка каждые 5 минут и перезапуск если упал
*/5 * * * * pgrep -f "python -m main" > /dev/null || /opt/telegram-agent/start-agent.sh
```

### 3. Скрипт остановки

```bash
#!/bin/bash
# /opt/telegram-agent/stop-agent.sh

if [ -f /opt/telegram-agent/agent.pid ]; then
    PID=$(cat /opt/telegram-agent/agent.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        rm /opt/telegram-agent/agent.pid
        echo "Telegram Agent остановлен"
    else
        echo "Процесс не найден"
    fi
else
    echo "PID файл не найден"
fi
```

## Мониторинг фоновых процессов

### Linux

```bash
# Проверка статуса службы
sudo systemctl status telegram-agent.service

# Просмотр логов в реальном времени
sudo journalctl -u telegram-agent.service -f

# Проверка использования ресурсов
htop
ps aux | grep python
top -p $(pgrep -f "python -m main")
```

### Windows

```cmd
# Просмотр служб
services.msc

# Просмотр процессов
tasklist | findstr python

# Просмотр логов
type "C:\opt\telegram-agent\logs\telegram-agent.log"
```

## Автоматический перезапуск при сбоях

### Systemd (Linux)

```ini
[Service]
Restart=always
RestartSec=10
StartLimitInterval=60
StartLimitBurst=5
```

### NSSM (Windows)

```cmd
# Настройка автоматического перезапуска
nssm set TelegramAgent AppExit Default Restart
nssm set TelegramAgent AppRestartDelay 10000
```

## Логирование фоновых процессов

### Настройка ротации логов

```bash
# Создание файла logrotate
sudo nano /etc/logrotate.d/telegram-agent
```

```
/opt/telegram-agent/logs/*.log {
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

### Просмотр логов

```bash
# Просмотр последних строк
tail -f /opt/telegram-agent/logs/telegram-monitor.log

# Поиск ошибок в логах
grep ERROR /opt/telegram-agent/logs/telegram-monitor.log

# Статистика по логам
wc -l /opt/telegram-agent/logs/telegram-monitor.log
```