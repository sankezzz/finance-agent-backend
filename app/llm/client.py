"""LLM provider client abstraction.

Wraps whichever provider SDK is configured (Groq/Claude/Gemini) behind
a single interface so agents can be swapped between providers without
changing agent code.
"""
