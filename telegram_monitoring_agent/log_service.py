"""
Сервис для управления логами и их записи в Wiki
"""

import json
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from database import Database
from wiki_client import YandexWikiMCPClient

logger = logging.getLogger(__name__)


class LogService:
    """Сервис для управления логами"""

    def __init__(self, database: Database, wiki_client: YandexWikiMCPClient):
        self.database = database
        self.wiki_client = wiki_client
        self.last_log_id = 0

    async def write_logs_to_wiki(self) -> bool:
        """Запись новых логов в Wiki файл"""
        try:
            # Получаем новые логи
            new_logs = self.database.get_new_logs(self.last_log_id)
            
            if not new_logs:
                logger.debug("No new logs to write to Wiki")
                return True

            # Обновляем last_log_id
            if new_logs:
                self.last_log_id = max(log['id'] for log in new_logs)

            # Формируем имя файла с текущей датой
            current_date = datetime.now().strftime("%Y-%m-%d")
            page_title = f"log{current_date}"  # Без подчёркивания, т.к. Wiki преобразует его
            folder_path = "homepage/otchety-telegramm/logi"

            # Формируем содержимое логов
            log_content = self._format_logs(new_logs)

            # Пытаемся найти существующую страницу
            existing_page = await self._find_log_page(page_title, folder_path)

            if existing_page:
                # Дописываем логи к существующей странице
                logger.info(f"Appending logs to existing page")
                success = await self._append_logs_to_page(existing_page, log_content)
            else:
                # Создаем новую страницу
                logger.info(f"Creating new log page")
                success = await self._create_log_page(page_title, folder_path, log_content)

            if success:
                logger.info(f"Successfully wrote {len(new_logs)} logs to Wiki")
            else:
                logger.error("Failed to write logs to Wiki")

            return success

        except Exception as e:
            logger.error(f"Error writing logs to Wiki: {e}")
            return False

    def _format_logs(self, logs: list) -> str:
        """Форматирование логов для записи"""
        lines = []
        for log in logs:
            timestamp = log['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            level = log['level']
            logger_name = log['logger_name']
            message = log['message']
            
            lines.append(f"{time_str} - {level} - {logger_name} - {message}")
        
        return "\n".join(lines)

    async def _find_log_page(self, page_title: str, folder_path: str) -> Optional[dict]:
        """Поиск существующей страницы логов по slug"""
        try:
            # Формируем slug для поиска
            slug = f"{folder_path}/{page_title}"
            
            logger.debug(f"Searching for page with slug: {slug}")
            
            # Используем get_page_by_slug - самый надёжный способ
            response = await self.wiki_client._send_mcp_request("tools/call", {
                "name": "ywiki.get_page_by_slug",
                "arguments": {"slug": slug}
            })
            
            if "result" in response:
                content_data = response["result"]["content"][0]["text"]
                result = json.loads(content_data)
                
                # Проверяем наличие ошибки в результате
                if "error" not in result:
                    logger.info(f"Found existing log page: id={result.get('id')}, slug={result.get('slug')}")
                    return result
                else:
                    logger.debug(f"Page not found: {result.get('error')}")
            
            return None

        except Exception as e:
            logger.debug(f"Error searching for page by slug: {e}")
            return None

    async def _append_logs_to_page(self, page: dict, new_content: str) -> bool:
        """Добавление логов к существующей странице"""
        try:
            page_id = page.get('id') or page.get('page_id')
            if not page_id:
                logger.error("No page_id found in page object")
                return False

            logger.info(f"Appending logs to page {page_id}")
            
            # Форматируем новые логи в блок кода
            new_logs_block = f"\n```\n{new_content}\n```\n"
            
            # Используем append-content API для добавления в конец страницы
            success = await self.wiki_client.append_content(page_id, new_logs_block)
            
            if success:
                logger.info(f"Successfully appended logs to page {page_id}")
            else:
                logger.error(f"Failed to append logs to page {page_id}")
            
            return success

        except Exception as e:
            logger.error(f"Error appending logs to page: {e}", exc_info=True)
            return False

    async def _create_log_page(self, page_title: str, folder_path: str, log_content: str) -> bool:
        """Создание новой страницы логов"""
        try:
            content = self._create_log_content(log_content)
            
            page_id = await self.wiki_client.create_page(
                title=page_title,
                content=content,
                folder_path=folder_path
            )

            return page_id is not None

        except Exception as e:
            logger.error(f"Error creating log page: {e}")
            return False

    def _create_log_content(self, log_content: str) -> str:
        """Создание содержимого страницы логов"""
        current_date = datetime.now().strftime("%d.%m.%Y")
        
        content = f"""# Логи системы мониторинга

**Дата:** {current_date}
**Время создания:** {datetime.now().strftime("%H:%M:%S")}

---

## Записи логов

```
{log_content}
```
"""
        return content

    async def cleanup_old_logs(self) -> int:
        """Очистка старых логов из БД (старше 7 дней)"""
        try:
            deleted_count = self.database.cleanup_old_logs(days_to_keep=7)
            logger.info(f"Cleaned up {deleted_count} old logs from database")
            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}")
            return 0
