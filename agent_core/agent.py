"""ReAct agent loop: reason -> act (tool call) -> observe -> repeat, until final answer."""
from __future__ import annotations

import json
import re

from llm_gateway.gateway import LLMGateway, Message
from tools.registry import ToolRegistry

try:
    import config_loader
except ImportError:
    config_loader = None

SYSTEM_PROMPT = """You are {name}, {personality}. Today's date is {date}.

═══ REASONING RULES — follow them strictly ═══

1. **Think step-by-step** before answering anything complex. Break multi-part questions.
2. **NEVER guess** numbers, dates, prices, or company facts. If the question needs real-time or company data (sales, invoices, revenue, news, weather, currency), ALWAYS call a tool.
3. **Error recovery** — If a tool returns an error or empty data: analyze WHY, adjust arguments (different date range, different parameter), and try ONCE more. Only say "no data" after a genuine retry.
4. **Interpret results** — Do not dump raw tool output. Give the headline number first, then a short breakdown in bullets, then one insight.
5. **Be concise** — Short paragraphs, bullet points, **bold** key figures. No fluff.
6. **Multi-part answers** — If the user asks multiple things, answer each in sequence.

═══ TOOL CALL FORMAT ═══
To call a tool, reply with EXACTLY this JSON on its own line:
TOOL_CALL: {{"name": "tool_name", "arguments": {{"arg": "value"}}}}

When you have the final answer, reply normally (no TOOL_CALL).

═══ FEW-SHOT EXAMPLES ═══

Arabic examples:
User: "طقس الرياض اليوم"
Assistant: TOOL_CALL: {{"name": "get_weather", "arguments": {{"city": "Riyadh"}}}}

User: "كم 500 دولار بالريال؟"
Assistant: TOOL_CALL: {{"name": "get_currency_rate", "arguments": {{"from_currency": "USD", "to_currency": "SAR"}}}}

English examples:
User: "What's the weather in Dubai?"
Assistant: TOOL_CALL: {{"name": "get_weather", "arguments": {{"city": "Dubai"}}}}

User: "How much is 100 USD in EUR?"
Assistant: TOOL_CALL: {{"name": "get_currency_rate", "arguments": {{"from_currency": "USD", "to_currency": "EUR"}}}}

User: "Search for latest AI news"
Assistant: TOOL_CALL: {{"name": "web_search", "arguments": {{"query": "latest AI news 2026"}}}}

User: "What time is it?"
Assistant: TOOL_CALL: {{"name": "get_current_time", "arguments": {{}}}}

User: "Generate a report about our sales"
Assistant: TOOL_CALL: {{"name": "generate_report", "arguments": {{"title": "Sales Summary", "content": "Company sales report for July 2026"}}}}

═══ AVAILABLE TOOLS ═══
{tools}
"""

ERROR_HINT = (
    "The tool call above failed or returned an error. Analyze the error, fix your arguments "
    "(e.g. different date format/range, valid parameter values) and try a different call. "
    "If the same tool fails twice, answer the user with what you know and say the data source had an issue."
)


def _build_system_prompt(tools_desc: str) -> str:
    import datetime
    identity = config_loader.agent_identity() if config_loader else {}

    # Get learning context
    learning_context = ""
    try:
        from memory.learning import learner
        learning_context = "\n" + learner.get_learning_context()
        personality_hint = learner.get_personality_hint()
        if personality_hint:
            learning_context += f"\n\n=== LEARNED PREFERENCES ===\n{personality_hint}"
    except Exception:
        pass

    prompt = SYSTEM_PROMPT.format(
        name=identity.get("name", "an enterprise AI agent"),
        personality=identity.get("personality", "a professional, concise enterprise assistant"),
        date=datetime.date.today().isoformat(),
        tools=tools_desc,
    )
    if learning_context:
        prompt += f"\n\n=== USER PROFILE (learned from past conversations) ===\n{learning_context}"

    lang = identity.get("language", "auto")
    if lang == "ar":
        prompt += "\nAlways answer in Arabic, regardless of the question's language."
    elif lang == "en":
        prompt += "\nAlways answer in English, regardless of the question's language."
    else:
        prompt += "\nAnswer in the same language as the user's message."
    return prompt


def _parse_tool_json(text: str) -> dict:
    """Parse LLM-generated JSON for tool calls, handling common formatting issues."""
    import re as _re
    # Remove trailing commas before closing braces/brackets
    cleaned = _re.sub(r',\s*([}\]])', r'\1', text)
    return json.loads(cleaned)


