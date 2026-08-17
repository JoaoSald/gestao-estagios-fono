"""Rótulos pt-BR (com acento) dos valores de enum exibidos na interface.

Os `.value` dos enums são chaves de banco, escritas sem acento e com `_`
(`ferias`, `terca`, `manha`, `em_andamento`) porque viram valores de `CREATE TYPE`
no Postgres. **Nada disso deve chegar cru à tela.** `rotulo()` traduz o valor para
o texto que a comissão lê; `opcoes()` monta as listas `(valor, rótulo)` dos selects.

Nos templates o mesmo está disponível como filtro Jinja: `{{ l.turno.value|rot }}`.

O mapa é achatado (valor → rótulo) porque nenhum valor se repete com sentido
diferente entre os enums ("concluida" é sempre "Concluída", "outro" é sempre "Outro").
"""
from __future__ import annotations

import enum

ROTULOS: dict[str, str] = {
    # Turno
    "manha": "Manhã",
    "tarde": "Tarde",
    "integral": "Integral",
    "noite": "Noite",
    # DiaSemana
    "segunda": "Segunda",
    "terca": "Terça",
    "quarta": "Quarta",
    "quinta": "Quinta",
    "sexta": "Sexta",
    "sabado": "Sábado",
    "domingo": "Domingo",
    # FaseArea
    "7": "7º",
    "9_10": "9º/10º",
    # StatusCiclo
    "rascunho": "Rascunho",
    "encerrado": "Encerrado",
    # StatusMatricula / StatusAlocacao / StatusSessao / StatusGrupo
    "em_andamento": "Em andamento",
    "concluida": "Concluída",
    "interrompida": "Interrompida",
    "incompleta": "Incompleta",
    "ativa": "Ativa",
    "cancelada": "Cancelada",
    "prevista": "Prevista",
    "cumprida": "Cumprida",
    "remanejada": "Remanejada",
    "previsto": "Previsto",
    # TipoAfastamento
    "ferias": "Férias",
    "licenca": "Licença",
    "outro": "Outro",
    # TipoEvento
    "academico": "Acadêmico",
    "feriado": "Feriado",
    "reuniao": "Reunião",
    "recesso": "Recesso",
    # OrigemEvento
    "manual": "Manual",
    "google": "Google Calendar",
    "api_feriados": "Feriado (API)",
    # TipoAtividade
    "ciclo": "Ciclo",
    "edicao": "Edição",
    "remanejo": "Remanejo",
    "sync": "Sincronização",
    # SituacaoHistorico
    "ciclo_completo": "Ciclo completo",
    "pendente": "Pendente",
    # PerfilUsuario
    "administrador": "Administrador",
    "coordenacao": "Coordenação",
    "docente": "Docente",
    "aluno": "Aluno",
}


def rotulo(valor) -> str:
    """Texto de tela de um valor de enum. Aceita o membro do enum ou o `.value`.

    Valor desconhecido volta legível (`_` → espaço, 1ª letra maiúscula) em vez de
    quebrar — assim um enum novo nunca deixa a tela em branco.
    """
    if valor is None:
        return ""
    if isinstance(valor, enum.Enum):
        valor = valor.value
    v = str(valor)
    if v in ROTULOS:
        return ROTULOS[v]
    return v.replace("_", " ").capitalize()


def opcoes(py_enum: type[enum.Enum]) -> list[tuple[str, str]]:
    """`[(valor, rótulo)]` de um enum, na ordem de declaração — para os selects."""
    return [(m.value, rotulo(m.value)) for m in py_enum]
