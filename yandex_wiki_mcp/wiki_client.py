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

        # Получаем новый IAM токен через обмен OAuth токена
        try:
            token_url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
            headers = {"Content-Type": "application/json"}

            # Способ 1: Обмен OAuth токена на IAM токен
            if self.oauth_token.startswith('y0_'):
                data = {"yandexPassportOauthToken": self.oauth_token}
                logger.info("Exchanging OAuth token for IAM token...")
            else:
                # Способ 2: Если уже IAM токен (для обратной совместимости)
                logger.info("Using provided IAM token directly...")
                self.iam_token = self.oauth_token
                # Устанавливаем время истечения через 12 часов
                self.iam_token_expires = datetime.now(timezone.utc) + timedelta(hours=12)
                return self.iam_token

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(token_url, headers=headers, json=data)

                # Обрабатываем разные ошибки
                if response.status_code == 401:
                    logger.error("OAuth token expired or invalid. Please get a new OAuth token from:")
                    logger.error("https://oauth.yandex.ru/authorize?response_type=token&client_id=4d1bf1b6426440a3b4b747b6f4f8e8f0")
                    return None
                elif response.status_code == 403:
                    logger.error("Access denied. Check if the OAuth token has correct permissions.")
                    return None

                response.raise_for_status()

                result = response.json()
                self.iam_token = result.get("iamToken")
                expires_at_str = result.get("expiresAt")

                if self.iam_token and expires_at_str:
                    # Парсим дату истечения
                    self.iam_token_expires = datetime.fromisoformat(
                        expires_at_str.replace('Z', '+00:00')
                    ).replace(tzinfo=timezone.utc)

                    logger.info(f"IAM token obtained successfully, expires at: {self.iam_token_expires}")
                    return self.iam_token
                else:
                    logger.error(f"Failed to get IAM token from response: {result}")
                    return None

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting IAM token: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 401:
                logger.error("🔑 OAuth token expired! Get new token at:")
                logger.error("https://oauth.yandex.ru/authorize?response_type=token&client_id=4d1bf1b6426440a3b4b747b6f4f8e8f0")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting IAM token: {e}")
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
        # Пробуем разные варианты структуры URL
        if self.config.organization_id and not endpoint.startswith('folders'):
            # Вариант 2: /{endpoint}?orgId={organization_id}
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            if not params:
                params = {}
            params["orgId"] = self.config.organization_id
        else:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Для Wiki API используем правильные заголовки согласно документации
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"OAuth {self.oauth_token}",
            "Host": "api.wiki.yandex.net"
        }

        # Для Yandex Cloud Organization используем X-Cloud-Org-Id
        if self.config.organization_id:
            headers["X-Cloud-Org-Id"] = self.config.organization_id

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=data)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=headers, json=data)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Обрабатываем редирект на страницу авторизации
                if response.status_code == 302:
                    redirect_url = response.headers.get('location', '')
                    if 'oauth.yandex.ru' in redirect_url or 'auth.cloud.yandex.ru' in redirect_url:
                        logger.error("🔐 OAuth authorization required for Wiki API")
                        logger.error("Please ensure your OAuth token has Wiki permissions")
                        logger.error("Token URL: https://oauth.yandex.ru/authorize?response_type=token&client_id=4d1bf1b6426440a3b4b747b6f4f8e8f0")
                        raise Exception("OAuth authorization required - check token permissions")

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")

                # Если проблема с авторизацией OAuth
                if e.response.status_code == 401:
                    logger.error("🔑 OAuth token expired or invalid for Wiki API")
                    logger.error("Get new token at: https://oauth.yandex.ru/authorize?response_type=token&client_id=4d1bf1b6426440a3b4b747b6f4f8e8f0")
                    raise Exception("OAuth token expired - get new token")
                elif e.response.status_code == 403:
                    logger.error("🚫 Access denied - OAuth token may not have Wiki permissions")
                    logger.error("Ensure the token has access to Yandex Wiki API")
                    raise Exception("Access denied - check token permissions")

                raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
            except httpx.RequestError as e:
                logger.error(f"Request error: {e}")
                raise Exception(f"Request failed: {e}")

    async def get_page_details(self, page_id: str) -> Dict[str, Any]:
        """Получить детальную информацию о странице по ID"""
        return await self._make_request("GET", f"pages/{page_id}")

    async def get_page_by_slug(self, slug: str) -> Dict[str, Any]:
        """Получить детальную информацию о странице по slug"""
        params = {"slug": slug}
        return await self._make_request("GET", "pages", params=params)


    async def search_pages(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """Поиск страниц"""
        params = {"query": query, "limit": limit}
        return await self._make_request("GET", "pages/search", params=params)

    async def get_page_list(self, slug: Optional[str] = None, folder_id: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """Получить список страниц"""
        params = {"limit": limit}
        if slug:
            params["slug"] = slug
        if folder_id:
            params["folderId"] = folder_id
        return await self._make_request("GET", "pages", params=params)

    async def create_page(
        self,
        slug: str,
        title: str,
        content: str,
        folder_id: Optional[str] = None,
        parent_page_id: Optional[str] = None,
        page_type: str = "page"
    ) -> Dict[str, Any]:
        """Создать новую страницу
        
        Args:
            slug: Идентификатор страницы (обязательно)
            title: Заголовок страницы (обязательно)
            content: Содержимое страницы в формате markdown (обязательно)
            folder_id: ID папки (опционально)
            parent_page_id: ID родительской страницы (опционально)
            page_type: Тип страницы (page, grid, cloud_page, wysiwyg, template)
        """
        # Согласно документации, slug должен быть в body, а не в query params
        data = {
            "slug": slug,
            "title": title,
            "page_type": page_type,
            "content": content  # content должен быть строкой, не объектом
        }

        if folder_id:
            data["folderId"] = folder_id
        if parent_page_id:
            data["parentPageId"] = parent_page_id

        return await self._make_request("POST", "pages", data=data)


    async def append_content(self, page_id: str, content: str) -> Dict[str, Any]:
        """Добавить контент в конец страницы"""
        data = {
            "content": content,
            "body": {
                "location": "bottom"
            }
        }
        return await self._make_request("POST", f"pages/{page_id}/append-content", data=data)

    async def delete_page(self, page_id: str) -> Dict[str, Any]:
        """Удалить страницу"""
        return await self._make_request("DELETE", f"pages/{page_id}")

    async def get_page_history(self, page_id: str, limit: int = 20) -> Dict[str, Any]:
        """Получить историю изменений страницы"""
        params = {"limit": limit}
        return await self._make_request("GET", f"pages/{page_id}/history", params=params)

    async def get_folders(self) -> Dict[str, Any]:
        """Получить список папок
        
        Примечание: В текущей версии API Yandex Wiki нет отдельного эндпоинта для папок.
        Используется эндпоинт pages для получения структуры.
        """
        # Получаем список страниц с минимальным лимитом для проверки доступа
        # slug является обязательным параметром для GET /pages
        return await self._make_request("GET", "pages", params={"slug": "homepage", "limit": 1})

    async def test_connection(self) -> bool:
        """Проверить соединение с API"""
        try:
            # Проверяем наличие OAuth токена
            if not self.oauth_token:
                logger.error("❌ No OAuth token configured")
                return False

            if not self.oauth_token.startswith('y0_'):
                logger.error("❌ Invalid OAuth token format (should start with y0_)")
                return False

            # Проверяем наличие организации ID
            if not self.config.organization_id:
                logger.error("❌ No organization ID configured")
                return False

            # Проверяем доступ к Wiki API через простой запрос списка страниц
            # slug является обязательным параметром для GET /pages
            result = await self._make_request("GET", "pages", params={"slug": "homepage", "limit": 1})
            logger.debug("✅ Wiki API connection test successful")
            return True

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            if "OAuth authorization required" in str(e):
                logger.error("💡 Tip: Ensure your OAuth token has Wiki API permissions")
                logger.error("Get new token at: https://oauth.yandex.ru/authorize?response_type=token&client_id=4d1bf1b6426440a3b4b747b6f4f8e8f0")
            return False