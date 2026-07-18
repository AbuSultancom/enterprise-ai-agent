"""Multi-Agent Orchestrator — routes requests to specialized sub-agents.

The OrchestratorAgent analyzes each user request, selects the most appropriate
specialized sub-agent (WebSearch, Accounting, Report, or General), and delegates
execution. Each sub-agent has only the tools relevant to its domain.

Usage:
    agent = OrchestratorAgent(gateway)
    result = await agent.run("What's the weather in London?")
    # => routed to WebSearchAgent
"""

from __future__ import annotations

from agent_core.agent import Agent
from llm_gateway.gateway import LLMGateway
from tools.registry import ToolRegistry, registry as main_registry

# ── Tool subsets for each specialized sub-agent ─────────────────────

WEBSEARCH_TOOLS: set[str] = {
    "web_search",
    "get_weather",
    "get_currency_rate",
    "calculator",
}

ACCOUNTING_TOOLS: set[str] = {
    "list_databases",
    "add_database",
    "diagnose_connection",
    "discover_schema_tool",
    "show_schema_config",
    "get_sales_summary",
    "get_revenue_by_month",
    "get_top_customers",
    "get_expenses_summary",
    "get_invoice",
    "get_cash_balance",
    "get_vendor_balances",
    "get_sales_by_item",
    "calculator",
}

REPORT_TOOLS: set[str] = {
    "generate_report",
    "list_reports",
    "search_conversations",
    "get_current_time",
    "calculator",
}


def _build_sub_registry(tool_names: set[str]) -> ToolRegistry:
    """Create a ToolRegistry containing only the named tools from the main registry."""
    sub = ToolRegistry()
    for name in tool_names:
        tool = main_registry.get(name)
        if tool is not None:
            sub._tools[name] = tool
    return sub


# Lazy sub-registry singletons — built on first access so that the main
# registry has already been populated by tools/builtin.py and tools/accounting.py.
_SUB_REGISTRIES: dict[str, ToolRegistry] = {}


def _get_sub_registry(key: str, tool_names: set[str]) -> ToolRegistry:
    """Return a cached sub-registry, building it from the (now-populated) main registry."""
    if key not in _SUB_REGISTRIES:
        _SUB_REGISTRIES[key] = _build_sub_registry(tool_names)
    return _SUB_REGISTRIES[key]

# ── Keyword-based routing rules ─────────────────────────────────────
# Order matters: first match wins. More specific / longer phrases first.
_ROUTING_RULES: list[tuple[list[str], str]] = [
    # Report — generating, listing, or saving reports (check first)
    (["generate report", "save report", "list report", "report generation",
      "create report", "write report", "make report",
      "report", "تقرير", "تقارير", "سوي", "انشئ", "اعمل"], "report"),
    # WebSearch — anything about searching the web, weather, currency
    (["web search", "look up online", "find online", "search online",
      "exchange rate", "currency rate",
      "weather", "web", "search", "news", "google", "internet",
      "find", "بحث", "ابحث", "طقس", "الطقس", "درجة الحرارة",
      "سعر", "صرف", "دولار", "ريال", "عملة", "يورو"], "websearch"),
    # Accounting — financial & ERP queries
    (["invoice", "sales", "revenue", "expense", "accounting", "financial",
      "profit", "customer", "vendor", "balance", "cash", "database",
      "accounting database", "sales summary", "top customer",
      "sell", "sold", "expenses summary", "paid", "payment",
      "مبيعات", "فاتورة", "محاسبة", "حساب", "رصيد", "إيراد", "مصروف",
      "عميل", "مورد", "أرباح", "إجمالي", "ضريبة", "كشف"], "accounting"),
]


def route_request(user_input: str) -> str:
    """Determine the best sub-agent for the given input using keyword matching.

    Returns one of: "websearch", "accounting", "report", "general".
    """
    lower = user_input.lower()
    for keywords, agent_name in _ROUTING_RULES:
        for kw in keywords:
            if kw in lower:
                return agent_name
    return "general"


# ── Orchestrator ────────────────────────────────────────────────────

class OrchestratorAgent:
    """Routes user requests to specialized sub-agents and composes the final answer.

    Delegates to one of four sub-agents:
      - WebSearchAgent  (web search, weather, currency, calculator)
      - AccountingAgent (accounting/ERP queries + calculator)
      - ReportAgent     (report generation, listing, conversations, time, calc)
      - GeneralAgent    (all tools — fallback when routing is uncertain)
    """

    def __init__(self, gateway: LLMGateway, max_steps: int = 8):
        self.gateway = gateway
        self.max_steps = max_steps

        # Build sub-agents with their restricted tool registries (lazy-built on demand)
        self._sub_agents: dict[str, Agent] = {
            "websearch": Agent(gateway, _get_sub_registry("web", WEBSEARCH_TOOLS), max_steps),
            "accounting": Agent(gateway, _get_sub_registry("acct", ACCOUNTING_TOOLS), max_steps),
            "report": Agent(gateway, _get_sub_registry("rpt", REPORT_TOOLS), max_steps),
            "general": Agent(gateway, main_registry, max_steps),
        }

    async def run(self, user_input: str, model: str | None = None,
                  history: list | None = None) -> dict:
        """Route the request to the best sub-agent and return its response."""
        target = route_request(user_input)
        agent = self._sub_agents.get(target, self._sub_agents["general"])

        try:
            result = await agent.run(user_input, model=model, history=history)
        except Exception as e:
            return {
                "answer": f"Orchestrator error ({target} agent): {e}",
                "steps": [{"tool": "_orchestrator_delegate",
                           "arguments": {"target": target},
                           "observation": f"Sub-agent '{target}' raised: {e}"}],
                "routed_to": target,
                "model": None,
                "provider": None,
            }

        result["routed_to"] = target
        return result

    async def run_stream(self, user_input: str, model: str | None = None,
                         history: list | None = None):
        """Streaming version — yields a 'routed' event first, then sub-agent events."""
        target = route_request(user_input)
        agent = self._sub_agents.get(target, self._sub_agents["general"])

        # Emit routing info as the first event so the client knows which sub-agent handled it
        yield {"type": "routed", "to": target}

        async for event in agent.run_stream(user_input, model=model, history=history):
            yield event
