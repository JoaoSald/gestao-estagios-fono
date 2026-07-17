"""ENUMs do domínio — espelham 1:1 os CREATE TYPE do DDL (modelagem_dados_v2.sql).

Cada enum Python vira um tipo ENUM nativo do PostgreSQL. Os valores (`.value`)
são exatamente as strings que vão pro banco; os nomes dos membros existem só
para o código Python (por isso `_5`/`_6_7`, que não podem começar com dígito).
"""
import enum

from sqlalchemy import Enum as SAEnum


class Turno(str, enum.Enum):
    manha = "manha"
    tarde = "tarde"
    integral = "integral"
    noite = "noite"


class DiaSemana(str, enum.Enum):
    segunda = "segunda"
    terca = "terca"
    quarta = "quarta"
    quinta = "quinta"
    sexta = "sexta"
    sabado = "sabado"
    domingo = "domingo"


class FaseArea(str, enum.Enum):
    _7 = "7"          # mini-ciclo (7º semestre): só Audiologia I
    _9_10 = "9_10"    # 9º/10º: demais áreas


class StatusCiclo(str, enum.Enum):
    rascunho = "rascunho"
    em_andamento = "em_andamento"
    encerrado = "encerrado"


class StatusMatricula(str, enum.Enum):
    em_andamento = "em_andamento"
    concluida = "concluida"
    interrompida = "interrompida"   # aluno parou por motivo extraordinário (ver regra §6.1)
    incompleta = "incompleta"       # período da caixa fechou com feitos < N → carry-forward (grade-primeiro, §10.5)


class StatusAlocacao(str, enum.Enum):
    ativa = "ativa"
    concluida = "concluida"
    cancelada = "cancelada"


class StatusSessao(str, enum.Enum):
    prevista = "prevista"
    cumprida = "cumprida"
    remanejada = "remanejada"
    cancelada = "cancelada"


class TipoAfastamento(str, enum.Enum):
    ferias = "ferias"
    licenca = "licenca"
    outro = "outro"


class TipoEvento(str, enum.Enum):
    academico = "academico"
    feriado = "feriado"
    reuniao = "reuniao"
    recesso = "recesso"
    outro = "outro"


class OrigemEvento(str, enum.Enum):
    manual = "manual"
    google = "google"
    api_feriados = "api_feriados"


class TipoAtividade(str, enum.Enum):
    ciclo = "ciclo"
    edicao = "edicao"
    remanejo = "remanejo"
    sync = "sync"


class SituacaoHistorico(str, enum.Enum):
    ciclo_completo = "ciclo_completo"
    pendente = "pendente"


class PerfilUsuario(str, enum.Enum):
    administrador = "administrador"
    coordenacao = "coordenacao"
    consulta = "consulta"


def pg_enum(py_enum: type[enum.Enum], name: str) -> SAEnum:
    """Cria o tipo SQLAlchemy Enum mapeado para um ENUM nativo do Postgres.

    - `values_callable`: usa o `.value` (e não o nome do membro) como valor no banco.
    - `create_type=False`: quem cria/derruba o TYPE é a migration do Alembic,
      não o create_table (evita erro de "type já existe" em tabelas repetidas).
    """
    return SAEnum(
        py_enum,
        name=name,
        native_enum=True,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


class StatusGrupo(str, enum.Enum):
    em_andamento = "em_andamento"   # onda atual (alunos hoje alocados no local)
    previsto = "previsto"           # onda futura projetada a partir da fila


# Instâncias compartilhadas (um objeto por TYPE do Postgres).
turno_enum = pg_enum(Turno, "turno_tipo")
dia_semana_enum = pg_enum(DiaSemana, "dia_semana_tipo")
fase_area_enum = pg_enum(FaseArea, "fase_area")
status_ciclo_enum = pg_enum(StatusCiclo, "status_ciclo")
status_matricula_enum = pg_enum(StatusMatricula, "status_matricula")
status_alocacao_enum = pg_enum(StatusAlocacao, "status_alocacao")
status_sessao_enum = pg_enum(StatusSessao, "status_sessao")
status_grupo_enum = pg_enum(StatusGrupo, "status_grupo")
tipo_afastamento_enum = pg_enum(TipoAfastamento, "tipo_afastamento")
tipo_evento_enum = pg_enum(TipoEvento, "tipo_evento")
origem_evento_enum = pg_enum(OrigemEvento, "origem_evento")
tipo_atividade_enum = pg_enum(TipoAtividade, "tipo_atividade")
situacao_historico_enum = pg_enum(SituacaoHistorico, "situacao_historico")
perfil_usuario_enum = pg_enum(PerfilUsuario, "perfil_usuario")

# Ordem de criação dos TYPES na migration inicial (nome_do_tipo, [valores]).
ALL_PG_ENUMS: list[tuple[str, list[str]]] = [
    ("turno_tipo", [m.value for m in Turno]),
    ("dia_semana_tipo", [m.value for m in DiaSemana]),
    ("fase_area", [m.value for m in FaseArea]),
    ("status_ciclo", [m.value for m in StatusCiclo]),
    ("status_matricula", [m.value for m in StatusMatricula]),
    ("status_alocacao", [m.value for m in StatusAlocacao]),
    ("status_sessao", [m.value for m in StatusSessao]),
    ("status_grupo", [m.value for m in StatusGrupo]),
    ("tipo_afastamento", [m.value for m in TipoAfastamento]),
    ("tipo_evento", [m.value for m in TipoEvento]),
    ("origem_evento", [m.value for m in OrigemEvento]),
    ("tipo_atividade", [m.value for m in TipoAtividade]),
    ("situacao_historico", [m.value for m in SituacaoHistorico]),
    ("perfil_usuario", [m.value for m in PerfilUsuario]),
]
