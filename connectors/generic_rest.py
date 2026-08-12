"""Generic REST API Connector for Enterprise Services (Odoo, SAP, QuickBooks, Custom Microservices)."""

from __future__ import annotations

from typing import Any

import httpx


class GenericRESTConnector:
    """Connector for querying external enterprise REST APIs securely."""

    def __init__(self, base_url: str, headers: dict[str, str] | None = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.get(url, params=params, headers=self.headers)
            res.raise_for_status()
            return res.json()

    async def post(self, endpoint: str, json_data: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(url, json=json_data, headers=self.headers)
            res.raise_for_status()
            return res.json()
