"""ReAct agent loop: reason -> act (tool call) -> observe -> repeat, until final answer."""
from __future__ import annotations

import json
import re

from llm_gateway.gateway import LLMGateway, Message
from tools.registry import ToolRegistry

SYSTEM_PROMPT = """You are an enterprise AI agent. Answer the user's request accurately.

You can use tools. To call a tool, reply with EXACTLY this format and nothing else:
TOOL_CALL: {{"name": "<tool_name>", "arguments": {{"arg": "value"}}}}

When you have the final answer, reply normally (no TOOL_CALL).

Available tools:
{tools}
"""


class Agent:
    def __init__(self, gateway: LLMGateway, registry: ToolRegistry, max_steps: int = 6):
        self.gateway = gateway
        self.registry = registry
        self.max_steps = max_steps

    async def run(self, user_input: str, model: str | None = None,
                  history: list[Message] | None = None) -> dict:
        messages = [Message(role="system", content=SYSTEM_PROMPT.format(tools=self.registry.describe()))]
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
            messages.append(Message(role="user", content=f"TOOL_RESULT: {observation}"))

        return {"answer": "Reached maximum reasoning steps without a final answer.", "steps": steps}
