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

REASONING RULES — follow them strictly:
1. Think step by step before answering anything complex.
2. NEVER guess numbers, dates, prices, or facts about the company. If the question needs
   real-time or company data (sales, invoices, revenue, news, weather), ALWAYS call a tool.
3. If a tool returns an error, empty data, or something unexpected: analyze WHY, adjust your
   arguments (different date range, different parameter, different tool) and try ONCE more.
   Only tell the user "no data found" after a genuine retry.
4. When tool data arrives, do not dump it raw — interpret it: give the headline number first,
   then a short breakdown in bullet points, then one insight or comparison if relevant.
5. If the question is ambiguous, answer the most likely interpretation AND mention what else
   you could look up.
6. Keep answers concise and well-formatted: short paragraphs, bullets, **bold** key figures.

TOOL USE — to call a tool, reply with EXACTLY this format and nothing else:
TOOL_CALL: {{"name": "<tool_name>", "arguments": {{"arg": "value"}}}}

When you have the final answer, reply normally (no TOOL_CALL).

Available tools:
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
    prompt = SYSTEM_PROMPT.format(
        name=identity.get("name", "an enterprise AI agent"),
        personality=identity.get("personality", "a professional, concise enterprise assistant"),
        date=datetime.date.today().isoformat(),
        tools=tools_desc,
    )
    lang = identity.get("language", "auto")
    if lang == "ar":
        prompt += "\nAlways answer in Arabic, regardless of the question's language."
    elif lang == "en":
        prompt += "\nAlways answer in English, regardless of the question's language."
    else:
        prompt += "\nAnswer in the same language as the user's message."
    return prompt


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
                call = json.loads(match.group(1))
                tool_name, args = call["name"], call.get("arguments", {})
            except (json.JSONDecodeError, KeyError) as e:
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
                call = json.loads(match.group(1))
                tool_name, args = call["name"], call.get("arguments", {})
            except (json.JSONDecodeError, KeyError) as e:
                yield {"type": "token", "text": f"\n(invalid tool call: {e})"}
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
