"""grade-primeiro: status_matricula 'incompleta' + grupo_alunos.fixado

Revision ID: f3b8c1d4e6a2
Revises: d4e8a1c6f3b2
Create Date: 2026-07-12

Modelo grade-primeiro (docs/REGRAS_MOTOR_ESCALA.md):
- status_matricula ganha 'incompleta' — o período da caixa fechou com
  feitos < N; a área não concluiu e faz carry-forward para o próximo ciclo (§10.5);
- grupo_alunos.fixado — protege o remanejo manual da coordenação de um reprocesso
  do motor (o "furo" do protótipo, onde regerar a escala apagava ajustes; §9.1).

Não muda estrutura de `grupos`: a mudança de papel (projeção → molde persistido) é
só semântica/docstring nos models.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3b8c1d4e6a2"
down_revision: Union[str, Sequence[str], None] = "d4e8a1c6f3b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Novo valor no ENUM (o autogenerate NÃO detecta adição de valor de enum).
    # PG 12+ aceita ADD VALUE dentro de transação desde que o valor não seja
    # USADO na mesma transação — aqui só o adicionamos, então é seguro.
    op.execute("ALTER TYPE status_matricula ADD VALUE IF NOT EXISTS 'incompleta'")
    # Remanejo manual durável: o motor respeita membros fixados numa regeração.
    op.add_column(
        "grupo_alunos",
        sa.Column("fixado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("grupo_alunos", "fixado")
    # NOTA: o Postgres não remove valor de ENUM de forma simples; o valor
    # 'incompleta' permanece em status_matricula (inofensivo). Removê-lo exigiria
    # recriar o tipo — evitado de propósito (mesmo padrão de 'interrompida').
