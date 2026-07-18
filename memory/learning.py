"""
Agent Learning Module — Self-Improving Agent
============================================
Learns communication style, user preferences, and successful patterns
from past conversations. Gets smarter with every interaction.
"""
from __future__ import annotations

import json
import os
import re as _re
from collections import Counter
from pathlib import Path


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEARNING_FILE = os.path.join(ROOT, "data", "learning.json")


class AgentLearner:
    """Learns from conversations: style, preferences, successful patterns."""

    def __init__(self):
        os.makedirs(os.path.dirname(LEARNING_FILE), exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(LEARNING_FILE):
            try:
                with open(LEARNING_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return self._defaults()

    def _defaults(self) -> dict:
        return {
            "user_profile": {
                "preferred_language": "ar",
                "formality": "professional",
                "response_length": "medium",  # short / medium / long
                "use_emojis": True,
                "top_topics": [],
                "common_questions": [],
            },
            "learned_facts": {},  # key-value facts about the company/user
            "tool_patterns": {},  # (query_type → best_tool) mapping
            "failed_patterns": [],  # patterns that never worked
            "conversation_count": 0,
            "total_messages": 0,
            "version": 1,
        }

    def save(self):
        with open(LEARNING_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def learn_from_exchange(self, user_message: str, assistant_response: str,
                            tools_used: list[str] = None, session_lang: str = "ar"):
        """Learn from a conversation exchange."""
        tools_used = tools_used or []
        self.data["conversation_count"] += 1
        self.data["total_messages"] += 2

        # 1. Detect language preference
        lang = session_lang if session_lang in ("ar", "en") else \
            "ar" if _re.search(r"[\u0600-\u06FF]", user_message) else "en"
        self.data["user_profile"]["preferred_language"] = lang

        # 2. Learn response length preference
        resp_len = len(assistant_response)
        if resp_len < 200:
            self.data["user_profile"]["response_length"] = "short"
        elif resp_len < 800:
            self.data["user_profile"]["response_length"] = "medium"
        else:
            self.data["user_profile"]["response_length"] = "long"

        # 3. Track topics
        topics = self._extract_topics(user_message)
        topic_counts = Counter(d["topic"] for d in self.data["user_profile"]["top_topics"])
        for topic in topics:
            topic_counts[topic] += 1
        self.data["user_profile"]["top_topics"] = [
            {"topic": t, "count": c} for t, c in topic_counts.most_common(10)
        ]

        # 4. Learn tool patterns
        if tools_used:
            query_type = self._classify_query(user_message)
            if query_type not in self.data["tool_patterns"]:
                self.data["tool_patterns"][query_type] = []
            for tool in tools_used:
                if tool not in self.data["tool_patterns"][query_type]:
                    self.data["tool_patterns"][query_type].append(tool)

        # 5. Track common questions
        clean = user_message.strip().lower()
        if clean and len(clean) > 5:
            questions = self.data["user_profile"]["common_questions"]
            q_texts = [q["text"] for q in questions]
            if clean not in q_texts:
                questions.append({"text": clean, "count": 1})
            else:
                idx = q_texts.index(clean)
                questions[idx]["count"] += 1
            # Keep top 20
            self.data["user_profile"]["common_questions"] = sorted(
                questions, key=lambda x: x["count"], reverse=True)[:20]

        # 6. Detect emoji usage
        if _re.search(r"[\U0001F300-\U0001F9FF]", user_message + assistant_response):
            self.data["user_profile"]["use_emojis"] = True

        self.save()

    def learn_fact(self, key: str, value: str):
        """Store a learned fact about the user/company."""
        self.data["learned_facts"][key] = value
        self.save()

    def learn_failure(self, query: str, tool: str, error: str):
        """Record a failed pattern to avoid."""
        pattern = f"{self._classify_query(query)}:{tool}:{error[:50]}"
        if pattern not in self.data["failed_patterns"]:
            self.data["failed_patterns"].append(pattern)
            if len(self.data["failed_patterns"]) > 50:
                self.data["failed_patterns"] = self.data["failed_patterns"][-50:]
        self.save()

    def was_failed(self, query: str, tool: str) -> bool:
        """Check if this pattern previously failed."""
        query_type = self._classify_query(query)
        for fp in self.data["failed_patterns"]:
            if fp.startswith(f"{query_type}:{tool}"):
                return True
        return False

    def get_learning_context(self) -> str:
        """Get a context string to inject into the system prompt."""
        d = self.data
        p = d["user_profile"]
        lines = []

        lines.append(f"User language preference: {p['preferred_language']}")
        lines.append(f"User communication style: {p['formality']}, prefer {p['response_length']} answers")

        if p["top_topics"]:
            top = ", ".join(t["topic"] for t in p["top_topics"][:5])
            lines.append(f"User's most discussed topics: {top}")

        if d["learned_facts"]:
            lines.append("Known facts about the company:")
            for key, value in list(d["learned_facts"].items())[:10]:
                lines.append(f"  • {key}: {value}")

        if d["tool_patterns"]:
            lines.append("Proven tool patterns:")
            for qtype, tools in list(d["tool_patterns"].items())[:5]:
                lines.append(f"  • {qtype}: use {', '.join(tools[:3])}")

        return "\n".join(lines)

    def get_personality_hint(self) -> str:
        """Get a personality/behavior hint for the system prompt."""
        p = self.data["user_profile"]
        lang = p.get("preferred_language", "ar")
        style = p.get("response_length", "medium")
        emoji = p.get("use_emojis", True)

        hints = []
        if lang == "ar":
            hints.append("Always answer in Arabic unless asked otherwise")
        if style == "short":
            hints.append("Keep answers concise and to the point — the user prefers brief replies")
        elif style == "long":
            hints.append("The user appreciates detailed, thorough answers")
        if emoji:
            hints.append("Use appropriate emojis to make responses more engaging")
        return "; ".join(hints) if hints else ""

    def _extract_topics(self, text: str) -> list[str]:
        """Extract topics/keywords from user message."""
        keywords = {
            "accounting": ["مبيعات", "فاتورة", "محاسبة", "أرباح", "رصيد", "sales", "invoice", "revenue"],
            "weather": ["طقس", "الطقس", "جو", "weather", "temperature"],
            "currency": ["دولار", "ريال", "سعر", "عملة", "currency", "usd", "sar", "exchange"],
            "stocks": ["سهم", "سوق", "تداول", "stock", "tadawul"],
            "zakat": ["زكاة", "زكاه", "zakat"],
            "tax": ["ضريبة", "vat", "ضريبه"],
            "reports": ["تقرير", "تقارير", "report"],
            "time": ["تاريخ", "وقت", "كم الساعة", "time", "date"],
            "hr": ["موظف", "راتب", "نهاية الخدمة", "salary", "employee"],
            "tech": ["كود", "برمجة", "code", "programming", "python"],
        }
        found = []
        text_lower = text.lower()
        for topic, kws in keywords.items():
            if any(kw in text_lower for kw in kws):
                found.append(topic)
        return found or ["general"]

    def _classify_query(self, query: str) -> str:
        """Classify the type of query for pattern learning."""
        query_lower = query.lower()
        if any(w in query_lower for w in ["طقس", "weather", "جو"]):
            return "weather"
        if any(w in query_lower for w in ["دولار", "ريال", "سعر", "عملة", "currency", "usd", "sar"]):
            return "currency"
        if any(w in query_lower for w in ["مبيع", "فاتورة", "sales", "invoice", "أرباح"]):
            return "accounting"
        if any(w in query_lower for w in ["تقرير", "سوي", "اكتب", "report", "generate"]):
            return "report"
        if any(w in query_lower for w in ["سهم", "stock", "تداول"]):
            return "stocks"
        if any(w in query_lower for w in ["زكاة", "zakat"]):
            return "zakat"
        if any(w in query_lower for w in ["ضريبة", "vat"]):
            return "tax"
        if any(w in query_lower for w in ["موظف", "salary", "نهاية الخدمة"]):
            return "hr"
        if any(w in query_lower for w in ["بحث", "search", "ابحث", "أخبار"]):
            return "search"
        return "general"


# Global instance
learner = AgentLearner()
