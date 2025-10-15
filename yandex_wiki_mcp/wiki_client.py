"""
HTTP клиент для работы с Yandex Wiki API
"""

import logging
from typing import Dict, Any, Optional, List
import httpx
import asyncio
from datetime import datetime, timezone, timedelta
from config import Config

logger = logging.getLogger(__name__)


class YandexWikiClient:
    """Клиент для работы с Yandex Wiki API"""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.wiki_api_url
        self.oauth_token = config.yandex_token
        self.iam_token = None
        self.iam_token_expires = None
        self.headers = {
            "Content-Type": "application/json"
        }
        # Добавляем X-Org-ID только если он есть
        if config.organization_id:
            self.headers["X-Org-ID"] = config.organization_id

    async def _get_iam_token(self) -> Optional[str]:
        """Получение или обновление IAM токена"""
        # Проверяем, есть ли действующий токен
        if (self.iam_token and self.iam_token_expires and
            self.iam_token_expires > datetime.now(timezone.utc) + timedelta(minutes=5)):
            return self.iam_token

        # Получаем новый IAM токен
        try:
            token_url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
            headers = {"Content-Type": "application/json"}
            data = {"yandexPassportOauthToken": self.oauth_token}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(token_url, headers=headers, json=data)
                response.raise_for_status()

                result = response.json()
                self.iam_token = result.get("iamToken")
                expires_at_str = result.get("expiresAt")

                if self.iam_token and expires_at_str:
                    # Парсим дату истечения
                    self.iam_token_expires = datetime.fromisoformat(
                        expires_at_str.replace('Z', '+00:00')
                    ).replace(tzinfo=timezone.utc)

                    logger.info(f"IAM token obtained, expires at: {self.iam_token_expires}")
                    return self.iam_token
                else:
                    logger.error("Failed to get IAM token from response")
                    return None

        except Exception as e:
            logger.error(f"Error getting IAM token: {e}")
            return None

    async def _ensure_valid_token(self) -> bool:
        """Убедиться, что есть действующий IAM токен"""
        token = await self._get_iam_token()
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
            return True
        return False

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Выполнение HTTP запроса к API"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Убеждаемся, что есть действующий токен
        if not await self._ensure_valid_token():
            raise Exception("Failed to get valid IAM token")

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=self.headers, params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=self.headers, json=data)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=self.headers, json=data)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=self.headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")

                # Если проблема с авторизацией (401), пробуем обновить токен и повторить запрос
                if e.response.status_code == 401:
                    logger.info("Authorization failed, refreshing IAM token...")
                    if await self._ensure_valid_token():
                        # Повторяем запрос с новым токеном
                        try:
                            if method.upper() == "GET":
                                response = await client.get(url, headers=self.headers, params=params)
                            elif method.upper() == "POST":
                                response = await client.post(url, headers=self.headers, json=data)
                            elif method.upper() == "PUT":
                                response = await client.put(url, headers=self.headers, json=data)
                            elif method.upper() == "DELETE":
                                response = await client.delete(url, headers=self.headers)

                            response.raise_for_status()
                            return response.json()
                        except Exception as retry_error:
                            logger.error(f"Retry failed: {retry_error}")

                raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
            except httpx.RequestError as e:
                logger.error(f"Request error: {e}")
                raise Exception(f"Request failed: {e}")

    async def get_page_details(self, page_id: str) -> Dict[str, Any]:
        """Получить детальную информацию о странице"""
        return await self._make_request("GET", f"pages/{page_id}")

    async def get_page_content(self, page_id: str) -> Dict[str, Any]:
        """Получить содержимое страницы"""
        return await self._make_request("GET", f"pages/{page_id}/content")

    async def search_pages(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """Поиск страниц"""
        params = {"query": query, "limit": limit}
        return await self._make_request("GET", "pages/search", params=params)

    async def get_page_list(self, folder_id: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """Получить список страниц"""
        params = {"limit": limit}
        if folder_id:
            params["folderId"] = folder_id
        return await self._make_request("GET", "pages", params=params)

    async def create_page(
        self,
        title: str,
        content: str,
        folder_id: Optional[str] = None,
        parent_page_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Создать новую страницу"""
        data = {
            "title": title,
            "content": {
                "body": content,
                "format": "markdown"
            }
        }

        if folder_id:
            data["folderId"] = folder_id
        if parent_page_id:
            data["parentPageId"] = parent_page_id

        return await self._make_request("POST", "pages", data=data)

    async def update_page(
        self,
        page_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None
    ) -> Dict[str, Any]:
        """Обновить существующую страницу"""
        data = {}

        if title:
            data["title"] = title
        if content:
            data["content"] = {
                "body": content,
                "format": "markdown"
            }

        return await self._make_request("PUT", f"pages/{page_id}", data=data)

    async def delete_page(self, page_id: str) -> Dict[str, Any]:
        """Удалить страницу"""
        return await self._make_request("DELETE", f"pages/{page_id}")

    async def get_page_history(self, page_id: str, limit: int = 20) -> Dict[str, Any]:
        """Получить историю изменений страницы"""
        params = {"limit": limit}
        return await self._make_request("GET", f"pages/{page_id}/history", params=params)

    async def get_folders(self) -> Dict[str, Any]:
        """Получить список папок"""
        return await self._make_request("GET", "folders")

    async def test_connection(self) -> bool:
        """Проверить соединение с API"""
        try:
            # Пробуем получить список папок для проверки соединения
            await self.get_folders()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False