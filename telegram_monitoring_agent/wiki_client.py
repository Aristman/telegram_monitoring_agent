"""
Клиент для работы с Yandex Wiki через MCP сервер
"""

import json
import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime

from config import YandexWikiConfig

logger = logging.getLogger(__name__)


class YandexWikiMCPClient:
    """Клиент для работы с Yandex Wiki MCP сервером"""

    def __init__(self, config: YandexWikiConfig):
        self.config = config
        self.base_url = config.wiki_mcp_url
        self.headers = {"Content-Type": "application/json"}

    async def _send_mcp_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Отправка MCP запроса"""
        import uuid
        request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {}
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    json=request,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error in Wiki MCP request: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error sending Wiki MCP request: {e}")
            raise

    async def initialize(self) -> bool:
        """Инициализация соединения с MCP сервером"""
        try:
            response = await self._send_mcp_request("initialize", {
                "protocolVersion": "2024-09-18",
                "clientInfo": {"name": "telegram-monitor", "version": "1.0.0"},
                "capabilities": {"tools": {}}
            })
            return "result" in response

        except Exception as e:
            logger.error(f"Error initializing Wiki MCP client: {e}")
            return False

    async def create_folder_structure(self, base_path: str) -> bool:
        """Создание структуры папок"""
        # Для Wiki папки создаются автоматически при создании страниц
        # Проверка соединения не требуется
        return True

    async def create_page(
        self,
        title: str,
        content: str,
        folder_path: Optional[str] = None
    ) -> Optional[str]:
        """Создание страницы в Wiki"""
        try:
            import re
            
            # Генерируем slug из folder_path и title
            # Транслитерация title: убираем спецсимволы, заменяем пробелы на дефисы
            slug_title = re.sub(r'[^\w\s-]', '', title.lower())
            slug_title = re.sub(r'[-\s]+', '-', slug_title).strip('-')
            
            if folder_path:
                # Slug = путь/название
                # Например: homepage/otchety-telegramm/2025-10-16-02-50-sourcecraft
                slug = f"{folder_path}/{slug_title}"
            else:
                # Если нет пути, используем только название
                slug = slug_title
            
            # Если slug пустой или слишком короткий, используем timestamp
            if len(slug) < 3:
                from datetime import datetime
                slug = f"page-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            arguments = {
                "slug": slug,
                "title": title,
                "content": content
            }

            response = await self._send_mcp_request("tools/call", {
                "name": "ywiki.create_page",
                "arguments": arguments
            })

            logger.debug(f"Wiki create_page request - slug: '{slug}', title: '{title}'")
            logger.debug(f"Wiki create_page response: {response}")

            if "result" in response:
                content_data = response["result"]["content"][0]["text"]
                result = json.loads(content_data)
                page_id = result.get("id") or result.get("page_id")
                
                if page_id:
                    logger.info(f"Successfully created Wiki page '{title}' at slug '{slug}' with ID: {page_id}")
                    return page_id
                else:
                    logger.error(f"No page ID in response for '{title}': {result}")
                    return None

            logger.error(f"No result in Wiki response for '{title}'")
            return None

        except Exception as e:
            logger.error(f"Error creating Wiki page '{title}': {e}", exc_info=True)
            return None

    async def update_page(
        self,
        page_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None
    ) -> bool:
        """Обновление страницы в Wiki"""
        try:
            arguments = {"page_id": page_id}

            if title:
                arguments["title"] = title
            if content:
                arguments["content"] = content

            response = await self._send_mcp_request("tools/call", {
                "name": "ywiki.update_page",
                "arguments": arguments
            })

            return "result" in response

        except Exception as e:
            logger.error(f"Error updating Wiki page '{page_id}': {e}")
            return False

    async def append_content(self, page_id: str, content: str) -> bool:
        """Добавление контента в конец страницы"""
        try:
            response = await self._send_mcp_request("tools/call", {
                "name": "ywiki.append_content",
                "arguments": {
                    "page_id": page_id,
                    "content": content
                }
            })

            return "result" in response

        except Exception as e:
            logger.error(f"Error appending content to Wiki page '{page_id}': {e}")
            return False

    async def search_pages(self, query: str) -> List[Dict[str, Any]]:
        """Поиск страниц"""
        try:
            response = await self._send_mcp_request("tools/call", {
                "name": "ywiki.search_pages",
                "arguments": {"query": query, "limit": 20}
            })

            if "result" in response:
                content_data = response["result"]["content"][0]["text"]
                result = json.loads(content_data)
                return result.get("pages", [])

            return []

        except Exception as e:
            logger.error(f"Error searching Wiki pages: {e}")
            return []

    async def get_page_content(self, page_id: str) -> Optional[str]:
        """Получение содержимого страницы"""
        try:
            response = await self._send_mcp_request("tools/call", {
                "name": "ywiki.get_page_content",
                "arguments": {"page_id": page_id}
            })

            if "result" in response:
                content_data = response["result"]["content"][0]["text"]
                result = json.loads(content_data)
                return result.get("content", {}).get("body")

            return None

        except Exception as e:
            logger.error(f"Error getting Wiki page content '{page_id}': {e}")
            return None


class WikiReportGenerator:
    """Генератор отчетов для Wiki"""

    def __init__(self, wiki_client: YandexWikiMCPClient, config: YandexWikiConfig):
        self.wiki_client = wiki_client
        self.config = config

    async def generate_chat_report(
        self,
        chat_title: str,
        messages: List[Dict[str, Any]],
        report_date: datetime
    ) -> Optional[str]:
        """Генерация отчета по чату"""
        try:
            # Формируем путь для отчета (фиксированный)
            folder_path = "homepage/otchety-telegramm"

            # Формируем имя документа: Дата-Время-Название чата
            date_str = report_date.strftime("%Y-%m-%d")
            time_str = report_date.strftime("%H-%M")
            page_title = f"{date_str}-{time_str}-{chat_title}"

            # Генерируем содержимое отчета
            content = self._generate_report_content(chat_title, messages, report_date)

            # Создаем страницу в Wiki
            page_id = await self.wiki_client.create_page(
                title=page_title,
                content=content,
                folder_path=folder_path
            )

            if page_id:
                logger.info(f"Created Wiki report page '{page_title}' with ID: {page_id}")
                return page_id
            else:
                logger.error(f"Failed to create Wiki report page '{page_title}'")
                return None

        except Exception as e:
            logger.error(f"Error generating chat report for '{chat_title}': {e}")
            return None

    def _generate_report_content(
        self,
        chat_title: str,
        messages: List[Dict[str, Any]],
        report_date: datetime
    ) -> str:
        """Генерация содержимого отчета"""
        date_str = report_date.strftime("%d.%m.%Y")
        time_str = report_date.strftime("%H:%M")

        content = f"""# Отчет по чату: {chat_title}

