"""
Планировщик задач для агента мониторинга
"""

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Callable, Any
from zoneinfo import ZoneInfo

from config import SchedulerConfig

logger = logging.getLogger(__name__)


class ScheduledTask:
    """Класс для представления запланированной задачи"""

    def __init__(
        self,
        name: str,
        func: Callable,
        schedule_time: time,
        timezone_str: str = "UTC",
        enabled: bool = True
    ):
        self.name = name
        self.func = func
        self.schedule_time = schedule_time
        self.timezone = ZoneInfo(timezone_str)
        self.enabled = enabled
        self.last_run = None
        self.next_run = self._calculate_next_run()
        self.is_interval = False

    def _calculate_next_run(self) -> datetime:
        """Расчет времени следующего запуска"""
        now = datetime.now(self.timezone)
        today_run = now.replace(
            hour=self.schedule_time.hour,
            minute=self.schedule_time.minute,
            second=self.schedule_time.second,
            microsecond=0
        )

        if today_run > now:
            return today_run
        else:
            return today_run + timedelta(days=1)

    def should_run(self, current_time: datetime) -> bool:
        """Проверка, нужно ли запустить задачу"""
        if not self.enabled:
            return False

        # Конвертируем текущее время в timezone задачи
        current_time_tz = current_time.astimezone(self.timezone)

        # Проверяем, наступило ли время запуска
        if current_time_tz >= self.next_run:
            # Проверяем, что задача не запускалась сегодня
            if (self.last_run is None or
                self.last_run.date() != current_time_tz.date()):
                return True

        return False

    def update_after_run(self, current_time: datetime):
        """Обновление времени после запуска"""
        current_time_tz = current_time.astimezone(self.timezone)
        self.last_run = current_time_tz
        self.next_run = self._calculate_next_run()

    def get_time_until_next_run(self, current_time: datetime) -> timedelta:
        """Получить время до следующего запуска"""
        current_time_tz = current_time.astimezone(self.timezone)
        return self.next_run - current_time_tz


class IntervalTask:
    """Класс для представления интервальной задачи"""

    def __init__(
        self,
        name: str,
        func: Callable,
        interval_seconds: int,
        enabled: bool = True
    ):
        self.name = name
        self.func = func
        self.interval_seconds = interval_seconds
        self.enabled = enabled
        self.last_run = None
        self.next_run = datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)
        self.is_interval = True

    def should_run(self, current_time: datetime) -> bool:
        """Проверка, нужно ли запустить задачу"""
        if not self.enabled:
            return False
        return current_time >= self.next_run

    def update_after_run(self, current_time: datetime):
        """Обновление времени после запуска"""
        self.last_run = current_time
        self.next_run = current_time + timedelta(seconds=self.interval_seconds)


