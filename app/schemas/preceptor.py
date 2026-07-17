"""Schemas de Preceptores (catálogo permanente; e-mail obrigatório = conta, AR-1)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PreceptorCreate(BaseModel):
    nome: str = Field(min_length=1)
    # E-mail é a "conta" do preceptor externo → obrigatório (AR-1).
    email: str = Field(min_length=3)
    ativo: bool = True


class PreceptorUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1)
    email: str | None = Field(default=None, min_length=3)
    ativo: bool | None = None


class PreceptorOut(ORMModel):
    id: int
    nome: str
    email: str
    ativo: bool