class Agent:
    def __init__(self, gateway: LLMGateway, registry: ToolRegistry, max_steps: int = 8):
        self.gateway = gateway
        self.registry = registry
        self.max_steps = max_steps

    async def run(self, user_input: str, model: str | None = None,
                  history: list[Message] | None = None) -> dict:
        messages = [Message(role="system", content=_build_system_prompt(self.registry.describe()))]
        messages.extend(history or [])
        messages.append(Message(role="user", content=user_input))

        steps: list[dict] = []
        for _ in range(self.max_steps):
            resp = await self.gateway.chat(messages, model=model)
            content = resp.content.strip()

            match = re.search(r'TOOL_CALL:\s*(\{.*\})', content, re.DOTALL)
            if not match:
                return {"answer": content, "steps": steps, "model": resp.model, "provider": resp.provider}

            try:
                call = _parse_tool_json(match.group(1))
                tool_name, args = call["name"], call.get("arguments", {})
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                # Try to recover: wrap single-quoted keys
                try:
                    fixed = match.group(1).replace("'", '"')
                    call = _parse_tool_json(fixed)
                    tool_name, args = call["name"], call.get("arguments", {})
                except Exception:
                    return {"answer": f"Agent produced an invalid tool call: {e}", "steps": steps}

            tool = self.registry.get(tool_name)
            if tool is None:
                observation = f"Error: unknown tool '{tool_name}'"
            else:
                try:
                    observation = await tool.run(**args)
                except Exception as e:
                    observation = f"Error running {tool_name}: {e}"

            steps.append({"tool": tool_name, "arguments": args, "observation": observation[:2000]})
            messages.append(Message(role="assistant", content=content))
            hint = "\n" + ERROR_HINT if observation.startswith("Error") else ""
            messages.append(Message(role="user", content=f"TOOL_RESULT: {observation}{hint}"))

        return {"answer": "Reached maximum reasoning steps without a final answer.", "steps": steps}

    # ---- Streaming version: yields events for SSE ----
    # {"type": "step", ...} for tool calls, {"type": "token", "text": ...} for the answer,
    # {"type": "done"} at the end. A hold-back buffer prevents tool-call markup from leaking.
    async def run_stream(self, user_input: str, model: str | None = None,
                         history: list[Message] | None = None):
        HOLD_BACK = 400  # chars kept buffered so TOOL_CALL markup is never streamed
        messages = [Message(role="system", content=_build_system_prompt(self.registry.describe()))]
        messages.extend(history or [])
        messages.append(Message(role="user", content=user_input))

        for _ in range(self.max_steps):
            buffer = ""
            async for delta in self.gateway.chat_stream(messages, model=model):
                buffer += delta
                if len(buffer) > HOLD_BACK:
                    chunk, buffer = buffer[:-HOLD_BACK], buffer[-HOLD_BACK:]
                    if "TOOL_CALL" not in chunk:
                        yield {"type": "token", "text": chunk}

            match = re.search(r'TOOL_CALL:\s*(\{.*\})', buffer, re.DOTALL)
            if not match:
                if buffer:
                    yield {"type": "token", "text": buffer}
                yield {"type": "done"}
                return

            try:
                call = _parse_tool_json(match.group(1))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                try:
                    fixed = match.group(1).replace("'", '"')
                    call = _parse_tool_json(fixed)
                except Exception:
                    yield {"type": "token", "text": f"\n(invalid tool call: {e})"}
                    yield {"type": "done"}
                    return
            try:
                tool_name, args = call["name"], call.get("arguments", {})
            except KeyError as e:
                yield {"type": "token", "text": f"\n(missing tool name in call)"}
                yield {"type": "done"}
                return

            tool = self.registry.get(tool_name)
            if tool is None:
                observation = f"Error: unknown tool '{tool_name}'"
            else:
                try:
                    observation = await tool.run(**args)
                except Exception as e:
                    observation = f"Error running {tool_name}: {e}"

            yield {"type": "step", "tool": tool_name, "arguments": args}
            messages.append(Message(role="assistant", content=buffer))
            hint = "\n" + ERROR_HINT if observation.startswith("Error") else ""
            messages.append(Message(role="user", content=f"TOOL_RESULT: {observation}{hint}"))

        yield {"type": "token", "text": "\nReached maximum reasoning steps."}
        yield {"type": "done"}
