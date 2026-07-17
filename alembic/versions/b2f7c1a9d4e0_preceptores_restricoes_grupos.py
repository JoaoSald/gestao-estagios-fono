"""preceptores, restricoes de local, grupos, cobertura e passagem de grupo

Reflete as regras da rodada de jul/2026 que MEXEM NA MODELAGEM (AR-1/2/3):

  AR-1 · Preceptores + cobertura + e-mails:
    - nova tabela `preceptores` (externos à UFCSPA; e-mail = conta);
    - `locais`: troca `preceptor` (texto) por `preceptor_tipo` + `preceptor_id`
      (FK POLIMÓRFICA: 'externo'->preceptores | 'docente'->docentes | nulo);
    - `afastamentos`: `docente_id` vira nullable + novo `preceptor_id` (XOR);
    - `alunos.email`.
  AR-2 · Restrições de local do aluno: nova tabela `restricoes_aluno_local`.
  AR-3 · Grupos: novo TYPE `status_grupo`, tabelas `grupos` e `grupo_alunos`,
         e `locais.passagem_grupo`.

AR-4 (teto 30h) e AR-5 (ajuste manual) são regras de MOTOR/TELA — não mexem no
schema, então não entram aqui.

Revision ID: b2f7c1a9d4e0
Revises: 9f5f9cff6d42
Create Date: 2026-07-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b2f7c1a9d4e0"
down_revision: Union[str, Sequence[str], None] = "9f5f9cff6d42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ENUM reutilizado nas colunas (create_type=False: o TYPE é criado à parte).
status_grupo = postgresql.ENUM(
    "em_andamento", "previsto", name="status_grupo", create_type=False
)


def upgrade() -> None:
    # ---- AR-3: TYPE status_grupo -------------------------------------------
    op.execute("CREATE TYPE status_grupo AS ENUM ('em_andamento', 'previsto')")

    # ---- AR-1: catálogo de preceptores -------------------------------------
    op.create_table(
        "preceptores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # ---- AR-2: restrições de local do aluno (blocklist) --------------------
    op.create_table(
        "restricoes_aluno_local",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aluno_id", sa.Integer(),
                  sa.ForeignKey("alunos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("local_id", sa.Integer(),
                  sa.ForeignKey("locais.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("aluno_id", "local_id", name="uq_restricao_aluno_local"),
    )

    # ---- AR-3: grupos (ondas por local) + membros --------------------------
    op.create_table(
        "grupos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ciclo_id", sa.Integer(),
                  sa.ForeignKey("ciclos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("local_id", sa.Integer(),
                  sa.ForeignKey("locais.id", ondelete="CASCADE"), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=False),
        sa.Column("onda", sa.Integer(), nullable=False),
        sa.Column("status", status_grupo, nullable=False),
        sa.Column("data_inicio", sa.Date(), nullable=False),
        sa.Column("data_fim", sa.Date(), nullable=False),
    )
    op.create_table(
        "grupo_alunos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("grupo_id", sa.Integer(),
                  sa.ForeignKey("grupos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("aluno_id", sa.Integer(),
                  sa.ForeignKey("alunos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("aviso", sa.String(), nullable=True),
        sa.UniqueConstraint("grupo_id", "aluno_id", name="uq_grupo_aluno"),
    )

    # ---- AR-1/AR-3: colunas novas em locais --------------------------------
    op.add_column("locais", sa.Column("preceptor_tipo", sa.String(), nullable=True))
    op.add_column("locais", sa.Column("preceptor_id", sa.Integer(), nullable=True))
    op.add_column("locais", sa.Column(
        "passagem_grupo", sa.Boolean(), nullable=False, server_default=sa.text("false")
    ))
    op.create_check_constraint(
        "ck_local_preceptor", "locais",
        "(preceptor_tipo IS NULL AND preceptor_id IS NULL) "
        "OR (preceptor_tipo IN ('externo', 'docente') AND preceptor_id IS NOT NULL)",
    )
    op.drop_column("locais", "preceptor")

    # ---- AR-1: afastamentos de docente OU preceptor (XOR) ------------------
    op.alter_column("afastamentos", "docente_id",
                    existing_type=sa.Integer(), nullable=True)
    op.add_column("afastamentos", sa.Column("preceptor_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_afastamentos_preceptor", "afastamentos", "preceptores",
        ["preceptor_id"], ["id"],
    )
    op.create_check_constraint(
        "ck_afast_pessoa", "afastamentos",
        "(docente_id IS NOT NULL) <> (preceptor_id IS NOT NULL)",
    )

    # ---- AR-1: e-mail do aluno ---------------------------------------------
    op.add_column("alunos", sa.Column("email", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("alunos", "email")

    op.drop_constraint("ck_afast_pessoa", "afastamentos", type_="check")
    op.drop_constraint("fk_afastamentos_preceptor", "afastamentos", type_="foreignkey")
    op.drop_column("afastamentos", "preceptor_id")
    # NOTA: volta docente_id a NOT NULL — só funciona se não houver afastamento
    # de preceptor (docente_id nulo). É o esperado num rollback logo após o upgrade.
    op.alter_column("afastamentos", "docente_id",
                    existing_type=sa.Integer(), nullable=False)

    op.add_column("locais", sa.Column("preceptor", sa.String(), nullable=True))
    op.drop_constraint("ck_local_preceptor", "locais", type_="check")
    op.drop_column("locais", "passagem_grupo")
    op.drop_column("locais", "preceptor_id")
    op.drop_column("locais", "preceptor_tipo")

    op.drop_table("grupo_alunos")
    op.drop_table("grupos")
    op.drop_table("restricoes_aluno_local")
    op.drop_table("preceptores")

    op.execute("DROP TYPE status_grupo")
