"""
Модели данных и работа с базой данных
"""

import sqlite3
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from pathlib import Path

from config import DatabaseConfig

logger = logging.getLogger(__name__)


class Message:
    """Модель сообщения"""

    def __init__(
        self,
        message_id: int,
        chat_id: str,
        chat_title: str,
        sender_id: int,
        sender_name: str,
        text: str,
        timestamp: datetime,
        reply_to_id: Optional[int] = None,
        media_type: Optional[str] = None,
        media_url: Optional[str] = None
    ):
        self.message_id = message_id
        self.chat_id = chat_id
        self.chat_title = chat_title
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.text = text
        self.timestamp = timestamp
        self.reply_to_id = reply_to_id
        self.media_type = media_type
        self.media_url = media_url

    def to_dict(self) -> Dict[str, Any]:
        return {
            'message_id': self.message_id,
            'chat_id': self.chat_id,
            'chat_title': self.chat_title,
            'sender_id': self.sender_id,
            'sender_name': self.sender_name,
            'text': self.text,
            'timestamp': self.timestamp.isoformat(),
            'reply_to_id': self.reply_to_id,
            'media_type': self.media_type,
            'media_url': self.media_url
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        return cls(
            message_id=data['message_id'],
            chat_id=data['chat_id'],
            chat_title=data['chat_title'],
            sender_id=data['sender_id'],
            sender_name=data['sender_name'],
            text=data['text'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            reply_to_id=data.get('reply_to_id'),
            media_type=data.get('media_type'),
            media_url=data.get('media_url')
        )


class Database:
    """Класс для работы с базой данных SQLite"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.db_path = Path(config.db_path)
        self._init_database()

    def _init_database(self):
        """Инициализация базы данных и создание таблиц"""
        # Создаем директорию для БД если она не существует
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Таблица сообщений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    chat_id TEXT NOT NULL,
                    chat_title TEXT NOT NULL,
                    sender_id INTEGER NOT NULL,
                    sender_name TEXT NOT NULL,
                    text TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    reply_to_id INTEGER,
                    media_type TEXT,
                    media_url TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(message_id, chat_id)
                )
            ''')

            # Таблица чатов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT UNIQUE NOT NULL,
                    chat_title TEXT NOT NULL,
                    chat_type TEXT NOT NULL,
                    last_message_id INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Индексы для оптимизации запросов
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_chat_timestamp
                ON messages(chat_id, timestamp DESC)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_sender
                ON messages(sender_id, timestamp DESC)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_reply
                ON messages(reply_to_id)
            ''')

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def get_connection(self):
        """Контекст менеджер для соединения с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_message(self, message: Message) -> bool:
        """Сохранение сообщения в базу данных"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Сначала обновляем или создаем запись о чате
                cursor.execute('''
                    INSERT OR REPLACE INTO chats (chat_id, chat_title, chat_type, last_message_id, updated_at)
                    VALUES (?, ?, 'telegram', ?, CURRENT_TIMESTAMP)
                ''', (message.chat_id, message.chat_title, message.message_id))

                # Вставляем или обновляем сообщение
                cursor.execute('''
                    INSERT OR REPLACE INTO messages
                    (message_id, chat_id, chat_title, sender_id, sender_name, text, timestamp,
                     reply_to_id, media_type, media_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    message.message_id,
                    message.chat_id,
                    message.chat_title,
                    message.sender_id,
                    message.sender_name,
                    message.text,
                    message.timestamp,
                    message.reply_to_id,
                    message.media_type,
                    message.media_url
                ))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error saving message: {e}")
            return False

    def save_messages_batch(self, messages: List[Message]) -> int:
        """Пакетное сохранение сообщений"""
        saved_count = 0
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                for message in messages:
                    try:
                        # Обновляем информацию о чате
                        cursor.execute('''
                            INSERT OR REPLACE INTO chats (chat_id, chat_title, chat_type, last_message_id, updated_at)
                            VALUES (?, ?, 'telegram', ?, CURRENT_TIMESTAMP)
                        ''', (message.chat_id, message.chat_title, message.message_id))

                        # Вставляем сообщение
                        cursor.execute('''
                            INSERT OR REPLACE INTO messages
                            (message_id, chat_id, chat_title, sender_id, sender_name, text, timestamp,
                             reply_to_id, media_type, media_url)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            message.message_id,
                            message.chat_id,
                            message.chat_title,
                            message.sender_id,
                            message.sender_name,
                            message.text,
                            message.timestamp,
                            message.reply_to_id,
                            message.media_type,
                            message.media_url
                        ))
                        saved_count += 1

                    except Exception as e:
                        logger.warning(f"Error saving message {message.message_id}: {e}")
                        continue

                conn.commit()
                logger.info(f"Saved {saved_count} out of {len(messages)} messages")

        except Exception as e:
            logger.error(f"Error in batch save: {e}")

        return saved_count

    def get_messages_by_chat(
        self,
        chat_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Получение сообщений из указанного чата"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                query = '''
                    SELECT message_id, chat_id, chat_title, sender_id, sender_name,
                           text, timestamp, reply_to_id, media_type, media_url
                    FROM messages
                    WHERE chat_id = ?
                '''
                params = [chat_id]

                if start_date:
                    query += ' AND timestamp >= ?'
                    params.append(start_date)

                if end_date:
                    query += ' AND timestamp <= ?'
                    params.append(end_date)

                query += ' ORDER BY timestamp ASC'

                if limit:
                    query += ' LIMIT ?'
                    params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [
                    Message(
                        message_id=row['message_id'],
                        chat_id=row['chat_id'],
                        chat_title=row['chat_title'],
                        sender_id=row['sender_id'],
                        sender_name=row['sender_name'],
                        text=row['text'],
                        timestamp=datetime.fromisoformat(row['timestamp']),
                        reply_to_id=row['reply_to_id'],
                        media_type=row['media_type'],
                        media_url=row['media_url']
                    )
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Error getting messages for chat {chat_id}: {e}")
            return []

    def get_messages_for_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        chat_id: Optional[str] = None
    ) -> Dict[str, List[Message]]:
        """Получение сообщений за период времени"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                query = '''
                    SELECT message_id, chat_id, chat_title, sender_id, sender_name,
                           text, timestamp, reply_to_id, media_type, media_url
                    FROM messages
                    WHERE timestamp >= ? AND timestamp <= ?
                '''
                params = [start_date, end_date]

                if chat_id:
                    query += ' AND chat_id = ?'
                    params.append(chat_id)

                query += ' ORDER BY chat_id, timestamp ASC'

                cursor.execute(query, params)
                rows = cursor.fetchall()

                # Группируем сообщения по чатам
                messages_by_chat = {}
                for row in rows:
                    chat_id = row['chat_id']
                    if chat_id not in messages_by_chat:
                        messages_by_chat[chat_id] = []

                    messages_by_chat[chat_id].append(
                        Message(
                            message_id=row['message_id'],
                            chat_id=row['chat_id'],
                            chat_title=row['chat_title'],
                            sender_id=row['sender_id'],
                            sender_name=row['sender_name'],
                            text=row['text'],
                            timestamp=datetime.fromisoformat(row['timestamp']),
                            reply_to_id=row['reply_to_id'],
                            media_type=row['media_type'],
                            media_url=row['media_url']
                        )
                    )

                return messages_by_chat

        except Exception as e:
            logger.error(f"Error getting messages for date range: {e}")
            return {}

    def get_last_message_id(self, chat_id: str) -> int:
        """Получение ID последнего сообщения в чате"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT MAX(message_id) as max_id FROM messages WHERE chat_id = ?',
                    (chat_id,)
                )
                row = cursor.fetchone()
                return row['max_id'] or 0

        except Exception as e:
            logger.error(f"Error getting last message ID for chat {chat_id}: {e}")
            return 0

    def get_active_chats(self) -> List[Dict[str, Any]]:
        """Получение списка активных чатов"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT chats.chat_id, chats.chat_title, chat_type, last_message_id,
                           updated_at, COUNT(messages.id) as message_count
                    FROM chats
                    LEFT JOIN messages ON chats.chat_id = messages.chat_id
                    GROUP BY chats.chat_id
                    ORDER BY updated_at DESC
                ''')

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting active chats: {e}")
            return []

    def cleanup_old_messages(self, days_to_keep: int = 30) -> int:
        """Очистка старых сообщений"""
        try:
            cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_to_keep)

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM messages WHERE timestamp < ?', (cutoff_date,))
                deleted_count = cursor.rowcount
                conn.commit()

                logger.info(f"Deleted {deleted_count} old messages")
                return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up old messages: {e}")
            return 0