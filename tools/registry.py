"""Tool registry — plug new capabilities into the agent with one decorator."""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    func: Callable
    parameters: dict[str, Any]

    async def run(self, **kwargs) -> str:
        result = self.func(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return str(result)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, description: str, parameters: dict[str, Any] | None = None):
        def decorator(func: Callable):
            self._tools[func.__name__] = Tool(
                name=func.__name__,
                description=description,
                func=func,
                parameters=parameters or {},
            )
            return func
        return decorator

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def describe(self) -> str:
        """Text block injected into the agent's system prompt."""
        lines = []
        for t in self._tools.values():
            params = ", ".join(f"{k}: {v.get('type', 'str')}" for k, v in t.parameters.items())
            lines.append(f"- {t.name}({params}): {t.description}")
        return "\n".join(lines)


registry = ToolRegistry()
