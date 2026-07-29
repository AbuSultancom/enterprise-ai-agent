"""Advanced unit and integration tests for Enterprise AI Agent enhancements."""
from __future__ import annotations

import sys
import os
import pytest
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm_gateway.gateway import PIIMasker, Message
from agent_core.security import SecurityManager, UserContext, Role
from agent_core.audit import AuditLogger, AUDIT_FILE
from memory.vector_rag import HybridRAGSearch, DocumentChunk


class TestPIIMasker:
    """Test PII Masking of sensitive information."""

    def test_credit_card_masking(self):
        text = "My card number is 4532 1234 5678 9012 please charge it."
        masked = PIIMasker.mask_text(text)
        assert "4532" not in masked
        assert "[REDACTED_CREDIT_CARD]" in masked

    def test_saudi_id_masking(self):
        text = "ID number 1098765432 is verified."
        masked = PIIMasker.mask_text(text)
        assert "1098765432" not in masked
        assert "[REDACTED_NATIONAL_ID]" in masked

    def test_token_masking(self):
        text = "Authorization: Bearer secret_token_value_12345678"
        masked = PIIMasker.mask_text(text)
        assert "secret_token_value_12345678" not in masked
        assert "[REDACTED_TOKEN]" in masked


class TestSecurityManager:
    """Test Role-Based Access Control (RBAC)."""

    def test_unrestricted_tool_allowed_for_employee(self):
        user = UserContext(user_id="emp1", username="employee", role=Role.EMPLOYEE)
        allowed, _ = SecurityManager.is_tool_allowed("calculator", user)
        assert allowed is True

    def test_restricted_financial_tool_denied_for_employee(self):
        user = UserContext(user_id="emp1", username="employee", role=Role.EMPLOYEE)
        allowed, reason = SecurityManager.is_tool_allowed("get_sales_summary", user)
        assert allowed is False
        assert "Access denied" in reason

    def test_restricted_financial_tool_allowed_for_manager(self):
        user = UserContext(user_id="m1", username="manager", role=Role.MANAGER)
        allowed, _ = SecurityManager.is_tool_allowed("get_sales_summary", user)
        assert allowed is True

    def test_admin_allowed_all_tools(self):
        user = UserContext(user_id="admin1", username="admin", role=Role.ADMIN)
        allowed, _ = SecurityManager.is_tool_allowed("add_database", user)
        assert allowed is True


class TestHybridRAG:
    """Test Hybrid BM25 + Vector Search engine."""

    def test_hybrid_bm25_search(self):
        rag = HybridRAGSearch()
        chunk1 = DocumentChunk(doc_id="d1", filename="sales.txt", text="Annual sales revenue for 2025 reached 5 million SAR", chunk_index=0)
        chunk2 = DocumentChunk(doc_id="d2", filename="hr.txt", text="Company policy grants 30 days of annual leave", chunk_index=0)
        rag.add_chunks([chunk1, chunk2])

        results = rag.hybrid_search("sales revenue", top_k=1)
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"


class TestNewTools:
    """Test Communication and Voice tools."""

    @classmethod
    def setup_class(cls):
        import tools.communication  # noqa: F401
        import tools.voice  # noqa: F401

    def test_email_tool(self):
        from tools.registry import registry
        tool = registry.get("send_email_notification")
        assert tool is not None
        res = asyncio.run(tool.run(to_email="user@test.com", subject="Test", body="Hello"))
        assert "sent" in res.lower() or "simulated" in res.lower()

    def test_webhook_tool(self):
        from tools.registry import registry
        tool = registry.get("send_webhook_alert")
        assert tool is not None
        res = asyncio.run(tool.run(webhook_url="https://httpbin.org/post", message="Test Alert"))
        assert isinstance(res, str)
