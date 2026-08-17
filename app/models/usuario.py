"""Autenticação — usuários e perfis (FASE 6)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Integer, String, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import PERFIS_EDICAO, PerfilUsuario, perfil_usuario_enum


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        UniqueConstraint("matricula", name="uq_usuarios_matricula"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    senha_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Padrão = menor privilégio: usuário criado sem perfil explícito só lê a escala.
    perfil: Mapped[PerfilUsuario] = mapped_column(
        perfil_usuario_enum, nullable=False, server_default=PerfilUsuario.aluno.value
    )
    # Identidade do aluno ENTRE ciclos. Não é `aluno_id` de propósito: `alunos` é por
    # ciclo (uq_aluno_ciclo_matricula), então um id apontaria para a linha do ciclo
    # velho no ano seguinte. A matrícula é o que sobrevive à virada.
    matricula: Mapped[str | None] = mapped_column(String)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    ultimo_acesso: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)

    @property
    def pode_editar(self) -> bool:
        """Só a comissão escreve (§ divisão de acesso). Leitura é o padrão."""
        return self.perfil in PERFIS_EDICAO
