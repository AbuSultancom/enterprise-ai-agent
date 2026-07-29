"""Generic REST API Connector for Enterprise Services (Odoo, SAP, QuickBooks, Custom Microservices)."""
from __future__ import annotations

import httpx
from typing import Any, Dict, Optional


class GenericRESTConnector:
    """Connector for querying external enterprise REST APIs securely."""

    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.get(url, params=params, headers=self.headers)
            res.raise_for_status()
            return res.json()

    async def post(self, endpoint: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(url, json=json_data, headers=self.headers)
            res.raise_for_status()
            return res.json()
