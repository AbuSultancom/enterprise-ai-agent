"""Long-term memory tools — the agent can deliberately remember, recall and
forget facts about the user and the company across conversations.

Backed by memory.learning.AgentLearner (data/learning.json), which is also
injected into the agent's system prompt on every run — so anything stored
here is automatically visible in future conversations.
"""

from __future__ import annotations

from .registry import registry


def _learner():
    from memory.learning import learner

    return learner


@registry.register(
    description="Remember an important fact long-term (user preference or company info, e.g. "
    "'default currency is SAR', 'main branch is Riyadh', 'fiscal year starts in January'). "
    "Use when the user asks you to remember something or states a durable preference.",
    parameters={
        "key": {"type": "str", "description": "Short fact name, e.g. 'default_currency'"},
        "value": {"type": "str", "description": "The fact to remember"},
    },
)
def remember_fact(key: str, value: str) -> str:
    try:
        _learner().learn_fact(key.strip(), value.strip())
        return f"✅ Remembered: {key} = {value}"
    except Exception as e:
        return f"❌ Could not save fact: {e}"


@registry.register(
    description="Recall all long-term remembered facts about the user and the company.",
    parameters={},
)
def recall_facts() -> str:
    try:
        facts = _learner().data.get("learned_facts", {})
        if not facts:
            return "No facts remembered yet."
        return "Remembered facts:\n" + "\n".join(f"  • {k}: {v}" for k, v in facts.items())
    except Exception as e:
        return f"❌ Could not load facts: {e}"


@registry.register(
    description="Forget (delete) a previously remembered fact by its key.",
    parameters={"key": {"type": "str", "description": "The fact key to delete"}},
)
def forget_fact(key: str) -> str:
    try:
        lr = _learner()
        if key in lr.data.get("learned_facts", {}):
            del lr.data["learned_facts"][key]
            lr.save()
            return f"✅ Forgot: {key}"
        return f"⚠️ No fact named '{key}'."
    except Exception as e:
        return f"❌ {e}"
