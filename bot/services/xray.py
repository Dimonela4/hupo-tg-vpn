"""Async client for the 3X-UI panel API."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import aiohttp

from bot.config import settings

class XRayService:
    def __init__(self):
        self.base_url = settings.XRAY_PANEL_URL.rstrip("/")
        self.api_key = settings.XRAY_API_KEY
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=20)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self.api_key}"
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        async with session.request(method, url, headers=headers, **kwargs) as response:
            body = await response.json(content_type=None)
            if response.status >= 400:
                raise RuntimeError(f"3X-UI returned HTTP {response.status}: {body}")
        if not isinstance(body, dict):
            raise RuntimeError("3X-UI returned an unexpected response")
        return body

    async def get_client_info(self, tg_id: int) -> list[dict]:
        result = await self._request(
            "GET", f"/panel/api/clients/get/tgId/{int(tg_id)}"
        )
        if not result.get("success"):
            message = str(result.get("msg", "")).lower()
            if "not found" in message or "no client" in message:
                return []
            raise RuntimeError(f"3X-UI client lookup failed: {result.get('msg')}")
        clients = result.get("obj") or []
        if isinstance(clients, dict):
            clients = [clients]
        if not isinstance(clients, list):
            raise RuntimeError("3X-UI returned invalid client data")
        return clients

    async def create_client(
        self,
        days: int,
        user_id: int,
        max_hwid: int = 3,
        expiry_ms: Optional[int] = None,
    ) -> bool:
        if days < 0 or (days == 0 and expiry_ms is None):
            raise ValueError("Client duration must be positive")
        expiry = expiry_ms if expiry_ms is not None else self.calculate_date(days)
        payload = {
            "client": {
                "email": str(user_id),
                "totalGB": 0,
                "expiryTime": expiry,
                "enable": True,
                "tgId": int(user_id),
                "limitHwid": max_hwid,
            },
            "inboundIds": settings.XRAY_INBOUND_IDS,
        }
        result = await self._request(
            "POST", "/panel/api/clients/add", json=payload
        )
        if not result.get("success"):
            raise RuntimeError(f"3X-UI client creation failed: {result.get('msg')}")
        return True

    async def set_expiry(self, tg_id: int, expiry_ms: int) -> str:
        clients = await self.get_client_info(tg_id)
        if not clients:
            await self.create_client(0, tg_id, expiry_ms=expiry_ms)
        else:
            client = clients[0].get("client", clients[0])
            if not isinstance(client, dict):
                raise RuntimeError("3X-UI client record is malformed")
            payload = dict(client)
            payload["email"] = str(tg_id)
            payload["tgId"] = int(tg_id)
            payload["expiryTime"] = expiry_ms
            payload["enable"] = True
            result = await self._request(
                "POST",
                f"/panel/api/clients/update/{tg_id}",
                json=payload,
            )
            if not result.get("success"):
                raise RuntimeError(f"3X-UI client update failed: {result.get('msg')}")
        key = await self.get_user_key(tg_id)
        if not key:
            raise RuntimeError("3X-UI did not return a subscription ID")
        return key

    async def extend_client(self, tg_id: int, days: int) -> dict:
        clients = await self.get_client_info(tg_id)
        if clients:
            client = clients[0].get("client", clients[0])
            current_expiry = int(client.get("expiryTime", 0) or 0)
            new_expiry = self.calculate_date(days, current_expiry)
            await self.set_expiry(tg_id, new_expiry)
        else:
            new_expiry = self.calculate_date(days)
            await self.create_client(days, tg_id, expiry_ms=new_expiry)
        return {
            "success": True,
            "new_expiry_time": self.calculate_date_beauty(new_expiry),
        }

    async def is_client_exists(self, tg_id: int) -> bool:
        return bool(await self.get_client_info(tg_id))

    async def get_expiry_date(self, tg_id: int) -> Optional[int]:
        clients = await self.get_client_info(tg_id)
        if not clients:
            return None
        client = clients[0].get("client", clients[0])
        return int(client.get("expiryTime", 0) or 0)

    async def get_expiry_date_beauty(self, tg_id: int) -> Optional[str]:
        expiry = await self.get_expiry_date(tg_id)
        return self.calculate_date_beauty(expiry) if expiry else None

    async def get_user_key(self, tg_id: int, sub_id: Optional[str] = None) -> Optional[str]:
        clients = await self.get_client_info(tg_id)
        for record in clients:
            client = record.get("client", record)
            current_sub_id = client.get("subId")
            if current_sub_id and (sub_id is None or current_sub_id == sub_id):
                return f"{settings.XRAY_SUB_URL.rstrip('/')}/{current_sub_id}"
        return None

    def calculate_date(self, days: int, time_before: int = 0) -> int:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        return max(now_ms, time_before or 0) + int(
            timedelta(days=days).total_seconds() * 1000
        )

    @staticmethod
    def calculate_date_beauty(ms: int) -> str:
        return datetime.fromtimestamp(ms / 1000).strftime("%d.%m.%Y")

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


xray_service = XRayService()
