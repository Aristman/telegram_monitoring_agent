"""
MCP инструменты для работы с Yandex Wiki
"""

import logging
from typing import Dict, Any, List, Optional
from wiki_client import YandexWikiClient

logger = logging.getLogger(__name__)


class ToolsHandler:
    """Обработчик MCP инструментов для Yandex Wiki"""

    def __init__(self, wiki_client: YandexWikiClient):
        self.wiki_client = wiki_client
        self._tools = [
            {
                "name": "ywiki.get_page",
                "description": "Получить детальную информацию о странице Yandex Wiki",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "ID страницы Yandex Wiki"
                        }
                    },
                    "required": ["page_id"]
                }
            },
            {
                "name": "ywiki.get_page_content",
                "description": "Получить содержимое страницы",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "ID страницы Yandex Wiki"
                        }
                    },
                    "required": ["page_id"]
                }
            },
            {
                "name": "ywiki.search_pages",
                "description": "Поиск страниц в Yandex Wiki",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Поисковый запрос"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Максимальное количество результатов (по умолчанию 20)",
                            "default": 20
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "ywiki.list_pages",
                "description": "Получить список страниц",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "folder_id": {
                            "type": "string",
                            "description": "ID папки (опционально)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Максимальное количество страниц (по умолчанию 50)",
                            "default": 50
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "ywiki.create_page",
                "description": "Создать новую страницу в Yandex Wiki",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Заголовок страницы"
                        },
                        "content": {
                            "type": "string",
                            "description": "Содержимое страницы в формате Markdown"
                        },
                        "folder_id": {
                            "type": "string",
                            "description": "ID папки для размещения страницы (опционально)"
                        },
                        "parent_page_id": {
                            "type": "string",
                            "description": "ID родительской страницы (опционально)"
                        }
                    },
                    "required": ["title", "content"]
                }
            },
            {
                "name": "ywiki.update_page",
                "description": "Обновить существующую страницу",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "ID страницы для обновления"
                        },
                        "title": {
                            "type": "string",
                            "description": "Новый заголовок страницы (опционально)"
                        },
                        "content": {
                            "type": "string",
                            "description": "Новое содержимое страницы в формате Markdown (опционально)"
                        }
                    },
                    "required": ["page_id"]
                }
            },
            {
                "name": "ywiki.delete_page",
                "description": "Удалить страницу",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "ID страницы для удаления"
                        }
                    },
                    "required": ["page_id"]
                }
            },
            {
                "name": "ywiki.get_page_history",
                "description": "Получить историю изменений страницы",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "ID страницы"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Максимальное количество записей (по умолчанию 20)",
                            "default": 20
                        }
                    },
                    "required": ["page_id"]
                }
            },
            {
                "name": "ywiki.get_folders",
                "description": "Получить список доступных папок",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "ywiki.test_connection",
                "description": "Проверить соединение с Yandex Wiki API",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Получить список доступных инструментов"""
        return self._tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить инструмент"""
        try:
            if tool_name == "ywiki.get_page":
                return await self.wiki_client.get_page_details(arguments["page_id"])

            elif tool_name == "ywiki.get_page_content":
                return await self.wiki_client.get_page_content(arguments["page_id"])

            elif tool_name == "ywiki.search_pages":
                query = arguments["query"]
                limit = arguments.get("limit", 20)
                return await self.wiki_client.search_pages(query, limit)

            elif tool_name == "ywiki.list_pages":
                folder_id = arguments.get("folder_id")
                limit = arguments.get("limit", 50)
                return await self.wiki_client.get_page_list(folder_id, limit)

            elif tool_name == "ywiki.create_page":
                title = arguments["title"]
                content = arguments["content"]
                folder_id = arguments.get("folder_id")
                parent_page_id = arguments.get("parent_page_id")
                return await self.wiki_client.create_page(title, content, folder_id, parent_page_id)

            elif tool_name == "ywiki.update_page":
                page_id = arguments["page_id"]
                title = arguments.get("title")
                content = arguments.get("content")
                return await self.wiki_client.update_page(page_id, title, content)

            elif tool_name == "ywiki.delete_page":
                return await self.wiki_client.delete_page(arguments["page_id"])

            elif tool_name == "ywiki.get_page_history":
                page_id = arguments["page_id"]
                limit = arguments.get("limit", 20)
                return await self.wiki_client.get_page_history(page_id, limit)

            elif tool_name == "ywiki.get_folders":
                return await self.wiki_client.get_folders()

            elif tool_name == "ywiki.test_connection":
                success = await self.wiki_client.test_connection()
                return {"success": success, "message": "Connection successful" if success else "Connection failed"}

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"error": str(e)}