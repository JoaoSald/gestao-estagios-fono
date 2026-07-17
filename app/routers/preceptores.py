"""Rotas REST de Preceptores (catálogo permanente; DELETE = soft-delete)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.preceptor import PreceptorCreate, PreceptorOut, PreceptorUpdate
from app.services import preceptor as service

router = APIRouter(prefix="/preceptores", tags=["preceptores"])


@router.get("", response_model=list[PreceptorOut])
def listar(incluir_inativos: bool = True, db: Session = Depends(get_db)):
    return service.listar(db, incluir_inativos=incluir_inativos)


@router.get("/{preceptor_id}", response_model=PreceptorOut)
def obter(preceptor_id: int, db: Session = Depends(get_db)):
    return service.obter(db, preceptor_id)


@router.post("", response_model=PreceptorOut, status_code=status.HTTP_201_CREATED)
def criar(dados: PreceptorCreate, db: Session = Depends(get_db)):
    return service.criar(db, dados)


@router.patch("/{preceptor_id}", response_model=PreceptorOut)
def atualizar(preceptor_id: int, dados: PreceptorUpdate, db: Session = Depends(get_db)):
    return service.atualizar(db, preceptor_id, dados)


@router.delete("/{preceptor_id}", response_model=PreceptorOut)
def desativar(preceptor_id: int, db: Session = Depends(get_db)):
    return service.desativar(db, preceptor_id)
