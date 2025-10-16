"""
Runtime конфигурация с поддержкой горячей перезагрузки
"""

import asyncio
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import time

logger = logging.getLogger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """Обработчик событий файловой системы для конфигурационного файла"""

    def __init__(self, callback: Callable, loop: asyncio.AbstractEventLoop):
        self.callback = callback
        self.loop = loop
        self._last_modified = 0

    def on_modified(self, event):
        """Обработчик изменения файла"""
        if event.is_directory:
            return

        # Проверяем, что это наш файл и не слишком частые изменения
        import time as time_module
        current_time = time_module.time()
        if current_time - self._last_modified < 1.0:  # Не чаще 1 раза в секунду
            return

        self._last_modified = current_time
        logger.debug("Configuration file modified, triggering reload")

        # Планируем задачу в основном event loop
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.callback(), self.loop)


class RuntimeConfigManager:
    """Менеджер runtime конфигурации с поддержкой горячей перезагрузки"""

    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._observers: Dict[str, List[Callable]] = {}
        self._file_observer = Observer()
        self._lock = asyncio.Lock()
        self._loaded = False

    async def start(self):
        """Запуск мониторинга конфигурации"""
        try:
            await self._load_config()
            self._setup_file_watcher()
            self._loaded = True
            logger.info(f"Runtime config manager started with {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to start runtime config manager: {e}")
            raise

    async def stop(self):
        """Остановка мониторинга"""
        if self._file_observer.is_alive():
            self._file_observer.stop()
            self._file_observer.join()
        logger.info("Runtime config manager stopped")

    async def _load_config(self):
        """Загрузка конфигурации из файла"""
        async with self._lock:
            try:
                if not self.config_path.exists():
                    logger.warning(f"Config file {self.config_path} not found, creating default")
                    await self._create_default_config()

                with open(self.config_path, 'r', encoding='utf-8') as f:
                    new_config = yaml.safe_load(f)

                # Валидация
                if self._validate_config(new_config):
                    old_config = self._config.copy()
                    self._config = new_config

                    # Уведомление подписчиков об изменениях
                    if self._loaded:  # Не уведомляем при первой загрузке
                        await self._notify_changes(old_config, new_config)

                    logger.debug("Configuration loaded successfully")
                else:
                    logger.error("Configuration validation failed")

            except Exception as e:
                logger.error(f"Error loading config: {e}")
                if not self._config:
                    # Если это первая загрузка и она не удалась, используем значения по умолчанию
                    await self._create_default_config()

    def _setup_file_watcher(self):
        """Настройка наблюдения за файлом"""
        try:
            # Получаем текущий event loop
            loop = asyncio.get_running_loop()
            event_handler = ConfigFileHandler(self._on_file_changed, loop)
            self._file_observer.schedule(
                event_handler,
                str(self.config_path.parent),
                recursive=False
            )
            self._file_observer.start()
            logger.debug("File watcher started")
        except Exception as e:
            logger.error(f"Failed to setup file watcher: {e}")

    async def _on_file_changed(self):
        """Обработчик изменения файла"""
        try:
            logger.info("Configuration file changed, reloading...")
            await self._load_config()
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """Валидация конфигурации"""
        try:
            # Базовая валидация структуры
            if not isinstance(config, dict):
                logger.error("Configuration must be a dictionary")
                return False

            # Валидация секции telegram
            if 'telegram' in config:
                telegram_config = config['telegram']
                if 'monitored_chats' in telegram_config:
                    chats = telegram_config['monitored_chats']
                    if not isinstance(chats, list):
                        logger.error("monitored_chats must be a list")
                        return False

                if 'collection' in telegram_config:
                    collection = telegram_config['collection']
                    if 'interval_seconds' in collection:
                        if not isinstance(collection['interval_seconds'], int) or collection['interval_seconds'] < 1:
                            logger.error("interval_seconds must be a positive integer")
                            return False

            # Валидация секции scheduler
            if 'scheduler' in config:
                scheduler_config = config['scheduler']
                if 'tasks' in scheduler_config:
                    tasks = scheduler_config['tasks']
                    if not isinstance(tasks, dict):
                        logger.error("scheduler.tasks must be a dictionary")
                        return False

                    # Валидация формата времени
                    for task_name, task_config in tasks.items():
                        if 'time' in task_config:
                            time_str = task_config['time']
                            try:
                                time.fromisoformat(time_str)
                            except ValueError:
                                logger.error(f"Invalid time format for {task_name}: {time_str}")
                                return False

            logger.debug("Configuration validation passed")
            return True

        except Exception as e:
            logger.error(f"Configuration validation error: {e}")
            return False

    async def _create_default_config(self):
        """Создание конфигурации по умолчанию"""
        default_config = {
            'telegram': {
                'monitored_chats': [],
                'collection': {
                    'interval_seconds': 300,
                    'max_messages_per_fetch': 100
                }
            },
            'scheduler': {
                'timezone': 'Europe/Moscow',
                'tasks': {
                    'daily_summary': {
                        'enabled': True,
                        'time': '21:00'
                    },
                    'periodic_reports': {
                        'enabled': True,
                        'times': ['08:00', '14:00', '21:30']
                    },
                    'write_logs_to_wiki': {
                        'enabled': True,
                        'interval_seconds': 3600
                    },
                    'cleanup_data': {
                        'enabled': True,
                        'time': '03:00',
                        'retention_days': 30
                    },
                    'cleanup_logs': {
                        'enabled': True,
                        'time': '02:00',
                        'retention_days': 7
                    }
                }
            },
            'wiki': {
                'base_folder': 'telegram_report',
                'page_naming': {
                    'date_format': '%Y-%m-%d',
                    'include_chat_title': True
                }
            },
            'logging': {
                'level': 'INFO',
                'file': 'telegram_monitor.log',
                'max_file_size_mb': 10,
                'backup_count': 5
            }
        }

        # Создаем директорию если не существует
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Сохраняем конфигурацию
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False,
                     allow_unicode=True, indent=2)

        logger.info(f"Default configuration created at {self.config_path}")

    async def _notify_changes(self, old_config: Dict[str, Any], new_config: Dict[str, Any]):
        """Уведомление подписчиков об изменениях"""
        try:
            # Находим измененные ключи
            changes = self._find_changes(old_config, new_config)

            for key_path, (old_val, new_val) in changes.items():
                if key_path in self._observers:
                    for callback in self._observers[key_path]:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(old_val, new_val)
                            else:
                                callback(old_val, new_val)
                        except Exception as e:
                            logger.error(f"Error in config change callback for {key_path}: {e}")

        except Exception as e:
            logger.error(f"Error notifying config changes: {e}")

    def _find_changes(self, old: Dict[str, Any], new: Dict[str, Any], prefix: str = '') -> Dict[str, tuple]:
        """Рекурсивный поиск изменений в конфигурации"""
        changes = {}

        # Проверяем все ключи в новой конфигурации
        for key in new:
            current_path = f"{prefix}.{key}" if prefix else key

            if key not in old:
                # Новый ключ
                changes[current_path] = (None, new[key])
            elif isinstance(new[key], dict) and isinstance(old[key], dict):
                # Рекурсивная проверка для вложенных словарей
                nested_changes = self._find_changes(old[key], new[key], current_path)
                changes.update(nested_changes)
            elif old[key] != new[key]:
                # Измененное значение
                changes[current_path] = (old[key], new[key])

        # Проверяем удаленные ключи
        for key in old:
            if key not in new:
                current_path = f"{prefix}.{key}" if prefix else key
                changes[current_path] = (old[key], None)

        return changes

    def subscribe(self, key_path: str, callback: Callable):
        """Подписка на изменения параметра по пути (например, 'telegram.monitored_chats')"""
        if key_path not in self._observers:
            self._observers[key_path] = []
        self._observers[key_path].append(callback)
        logger.debug(f"Subscribed to config changes for: {key_path}")

    def unsubscribe(self, key_path: str, callback: Callable):
        """Отписка от изменений параметра"""
        if key_path in self._observers:
            if callback in self._observers[key_path]:
                self._observers[key_path].remove(callback)
                if not self._observers[key_path]:
                    del self._observers[key_path]

    def get(self, key_path: str, default: Any = None) -> Any:
        """Получение значения параметра по пути (например, 'telegram.collection.interval_seconds')"""
        keys = key_path.split('.')
        value = self._config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def get_all(self) -> Dict[str, Any]:
        """Получение всей конфигурации"""
        return self._config.copy()

    def get_telegram_config(self) -> Dict[str, Any]:
        """Получение Telegram конфигурации"""
        return self.get('telegram', {})

    def get_scheduler_config(self) -> Dict[str, Any]:
        """Получение конфигурации планировщика"""
        return self.get('scheduler', {})

    def get_wiki_config(self) -> Dict[str, Any]:
        """Получение Wiki конфигурации"""
        return self.get('wiki', {})

    def get_logging_config(self) -> Dict[str, Any]:
        """Получение конфигурации логирования"""
        return self.get('logging', {})

    def is_loaded(self) -> bool:
        """Проверка, загружена ли конфигурация"""
        return self._loaded