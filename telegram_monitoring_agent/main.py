"""
Основной файл приложения Telegram Monitoring Agent
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from config import AppConfig, validate_config, RuntimeConfigManager
from database import Database
from telegram_collector import TelegramCollector
from summary_service import SummaryService
from scheduler import TaskScheduler, DailySummaryScheduler
from log_handler import DatabaseLogHandler
from log_service import LogService

# Глобальный database log handler
db_log_handler = DatabaseLogHandler()

# Настройка логирования
def setup_logging(config: AppConfig):
    """Настройка логирования"""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    # Создаем директорию для логов
    log_file = Path(config.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Настраиваем форматирование
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Настраиваем обработчики
    handlers = []

    # Файловый обработчик
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    handlers.append(file_handler)

    # Консольный обработчик с поддержкой Unicode
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    # Устанавливаем кодировку UTF-8 для консоли
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    handlers.append(console_handler)

    # Добавляем database handler
    db_log_handler.setFormatter(formatter)
    handlers.append(db_log_handler)

    # Настраиваем корневой логгер
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True
    )

    if config.debug:
        logging.getLogger().setLevel(logging.DEBUG)


class TelegramMonitoringAgent:
    """Основной класс агента мониторинга"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.runtime_config = RuntimeConfigManager()
        self.database = None
        self.telegram_collector = None
        self.summary_service = None
        self.log_service = None
        self.scheduler = None
        self.daily_scheduler = None
        self.collection_task = None
        self.running = False

    async def initialize(self) -> bool:
        """Инициализация агента"""
        try:
            logging.info("Initializing Telegram Monitoring Agent...")

            # Запуск runtime конфигурации
            await self.runtime_config.start()
            logging.info("Runtime configuration started")

            # Валидация конфигурации (с учетом runtime конфигурации)
            errors = validate_config(self.config, self.runtime_config)
            if errors:
                logging.error("Configuration validation failed:")
                for error in errors:
                    logging.error(f"  - {error}")
                return False

            # Инициализация базы данных
            self.database = Database(self.config.get_database_config())
            logging.info("Database initialized")

            # Подключаем database handler к БД
            db_log_handler.set_database(self.database)

            # Инициализация сборщика сообщений
            self.telegram_collector = TelegramCollector(
                self.config.get_telegram_config(),
                self.database
            )

            # Инициализация сервиса суммаризации
            self.summary_service = SummaryService(self.config)
            if not await self.summary_service.initialize():
                logging.error("Failed to initialize summary service")
                return False

            # Инициализация сервиса логов
            self.log_service = LogService(
                self.database,
                self.summary_service.wiki_client
            )
            logging.info("Log service initialized")

            # Инициализация планировщика
            self.scheduler = TaskScheduler(self.config.get_scheduler_config())
            self.daily_scheduler = DailySummaryScheduler(
                self.scheduler,
                self.config.get_scheduler_config()
            )

            # Передача runtime конфигурации в компоненты
            self.telegram_collector.set_runtime_config(self.runtime_config)
            self.scheduler.set_runtime_config(self.runtime_config)

            # Настройка задач планировщика
            await self._setup_scheduled_tasks()

            # Настройка подписчиков на изменения конфигурации
            await self._setup_config_subscribers()

            logging.info("Agent initialized successfully")
            return True

        except Exception as e:
            logging.error(f"Error initializing agent: {e}")
            return False

    async def _setup_scheduled_tasks(self):
        """Настройка запланированных задач"""
        try:
            scheduler_config = self.runtime_config.get_scheduler_config()

            # Задача ежедневной суммаризации
            daily_summary_config = scheduler_config.get('tasks', {}).get('daily_summary', {})
            if daily_summary_config.get('enabled', True):
                time_parts = daily_summary_config.get('time', '21:00').split(':')
                hour, minute = int(time_parts[0]), int(time_parts[1])
                self.daily_scheduler.setup_daily_summary_task(
                    self._daily_summary_task,
                    hour=hour,
                    minute=minute
                )

            # Задачи периодической генерации отчетов
            periodic_reports_config = scheduler_config.get('tasks', {}).get('periodic_reports', {})
            if periodic_reports_config.get('enabled', True):
                times = periodic_reports_config.get('times', ['08:00', '14:00', '21:30'])
                for i, time_str in enumerate(times):
                    time_parts = time_str.split(':')
                    hour, minute = int(time_parts[0]), int(time_parts[1])
                    task_name = f"periodic_reports_{i}" if i > 0 else "periodic_reports"
                    self.scheduler.add_daily_task(
                        name=task_name,
                        func=self._periodic_reports_task,
                        hour=hour,
                        minute=minute
                    )

            # Задача записи логов в Wiki
            write_logs_config = scheduler_config.get('tasks', {}).get('write_logs_to_wiki', {})
            if write_logs_config.get('enabled', True):
                interval_seconds = write_logs_config.get('interval_seconds', 3600)
                self.scheduler.add_interval_task(
                    name="write_logs_to_wiki",
                    func=self._write_logs_task,
                    interval_seconds=interval_seconds
                )

            # Задача очистки старых данных
            cleanup_data_config = scheduler_config.get('tasks', {}).get('cleanup_data', {})
            if cleanup_data_config.get('enabled', True):
                time_parts = cleanup_data_config.get('time', '03:00').split(':')
                hour, minute = int(time_parts[0]), int(time_parts[1])
                self.scheduler.add_daily_task(
                    name="cleanup_old_data",
                    func=self._cleanup_task,
                    hour=hour,
                    minute=minute
                )

            # Задача очистки старых логов
            cleanup_logs_config = scheduler_config.get('tasks', {}).get('cleanup_logs', {})
            if cleanup_logs_config.get('enabled', True):
                time_parts = cleanup_logs_config.get('time', '02:00').split(':')
                hour, minute = int(time_parts[0]), int(time_parts[1])
                self.scheduler.add_daily_task(
                    name="cleanup_old_logs",
                    func=self._cleanup_logs_task,
                    hour=hour,
                    minute=minute
                )

            logging.info("Scheduled tasks configured from runtime configuration")

        except Exception as e:
            logging.error(f"Error setting up scheduled tasks: {e}")

    async def _setup_config_subscribers(self):
        """Настройка подписчиков на изменения конфигурации"""
        try:
            # Подписка на изменения списка чатов
            self.runtime_config.subscribe('telegram.monitored_chats', self._on_monitored_chats_changed)

            # Подписка на изменения планировщика
            self.runtime_config.subscribe('scheduler.tasks', self._on_scheduler_tasks_changed)

            # Подписка на изменения интервалов сбора
            self.runtime_config.subscribe('telegram.collection.interval_seconds', self._on_collection_interval_changed)

            logging.info("Configuration subscribers set up")

        except Exception as e:
            logging.error(f"Error setting up config subscribers: {e}")

    async def _on_monitored_chats_changed(self, old_chats, new_chats):
        """Обработчик изменения списка отслеживаемых чатов"""
        try:
            if old_chats != new_chats:
                logging.info(f"Monitored chats changed: {old_chats} -> {new_chats}")
                # Обновление конфигурации сборщика сообщений
                if self.telegram_collector:
                    await self.telegram_collector.update_monitored_chats(new_chats)
        except Exception as e:
            logging.error(f"Error handling monitored chats change: {e}")

    async def _on_scheduler_tasks_changed(self, old_config, new_config):
        """Обработчик изменения конфигурации планировщика"""
        try:
            logging.info("Scheduler tasks configuration changed")
            # Перенастройка задач планировщика
            await self._reconfigure_scheduler_tasks(new_config)
        except Exception as e:
            logging.error(f"Error handling scheduler tasks change: {e}")

    async def _on_collection_interval_changed(self, old_interval, new_interval):
        """Обработчик изменения интервала сбора сообщений"""
        try:
            if old_interval != new_interval:
                logging.info(f"Collection interval changed: {old_interval}s -> {new_interval}s")
                # Обновление интервала в сборщике сообщений
                if self.telegram_collector:
                    await self.telegram_collector.update_collection_interval(new_interval)
        except Exception as e:
            logging.error(f"Error handling collection interval change: {e}")

    async def _reconfigure_scheduler_tasks(self, new_scheduler_config):
        """Перенастройка задач планировщика"""
        try:
            # Отключаем старые задачи
            await self.scheduler.clear_all_tasks()

            # Обновляем конфигурацию планировщика
            self.scheduler.config = new_scheduler_config

            # Настраиваем новые задачи
            await self._setup_scheduled_tasks()

            logging.info("Scheduler tasks reconfigured successfully")
        except Exception as e:
            logging.error(f"Error reconfiguring scheduler tasks: {e}")

    async def start(self) -> bool:
        """Запуск агента"""
        try:
            if not await self.initialize():
                return False

            logging.info("Starting Telegram Monitoring Agent...")

            # Запуск сборщика сообщений
            if not await self.telegram_collector.start():
                logging.error("Failed to start Telegram collector")
                return False

            # Запуск цикла сбора сообщений
            self.collection_task = asyncio.create_task(self.telegram_collector.run_collection_loop())

            # Запуск планировщика
            await self.scheduler.start()

            self.running = True
            logging.info("Agent started successfully")

            # Запуск основного цикла
            await self._main_loop()

            return True

        except Exception as e:
            logging.error(f"Error starting agent: {e}")
            return False

    async def stop(self):
        """Остановка агента"""
        logging.info("Stopping Telegram Monitoring Agent...")

        self.running = False

        # Остановка задачи сбора сообщений
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass

        # Остановка компонентов
        if self.telegram_collector:
            await self.telegram_collector.stop()

        if self.scheduler:
            await self.scheduler.stop()

        # Остановка runtime конфигурации
        if self.runtime_config:
            await self.runtime_config.stop()

        logging.info("Agent stopped")

    async def _main_loop(self):
        """Основной цикл агента"""
        try:
            # Основной цикл просто ждет сигнала остановки
            # Health check выполняется только при запуске
            while self.running:
                await asyncio.sleep(60)  # Проверяем флаг running каждую минуту

        except asyncio.CancelledError:
            logging.info("Main loop cancelled")
        except Exception as e:
            logging.error(f"Error in main loop: {e}")

    async def _daily_summary_task(self):
        """Задача ежедневной суммаризации"""
        try:
            logging.info("Starting daily summary task")
            success = await self.summary_service.create_daily_summary()

            if success:
                logging.info("Daily summary completed successfully")
            else:
                logging.error("Daily summary failed")

        except Exception as e:
            logging.error(f"Error in daily summary task: {e}")

    async def _periodic_reports_task(self):
        """Задача периодической генерации отчетов"""
        try:
            logging.info("Starting periodic reports task")
            results = await self.summary_service.create_periodic_reports()

            successful = sum(1 for success in results.values() if success)
            total = len(results)

            logging.info(f"Periodic reports completed: {successful}/{total} successful")

        except Exception as e:
            logging.error(f"Error in periodic reports task: {e}")

    async def _cleanup_task(self):
        """Задача очистки старых данных"""
        try:
            logging.info("Starting cleanup task")
            deleted_count = await self.summary_service.cleanup_old_reports()
            logging.info(f"Cleanup completed: {deleted_count} items deleted")

        except Exception as e:
            logging.error(f"Error in cleanup task: {e}")

    async def _write_logs_task(self):
        """Задача записи логов в Wiki"""
        try:
            logging.debug("Starting write logs to Wiki task")
            success = await self.log_service.write_logs_to_wiki()
            
            if success:
                logging.debug("Logs written to Wiki successfully")
            else:
                logging.warning("Failed to write logs to Wiki")

        except Exception as e:
            logging.error(f"Error in write logs task: {e}")

    async def _cleanup_logs_task(self):
        """Задача очистки старых логов"""
        try:
            logging.info("Starting cleanup logs task")
            deleted_count = await self.log_service.cleanup_old_logs()
            logging.info(f"Cleanup logs completed: {deleted_count} items deleted")

        except Exception as e:
            logging.error(f"Error in cleanup logs task: {e}")

    async def get_status(self) -> dict:
        """Получение статуса агента"""
        try:
            if not self.summary_service:
                return {"status": "not_initialized"}

            return await self.summary_service.get_service_status()

        except Exception as e:
            logging.error(f"Error getting agent status: {e}")
            return {"status": "error", "error": str(e)}


# Глобальные переменные для управления агентом
agent: Optional[TelegramMonitoringAgent] = None
shutdown_event = asyncio.Event()


async def main():
    """Основная функция"""
    try:
        # Загрузка конфигурации
        config = AppConfig()

        # Настройка логирования
        setup_logging(config)

        logging.info("Starting Telegram Monitoring Agent...")

        # Создание агента
        global agent
        agent = TelegramMonitoringAgent(config)

        # Установка обработчиков сигналов
        def signal_handler(signum, frame):
            logging.info(f"Received signal {signum}, shutting down...")
            shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Запуск агента
        agent_task = asyncio.create_task(agent.start())

        # Ожидание сигнала завершения
        await shutdown_event.wait()

        # Остановка агента
        logging.info("Shutting down agent...")
        agent_task.cancel()

        try:
            await agent_task
        except asyncio.CancelledError:
            pass

        await agent.stop()
        logging.info("Agent shutdown complete")

    except Exception as e:
        logging.error(f"Fatal error in main: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt, exiting...")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)