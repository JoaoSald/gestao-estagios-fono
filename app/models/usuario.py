"""Autenticação — usuários e perfis (FASE 6)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Integer, String, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import PerfilUsuario, perfil_usuario_enum


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    senha_hash: Mapped[str] = mapped_column(String, nullable=False)
    perfil: Mapped[PerfilUsuario] = mapped_column(
        perfil_usuario_enum, nullable=False, server_default=PerfilUsuario.consulta.value
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