class TaskScheduler:
    """Планировщик задач"""

    def __init__(self, config: SchedulerConfig):
        self.config = config
        self.tasks: Dict[str, ScheduledTask] = {}
        self.interval_tasks: Dict[str, IntervalTask] = {}
        self.running = False
        self._scheduler_task = None

    def add_daily_task(
        self,
        name: str,
        func: Callable,
        hour: int,
        minute: int = 0,
        enabled: bool = True
    ) -> bool:
        """Добавление ежедневной задачи"""
        try:
            schedule_time = time(hour=hour, minute=minute)
            task = ScheduledTask(
                name=name,
                func=func,
                schedule_time=schedule_time,
                timezone_str=self.config.timezone,
                enabled=enabled
            )

            self.tasks[name] = task
            logger.info(f"Added daily task '{name}' at {hour:02d}:{minute:02d} ({self.config.timezone})")
            return True

        except Exception as e:
            logger.error(f"Error adding daily task '{name}': {e}")
            return False

    def add_interval_task(
        self,
        name: str,
        func: Callable,
        interval_seconds: int,
        enabled: bool = True
    ) -> bool:
        """Добавление интервальной задачи"""
        try:
            task = IntervalTask(
                name=name,
                func=func,
                interval_seconds=interval_seconds,
                enabled=enabled
            )

            self.interval_tasks[name] = task
            logger.info(f"Added interval task '{name}' with interval {interval_seconds} seconds")
            return True

        except Exception as e:
            logger.error(f"Error adding interval task '{name}': {e}")
            return False

    def add_task(self, task: ScheduledTask) -> bool:
        """Добавление задачи"""
        try:
            self.tasks[task.name] = task
            logger.info(f"Added task '{task}' at {task.schedule_time} ({task.timezone})")
            return True

        except Exception as e:
            logger.error(f"Error adding task '{task.name}': {e}")
            return False

    def remove_task(self, name: str) -> bool:
        """Удаление задачи"""
        if name in self.tasks:
            del self.tasks[name]
            logger.info(f"Removed task '{name}'")
            return True
        else:
            logger.warning(f"Task '{name}' not found")
            return False

    def enable_task(self, name: str) -> bool:
        """Включение задачи"""
        if name in self.tasks:
            self.tasks[name].enabled = True
            logger.info(f"Enabled task '{name}'")
            return True
        else:
            logger.warning(f"Task '{name}' not found")
            return False

    def disable_task(self, name: str) -> bool:
        """Отключение задачи"""
        if name in self.tasks:
            self.tasks[name].enabled = False
            logger.info(f"Disabled task '{name}'")
            return True
        else:
            logger.warning(f"Task '{name}' not found")
            return False

    def get_task_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Получение статуса задачи"""
        if name in self.tasks:
            task = self.tasks[name]
            return {
                "name": task.name,
                "enabled": task.enabled,
                "schedule_time": task.schedule_time.isoformat(),
                "timezone": str(task.timezone),
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "next_run": task.next_run.isoformat() if task.next_run else None
            }
        else:
            return None

    def get_all_tasks_status(self) -> Dict[str, Dict[str, Any]]:
        """Получение статуса всех задач"""
        return {name: self.get_task_status(name) for name in self.tasks.keys()}

    async def start(self):
        """Запуск планировщика"""
        if self.running:
            logger.warning("Scheduler is already running")
            return

        self.running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Task scheduler started")

    async def stop(self):
        """Остановка планировщика"""
        self.running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("Task scheduler stopped")

    async def _scheduler_loop(self):
        """Основной цикл планировщика"""
        logger.info(f"Scheduler started with {len(self.tasks)} daily tasks and {len(self.interval_tasks)} interval tasks")

        while self.running:
            try:
                current_time = datetime.now(timezone.utc)

                # Проверяем все ежедневные задачи
                for task_name, task in self.tasks.items():
                    if task.should_run(current_time):
                        await self._run_task(task, current_time)

                # Проверяем все интервальные задачи
                for task_name, task in self.interval_tasks.items():
                    if task.should_run(current_time):
                        await self._run_interval_task(task, current_time)

                # Ждем до следующей минуты
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)

    async def _run_task(self, task: ScheduledTask, current_time: datetime):
        """Запуск задачи"""
        logger.info(f"Running scheduled task '{task.name}'")

        try:
            # Запускаем задачу
            if asyncio.iscoroutinefunction(task.func):
                await task.func()
            else:
                task.func()

            # Обновляем время запуска
            task.update_after_run(current_time)
            logger.info(f"Task '{task.name}' completed successfully")

        except Exception as e:
            logger.error(f"Error running task '{task.name}': {e}")
            # Все равно обновляем время, чтобы не запускать в случае ошибки
            task.update_after_run(current_time)

    async def _run_interval_task(self, task: IntervalTask, current_time: datetime):
        """Запуск интервальной задачи"""
        logger.debug(f"Running interval task '{task.name}'")

        try:
            # Запускаем задачу
            if asyncio.iscoroutinefunction(task.func):
                await task.func()
            else:
                task.func()

            # Обновляем время запуска
            task.update_after_run(current_time)
            logger.debug(f"Interval task '{task.name}' completed successfully")

        except Exception as e:
            logger.error(f"Error running interval task '{task.name}': {e}")
            # Все равно обновляем время, чтобы не запускать в случае ошибки
            task.update_after_run(current_time)

    async def run_task_now(self, name: str) -> bool:
        """Немедленный запуск задачи"""
        if name not in self.tasks:
            logger.warning(f"Task '{name}' not found")
            return False

        task = self.tasks[name]
        current_time = datetime.now(timezone.utc)

        logger.info(f"Running task '{name}' immediately")

        try:
            if asyncio.iscoroutinefunction(task.func):
                await task.func()
            else:
                task.func()

            logger.info(f"Task '{name}' completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error running task '{name}': {e}")
            return False


class DailySummaryScheduler:
    """Специализированный планировщик для ежедневных сводок"""

    def __init__(self, scheduler: TaskScheduler, config: SchedulerConfig):
        self.scheduler = scheduler
        self.config = config

    def setup_daily_summary_task(self, summary_func: Callable) -> bool:
        """Настройка ежедневной задачи суммаризации"""
        try:
            # Парсим время из конфигурации
            time_parts = self.config.daily_summary_time.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            # Добавляем задачу
            success = self.scheduler.add_daily_task(
                name="daily_summary",
                func=summary_func,
                hour=hour,
                minute=minute,
                enabled=True
            )

            if success:
                logger.info(f"Daily summary scheduled for {hour:02d}:{minute:02d} ({self.config.timezone})")

            return success

        except Exception as e:
            logger.error(f"Error setting up daily summary task: {e}")
            return False

    def get_next_summary_time(self) -> Optional[datetime]:
        """Получить время следующей сводки"""
        if "daily_summary" in self.scheduler.tasks:
            task = self.scheduler.tasks["daily_summary"]
            return task.next_run
        return None

    def get_time_until_next_summary(self) -> Optional[timedelta]:
        """Получить время до следующей сводки"""
        if "daily_summary" in self.scheduler.tasks:
            task = self.scheduler.tasks["daily_summary"]
            current_time = datetime.now(timezone.utc)
            return task.get_time_until_next_run(current_time)
        return None