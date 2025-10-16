"""
Основной файл приложения Telegram Monitoring Agent
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from config import AppConfig, validate_config
from database import Database
from telegram_collector import TelegramCollector
from summary_service import SummaryService
from scheduler import TaskScheduler, DailySummaryScheduler

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
        self.database = None
        self.telegram_collector = None
        self.summary_service = None
        self.scheduler = None
        self.daily_scheduler = None
        self.collection_task = None
        self.running = False

    async def initialize(self) -> bool:
        """Инициализация агента"""
        try:
            logging.info("Initializing Telegram Monitoring Agent...")

            # Валидация конфигурации
            errors = validate_config(self.config)
            if errors:
                logging.error("Configuration validation failed:")
                for error in errors:
                    logging.error(f"  - {error}")
                return False

            # Инициализация базы данных
            self.database = Database(self.config.get_database_config())
            logging.info("Database initialized")

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

            # Инициализация планировщика
            self.scheduler = TaskScheduler(self.config.get_scheduler_config())
            self.daily_scheduler = DailySummaryScheduler(
                self.scheduler,
                self.config.get_scheduler_config()
            )

            # Настройка задач планировщика
            await self._setup_scheduled_tasks()

            logging.info("Agent initialized successfully")
            return True

        except Exception as e:
            logging.error(f"Error initializing agent: {e}")
            return False

    async def _setup_scheduled_tasks(self):
        """Настройка запланированных задач"""
        try:
            # Задача ежедневной суммаризации
            self.daily_scheduler.setup_daily_summary_task(
                self._daily_summary_task
            )

            # Задача периодической генерации отчетов (каждые 2 часа)
            self.scheduler.add_daily_task(
                name="periodic_reports",
                func=self._periodic_reports_task,
                hour=8, minute=0  # 08:00
            )

            self.scheduler.add_daily_task(
                name="periodic_reports_afternoon",
                func=self._periodic_reports_task,
                hour=14, minute=0  # 14:00
            )

            self.scheduler.add_daily_task(
                name="periodic_reports_evening",
                func=self._periodic_reports_task,
                hour=3, minute=3  # 18:00
            )

            # Задача очистки старых данных (каждую неделю в 3:00)
            self.scheduler.add_daily_task(
                name="cleanup_old_data",
                func=self._cleanup_task,
                hour=3, minute=0
            )

            logging.info("Scheduled tasks configured")

        except Exception as e:
            logging.error(f"Error setting up scheduled tasks: {e}")

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

        logging.info("Agent stopped")

    async def _main_loop(self):
        """Основной цикл агента"""
        try:
            while self.running:
                # Проверяем статус компонентов
                await self._health_check()

                # Ждем перед следующей проверкой
                await asyncio.sleep(300)  # 5 минут

        except asyncio.CancelledError:
            logging.info("Main loop cancelled")
        except Exception as e:
            logging.error(f"Error in main loop: {e}")

    async def _health_check(self):
        """Проверка здоровья компонентов"""
        try:
            # Проверяем статус сервиса суммаризации
            status = await self.summary_service.get_service_status()

            if not status.get('wiki_connected'):
                logging.warning("Wiki service is not connected")

            if not status.get('gpt_connected'):
                logging.warning("GPT service is not connected")

            # Логируем статистику
            active_chats = status.get('active_chats_count', 0)
            if active_chats > 0:
                logging.debug(f"Monitoring {active_chats} active chats")

        except Exception as e:
            logging.error(f"Error during health check: {e}")

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