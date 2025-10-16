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
                
                # Если получили ошибку SLUG_OCCUPIED, значит страница существует
                # Попробуем найти её ещё раз и обновить
                if not success:
                    logger.warning("Failed to create page, trying to find and update existing page")
                    existing_page = await self._find_log_page_by_search(page_title)
                    if existing_page:
                        logger.info(f"Found page via search, appending logs")
                        success = await self._append_logs_to_page(existing_page, log_content)

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
            
            logger.info(f"Searching for page with slug: {slug}")
            
            # Пробуем два варианта:
            # 1. Поиск по полному slug
            response = await self.wiki_client._send_mcp_request("tools/call", {
                "name": "ywiki.get_page_list",
                "arguments": {"slug": slug, "limit": 10}
            })
            
            logger.debug(f"get_page_list (by slug) response: {response}")
            
            if "result" in response:
                content_data = response["result"]["content"][0]["text"]
                result = json.loads(content_data)
                
                # Проверяем на ошибку
                if "error" not in result:
                    pages = result.get("pages", [])
                    logger.info(f"Found {len(pages)} pages by slug")
                    
                    if pages and len(pages) > 0:
                        # Ищем точное совпадение
                        for page in pages:
                            if page.get('slug') == slug or page.get('title') == page_title:
                                logger.info(f"Found existing log page: {page.get('id', 'unknown')}")
                                return page
            
            # 2. Поиск по родительской папке
            logger.info(f"Trying to list pages in folder: {folder_path}")
            response2 = await self.wiki_client._send_mcp_request("tools/call", {
                "name": "ywiki.get_page_list",
                "arguments": {"slug": folder_path, "limit": 50}
            })
            
            logger.info(f"get_page_list (by folder) response: {response2}")
            
            if "result" in response2:
                content_data = response2["result"]["content"][0]["text"]
                result = json.loads(content_data)
                
                logger.info(f"Parsed folder result: {result}")
                
                if "error" not in result:
                    pages = result.get("pages", [])
                    logger.info(f"Found {len(pages)} pages in folder")
                    
                    # Логируем все найденные страницы
                    if pages:
                        logger.info(f"Pages in folder:")
                        for p in pages:
                            logger.info(f"  - title={p.get('title')}, slug={p.get('slug')}, id={p.get('id')}")
                    
                    # Ищем нужную страницу по названию
                    for page in pages:
                        if page.get('title') == page_title or page.get('slug', '').endswith(page_title):
                            logger.info(f"Found existing log page in folder: {page.get('id', 'unknown')}")
                            return page
                else:
                    logger.warning(f"Error in folder listing: {result.get('error')}")
            
            logger.info(f"No existing page found for slug: {slug}")
            return None

        except Exception as e:
            logger.warning(f"Error searching for page by slug: {e}")
            return None

    async def _find_log_page_by_search(self, page_title: str) -> Optional[dict]:
        """Поиск существующей страницы логов через прямой запрос"""
        try:
            # Формируем полный slug страницы
            slug = f"homepage/otchety-telegramm/logi/{page_title}"
            logger.info(f"Trying direct page access with slug: {slug}")
            
            # Пытаемся получить страницу напрямую через get_page
            # Используем slug как page_id (в Yandex Wiki slug может использоваться как ID)
            response = await self.wiki_client._send_mcp_request("tools/call", {
                "name": "ywiki.get_page",
                "arguments": {"page_id": slug}
            })
            
            logger.debug(f"get_page response: {response}")
            
            if "result" in response:
                content_data = response["result"]["content"][0]["text"]
                result = json.loads(content_data)
                
                # Проверяем наличие ошибки в результате
                if "error" in result:
                    logger.info(f"Page not found (API returned error): {result['error']}")
                    return None
                
                logger.debug(f"Parsed result: {result}")
                
                # Проверяем, что это нужная страница
                if result.get('slug') == slug or result.get('title') == page_title:
                    logger.info(f"Found page via direct access: {result.get('id', 'unknown')}")
                    return result
                else:
                    logger.warning(f"Page found but slug/title mismatch. Got slug={result.get('slug')}, title={result.get('title')}")
            else:
                logger.warning(f"No result in response: {response}")
            
            logger.info(f"Page not found via direct access")
            return None

        except Exception as e:
            logger.error(f"Error accessing page directly: {e}", exc_info=True)
            return None

    async def _append_logs_to_page(self, page: dict, new_content: str) -> bool:
        """Добавление логов к существующей странице"""
        try:
            page_id = page.get('id') or page.get('page_id')
            if not page_id:
                logger.error("No page_id found in page object")
                return False

            logger.info(f"Appending logs to page {page_id}")
            
            # Форматируем контент для добавления
            append_text = f"\n```\n{new_content}\n```\n"
            
            # Используем append_content API для добавления в конец страницы
            success = await self.wiki_client.append_content(page_id, append_text)
            
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
**Последнее обновление:** {datetime.now().strftime("%H:%M:%S")}

---

## Записи логов

```
{log_content}
```

---

*Этот файл автоматически обновляется системой мониторинга.*
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
