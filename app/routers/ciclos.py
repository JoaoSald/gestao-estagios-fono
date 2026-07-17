"""Rotas REST de Ciclos (máquina de estados)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import NaoEncontrado
from app.schemas.ciclo import CicloCreate, CicloEncerrar, CicloOut, EstadoInicial
from app.services import ciclo as service

router = APIRouter(prefix="/ciclos", tags=["ciclos"])


@router.get("/estado", response_model=EstadoInicial)
def estado(db: Session = Depends(get_db)):
    """Estado da aplicação — 'nenhum' | 'rascunho' | 'em_andamento' + o ciclo ativo."""
    estado_str, ciclo = service.estado_inicial(db)
    return EstadoInicial(estado=estado_str, ciclo=ciclo)


@router.get("/ativo", response_model=CicloOut)
def ativo(db: Session = Depends(get_db)):
    ciclo = service.obter_ativo(db)
    if ciclo is None:
        raise NaoEncontrado("Nenhum ciclo ativo.")
    return ciclo


@router.get("/{ciclo_id}", response_model=CicloOut)
def obter(ciclo_id: int, db: Session = Depends(get_db)):
    return service.obter(db, ciclo_id)


@router.post("", response_model=CicloOut, status_code=status.HTTP_201_CREATED)
def abrir(dados: CicloCreate, db: Session = Depends(get_db)):
    """Abre um ciclo em rascunho (início do bootstrap)."""
    return service.abrir(db, dados)


@router.post("/{ciclo_id}/confirmar", response_model=CicloOut)
def confirmar(ciclo_id: int, db: Session = Depends(get_db)):
    """rascunho → em_andamento."""
    return service.confirmar(db, ciclo_id)


@router.post("/{ciclo_id}/encerrar", response_model=CicloOut)
def encerrar(ciclo_id: int, dados: CicloEncerrar, db: Session = Depends(get_db)):
    """em_andamento → encerrado (exige o ano como confirmação)."""
    return service.encerrar(db, ciclo_id, dados.ano)
