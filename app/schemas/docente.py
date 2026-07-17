"""Schemas de Docentes (catálogo permanente; soft-delete via `ativo`)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class DocenteCreate(BaseModel):
    nome: str = Field(min_length=1)
    email: str | None = None
    ativo: bool = True


class DocenteUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1)
    email: str | None = None
    ativo: bool | None = None


class DocenteOut(ORMModel):
    id: int
    nome: str
    email: str | None
    ativo: bool
