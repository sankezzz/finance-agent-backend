"""Exercise the chat endpoint against a user's latest analysis.

Sends a few of the assignment's sample questions as a multi-turn conversation
(client-held history) and prints the grounded answers.

Usage:
  python tests/test_chat.py <user_id>
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

QUESTIONS = [
    "How much do I spend every month?",
    "What are my top expense categories?",
    "Am I overspending?",
    "What is my financial health score and why?",
    "How long will my emergency fund last?",
]


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python tests/test_chat.py <user_id>")
    user_id = sys.argv[1]

    history: list[dict] = []
    for q in QUESTIONS:
        history.append({"role": "user", "content": q})
        r = client.post("/chat", json={"user_id": user_id, "messages": history})
        if r.status_code != 200:
            sys.exit(f"chat failed {r.status_code}: {r.text}")
        answer = r.json()["content"]
        history.append({"role": "assistant", "content": answer})
        print("\n" + "=" * 72)
        print(f"Q: {q}")
        print("-" * 72)
        print(answer)

    print("\n" + "=" * 72)
    print(f"DONE — {len(QUESTIONS)} turns, history carried client-side ({len(history)} messages)")


if __name__ == "__main__":
    main()
