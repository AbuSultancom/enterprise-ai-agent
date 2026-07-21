"""Basic unit tests for Enterprise AI Agent — tools, registry, calculations."""
from __future__ import annotations

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestToolImports:
    """Test that core modules import without errors."""

    def test_import_registry(self):
        """Registry should import cleanly and have a singleton."""
        from tools.registry import registry
        assert registry is not None
        assert hasattr(registry, "_tools")
        assert hasattr(registry, "list")
        assert hasattr(registry, "get")

    def test_import_builtin_tools_registers(self):
        """Importing tools.builtin should populate the registry."""
        from tools.registry import registry
        import tools.builtin  # noqa: F401 — triggers @registry.register decorators
        assert len(registry.list()) > 0

    def test_import_accounting_tools(self):
        """Importing tools.accounting should add accounting tools."""
        from tools.registry import registry
        import tools.builtin  # noqa: F401
        import tools.accounting  # noqa: F401
        # Builtin + accounting should be 33 total
        tool_count = len(registry.list())
        assert tool_count >= 33, f"Expected at least 33 tools, got {tool_count}"


class TestRegistry:
    """Test ToolRegistry operations after tools are registered."""

    @classmethod
    def setup_class(cls):
        """Import all tool modules once for all registry tests."""
        import tools.builtin  # noqa: F401
        import tools.accounting  # noqa: F401

    def test_33_tools_registered(self):
        """Verify at least 33 tools are registered (builtin + accounting)."""
        from tools.registry import registry
        tool_names = [t.name for t in registry.list()]
        assert len(tool_names) >= 33, (
            f"Expected at least 33 tools, got {len(tool_names)}: {sorted(tool_names)}"
        )

    def test_get_existing_tool(self):
        """registry.get() should return a Tool for a known name."""
        from tools.registry import registry
        tool = registry.get("calculator")
        assert tool is not None
        assert tool.name == "calculator"

    def test_get_nonexistent_tool(self):
        """registry.get() should return None for an unknown name."""
        from tools.registry import registry
        assert registry.get("nonexistent_tool_xyz") is None

    def test_list_returns_tools(self):
        """registry.list() returns Tool objects with required attributes."""
        from tools.registry import registry
        tools = registry.list()
        assert len(tools) > 0
        for t in tools:
            assert hasattr(t, "name")
            assert hasattr(t, "description")
            assert hasattr(t, "func")
            assert hasattr(t, "parameters")

    def test_describe_returns_string(self):
        """registry.describe() returns a non-empty string."""
        from tools.registry import registry
        desc = registry.describe()
        assert isinstance(desc, str)
        assert len(desc) > 0


class TestCalculatorTool:
    """Test the calculator tool."""

    @classmethod
    def setup_class(cls):
        import tools.builtin  # noqa: F401

    def test_calculator_basic_addition(self):
        """Calculator: 2 + 3 = 5."""
        from tools.registry import registry
        import asyncio
        tool = registry.get("calculator")
        result = asyncio.run(tool.run(expression="2 + 3"))
        assert "5" in result

    def test_calculator_multiplication(self):
        """Calculator: 7 * 8 = 56."""
        from tools.registry import registry
        import asyncio
        tool = registry.get("calculator")
        result = asyncio.run(tool.run(expression="7 * 8"))
        assert "56" in result

    def test_calculator_division(self):
        """Calculator: 100 / 4 = 25."""
        from tools.registry import registry
        import asyncio
        tool = registry.get("calculator")
        result = asyncio.run(tool.run(expression="100 / 4"))
        assert "25" in result

    def test_calculator_complex_expression(self):
        """Calculator: (10 + 5) * 2 - 3 = 27."""
        from tools.registry import registry
        import asyncio
        tool = registry.get("calculator")
        result = asyncio.run(tool.run(expression="(10 + 5) * 2 - 3"))
        assert "27" in result


class TestVatCalc:
    """Test Saudi VAT calculator (15%)."""

    @classmethod
    def setup_class(cls):
        import tools.builtin  # noqa: F401

    def test_vat_add_exclusive(self):
        """VAT added: 1000 + 15% = 1150."""
        from tools.registry import registry
        import asyncio
        tool = registry.get("vat_calc")
        result = asyncio.run(tool.run(amount=1000, inclusive=False))
        assert "150" in result     # VAT amount
        assert "1,150" in result   # total

    def test_vat_extract_inclusive(self):
        """VAT extracted: 1150 inclusive → VAT = 150, original = 1000."""
        from tools.registry import registry
        import asyncio
        tool = registry.get("vat_calc")
        result = asyncio.run(tool.run(amount=1150, inclusive=True))
        assert "150" in result     # VAT amount
        assert "1,000" in result   # original amount

    def test_vat_zero_amount(self):
        """VAT on zero = zero."""
        from tools.registry import registry
        import asyncio
        tool = registry.get("vat_calc")
        result = asyncio.run(tool.run(amount=0, inclusive=False))
        assert "0.00" in result


class TestZakatCalc:
    """Test Zakat calculator (2.5%)."""

    @classmethod
    def setup_class(cls):
        import tools.builtin  # noqa: F401

    def test_zakat_basic(self):
        """Zakat on 100,000 cash only = 2,500."""
        from tools.registry import registry
        import asyncio
        tool = registry.get("zakat_calc")
        result = asyncio.run(tool.run(cash=100000))
        assert "2,500" in result

    def test_zakat_with_debts(self):
        """Zakat on 100,000 cash minus 20,000 debts → net 80,000 → zakat 2,000."""
        from tools.registry import registry
        import asyncio
        tool = registry.get("zakat_calc")
        result = asyncio.run(tool.run(cash=100000, debts=20000))
        assert "2,000" in result

    def test_zakat_all_zero(self):
        """Zakat with all zeros → 0."""
        from tools.registry import registry
        import asyncio
        tool = registry.get("zakat_calc")
        result = asyncio.run(tool.run())
        assert "0.00" in result
