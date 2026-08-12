"""API endpoint integration tests using FastAPI's async test client."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Health endpoint ─────────────────────────────────────────────────────────


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, test_client):
        async with test_client as client:
            r = await client.get("/health")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_health_schema(self, test_client):
        async with test_client as client:
            r = await client.get("/health")
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "tools_count" in data
        assert "providers" in data
        assert isinstance(data["tools_count"], int)
        assert data["tools_count"] > 0


# ─── Tools endpoint ───────────────────────────────────────────────────────────


class TestToolsEndpoint:
    """Tests for GET /v1/tools."""

    @pytest.mark.asyncio
    async def test_tools_requires_auth(self, test_client):
        async with test_client as client:
            r = await client.get("/v1/tools")
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_tools_returns_list(self, test_client, user_headers):
        async with test_client as client:
            r = await client.get("/v1/tools", headers=user_headers)
        assert r.status_code == 200
        tools = r.json()
        assert isinstance(tools, list)
        assert len(tools) > 0
        # Each tool should have name, description, parameters
        for t in tools:
            assert "name" in t
            assert "description" in t


# ─── Auth / Rate Limiting ────────────────────────────────────────────────────


class TestAuthentication:
    """Test API key authentication."""

    @pytest.mark.asyncio
    async def test_invalid_key_returns_403(self, test_client):
        async with test_client as client:
            r = await client.get("/v1/tools", headers={"X-API-Key": "invalid-key"})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_access_admin_endpoints(self, test_client, admin_headers):
        async with test_client as client:
            r = await client.get("/v1/admin/audit", headers=admin_headers)
        # Should return 200 (empty list if no audit file)
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_user_cannot_access_admin_endpoints(self, test_client, user_headers):
        async with test_client as client:
            r = await client.get("/v1/admin/audit", headers=user_headers)
        assert r.status_code == 403


# ─── Security Headers ────────────────────────────────────────────────────────


class TestSecurityHeaders:
    """Verify security headers are present on responses."""

    @pytest.mark.asyncio
    async def test_security_headers_present(self, test_client):
        async with test_client as client:
            r = await client.get("/health")
        assert "X-Content-Type-Options" in r.headers
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" in r.headers
        assert r.headers["X-Frame-Options"] == "DENY"

    @pytest.mark.asyncio
    async def test_process_time_header(self, test_client):
        async with test_client as client:
            r = await client.get("/health")
        assert "X-Process-Time" in r.headers
        # Should be a number ending with 'ms'
        assert r.headers["X-Process-Time"].endswith("ms")


# ─── Knowledge Base endpoints ────────────────────────────────────────────────


class TestKnowledgeEndpoints:
    """Test /v1/knowledge endpoints."""

    @pytest.mark.asyncio
    async def test_list_knowledge_user(self, test_client, user_headers):
        async with test_client as client:
            r = await client.get("/v1/knowledge", headers=user_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @pytest.mark.asyncio
    async def test_add_doc_requires_admin(self, test_client, user_headers):
        async with test_client as client:
            r = await client.post(
                "/v1/knowledge",
                json={"title": "Test", "content": "Test content"},
                headers=user_headers,
            )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_add_doc_as_admin(self, test_client, admin_headers):
        async with test_client as client:
            r = await client.post(
                "/v1/knowledge",
                json={
                    "title": "Test Doc",
                    "content": "This is test content for the knowledge base.",
                },
                headers=admin_headers,
            )
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert data["title"] == "Test Doc"


# ─── Agent Settings ──────────────────────────────────────────────────────────


class TestAgentSettings:
    """Test /v1/settings/agent endpoints."""

    @pytest.mark.asyncio
    async def test_get_settings(self, test_client, user_headers):
        async with test_client as client:
            r = await client.get("/v1/settings/agent", headers=user_headers)
        assert r.status_code == 200
        data = r.json()
        assert "name" in data
        assert "personality" in data
        assert "language" in data

    @pytest.mark.asyncio
    async def test_update_settings_as_admin(self, test_client, admin_headers):
        async with test_client as client:
            r = await client.post(
                "/v1/settings/agent",
                json={"name": "Test Agent"},
                headers=admin_headers,
            )
        assert r.status_code == 200
        assert r.json()["settings"]["name"] == "Test Agent"


# ─── Conversation endpoints ──────────────────────────────────────────────────


class TestConversationEndpoints:
    """Test /v1/conversations endpoints."""

    @pytest.mark.asyncio
    async def test_list_conversations(self, test_client, user_headers):
        async with test_client as client:
            r = await client.get("/v1/conversations", headers=user_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(self, test_client, user_headers):
        async with test_client as client:
            r = await client.get("/v1/conversations/nonexistent-id-xyz", headers=user_headers)
        # Should return empty messages list (session not found = empty)
        assert r.status_code == 200
