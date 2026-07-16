"""Categorizer LLM contract.

The shape the categorizer asks the LLM to return (via `instructor`) for the
batch of unknown merchants the rules table couldn't classify. `category` is
validated against the TransactionCategory enum, so instructor retries if the
model returns anything off-list.
"""

from pydantic import BaseModel, Field

from app.models.transaction import TransactionCategory


class MerchantCategory(BaseModel):
    merchant: str
    category: TransactionCategory


class CategoryBatch(BaseModel):
    assignments: list[MerchantCategory] = Field(default_factory=list)
