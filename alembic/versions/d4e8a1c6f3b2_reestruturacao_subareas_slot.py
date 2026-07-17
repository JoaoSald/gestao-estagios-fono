"""reestruturacao: sub-areas (area_mae/composta), fase 7|9_10, slot de 1 dia + horas_sessao

Reflete a reestruturação de jul/2026 (fonte: protótipo versao_2 / mock.js):

  1. FASE renomeada: '5' -> '7' (Audiologia I) e '6_7' -> '9_10' (demais).
     Feito com ALTER TYPE ... RENAME VALUE (preserva os dados existentes).
  2. Áreas COMPOSTAS: `areas.composta` (container não matriculável, ex.: Audiologia II,
     Hospitalar) + `areas.area_mae_id` (FK self) nas SUB-ÁREAS leaf.
  3. Modelo SLOT: cada local = 1 (campo+dia+turno). `locais.horas_sessao` (horas reais
     por encontro; numero_encontros = teto(carga_horaria/horas_sessao)). Aposenta a
     tabela `locais_dias` (multi-dia) — cada dia vira um local próprio.

Regras de MOTOR/TELA da reestruturação (motor por linha do tempo, corte de ciclo,
teto 30h, ordenamento por fase, seleção de áreas por aluno, "não faz neste ciclo",
mover grupo, matrícula = gatilho de remanejo) NÃO mexem no schema — ficam nas specs.

Revision ID: d4e8a1c6f3b2
Revises: b2f7c1a9d4e0
Create Date: 2026-07-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d4e8a1c6f3b2"
down_revision: Union[str, None] = "b2f7c1a9d4e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. FASE: renomeia os valores do ENUM (atualiza dados e defaults automaticamente)
    op.execute("ALTER TYPE fase_area RENAME VALUE '5' TO '7'")
    op.execute("ALTER TYPE fase_area RENAME VALUE '6_7' TO '9_10'")

    # 2. Áreas compostas + sub-áreas
    op.add_column("areas", sa.Column(
        "composta", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("areas", sa.Column("area_mae_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_areas_area_mae", "areas", "areas", ["area_mae_id"], ["id"])

    # 3. Modelo slot: horas por encontro; aposenta multi-dia
    op.add_column("locais", sa.Column("horas_sessao", sa.Float(), nullable=True))
    op.drop_table("locais_dias")


def downgrade() -> None:
    # 3. volta o multi-dia
    op.create_table(
        "locais_dias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("local_id", sa.Integer(), nullable=False),
        sa.Column("dia_semana",
                  postgresql.ENUM(name="dia_semana_tipo", create_type=False), nullable=False),
        sa.ForeignKeyConstraint(["local_id"], ["locais.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("local_id", "dia_semana", name="uq_local_dia"),
    )
    op.drop_column("locais", "horas_sessao")

    # 2. remove sub-áreas/compostas
    op.drop_constraint("fk_areas_area_mae", "areas", type_="foreignkey")
    op.drop_column("areas", "area_mae_id")
    op.drop_column("areas", "composta")

    # 1. volta os valores do ENUM
    op.execute("ALTER TYPE fase_area RENAME VALUE '9_10' TO '6_7'")
    op.execute("ALTER TYPE fase_area RENAME VALUE '7' TO '5'")
