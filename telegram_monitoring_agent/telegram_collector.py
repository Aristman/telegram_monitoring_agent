"""
Сборщик сообщений из Telegram через MCP сервер
"""

import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta
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

            logger.debug(f"Sending MCP request: {method}")
            logger.debug(f"Request params: {params}")
            logger.debug(f"Raw request: '{request_json}'")

            self.server_process.stdin.write(request_bytes)
            await self.server_process.stdin.drain()

            # Читаем ответ
            response_data = await self._read_mcp_response()
            logger.debug(f"Received MCP response: {response_data}")
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

        try:
            # Читаем заголовки построчно до пустой строки
            headers = {}
            while True:
                line = await self.server_process.stdout.readline()
                if not line:
                    logger.error("Connection closed while reading headers")
                    return {"error": "Connection closed"}
                
                line_str = line.decode('utf-8', errors='replace').strip()
                
                # Пустая строка означает конец заголовков
                if not line_str:
                    break
                
                # Парсим заголовок
                if ':' in line_str:
                    key, value = line_str.split(':', 1)
                    headers[key.strip().lower()] = value.strip()
            
            # Получаем Content-Length
            content_length_str = headers.get('content-length', '0')
            try:
                content_length = int(content_length_str)
            except ValueError:
                logger.error(f"Invalid Content-Length: {content_length_str}")
                return {"error": f"Invalid Content-Length: {content_length_str}"}
            
            if content_length <= 0:
                logger.error("Content-Length is 0 or negative")
                return {"error": "Invalid Content-Length"}
            
            logger.debug(f"Content-Length: {content_length}")
            
            # Читаем тело ответа точно указанной длины
            body_bytes = await self.server_process.stdout.readexactly(content_length)
            body_str = body_bytes.decode('utf-8', errors='replace')
            
            logger.debug(f"Received {len(body_bytes)} bytes")
            logger.debug(f"Response body (first 200 chars): {body_str[:200]}")
            
            # Парсим JSON
            try:
                response = json.loads(body_str)
                return response
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                logger.error(f"Full response body: {body_str}")
                return {"error": f"JSON decode error: {e}", "raw": body_str}
        
        except asyncio.IncompleteReadError as e:
            logger.error(f"Incomplete read: expected {e.expected} bytes, got {len(e.partial)} bytes")
            logger.error(f"Partial data: {e.partial.decode('utf-8', errors='replace')}")
            return {"error": "Incomplete response"}
        except Exception as e:
            logger.error(f"Error reading MCP response: {e}", exc_info=True)
            return {"error": str(e)}

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
            logger.info(f"ℹ️ Запрос информации о чате {chat_id}")

            response = await self._send_mcp_request("tools/call", {
                "name": "tg.resolve_chat",
                "arguments": {"chat": chat_id}
            })

            if "result" in response and response["result"]:
                if "content" in response["result"] and len(response["result"]["content"]) > 0:
                    content = response["result"]["content"][0]["text"]
                    chat_info = json.loads(content)
                    chat_title = chat_info.get("title", chat_id)
                    logger.info(f"ℹ️ Получена информация о чате: {chat_title} ({chat_id})")
                    return chat_info
                else:
                    logger.warning(f"⚠️ Пустой content в ответе о чате {chat_id}")
                    return None
            else:
                logger.warning(f"⚠️ Не удалось получить информацию о чате {chat_id}")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка при получении информации о чате {chat_id}: {e}")
            return None

    async def fetch_messages(
        self,
        chat_id: str,
        limit: int = 100,
        min_id: int = 0
    ) -> List[Dict[str, Any]]:
        """Получение сообщений из чата"""
        try:
            # logger.info(f"📡 Отправка MCP запроса в Telegram для чата {chat_id}")
            # logger.info(f"📋 Параметры запроса: limit={limit}, min_id={min_id}")

            response = await self._send_mcp_request("tools/call", {
                "name": "tg.read_messages",
                "arguments": {
                    "chat": chat_id,
                    "page_size": limit,
                    "min_id": min_id
                }
            })

            # logger.info(f"📥 Получен MCP ответ от Telegram для чата {chat_id}")

            if "result" in response and response["result"]:
                if "content" in response["result"] and len(response["result"]["content"]) > 0:
                    content = response["result"]["content"][0]["text"]
                    data = json.loads(content)
                    messages = data.get("messages", [])

                    # logger.info(f"✅ Успешно получены {len(messages)} сообщений из чата {chat_id}")

                    # Логируем детальную информацию о сообщениях
                    if messages:
                        first_msg = messages[0]
                        last_msg = messages[-1]
                        # logger.info(f"📝 Первый результат: ID={first_msg.get('id', 'N/A')}, дата={first_msg.get('date', 'N/A')}")
                        # logger.info(f"📝 Последний результат: ID={last_msg.get('id', 'N/A')}, дата={last_msg.get('date', 'N/A')}")

                        # Логируем информацию об отправителях
                        senders = set()
                        for msg in messages[:10]:  # Проверяем первые 10 сообщений
                            if "from" in msg:
                                senders.add(msg["from"].get("display", "Unknown"))

                        # if senders:
                            # logger.info(f"👥 Отправители в этой партии: {', '.join(list(senders)[:5])}")

                    return messages
                else:
                    logger.warning(f"⚠️ Пустой content в MCP ответе от чата {chat_id}")
                    return []
            else:
                logger.warning(f"⚠️ Нет результата в MCP ответе от чата {chat_id}")
                logger.warning(f"🔍 Структура ответа: {list(response.keys()) if isinstance(response, dict) else type(response)}")
                return []

        except Exception as e:
            logger.error(f"❌ Ошибка при получении сообщений из чата {chat_id}: {e}")
            logger.error(f"🔍 Параметры запроса: chat={chat_id}, limit={limit}, min_id={min_id}")
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
        start_time = datetime.now()
        try:
            # logger.info(f"🔍 Начинаем сбор сообщений из чата {chat_id}")

            # Получаем ID последнего сохраненного сообщения
            last_message_id = self.database.get_last_message_id(chat_id)
            logger.info(f"📋 Последнее сохраненное сообщение в чате {chat_id}: ID={last_message_id}")

            # Получаем новые сообщения
            # logger.info(f"📡 Запрашиваем сообщения из Telegram: chat={chat_id}, limit={self.telegram_config.max_messages_per_fetch}, min_id={last_message_id}")

            messages_data = await self.mcp_client.fetch_messages(
                chat_id=chat_id,
                limit=self.telegram_config.max_messages_per_fetch,
                min_id=last_message_id
            )

            # Логируем результат запроса
            if messages_data:
                # logger.info(f"✅ Получено {len(messages_data)} сообщений из Telegram для чата {chat_id}")
                # Логируем информацию о первом и последнем сообщении
                if messages_data:
                    first_msg_id = messages_data[0].get("id", "unknown")
                    last_msg_id = messages_data[-1].get("id", "unknown")
                    # logger.info(f"📝 Диапазон ID сообщений: с {first_msg_id} по {last_msg_id}")
            else:
                # logger.info(f"⭕ Новых сообщений в чате {chat_id} не найдено")
                return 0

            # Получаем информацию о чате
            # logger.info(f"ℹ️ Запрашиваем информацию о чате {chat_id}")
            chat_info = await self.mcp_client.get_chat_info(chat_id)
            chat_title = chat_info.get("title", chat_id) if chat_info else chat_id
            # logger.info(f"💬 Название чата: {chat_title}")

            # Конвертируем сообщения в объекты Message
            messages = []
            skipped_empty = 0
            for msg_data in messages_data:
                # Пропускаем сообщения без текста
                text = msg_data.get("text", "").strip()
                if not text:
                    skipped_empty += 1
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

            # if skipped_empty > 0:
                # logger.info(f"🚫 Пропущено {skipped_empty} сообщений без текста")

            # Сохраняем сообщения в базу данных
            # logger.info(f"💾 Сохраняем {len(messages)} сообщений в базу данных")
            saved_count = self.database.save_messages_batch(messages)

            # Логируем финальный результат
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"✅ Сбор сообщений из чата {chat_id} завершен:")
            logger.info(f"   📊 Получено: {len(messages_data)} сообщений")
            logger.info(f"   💾 Сохранено: {saved_count} сообщений")
            logger.info(f"   ⏱️ Время выполнения: {duration:.2f} секунд")

            return saved_count

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.error(f"❌ Ошибка при сборе сообщений из чата {chat_id}: {e}")
            logger.error(f"   ⏱️ Время до ошибки: {duration:.2f} секунд")
            logger.error(f"   🔍 Последнее ID сообщения: {last_message_id if 'last_message_id' in locals() else 'unknown'}")
            return 0

    async def collect_all_chats(self) -> Dict[str, int]:
        """Сбор сообщений из всех настроенных чатов"""
        cycle_start_time = datetime.now()
        results = {}
        total_chats = len(self.telegram_config.monitored_chats)

        # logger.info(f"🚀 Начинаем сбор сообщений из {total_chats} чатов")

        for i, chat_id in enumerate(self.telegram_config.monitored_chats, 1):
            if not self.is_running:
                logger.warning("⏹️ Сбор сообщений прерван")
                break

            try:
                logger.info(f"📋 [{i}/{total_chats}] Обработка чата: {chat_id}")
                count = await self.collect_messages(chat_id)
                results[chat_id] = count

                if count > 0:
                    logger.info(f"✅ Чат {chat_id}: {count} новых сообщений")
                else:
                    logger.info(f"⭕ Чат {chat_id}: нет новых сообщений")

            except Exception as e:
                logger.error(f"❌ Ошибка при обработке чата {chat_id}: {e}")
                results[chat_id] = 0

        # Логируем итоги цикла
        cycle_end_time = datetime.now()
        cycle_duration = (cycle_end_time - cycle_start_time).total_seconds()
        total_collected = sum(results.values())

        logger.info(f"📊 Цикл сбора сообщений завершен:")
        logger.info(f"   ⏱️ Время выполнения: {cycle_duration:.2f} секунд")
        logger.info(f"   📨 Всего собрано: {total_collected} сообщений")
        logger.info(f"   📋 Обработано чатов: {len(results)} из {total_chats}")

        if total_collected > 0:
            logger.info("💾 Детализация по чатам:")
            for chat_id, count in results.items():
                if count > 0:
                    logger.info(f"   📌 {chat_id}: {count} сообщений")

        return results

    async def run_collection_loop(self):
        """Основной цикл сбора сообщений"""
        cycle_count = 0

        logger.info(f"🔄 Запуск основного цикла сбора сообщений")
        logger.info(f"📋 Настроено чатов: {len(self.telegram_config.monitored_chats)}")
        logger.info(f"📝 Список чатов: {self.telegram_config.monitored_chats}")
        logger.info(f"⏰ Интервал сбора: {self.telegram_config.message_collection_interval} секунд")

        while self.is_running:
            cycle_count += 1
            cycle_start_time = datetime.now()

            try:
                # logger.info(f"🚀 Начинаем цикл сбора #{cycle_count} в {cycle_start_time.strftime('%H:%M:%S')}")

                results = await self.collect_all_chats()
                total_collected = sum(results.values())

                cycle_end_time = datetime.now()
                cycle_duration = (cycle_end_time - cycle_start_time).total_seconds()

                # Итоги цикла
                if total_collected > 0:
                    logger.info(f"✅ Цикл #{cycle_count} завершен успешно:")
                    logger.info(f"   📨 Собрано сообщений: {total_collected}")
                    logger.info(f"   ⏱️ Длительность цикла: {cycle_duration:.2f} сек")
                else:
                    logger.info(f"⭕ Цикл #{cycle_count} завершен: новых сообщений нет")
                    logger.info(f"   ⏱️ Длительность цикла: {cycle_duration:.2f} сек")

                # Расчет следующего запуска
                next_run_time = cycle_end_time + timedelta(seconds=self.telegram_config.message_collection_interval)
                logger.info(f"⏭️ Следующий запуск: {next_run_time.strftime('%H:%M:%S')}")

                # Ждем следующего цикла
                logger.info(f"💤 Ожидание {self.telegram_config.message_collection_interval} секунд до следующего цикла...")
                await asyncio.sleep(self.telegram_config.message_collection_interval)

            except asyncio.CancelledError:
                logger.info(f"⏹️ Цикл сбора сообщений остановлен после {cycle_count} итераций")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле #{cycle_count}: {e}")
                logger.info(f"⏱️ Пауза 60 секунд перед повторной попыткой...")
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