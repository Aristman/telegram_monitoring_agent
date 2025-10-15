"""
Сервис суммаризации сообщений и создания отчетов
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from config import AppConfig
from database import Database, Message
from wiki_client import YandexWikiMCPClient, WikiReportGenerator
from yandex_gpt import YandexGPTClient, MessageSummarizer
from telegram_collector import TelegramCollector

logger = logging.getLogger(__name__)


class SummaryService:
    """Основной сервис для суммаризации и создания отчетов"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.database = Database(config.get_database_config())
        self.wiki_client = YandexWikiMCPClient(config.get_wiki_config())
        self.wiki_generator = WikiReportGenerator(self.wiki_client, config.get_wiki_config())
        self.gpt_client = YandexGPTClient(config.get_gpt_config())
        self.summarizer = MessageSummarizer(self.gpt_client)

    async def initialize(self) -> bool:
        """Инициализация сервиса"""
        try:
            # Проверяем соединение с Wiki
            wiki_connected = await self.wiki_client.initialize()
            if not wiki_connected:
                logger.error("Failed to connect to Wiki MCP server")
                return False

            # Проверяем соединение с GPT
            gpt_connected = await self.gpt_client.test_connection()
            if not gpt_connected:
                logger.error("Failed to connect to Yandex GPT")
                return False

            logger.info("Summary service initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error initializing summary service: {e}")
            return False

    async def create_daily_summary(self, target_date: Optional[datetime] = None) -> bool:
        """Создание дневной сводки"""
        try:
            if target_date is None:
                # Используем вчерашний день
                target_date = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) - timedelta(days=1)

            logger.info(f"Creating daily summary for {target_date.strftime('%Y-%m-%d')}")

            # Получаем все сообщения за день
            start_date = target_date
            end_date = target_date + timedelta(days=1)

            messages_by_chat = self.database.get_messages_for_date_range(
                start_date=start_date,
                end_date=end_date
            )

            if not messages_by_chat:
                logger.info(f"No messages found for {target_date.strftime('%Y-%m-%d')}")
                return True

            logger.info(f"Found messages from {len(messages_by_chat)} chats")

            # Создаем сводки для каждого чата
            chat_summaries = {}
            total_pages_created = 0

            for chat_id, messages in messages_by_chat.items():
                try:
                    # Получаем заголовок чата
                    chat_title = messages[0].chat_title if messages else chat_id

                    # Создаем сводку с помощью GPT
                    messages_data = [msg.to_dict() for msg in messages]
                    summary = await self.summarizer.summarize_daily_messages(
                        chat_title=chat_title,
                        messages=messages_data
                    )

                    if summary:
                        chat_summaries[chat_title] = summary

                        # Создаем страницу сводки в Wiki
                        page_id = await self.wiki_generator.create_daily_summary(
                            chat_title=chat_title,
                            summary=summary,
                            summary_date=target_date
                        )

                        if page_id:
                            total_pages_created += 1
                            logger.info(f"Created daily summary for chat '{chat_title}'")

                    else:
                        logger.warning(f"Failed to generate summary for chat '{chat_title}'")

                except Exception as e:
                    logger.error(f"Error processing chat '{chat_id}': {e}")
                    continue

            # Создаем главную страницу сводки
            if chat_summaries:
                main_page_id = await self.wiki_generator.create_main_summary_page(
                    summaries=chat_summaries,
                    summary_date=target_date
                )

                if main_page_id:
                    total_pages_created += 1
                    logger.info(f"Created main summary page for {target_date.strftime('%Y-%m-%d')}")

            logger.info(f"Daily summary completed. Created {total_pages_created} pages")
            return True

        except Exception as e:
            logger.error(f"Error creating daily summary: {e}")
            return False

    async def create_chat_report(self, chat_id: str, report_date: Optional[datetime] = None, hours_back: int = 6) -> bool:
        """Создание отчета по конкретному чату на основе диапазона ID сообщений"""
        try:
            if report_date is None:
                report_date = datetime.now(timezone.utc)

            # Получаем ID последнего отправленного сообщения
            last_sent_id = self.database.get_last_sent_message_id(chat_id)
            
            # Получаем ID последнего прочитанного сообщения
            last_read_id = self.database.get_last_message_id(chat_id)

            logger.info(f"Creating report for chat {chat_id}: messages from ID {last_sent_id} to {last_read_id}")

            # Если нет новых сообщений
            if last_read_id <= last_sent_id:
                logger.info(f"No new messages for chat {chat_id} (last_sent: {last_sent_id}, last_read: {last_read_id})")
                return True

            # Получаем сообщения по диапазону ID
            messages = self.database.get_messages_by_id_range(
                chat_id=chat_id,
                min_message_id=last_sent_id,
                max_message_id=last_read_id
            )

            if not messages:
                logger.warning(f"No messages found in range {last_sent_id}-{last_read_id} for chat {chat_id}")
                return True

            # Получаем заголовок чата
            chat_title = messages[0].chat_title if messages else chat_id

            # Создаем отчет в Wiki
            messages_data = [msg.to_dict() for msg in messages]
            page_id = await self.wiki_generator.generate_chat_report(
                chat_title=chat_title,
                messages=messages_data,
                report_date=report_date
            )

            if page_id:
                # Обновляем ID последнего отправленного сообщения
                self.database.update_last_sent_message_id(chat_id, last_read_id)
                logger.info(f"Created chat report for '{chat_title}' with {len(messages)} messages (ID range: {last_sent_id}-{last_read_id})")
                return True
            else:
                logger.error(f"Failed to create chat report for '{chat_title}'")
                return False

        except Exception as e:
            logger.error(f"Error creating chat report for {chat_id}: {e}")
            return False

    async def create_periodic_reports(self) -> Dict[str, bool]:
        """Создание периодических отчетов по всем чатам"""
        try:
            results = {}
            current_time = datetime.now(timezone.utc)

            # Получаем активные чаты
            active_chats = self.database.get_active_chats()

            for chat_info in active_chats:
                chat_id = chat_info['chat_id']
                chat_title = chat_info['chat_title']

                try:
                    success = await self.create_chat_report(chat_id, current_time)
                    results[chat_title] = success

                except Exception as e:
                    logger.error(f"Error creating report for chat '{chat_title}': {e}")
                    results[chat_title] = False

            successful_reports = sum(1 for success in results.values() if success)
            logger.info(f"Periodic reports completed: {successful_reports}/{len(results)} successful")

            return results

        except Exception as e:
            logger.error(f"Error creating periodic reports: {e}")
            return {}

    async def analyze_chat_trends(self, chat_id: str, days: int = 7) -> Optional[Dict[str, Any]]:
        """Анализ трендов в чате за указанный период"""
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            # Получаем сообщения за период
            messages = self.database.get_messages_by_chat(
                chat_id=chat_id,
                start_date=start_date,
                end_date=end_date
            )

            if not messages:
                return None

            # Группируем сообщения по дням
            daily_stats = {}
            for message in messages:
                day_key = message.timestamp.strftime('%Y-%m-%d')
                if day_key not in daily_stats:
                    daily_stats[day_key] = {
                        'message_count': 0,
                        'participants': set(),
                        'messages': []
                    }

                daily_stats[day_key]['message_count'] += 1
                daily_stats[day_key]['participants'].add(message.sender_name)
                daily_stats[day_key]['messages'].append(message.to_dict())

            # Извлекаем темы для каждого дня
            trends = {}
            for day, stats in daily_stats.items():
                messages_data = stats['messages']
                topics = await self.summarizer.extract_topics(messages_data)

                trends[day] = {
                    'message_count': stats['message_count'],
                    'participant_count': len(stats['participants']),
                    'participants': list(stats['participants']),
                    'topics': topics
                }

            return {
                'chat_id': chat_id,
                'period': f"{days} days",
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'daily_trends': trends,
                'total_messages': sum(stats['message_count'] for stats in daily_stats.values()),
                'total_participants': len(set(
                    participant for stats in daily_stats.values()
                    for participant in stats['participants']
                ))
            }

        except Exception as e:
            logger.error(f"Error analyzing trends for chat {chat_id}: {e}")
            return None

    async def cleanup_old_reports(self, days_to_keep: int = 30) -> int:
        """Очистка старых данных"""
        try:
            # Очищаем старые сообщения из БД
            deleted_messages = self.database.cleanup_old_messages(days_to_keep)

            # TODO: Добавить очистку старых Wiki страниц при необходимости

            logger.info(f"Cleanup completed: {deleted_messages} old messages deleted")
            return deleted_messages

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0

    async def get_service_status(self) -> Dict[str, Any]:
        """Получение статуса сервиса"""
        try:
            # Проверяем соединения
            wiki_status = await self.wiki_client._send_mcp_request("tools/call", {
                "name": "ywiki.test_connection",
                "arguments": {}
            }) if self.wiki_client else None

            gpt_status = await self.gpt_client.test_connection() if self.gpt_client else False

            # Получаем статистику по БД
            active_chats = self.database.get_active_chats()

            return {
                'wiki_connected': wiki_status is not None,
                'gpt_connected': gpt_status,
                'active_chats_count': len(active_chats),
                'active_chats': [
                    {
                        'chat_id': chat['chat_id'],
                        'chat_title': chat['chat_title'],
                        'message_count': chat['message_count'],
                        'last_activity': chat['updated_at']
                    }
                    for chat in active_chats
                ],
                'service_initialized': True
            }

        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {
                'wiki_connected': False,
                'gpt_connected': False,
                'active_chats_count': 0,
                'active_chats': [],
                'service_initialized': False,
                'error': str(e)
            }