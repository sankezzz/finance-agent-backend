"""Prompt templates for the Categorization Agent's LLM fallback path.

Only merchants the rules table couldn't classify reach the LLM, batched into
a single call. The model must pick from the fixed TransactionCategory set.
"""

from app.models.transaction import TransactionCategory

CATEGORIZER_SYSTEM = (
    "You categorize financial-transaction merchants. For each merchant, choose "
    "exactly one category from the allowed list based on what it most likely "
    "sells or represents. If genuinely unclear, use Other. Return one "
    "assignment per merchant and nothing else."
)


def build_categorizer_prompt(merchants: list[str]) -> str:
    """Return a prompt asking the LLM to categorize a batch of merchants."""
    categories = ", ".join(c.value for c in TransactionCategory)
    listing = "\n".join(f"- {m}" for m in merchants)
    return (
        f"Allowed categories: {categories}.\n\n"
        "Assign each of these merchants/descriptions to exactly one category:\n"
        f"{listing}"
    )
