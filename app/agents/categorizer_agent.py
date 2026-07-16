"""Categorization Agent (hybrid: rules first, LLM fallback).

Reads this run's transactions and fills the three fields the parser left
blank — category, is_recurring, is_subscription:

  * category: a keyword RULES table classifies known merchants for free;
    only unknown *debit* merchants (deduped) go to the LLM in ONE batched
    call. Credits default to Income (salary) / Transfer.
  * is_recurring / is_subscription: deterministic heuristics (group by
    merchant, monthly cadence, subscription keyword list). No LLM.

Facts are untouched — they already carry kind/subtype from the parser.
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.agents.base import AgentContext, BaseAgent
from app.config import get_settings
from app.llm.client import get_structured_llm
from app.llm.prompts.categorizer import CATEGORIZER_SYSTEM, build_categorizer_prompt
from app.models.categorizer import CategoryBatch
from app.models.transaction import Transaction, TransactionCategory, TransactionDirection
from app.pipeline.stages import Stage
from app.services import transaction_service
from app.services.transaction_service import CategoryUpdate

# Keyword -> category rules. Matched on WORD BOUNDARIES (so "ajio" no longer
# collides with "jio"). First match wins, so order matters: specific/savings
# meanings are checked before generic ones.
_RULES: list[tuple[TransactionCategory, tuple[str, ...]]] = [
    # Investments first — SIP/MF outflows are savings, must not fall through to
    # Income/Shopping/Other.
    (TransactionCategory.investment, (
        "sip", "starmf", "groww", "zerodha", "upstox", "mutual fund", "elss",
        "nps", "ppf", "indmoney", "kuvera", "smallcase", "nifty",
    )),
    (TransactionCategory.emi_loan, (
        "emi", "loan", "bajaj finance", "tata capital", "nbfc",
    )),
    (TransactionCategory.entertainment, (
        "netflix", "spotify", "hotstar", "disney", "prime video", "sony liv",
        "zee5", "youtube", "bookmyshow", "pvr", "inox", "steam", "audible",
    )),
    (TransactionCategory.utilities, (
        "electricity", "water bill", "broadband", "fibernet", "act fibernet",
        "airtel", "jio", "vodafone", "bsnl", "recharge", "dth", "tata power",
        "adani", "gas bill", "billdesk", "msedcl",
    )),
    (TransactionCategory.travel, (
        "uber", "ola", "rapido", "irctc", "makemytrip", "goibibo", "cleartrip",
        "indigo", "vistara", "spicejet", "redbus", "petrol", "fuel", "hp",
        "indian oil", "bharat petroleum", "fastag", "metro", "toll",
    )),
    (TransactionCategory.health, (
        "pharmacy", "pharmeasy", "1mg", "netmeds", "apollo", "hospital",
        "clinic", "medical", "diagnostic", "lab", "cult.fit", "cultfit",
    )),
    (TransactionCategory.food, (
        "swiggy", "zomato", "faasos", "eatsure", "bigbasket", "blinkit",
        "zepto", "dunzo", "dominos", "mcdonald", "kfc", "burger", "starbucks",
        "cafe", "restaurant", "bakery", "dmart", "reliance fresh", "grocery",
    )),
    (TransactionCategory.shopping, (
        "amazon", "flipkart", "myntra", "ajio", "meesho", "nykaa", "tatacliq",
        "croma", "reliance digital", "decathlon", "lifestyle", "ikea",
    )),
    (TransactionCategory.rent, ("rent", "landlord")),
    # Card bill payments and ATM cash are money moving, NOT new spend/debt.
    # Categorizing a credit-card bill payment here (Transfer, excluded from the
    # spend ratios) avoids double-counting: the card's actual purchases are
    # already captured as expenses via the credit-card statement's transactions.
    (TransactionCategory.transfer, (
        "atm", "atm wdl", "cash withdrawal", "credit card payment",
        "card payment", "cc payment", "credit card bill",
    )),
]

# Recurring charges to a service (implies is_recurring). Kept separate from the
# category so Netflix stays "Entertainment" AND flags as a subscription.
_SUBSCRIPTION_KEYWORDS = (
    "netflix", "spotify", "hotstar", "disney", "prime", "youtube", "sony liv",
    "zee5", "audible", "gym", "cult.fit", "cultfit", "membership", "adobe",
    "microsoft", "google one", "icloud", "notion", "canva", "coursera",
)

_INCOME_KEYWORDS = ("salary", "payroll", "stipend")


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    """True if any keyword appears in text as a whole word/phrase.

    Word-boundary matching so "ajio" doesn't match the "jio" keyword, etc.
    """
    return any(re.search(rf"\b{re.escape(kw)}\b", text) for kw in keywords)


class CategorizerAgent(BaseAgent):
    stage = Stage.categorize

    def run(self, ctx: AgentContext) -> None:
        txns = transaction_service.list_transactions(ctx.run_id)
        if not txns:
            return

        recurring_flags = self._detect_recurring(txns)
        categories = self._categorize(txns)

        updates = [
            CategoryUpdate(
                id=str(t.id),
                category=categories[str(t.id)],
                is_recurring=recurring_flags[str(t.id)][0],
                is_subscription=recurring_flags[str(t.id)][1],
            )
            for t in txns
        ]
        transaction_service.apply_categorizations(updates)

    # -- categorization ----------------------------------------------------

    def _categorize(self, txns: list[Transaction]) -> dict[str, str]:
        """Return {txn_id: category value}, using rules then a batched LLM call."""
        result: dict[str, str] = {}
        unknown_debits: set[str] = set()

        for t in txns:
            category = self._match_rule(t)
            if category is not None:
                result[str(t.id)] = category.value
            elif t.direction == TransactionDirection.credit:
                result[str(t.id)] = TransactionCategory.transfer.value
            else:
                result[str(t.id)] = ""  # placeholder, resolved by the LLM below
                unknown_debits.add(self._display(t))

        if unknown_debits:
            try:
                mapping = self._llm_categorize(sorted(unknown_debits))
            except Exception:  # noqa: BLE001 — fallback is best-effort, never fail the run
                mapping = {}
            for t in txns:
                if result[str(t.id)] == "":
                    result[str(t.id)] = mapping.get(
                        self._display(t), TransactionCategory.other.value
                    )

        return result

    def _match_rule(self, txn: Transaction) -> TransactionCategory | None:
        text = f"{txn.merchant or ''} {txn.description}".lower()
        if txn.direction == TransactionDirection.credit and _contains_any(text, _INCOME_KEYWORDS):
            return TransactionCategory.income
        for category, keywords in _RULES:
            if _contains_any(text, keywords):
                return category
        return None

    def _llm_categorize(self, merchants: list[str]) -> dict[str, str]:
        # JSON mode: llama-3.1-8b mangles the tool-call wrapper, but returns
        # clean JSON reliably.
        client = get_structured_llm("json")
        settings = get_settings()
        batch: CategoryBatch = client.chat.completions.create(
            model=settings.CATEGORIZER_GROQ_MODEL,
            response_model=CategoryBatch,
            temperature=0,
            max_retries=2,
            messages=[
                {"role": "system", "content": CATEGORIZER_SYSTEM},
                {"role": "user", "content": build_categorizer_prompt(merchants)},
            ],
        )
        return {a.merchant: a.category.value for a in batch.assignments}

    # -- recurring / subscription detection --------------------------------

    def _detect_recurring(self, txns: list[Transaction]) -> dict[str, tuple[bool, bool]]:
        """Return {txn_id: (is_recurring, is_subscription)} via grouping heuristics."""
        groups: dict[str, list[Transaction]] = defaultdict(list)
        for t in txns:
            groups[self._key(t)].append(t)

        flags: dict[str, tuple[bool, bool]] = {}
        for key, items in groups.items():
            months = {(d.year, d.month) for d in (t.txn_date for t in items) if d}
            is_subscription = _contains_any(key, _SUBSCRIPTION_KEYWORDS)
            # Recurring if it spans 2+ months, repeats 3+ times, or is a subscription.
            is_recurring = is_subscription or len(months) >= 2 or len(items) >= 3
            for t in items:
                flags[str(t.id)] = (is_recurring, is_subscription)
        return flags

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _display(txn: Transaction) -> str:
        return (txn.merchant or txn.description or "").strip()

    @staticmethod
    def _key(txn: Transaction) -> str:
        return (txn.merchant or txn.description or "").strip().lower()
