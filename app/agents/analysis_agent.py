"""Financial Analysis Agent (thin wrapper, no LLM work).

Calculates monthly spending, savings rate, debt ratio, emergency
runway, and financial health score by delegating entirely to the pure
functions in core/finance. Reads categorized transactions for a run_id,
writes the financial snapshot + metrics.
"""
