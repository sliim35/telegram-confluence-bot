"""
Tests for RAG pipeline: parse_json, ai_analyze_query, DMPQL docs retrieval.

Run: python test_rag.py
Requires: .env with LLM_BASE_URL, LLM_API_KEY
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

# main.py reads env at import time — fail fast if missing
for key in ("LLM_BASE_URL", "LLM_API_KEY"):
    if not os.getenv(key):
        print(f"ERROR: {key} not set in .env")
        sys.exit(1)

from main import parse_json, ai_analyze_query

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}{f' — {detail}' if detail else ''}")


# ═════════════════════════════════════════════════════════════════
# 1. parse_json — pure function, no LLM needed
# ═════════════════════════════════════════════════════════════════
print("\n── parse_json ──")

result = parse_json('{"intent": "DOCS", "query": "test"}', "test")
check("plain JSON", result is not None and result["intent"] == "DOCS")

result = parse_json('```json\n{"key": "value"}\n```', "test")
check("markdown-fenced JSON", result is not None and result["key"] == "value")

result = parse_json("not json at all", "test")
check("invalid JSON returns None", result is None)

result = parse_json('```\n{"a": 1}\n```', "test")
check("fenced without lang tag", result is not None and result["a"] == 1)


# ═════════════════════════════════════════════════════════════════
# 2. ai_analyze_query — single LLM call (route + rewrite + extract)
# ═════════════════════════════════════════════════════════════════
print("\n── ai_analyze_query: intent routing ──")

# DOCS intent
result = ai_analyze_query("Что такое DMPQL?", history=[])
check(
    "DOCS question → intent=DOCS",
    result["intent"] == "DOCS",
    f"got intent={result['intent']}",
)
check("DOCS → query is non-empty", len(result["query"]) > 0)

# GENERATE intent
result = ai_analyze_query("Составь запрос для мужчин старше 25 лет", history=[])
check(
    "GENERATE question → intent=GENERATE",
    result["intent"] == "GENERATE",
    f"got intent={result['intent']}",
)
check("GENERATE → syntax_query non-empty", len(result.get("syntax_query", "")) > 0)
check("GENERATE → taxonomy_query non-empty", len(result.get("taxonomy_query", "")) > 0)

# force_generate
result = ai_analyze_query("фильтр по городу Москва", history=[], force_generate=True)
check(
    "force_generate=True → intent=GENERATE",
    result["intent"] == "GENERATE",
    f"got intent={result['intent']}",
)

print("\n── ai_analyze_query: history rewrite ──")

history = [
    "User: Как фильтровать по городу?",
    "Bot: Используйте customer_profiles с attr для города.",
]
result = ai_analyze_query("А как это сделать для возраста?", history=history)
check(
    "pronoun resolution rewrites query",
    "возраст" in result["query"].lower() or "age" in result["query"].lower(),
    f"query='{result['query']}'",
)

# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════
print(f"\n{'═' * 50}")
total = passed + failed
print(f"Results: {passed}/{total} passed, {failed} failed")
sys.exit(1 if failed > 0 else 0)
