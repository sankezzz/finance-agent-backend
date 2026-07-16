"""Security utilities.

Masks account numbers and scrubs PII from extracted document text BEFORE
it is placed in an LLM prompt. Masking keeps the last 4 digits so the
model still has enough context to attach a transaction to an account,
without the full sensitive number ever leaving our process.
"""

import re

# 16-digit card numbers, optionally grouped in 4s by spaces/hyphens.
_CARD = re.compile(r"\b\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{4}\b")
# Contiguous long digit runs (bank account numbers): 9-18 digits.
_ACCOUNT = re.compile(r"\b\d{9,18}\b")
# Indian PAN (e.g. ABCDE1234F).
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
# Email addresses.
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def mask_account_number(value: str) -> str:
    """Mask all but the last 4 digits of an account/card-like number."""
    digits = re.sub(r"\D", "", value)
    if len(digits) <= 4:
        return value
    return "X" * (len(digits) - 4) + digits[-4:]


def scrub_text(text: str) -> str:
    """Return `text` with account numbers, cards, PAN, and emails masked."""
    text = _CARD.sub(lambda m: mask_account_number(m.group()), text)
    text = _ACCOUNT.sub(lambda m: mask_account_number(m.group()), text)
    text = _PAN.sub("[PAN]", text)
    text = _EMAIL.sub("[EMAIL]", text)
    return text
