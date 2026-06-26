"""Task 4 - Pydantic request/response models. TODO: flesh out per endpoint."""
from __future__ import annotations

from pydantic import BaseModel


class TopProduct(BaseModel):
    product: str
    mentions: int
