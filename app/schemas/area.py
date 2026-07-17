"""Schemas de Áreas (catálogo permanente; composta/sub-áreas)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import FaseArea
from app.schemas.common import ORMModel

# Cor #hex de 3 ou 6 dígitos (opcional).
COR_REGEX = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


class AreaBase(BaseModel):
    nome: str = Field(min_length=1)
    carga_exigida: int = Field(gt=0, description="Carga horária exigida (h). > 0.")
    fase: FaseArea = FaseArea._9_10
    cor: str | None = Field(default=None, pattern=COR_REGEX)
    pre_requisito: bool = False
    composta: bool = False
    area_mae_id: int | None = None


class AreaCreate(AreaBase):
    pass


class AreaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1)
    carga_exigida: int | None = Field(default=None, gt=0)
    fase: FaseArea | None = None
    cor: str | None = Field(default=None, pattern=COR_REGEX)
    pre_requisito: bool | None = None
    composta: bool | None = None
    area_mae_id: int | None = None


class AreaOut(ORMModel):
    id: int
    nome: str
    carga_exigida: int
    fase: FaseArea
    cor: str | None
    pre_requisito: bool
    composta: bool
    area_mae_id: int | None
