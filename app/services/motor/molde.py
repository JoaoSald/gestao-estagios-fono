"""Fase 1 — Materialização do molde (§4).

Unidade atômica = (local, dia). No modelo SLOT (1 local = 1 campo+dia+turno), cada local
é UMA família de caixas. Fatia as datas viáveis em blocos consecutivos de N encontros;
cada bloco COMPLETO vira uma caixa. O bloco final incompleto é descartado (§4, passo 5; decisão §11.1) —
capacidade perdida no ciclo. As caixas saem encadeadas (a próxima começa onde a anterior
terminou), pois são fatias consecutivas da mesma fila de datas.

Construtor PURO: não toca o banco. A persistência do molde vive em `persistencia.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rotulos import rotulo
from app.models.ciclo import Ciclo
from app.models.local import Local
from app.services.motor.calendario import ContextoCalendario, horas_sessao, ocorrencias_dia


@dataclass
class Caixa:
    """Vaga de onda: uma corrida completa de um grupo numa área (§2).

    N sessões consecutivas no dia fixo do slot. Terminar a caixa = concluir a área.
    `ocupantes` = aluno_ids; `fixos` = subset pinado (montagem/travada), imune à
    consolidação e ao auto-preenchimento.
    """
    local: Local
    area_id: int
    onda: int
    datas: list[date]
    data_inicio: date
    data_fim: date
    capacidade: int
    horas: float                              # horas/semana do slot (= horas_sessao × 1 dia)
    ocupantes: list[int] = field(default_factory=list)
    fixos: set[int] = field(default_factory=set)

    @property
    def vaga(self) -> int:
        return self.capacidade - len(self.ocupantes)

    def tem_vaga(self) -> bool:
        return len(self.ocupantes) < self.capacidade


@dataclass
class LocalSemGrupo:
    """Slot ativo que não fecha NENHUM grupo no ciclo — capacidade perdida (§4 passo 5).

    Dado ESTRUTURADO do diagnóstico. A mensagem em prosa (`mensagem`) é derivada daqui,
    então o motor tem uma só fonte para o aviso e a UI pode pintar/tabelar o mesmo fato
    (cor da área, nº sugerido de encontros, edição inline). Nome e cor da área NÃO moram
    aqui: quem resolve rótulo de sub-área ("Mãe - Sub") e cor é a camada de UI, que tem o
    catálogo à mão.
    """
    local_id: int
    area_id: int
    campo: str
    unidade: str | None
    dia: str                    # rótulo pt-BR (já passou por `rotulo`)
    turno: str
    hora_inicio: time
    hora_fim: time
    encontros: int              # N pedido (do espelho)
    ocorrencias: int            # ocorrências do dia no ciclo, ANTES dos bloqueios
    viaveis: int                # datas que sobraram
    horas_sessao: float
    passagem_grupo: bool
    causa: str                  # 'sem_docente' | 'encontros_invalidos' | 'datas_insuficientes'

    @property
    def faltam(self) -> int:
        """Quantas datas faltam para fechar um grupo (0 quando a causa é outra)."""
        return max(0, self.encontros - self.viaveis)

    @property
    def bloqueadas(self) -> int:
        """Datas perdidas para feriado/afastamento/indisponibilidade."""
        return max(0, self.ocorrencias - self.viaveis)

    @property
    def sugerido(self) -> int:
        """Maior nº de encontros que ainda fecha 1 grupo neste slot."""
        return self.viaveis


def mensagem(p: LocalSemGrupo, nome_area: str) -> str:
    """Aviso em prosa (pt-BR) derivado do diagnóstico — usado nas listas de `avisos`."""
    onde = f"{nome_area} — {p.campo}"
    if p.causa == "sem_docente":
        return f"{onde} ({p.dia}) sem docente — pulado."
    onde = f"{onde} ({p.dia}/{p.turno})"
    if p.causa == "encontros_invalidos":
        return f"{onde}: número de encontros inválido ({p.encontros}) — nenhum grupo gerado."
    return (
        f"{onde}: precisa de {p.encontros} encontros, mas só há {p.viaveis} data(s) "
        f"viável(is) no ciclo (feriados/afastamentos/recesso) — NENHUM grupo gerado. "
        f"Reduza o nº de encontros, ofereça outro dia ou estenda o ciclo."
    )


def diagnosticar(local: Local, ciclo: Ciclo, ctx: ContextoCalendario, causa: str) -> LocalSemGrupo:
    """Monta o diagnóstico de um slot que não fechou grupo."""
    ocorrencias = len(ocorrencias_dia(local.dia_semana, ciclo.data_inicio, ciclo.data_fim))
    # Sem docente o slot cai por cobertura em TODAS as datas (§4/§8.3) — não vale varrer.
    viaveis = 0 if causa == "sem_docente" else len(ctx.datas_viaveis(local, ciclo))
    return LocalSemGrupo(
        local_id=local.id, area_id=local.area_id, campo=local.campo, unidade=local.unidade,
        dia=rotulo(local.dia_semana), turno=rotulo(local.turno),
        hora_inicio=local.hora_inicio, hora_fim=local.hora_fim,
        encontros=local.numero_encontros, ocorrencias=ocorrencias, viaveis=viaveis,
        horas_sessao=horas_sessao(local), passagem_grupo=bool(local.passagem_grupo),
        causa=causa,
    )


def _nome_area(local: Local) -> str:
    """Nome da área do local para as mensagens (área — local). Tolera objeto sem a
    relação carregada (ex.: testes com Local transiente) → cai no id da área."""
    try:
        if local.area is not None:
            return local.area.nome
    except Exception:
        pass
    return f"área {local.area_id}"


def locais_ativos(db: Session, ciclo: Ciclo) -> list[Local]:
    return list(db.scalars(select(Local).where(
        Local.ciclo_id == ciclo.id, Local.ativo.is_(True)
    ).order_by(Local.id)).all())


def caixas_do_local(local: Local, ciclo: Ciclo, ctx: ContextoCalendario) -> list[Caixa]:
    """Fatia as datas viáveis do slot em blocos de N; blocos completos viram caixas.

    **Passagem de grupo** (`local.passagem_grupo`): ondas consecutivas se sobrepõem em
    1 dia — o último encontro de uma onda é o primeiro da seguinte (a comissão faz a
    passagem nesse dia, com o grupo que sai e o que entra juntos). O passo entre inícios
    de ondas recua 1 dia. Sem passagem, as ondas são fatias disjuntas (a próxima começa
    depois da anterior). N==1 não admite passagem (o bloco tem 1 dia só).
    """
    n = local.numero_encontros
    if n <= 0:
        return []
    datas = ctx.datas_viaveis(local, ciclo)
    horas = horas_sessao(local)
    passo = n - 1 if (local.passagem_grupo and n > 1) else n
    caixas: list[Caixa] = []
    onda = 0
    for i in range(0, len(datas), passo):
        bloco = datas[i:i + n]
        if len(bloco) < n:
            break  # bloco final incompleto → não vira caixa (§4, passo 5)
        onda += 1
        caixas.append(Caixa(
            local=local, area_id=local.area_id, onda=onda,
            datas=bloco, data_inicio=bloco[0], data_fim=bloco[-1],
            capacidade=local.capacidade, horas=horas,
        ))
    return caixas


def materializar_molde(
    db: Session,
    ciclo: Ciclo,
    ctx: ContextoCalendario,
    locais: list[Local] | None = None,
    avisos: list[str] | None = None,
    perdidos: list[LocalSemGrupo] | None = None,
) -> list[Caixa]:
    """Molde do ciclo: todas as caixas de todos os slots ativos. Determinístico (§4).

    Local ativo sem docente é pulado ('todo local ativo precisa de docente' é
    validação, não constraint).

    Diagnóstico dos slots que não fecham grupo: `perdidos` recebe o dado ESTRUTURADO
    (`LocalSemGrupo`) e `avisos` a mesma coisa em prosa — ambos derivados da mesma
    apuração, então a tela e o log nunca divergem. Os dois são opcionais.
    """
    if locais is None:
        locais = locais_ativos(db, ciclo)
    caixas: list[Caixa] = []
    for local in locais:
        # Local ativo que não fecha NENHUMA caixa some da escala em silêncio — diagnostica
        # por quê. Causa típica: numero_encontros ≈ nº de ocorrências do dia no ciclo, e
        # feriados/afastamentos/recesso derrubam as datas viáveis abaixo de N (o bloco final
        # fica incompleto e é descartado, §4 passo 5).
        causa: str | None = None
        caixas_local: list[Caixa] = []
        if local.docente_id is None:
            causa = "sem_docente"
        else:
            caixas_local = caixas_do_local(local, ciclo, ctx)
            if not caixas_local:
                causa = ("encontros_invalidos" if local.numero_encontros <= 0
                         else "datas_insuficientes")

        if causa is not None and (avisos is not None or perdidos is not None):
            diag = diagnosticar(local, ciclo, ctx, causa)
            if perdidos is not None:
                perdidos.append(diag)
            if avisos is not None:
                avisos.append(mensagem(diag, _nome_area(local)))

        caixas.extend(caixas_local)
    return caixas
