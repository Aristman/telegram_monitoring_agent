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
        request = {
            "jsonrpc": "2.0",
            "id": 1,
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
        try:
            # Для Wiki папки создаются автоматически при создании страниц
            # Базовая проверка соединения
            response = await self._send_mcp_request("tools/call", {
                "name": "ywiki.test_connection",
                "arguments": {}
            })

            if "result" in response:
                content = response["result"]["content"][0]["text"]
                result = json.loads(content)
                return result.get("success", False)

            return False

        except Exception as e:
            logger.error(f"Error testing Wiki connection: {e}")
            return False

    async def create_page(
        self,
        title: str,
        content: str,
        folder_path: Optional[str] = None
    ) -> Optional[str]:
        """Создание страницы в Wiki"""
        try:
            arguments = {
                "title": title,
                "content": content
            }

            # Если указана папка, добавляем в заголовок путь
            if folder_path:
                title = f"{folder_path}/{title}"

            response = await self._send_mcp_request("tools/call", {
                "name": "ywiki.create_page",
                "arguments": arguments
            })

            if "result" in response:
                content_data = response["result"]["content"][0]["text"]
                result = json.loads(content_data)
                return result.get("id")

            return None

        except Exception as e:
            logger.error(f"Error creating Wiki page '{title}': {e}")
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
            # Формируем путь для отчета
            date_str = report_date.strftime("%Y-%m-%d")
            time_str = report_date.strftime("%H-%M")
            folder_path = f"{self.config.base_folder}/{date_str}/{time_str}"

            # Формируем заголовок страницы
            page_title = f"Отчет по чату: {chat_title}"

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
            hour = msg['timestamp'].hour
            if hour not in messages_by_time:
                messages_by_time[hour] = []
            messages_by_time[hour].append(msg)

        # Генерируем отчет по времени
        for hour in sorted(messages_by_time.keys()):
            content += f"\n### {hour:02d}:00 - {hour+1:02d}:00\n\n"

            for msg in messages_by_time[hour]:
                time_str = msg['timestamp'].strftime("%H:%M")
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