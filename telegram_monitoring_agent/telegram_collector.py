"""
Сборщик сообщений из Telegram через MCP сервер
"""

import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import subprocess
import sys

from config import TelegramConfig
from database import Database, Message

logger = logging.getLogger(__name__)


class TelegramMCPClient:
    """Клиент для работы с Telegram MCP сервером"""

    def __init__(self, config: TelegramConfig):
        self.config = config
        self.server_process = None
        self.use_stdio = config.telegram_mcp_url == "stdio"

    async def start_server(self) -> bool:
        """Запуск Telegram MCP сервера"""
        if self.use_stdio:
            try:
                # Запускаем MCP сервер как subprocess
                cmd = [
                    sys.executable,
                    "-u",
                    "main.py"
                ]

                self.server_process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE,
                    cwd="../telegram_mcp_server_py"
                )

                # Ждем готовности сервера
                await asyncio.sleep(2)

                # Проверяем, что процесс запущен
                if self.server_process.returncode is not None:
                    logger.error("Telegram MCP server failed to start")
                    return False

                logger.info("Telegram MCP server started successfully via stdio")
                return True

            except Exception as e:
                logger.error(f"Error starting Telegram MCP server: {e}")
                return False
        else:
            # Используем HTTP MCP сервер
            logger.info(f"Using Telegram MCP server via HTTP: {self.config.telegram_mcp_url}")
            return True

    async def stop_server(self):
        """Остановка Telegram MCP сервера"""
        if self.server_process and self.use_stdio:
            self.server_process.terminate()
            await self.server_process.wait()
            logger.info("Telegram MCP server stopped")

    async def _send_mcp_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Отправка MCP запроса"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }

        if self.use_stdio:
            # Используем STDIO коммуникацию
            if not self.server_process:
                raise RuntimeError("Telegram MCP server is not running")

            # Отправляем запрос
            request_json = json.dumps(request)
            request_bytes = f"Content-Length: {len(request_json)}\r\n\r\n{request_json}".encode('utf-8')

            self.server_process.stdin.write(request_bytes)
            await self.server_process.stdin.drain()

            # Читаем ответ
            response_data = await self._read_mcp_response()
            return response_data
        else:
            # Используем HTTP коммуникацию
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.config.telegram_mcp_url,
                    json=request,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()

    async def _read_mcp_response(self) -> Dict[str, Any]:
        """Чтение MCP ответа"""
        if not self.server_process:
            raise RuntimeError("Telegram MCP server is not running")

        # Читаем заголовки
        headers = {}
        while True:
            line = await self.server_process.stdout.readline()
            if not line:
                break

            line = line.decode('utf-8').strip()
            if not line:
                break

            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()

        # Читаем тело
        content_length = int(headers.get('content-length', '0'))
        if content_length > 0:
            body_bytes = await self.server_process.stdout.read(content_length)
            body_json = body_bytes.decode('utf-8')
            return json.loads(body_json)

        return {}

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
            logger.error(f"Error initializing Telegram MCP client: {e}")
            return False

    async def get_chat_info(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Получение информации о чате"""
        try:
            response = await self._send_mcp_request("tools/call", {
                "name": "tg.resolve_chat",
                "arguments": {"chat": chat_id}
            })

            if "result" in response:
                content = response["result"]["content"][0]["text"]
                return json.loads(content)
            return None

        except Exception as e:
            logger.error(f"Error getting chat info for {chat_id}: {e}")
            return None

    async def fetch_messages(
        self,
        chat_id: str,
        limit: int = 100,
        min_id: int = 0
    ) -> List[Dict[str, Any]]:
        """Получение сообщений из чата"""
        try:
            response = await self._send_mcp_request("tools/call", {
                "name": "tg.read_messages",
                "arguments": {
                    "chat": chat_id,
                    "page_size": limit,
                    "min_id": min_id
                }
            })

            if "result" in response:
                content = response["result"]["content"][0]["text"]
                data = json.loads(content)
                return data.get("messages", [])
            return []

        except Exception as e:
            logger.error(f"Error fetching messages from {chat_id}: {e}")
            return []


class TelegramCollector:
    """Основной класс для сбора сообщений из Telegram"""

    def __init__(self, telegram_config: TelegramConfig, database: Database):
        self.telegram_config = telegram_config
        self.database = database
        self.mcp_client = TelegramMCPClient(telegram_config)
        self.is_running = False

    async def start(self) -> bool:
        """Запуск сборщика сообщений"""
        try:
            # Запускаем MCP сервер
            if not await self.mcp_client.start_server():
                logger.error("Failed to start Telegram MCP server")
                return False

            # Инициализируем клиент
            if not await self.mcp_client.initialize():
                logger.error("Failed to initialize Telegram MCP client")
                return False

            self.is_running = True
            logger.info("Telegram collector started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting Telegram collector: {e}")
            return False

    async def stop(self):
        """Остановка сборщика сообщений"""
        self.is_running = False
        await self.mcp_client.stop_server()
        logger.info("Telegram collector stopped")

    async def collect_messages(self, chat_id: str) -> int:
        """Сбор сообщений из указанного чата"""
        try:
            # Получаем ID последнего сохраненного сообщения
            last_message_id = self.database.get_last_message_id(chat_id)

            # Получаем новые сообщения
            messages_data = await self.mcp_client.fetch_messages(
                chat_id=chat_id,
                limit=self.telegram_config.max_messages_per_fetch,
                min_id=last_message_id
            )

            if not messages_data:
                logger.debug(f"No new messages in chat {chat_id}")
                return 0

            # Получаем информацию о чате
            chat_info = await self.mcp_client.get_chat_info(chat_id)
            chat_title = chat_info.get("title", chat_id) if chat_info else chat_id

            # Конвертируем сообщения в объекты Message
            messages = []
            for msg_data in messages_data:
                # Пропускаем сообщения без текста
                text = msg_data.get("text", "").strip()
                if not text:
                    continue

                message = Message(
                    message_id=msg_data["id"],
                    chat_id=chat_id,
                    chat_title=chat_title,
                    sender_id=msg_data["from"]["id"],
                    sender_name=msg_data["from"]["display"],
                    text=text,
                    timestamp=datetime.fromisoformat(msg_data["date"].replace('Z', '+00:00')),
                    reply_to_id=msg_data.get("reply_to_id")
                )
                messages.append(message)

            # Сохраняем сообщения в базу данных
            saved_count = self.database.save_messages_batch(messages)

            logger.info(f"Collected {saved_count} new messages from chat {chat_id}")
            return saved_count

        except Exception as e:
            logger.error(f"Error collecting messages from chat {chat_id}: {e}")
            return 0

    async def collect_all_chats(self) -> Dict[str, int]:
        """Сбор сообщений из всех настроенных чатов"""
        results = {}

        for chat_id in self.telegram_config.monitored_chats:
            if not self.is_running:
                break

            try:
                count = await self.collect_messages(chat_id)
                results[chat_id] = count

            except Exception as e:
                logger.error(f"Error collecting from chat {chat_id}: {e}")
                results[chat_id] = 0

        return results

    async def run_collection_loop(self):
        """Основной цикл сбора сообщений"""
        logger.info(f"Starting message collection loop for {len(self.telegram_config.monitored_chats)} chats")

        while self.is_running:
            try:
                results = await self.collect_all_chats()

                total_collected = sum(results.values())
                if total_collected > 0:
                    logger.info(f"Collection cycle completed. Total messages collected: {total_collected}")
                    for chat_id, count in results.items():
                        if count > 0:
                            logger.debug(f"  Chat {chat_id}: {count} messages")

                # Ждем следующего цикла
                await asyncio.sleep(self.telegram_config.message_collection_interval)

            except asyncio.CancelledError:
                logger.info("Collection loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                await asyncio.sleep(60)  # Ждем минуту перед повторной попыткой

    async def get_chat_messages_for_summary(
        self,
        chat_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Message]:
        """Получение сообщений для суммаризации"""
        return self.database.get_messages_by_chat(
            chat_id=chat_id,
            start_date=start_date,
            end_date=end_date
        )