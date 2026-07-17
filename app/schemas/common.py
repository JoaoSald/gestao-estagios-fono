"""Base compartilhada dos schemas Pydantic v2."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Schema de saída que lê direto do model SQLAlchemy (from_attributes)."""

    model_config = ConfigDict(from_attributes=True)
