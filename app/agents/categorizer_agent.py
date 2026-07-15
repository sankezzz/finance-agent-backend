"""Categorization Agent (hybrid: rules first, LLM fallback).

Categorizes normalized transactions, identifies recurring expenses, and
detects subscriptions. Known merchants/patterns are matched with rules;
unrecognized merchants fall back to an LLM call. Reads normalized
records for a run_id, writes categorized transactions.
"""
