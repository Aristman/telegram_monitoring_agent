#!/usr/bin/env python3
"""
Yandex Wiki MCP Server

HTTP MCP сервер для работы с Yandex Wiki API.
Предоставляет инструменты для просмотра и создания страниц.
"""

import json
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import httpx
from pydantic import BaseModel

from config import Config
from wiki_client import YandexWikiClient
from tools import ToolsHandler


# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class YandexWikiMCPServer:
    def __init__(self):
        self.config = Config()
        self.wiki_client = YandexWikiClient(self.config)
        self.tools_handler = ToolsHandler(self.wiki_client)
        self.app = FastAPI(title="Yandex Wiki MCP Server", version="1.0.0")
        self._setup_routes()

    def _setup_routes(self):
        """Настройка маршрутов FastAPI"""

        @self.app.post("/")
        async def handle_mcp_request(request: MCPRequest):
            """Основной обработчик MCP запросов"""
            try:
                return await self._handle_request(request)
            except Exception as e:
                logger.error(f"Error handling request: {e}")
                return MCPResponse(
                    id=request.id,
                    error={"code": -32000, "message": str(e)}
                )

        @self.app.get("/health")
        async def health_check():
            """Проверка здоровья сервера"""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}

        @self.app.get("/")
        async def root():
            """Информация о сервере"""
            return {
                "name": "Yandex Wiki MCP Server",
                "version": "1.0.0",
                "description": "MCP сервер для работы с Yandex Wiki API"
            }

    async def _handle_request(self, request: MCPRequest) -> MCPResponse:
        """Обработка MCP запроса"""
        method = request.method
        params = request.params or {}

        if method == "initialize":
            return MCPResponse(
                id=request.id,
                result={
                    "protocolVersion": "2024-09-18",
                    "serverInfo": {"name": "yandex-wiki-mcp-server", "version": "1.0.0"},
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                        "prompts": {}
                    }
                }
            )

        elif method == "tools/list":
            tools = await self.tools_handler.list_tools()
            return MCPResponse(
                id=request.id,
                result={"tools": tools}
            )

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if not tool_name:
                return MCPResponse(
                    id=request.id,
                    error={"code": -32602, "message": "Missing tool name"}
                )

            try:
                result = await self.tools_handler.call_tool(tool_name, arguments)
                return MCPResponse(
                    id=request.id,
                    result={"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
                )
            except Exception as e:
                return MCPResponse(
                    id=request.id,
                    error={"code": -32000, "message": str(e)}
                )

        else:
            return MCPResponse(
                id=request.id,
                error={"code": -32601, "message": f"Method not found: {method}"}
            )


def create_app() -> FastAPI:
    """Создание FastAPI приложения"""
    server = YandexWikiMCPServer()
    return server.app


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Yandex Wiki MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Хост для запуска сервера")
    parser.add_argument("--port", type=int, default=8080, help="Порт для запуска сервера")
    parser.add_argument("--reload", action="store_true", help="Автоматическая перезагрузка при изменениях")

    args = parser.parse_args()

    logger.info(f"Starting Yandex Wiki MCP Server on {args.host}:{args.port}")

    uvicorn.run(
        "main:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
        log_level="info"
    )