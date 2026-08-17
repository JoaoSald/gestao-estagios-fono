"""perfis_de_acesso (FASE 6)

`consulta` virou `docente` e nasceu `aluno`: leitura deixou de ser um perfil só, porque
o alcance é diferente (docente lê painel/histórico; aluno lê apenas a escala). O DEFAULT
da coluna passa a ser `aluno` — menor privilégio, para que usuário criado sem perfil
explícito não ganhe acesso por omissão.

`usuarios.matricula` é a identidade do aluno ENTRE ciclos (ver comentário no model).

Revision ID: a1c3e5f70b21
Revises: 9fd4120b1555
Create Date: 2026-08-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c3e5f70b21"
down_revision: Union[str, Sequence[str], None] = "9fd4120b1555"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ... ADD VALUE não pode ter o valor novo USADO na mesma transação;
    # o autocommit_block tira estes dois comandos da transação da migration.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE perfil_usuario RENAME VALUE 'consulta' TO 'docente'")
        op.execute("ALTER TYPE perfil_usuario ADD VALUE IF NOT EXISTS 'aluno'")

    # SQL cru em vez de alter_column: mexer no server_default de coluna com ENUM nativo
    # faz o Alembic querer recriar o TYPE (e aqui ele já existe).
    op.execute("ALTER TABLE usuarios ALTER COLUMN perfil SET DEFAULT 'aluno'")

    op.add_column("usuarios", sa.Column("matricula", sa.String(), nullable=True))
    op.create_unique_constraint("uq_usuarios_matricula", "usuarios", ["matricula"])
    op.add_column("usuarios", sa.Column("ultimo_acesso", sa.TIMESTAMP(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("usuarios", "ultimo_acesso")
    op.drop_constraint("uq_usuarios_matricula", "usuarios", type_="unique")
    op.drop_column("usuarios", "matricula")

    # O Postgres não remove valor de ENUM: recria o TYPE com os 3 originais,
    # rebaixando docente/aluno para `consulta`.
    op.execute("ALTER TABLE usuarios ALTER COLUMN perfil DROP DEFAULT")
    op.execute("ALTER TYPE perfil_usuario RENAME TO perfil_usuario_antigo")
    op.execute("CREATE TYPE perfil_usuario AS ENUM ('administrador', 'coordenacao', 'consulta')")
    op.execute(
        "ALTER TABLE usuarios ALTER COLUMN perfil TYPE perfil_usuario USING "
        "(CASE WHEN perfil::text IN ('administrador', 'coordenacao') "
        "THEN perfil::text ELSE 'consulta' END)::perfil_usuario"
    )
    op.execute("DROP TYPE perfil_usuario_antigo")
    op.execute("ALTER TABLE usuarios ALTER COLUMN perfil SET DEFAULT 'consulta'")
