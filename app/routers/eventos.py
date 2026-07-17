"""Rotas REST de Eventos (calendário do ciclo ativo)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.evento import EventoCreate, EventoOut, EventoUpdate
from app.services import evento as service

router = APIRouter(prefix="/eventos", tags=["eventos"])


@router.get("", response_model=list[EventoOut])
def listar(db: Session = Depends(get_db)):
    return service.listar(db)


@router.get("/{evento_id}", response_model=EventoOut)
def obter(evento_id: int, db: Session = Depends(get_db)):
    return service.obter(db, evento_id)


@router.post("", response_model=EventoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: EventoCreate, db: Session = Depends(get_db)):
    return service.criar(db, dados)


@router.patch("/{evento_id}", response_model=EventoOut)
def atualizar(evento_id: int, dados: EventoUpdate, db: Session = Depends(get_db)):
    return service.atualizar(db, evento_id, dados)


@router.delete("/{evento_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(evento_id: int, db: Session = Depends(get_db)):
    service.remover(db, evento_id)
