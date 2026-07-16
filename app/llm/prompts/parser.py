"""Prompt templates for the Document Parser Agent.

Each document type gets its own extraction guidance so the LLM shapes its
output to the file: bank/credit-card statements yield `transactions`
(ledger line-items); salary/loan/investment statements yield `facts`
(point-in-time figures). The response schema (models.parser.ParsedDocument)
is enforced separately by `instructor`.
"""

from app.models.document import DocumentType

PARSER_SYSTEM = (
    "You extract structured financial data from a single uploaded document. "
    "Return only data that is actually present in the text — never invent "
    "numbers. Use positive amounts and set direction explicitly. Use ISO "
    "dates (YYYY-MM-DD) when a date is available, otherwise null."
)

# Per-document-type guidance appended to the shared instructions.
_GUIDANCE: dict[DocumentType, str] = {
    DocumentType.bank_statement: (
        "This is a BANK STATEMENT. Fill `transactions` with every ledger entry: "
        "money received is direction='credit', money spent is direction='debit'. "
        "Leave `facts` empty unless a closing/available balance is shown — if so, "
        "add one fact {kind:'asset', subtype:'savings_balance', amount:<balance>}."
    ),
    DocumentType.credit_card_statement: (
        "This is a CREDIT CARD STATEMENT. Fill `transactions` with each purchase "
        "(direction='debit') and payment/refund (direction='credit'). Add one fact "
        "{kind:'liability', subtype:'cc_outstanding', amount:<total amount due>} "
        "for the outstanding balance if shown."
    ),
    DocumentType.salary_slip: (
        "This is a SALARY SLIP. Do NOT produce transactions. Add facts: "
        "{kind:'income', subtype:'salary', amount:<net pay>}, and where shown "
        "{kind:'income', subtype:'gross_salary', amount:<gross>}. Record notable "
        "deductions (tax, PF) inside the salary fact's `meta`."
    ),
    DocumentType.loan_statement: (
        "This is a LOAN STATEMENT. Add a fact {kind:'liability', subtype:<loan "
        "type e.g. home_loan/personal_loan>, amount:<outstanding principal>} with "
        "`meta` holding emi and interest_rate when shown. EMI payments listed as "
        "transactions may go in `transactions` (direction='debit')."
    ),
    DocumentType.investment_statement: (
        "This is an INVESTMENT STATEMENT. Do NOT produce transactions. Add one "
        "fact per holding {kind:'asset', subtype:<mutual_fund/stocks/fd/etc>, "
        "label:<instrument name>, amount:<current value>}."
    ),
}


def build_parser_prompt(document_type: DocumentType, text: str) -> str:
    """Return the extraction prompt for a document of the given type."""
    guidance = _GUIDANCE.get(
        document_type,
        "Extract any financial line-items into `transactions` and any "
        "point-in-time figures into `facts`.",
    )
    return f"{guidance}\n\nDocument text:\n\n{text}"