**Дата:** {date_str}
**Время генерации:** {time_str}
**Количество сообщений:** {len(messages)}

---

## Сообщения

"""

        # Группируем сообщения по времени
        messages_by_time = {}
        for msg in messages:
            # Преобразуем timestamp из строки в datetime
            timestamp = datetime.fromisoformat(msg['timestamp']) if isinstance(msg['timestamp'], str) else msg['timestamp']
            hour = timestamp.hour
            if hour not in messages_by_time:
                messages_by_time[hour] = []
            messages_by_time[hour].append(msg)

        # Генерируем отчет по времени
        for hour in sorted(messages_by_time.keys()):
            content += f"\n### {hour:02d}:00 - {hour+1:02d}:00\n\n"

            for msg in messages_by_time[hour]:
                # Преобразуем timestamp из строки в datetime
                timestamp = datetime.fromisoformat(msg['timestamp']) if isinstance(msg['timestamp'], str) else msg['timestamp']
                time_str = timestamp.strftime("%H:%M")
                sender_name = msg['sender_name']
                text = msg['text']

                content += f"**{time_str}** - *{sender_name}*: {text}\n\n"

        content += """
---

*Этот отчет автоматически сгенерирован системой мониторинга Telegram.*
"""

        return content

    async def create_daily_summary(
        self,
        chat_title: str,
        summary: str,
        summary_date: datetime
    ) -> Optional[str]:
        """Создание дневной сводки"""
        try:
            # Формируем путь для сводки
            date_str = summary_date.strftime("%Y-%m-%d")
            folder_path = f"{self.config.base_folder}/{date_str}/summary"

            # Формируем заголовок страницы
            page_title = f"Сводка за день: {chat_title} ({date_str})"

            # Создаем содержимое страницы
            content = f"""# Дневная сводка: {chat_title}

**Дата:** {date_str}
**Время генерации:** {summary_date.strftime("%H:%M")}

---

## Сводка сообщений

{summary}

---

*Эта сводка автоматически сгенерирована с помощью Yandex GPT.*
"""

            # Создаем страницу в Wiki
            page_id = await self.wiki_client.create_page(
                title=page_title,
                content=content,
                folder_path=folder_path
            )

            if page_id:
                logger.info(f"Created daily summary page '{page_title}' with ID: {page_id}")
                return page_id
            else:
                logger.error(f"Failed to create daily summary page '{page_title}'")
                return None

        except Exception as e:
            logger.error(f"Error creating daily summary for '{chat_title}': {e}")
            return None

    async def create_main_summary_page(
        self,
        summaries: Dict[str, str],
        summary_date: datetime
    ) -> Optional[str]:
        """Создание главной страницы сводки за день"""
        try:
            date_str = summary_date.strftime("%Y-%m-%d")
            folder_path = f"{self.config.base_folder}/{date_str}"

            # Формируем заголовок страницы
            page_title = f"Главная сводка за {date_str}"

            # Создаем содержимое страницы
            content = f"""# Главная сводка за {date_str}

**Дата:** {date_str}
**Время генерации:** {summary_date.strftime("%H:%M")}
**Количество чатов:** {len(summaries)}

---

## Сводки по чатам

"""

            for chat_title, summary in summaries.items():
                content += f"""
### {chat_title}

{summary}

---

"""

            content += """
*Эта страница автоматически сгенерирована системой мониторинга Telegram.*
"""

            # Создаем страницу в Wiki
            page_id = await self.wiki_client.create_page(
                title=page_title,
                content=content,
                folder_path=folder_path
            )

            if page_id:
                logger.info(f"Created main summary page '{page_title}' with ID: {page_id}")
                return page_id
            else:
                logger.error(f"Failed to create main summary page '{page_title}'")
                return None

        except Exception as e:
            logger.error(f"Error creating main summary page: {e}")
            return None