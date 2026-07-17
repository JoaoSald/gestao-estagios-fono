"""Rotas REST de Afastamentos (escopados no ciclo ativo)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.afastamento import AfastamentoCreate, AfastamentoOut
from app.services import afastamento as service

router = APIRouter(prefix="/afastamentos", tags=["afastamentos"])


@router.get("", response_model=list[AfastamentoOut])
def listar(db: Session = Depends(get_db)):
    return service.listar(db)


@router.get("/{afastamento_id}", response_model=AfastamentoOut)
def obter(afastamento_id: int, db: Session = Depends(get_db)):
    return service.obter(db, afastamento_id)


@router.post("", response_model=AfastamentoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: AfastamentoCreate, db: Session = Depends(get_db)):
    return service.criar(db, dados)


@router.delete("/{afastamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(afastamento_id: int, db: Session = Depends(get_db)):
    service.remover(db, afastamento_id)
