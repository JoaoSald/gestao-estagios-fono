"""Rotas REST de Áreas (catálogo permanente)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.area import AreaCreate, AreaOut, AreaUpdate
from app.services import area as service

router = APIRouter(prefix="/areas", tags=["áreas"])


@router.get("", response_model=list[AreaOut])
def listar(db: Session = Depends(get_db)):
    return service.listar(db)


@router.get("/{area_id}", response_model=AreaOut)
def obter(area_id: int, db: Session = Depends(get_db)):
    return service.obter(db, area_id)


@router.post("", response_model=AreaOut, status_code=status.HTTP_201_CREATED)
def criar(dados: AreaCreate, db: Session = Depends(get_db)):
    return service.criar(db, dados)


@router.patch("/{area_id}", response_model=AreaOut)
def atualizar(area_id: int, dados: AreaUpdate, db: Session = Depends(get_db)):
    return service.atualizar(db, area_id, dados)


@router.delete("/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(area_id: int, db: Session = Depends(get_db)):
    service.remover(db, area_id)
