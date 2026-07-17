"""Eventos de meio de ciclo (§7/§8) — reajuste de raio pequeno.

O molde é fixo; o dia a dia é operação de CONTEÚDO. Só afastamento/feriado tardio muda
datas (reflow da caixa em andamento). Desmatrícula (§8.2) vive em `services/desmatricula.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import Conflito, DomainError
from app.models.aluno import Aluno, Matricula
from app.models.enums import StatusAlocacao, StatusGrupo, StatusMatricula, StatusSessao
from app.models.escala import Alocacao, Grupo, GrupoAluno, Sessao
from app.models.local import Local
from app.models.operacao import FilaRemanejo
from app.services import common
from app.services.motor import calendario, encontros, estado, molde
from app.services.motor.ajuste import ResultadoAjuste, _bloqueados
from app.services.motor.calendario import ocorrencias_dia
from app.services.motor.restricoes import viola_restricoes


def nova_matricula(db: Session, aluno_id: int, area_id: int) -> ResultadoAjuste:
    """Encaixa uma área nova numa CAIXA FUTURA existente com vaga (§8.1). Raio: 1 caixa."""
    aluno = common.obter_ou_404(db, Aluno, aluno_id, "Aluno")
    ctx = calendario.carregar_contexto(db, aluno.ciclo)
    mv = estado.carregar_molde_vivo(db, aluno.ciclo, ctx)
    hoje = date.today()

    mat = estado.matricula_de(db, aluno_id, area_id)
    if mat is None or mat.status not in (StatusMatricula.em_andamento, StatusMatricula.incompleta):
        raise DomainError("Matricule a área (em andamento) antes de encaixar.")
    if any(cx.area_id == area_id and aluno_id in cx.ocupantes for cx in mv.caixas.values()):
        raise Conflito("O aluno já está alocado nesta área.")

    comp = mv.compromissos(aluno_id)
    bloq = _bloqueados(db, aluno_id)
    candidatos = sorted(
        [(gid, cx) for gid, cx in mv.por_area(area_id) if cx.data_inicio > hoje and cx.tem_vaga()],
        key=lambda t: t[1].data_inicio,
    )
    for gid, cx in candidatos:
        if viola_restricoes(comp, cx, bloq) is None:
            if mat.status != StatusMatricula.em_andamento:
                mat.status = StatusMatricula.em_andamento
            estado.sentar(db, aluno_id, cx, gid, mat.id, fixado=False)
            common.registrar_atividade(db, aluno.ciclo, f"{aluno.nome} encaixado em {cx.local.campo} (matrícula nova).")
            common.commit(db, "Não foi possível encaixar a matrícula.")
            return ResultadoAjuste(True, sugestao={"grupo_id": gid, "data_inicio": cx.data_inicio.isoformat()})
    return ResultadoAjuste(False, ["sem caixa futura viável — fila / próximo ciclo"])


def novo_local(db: Session, local_id: int) -> dict:
    """Materializa as caixas do local novo e oferece as vagas à fila (§8.4). Raio: 1 local."""
    local = common.obter_ou_404(db, Local, local_id, "Local")
    if local.docente_id is None:
        raise DomainError("Defina o docente do local antes de materializar suas caixas.")
    ciclo = local.ciclo
    ctx = calendario.carregar_contexto(db, ciclo)
    hoje = date.today()

    existentes = {
        g.onda for g in db.scalars(select(Grupo).where(
            Grupo.ciclo_id == ciclo.id, Grupo.local_id == local_id
        )).all()
    }
    criadas = 0
    for cx in molde.caixas_do_local(local, ciclo, ctx):
        if cx.onda in existentes:
            continue
        status = StatusGrupo.em_andamento if cx.data_inicio <= hoje else StatusGrupo.previsto
        db.add(Grupo(
            ciclo_id=ciclo.id, local_id=local_id, area_id=cx.area_id, onda=cx.onda,
            status=status, data_inicio=cx.data_inicio, data_fim=cx.data_fim,
        ))
        criadas += 1
    db.flush()

    # Oferece à fila: matrículas em_andamento da área SEM alocação ativa, por ordenamento.
    mv = estado.carregar_molde_vivo(db, ciclo, ctx)
    novas = sorted(
        [(gid, cx) for gid, cx in mv.caixas.items() if cx.local.id == local_id],
        key=lambda t: t[1].onda,
    )
    espera = db.scalars(
        select(Matricula).join(Aluno, Matricula.aluno_id == Aluno.id)
        .where(Aluno.ciclo_id == ciclo.id, Matricula.area_id == local.area_id,
               Matricula.status == StatusMatricula.em_andamento)
        .order_by(Aluno.ordenamento)
    ).all()
    alocados = 0
    for mat in espera:
        aluno_id = mat.aluno_id
        if any(aluno_id in cx.ocupantes for cx in mv.caixas.values() if cx.area_id == local.area_id):
            continue  # já alocado nessa área
        comp = mv.compromissos(aluno_id)
        bloq = _bloqueados(db, aluno_id)
        for gid, cx in novas:
            if cx.tem_vaga() and viola_restricoes(comp, cx, bloq) is None:
                estado.sentar(db, aluno_id, cx, gid, mat.id, fixado=False)
                cx.ocupantes.append(aluno_id)
                alocados += 1
                break
    common.registrar_atividade(db, ciclo, f"Local {local.campo} materializado — {alocados} alocados da fila.")
    common.commit(db, "Não foi possível materializar o local.")
    return {"caixas_criadas": criadas, "alocados": alocados}


# ==================== Reflow / descarte / pendências (§8.3) ====================
@dataclass
class ImpactoLocal:
    local_id: int
    campo: str
    caixas_reflowadas: int = 0
    sessoes_movidas: int = 0
    conclusoes: list = field(default_factory=list)   # {aluno, de, para}
    descartes: list = field(default_factory=list)    # {aluno, feitos, total}

    def tem(self) -> bool:
        return bool(self.sessoes_movidas or self.descartes or self.conclusoes)


@dataclass
class ResumoImpacto:
    locais: list = field(default_factory=list)        # ImpactoLocal
    novas_caixas: int = 0
    colocados: list = field(default_factory=list)     # {aluno, local, data_inicio}
    aguardando: list = field(default_factory=list)    # {aluno, area_id, motivo}

    def tem_mudanca(self) -> bool:
        return bool(any(i.tem() for i in self.locais) or self.novas_caixas
                    or self.colocados or self.aguardando)


def _nome_aluno(db: Session, aluno_id: int) -> str:
    a = db.get(Aluno, aluno_id)
    return a.nome if a else str(aluno_id)


def _tem_aloc_ativa(db: Session, matricula_id: int) -> bool:
    return db.scalars(select(Alocacao).where(
        Alocacao.matricula_id == matricula_id, Alocacao.status == StatusAlocacao.ativa
    )).first() is not None


def _alocs_ativas_do_grupo(db: Session, local_id: int, aluno_ids: list[int]) -> list[Alocacao]:
    if not aluno_ids:
        return []
    return list(db.scalars(select(Alocacao).where(
        Alocacao.local_id == local_id, Alocacao.status == StatusAlocacao.ativa,
        Alocacao.aluno_id.in_(aluno_ids),
    )).all())


def _descartar(db: Session, aloc: Alocacao, grupo_id: int, hoje: date, imp: ImpactoLocal) -> None:
    """Caixa não fecha no ciclo → cancela a alocação e as sessões FUTURAS, preserva as
    cumpridas (carry-forward) e devolve o aluno à fila (matrícula segue em_andamento)."""
    for s in db.scalars(select(Sessao).where(
        Sessao.alocacao_id == aloc.id, Sessao.status == StatusSessao.prevista, Sessao.data >= hoje
    )).all():
        s.status = StatusSessao.cancelada
    aloc.status = StatusAlocacao.cancelada
    ga = db.scalars(select(GrupoAluno).where(
        GrupoAluno.grupo_id == grupo_id, GrupoAluno.aluno_id == aloc.aluno_id
    )).first()
    if ga is not None:
        db.delete(ga)
    m = db.get(Matricula, aloc.matricula_id)
    if m is not None:
        m.data_conclusao_prevista = None  # matrícula segue em_andamento → volta à fila
        cont = encontros.contar_encontros(db, m)
        imp.descartes.append({"aluno": _nome_aluno(db, aloc.aluno_id),
                              "feitos": cont["feitos"], "total": cont["total"]})
    db.flush()


def _redistribuir_local(db: Session, ciclo, local: Local, ctx, hoje: date, resumo: ResumoImpacto) -> None:
    """Reflui as caixas do local de `hoje` em diante, ENCADEADAS (a próxima começa depois
    da anterior — o slot não roda 2 grupos juntos). Caixa que não fecha no ciclo é
    descartada com carry-forward (§8.3). Concluídas/passadas ficam intactas."""
    grupos = list(db.scalars(select(Grupo).where(
        Grupo.ciclo_id == ciclo.id, Grupo.local_id == local.id
    ).order_by(Grupo.data_inicio)).all())
    if not grupos:
        return
    n = local.numero_encontros or 0
    stream = [d for d in ocorrencias_dia(local.dia_semana, hoje, ciclo.data_fim)
              if not ctx.data_bloqueada(d, local)]
    ci = 0
    imp = ImpactoLocal(local_id=local.id, campo=local.campo)
    for g in grupos:
        if g.data_fim < hoje:
            continue  # caixa passada/concluída — intacta
        aluno_ids = [m.aluno_id for m in g.membros]
        alocs = _alocs_ativas_do_grupo(db, local.id, aluno_ids)
        em_andamento = g.data_inicio <= hoje

        if not alocs:                       # caixa vazia
            if em_andamento:
                continue                    # já rodando, sem alunos → não mexe
            block = stream[ci:ci + n]
            if len(block) < n:
                ci = len(stream)
                continue
            ci += n
            g.data_inicio, g.data_fim = block[0], block[-1]
            continue

        # caixa com alunos: futuras a re-datar (em andamento) ou todas (futura)
        fut: dict[int, list] = {}
        need = 0
        for a in alocs:
            q = select(Sessao).where(Sessao.alocacao_id == a.id)
            if em_andamento:
                q = q.where(Sessao.status == StatusSessao.prevista, Sessao.data >= hoje)
            fs = list(db.scalars(q.order_by(Sessao.data)).all())
            fut[a.id] = fs
            need = max(need, len(fs))

        block = stream[ci:ci + need]
        if len(block) < need:               # não fecha no ciclo → descarte + carry-forward
            for a in alocs:
                _descartar(db, a, g.id, hoje, imp)
            ci = len(stream)
            continue
        ci += need

        moved = 0
        for a in alocs:
            fs = fut[a.id]
            alvo = block[:len(fs)]
            for s, nd in zip(fs, alvo):
                if s.data != nd:
                    s.data = nd
                    moved += 1
            if alvo:
                a.data_fim_prevista = alvo[-1]
                if not em_andamento:
                    a.data_inicio = alvo[0]
                m = db.get(Matricula, a.matricula_id)
                if m is not None and m.data_conclusao_prevista != alvo[-1]:
                    imp.conclusoes.append({"aluno": _nome_aluno(db, a.aluno_id),
                                           "de": m.data_conclusao_prevista, "para": alvo[-1]})
                    m.data_conclusao_prevista = alvo[-1]
        if moved:
            imp.caixas_reflowadas += 1
            imp.sessoes_movidas += moved
        if not em_andamento:
            g.data_inicio = block[0]
        g.data_fim = block[-1]

    if imp.tem():
        resumo.locais.append(imp)
    db.flush()


def _materializar_faltantes(db: Session, ciclo, ctx, hoje: date) -> int:
    """Cria os Grupos que faltam para os locais ativos (novo local §8.4 + caixas
    sempre visíveis, mesmo vazias). Retorna quantas caixas foram criadas."""
    criadas = 0
    for local in molde.locais_ativos(db, ciclo):
        if local.docente_id is None:
            continue
        existentes = {g.onda for g in db.scalars(select(Grupo).where(
            Grupo.ciclo_id == ciclo.id, Grupo.local_id == local.id)).all()}
        for cx in molde.caixas_do_local(local, ciclo, ctx):
            if cx.onda in existentes:
                continue
            status = StatusGrupo.em_andamento if cx.data_inicio <= hoje else StatusGrupo.previsto
            db.add(Grupo(ciclo_id=ciclo.id, local_id=local.id, area_id=cx.area_id, onda=cx.onda,
                         status=status, data_inicio=cx.data_inicio, data_fim=cx.data_fim))
            criadas += 1
    db.flush()
    return criadas


def _colocar_aguardando(db: Session, ciclo, ctx, hoje: date, resumo: ResumoImpacto) -> None:
    """Coloca matrículas em_andamento SEM alocação ativa (aluno novo §8.1, troca de área
    §8.6, ou aluno vindo de descarte) na caixa FUTURA mais cedo com vaga viável."""
    mv = estado.carregar_molde_vivo(db, ciclo, ctx)
    mats = db.scalars(select(Matricula).join(Aluno, Matricula.aluno_id == Aluno.id)
        .where(Aluno.ciclo_id == ciclo.id, Matricula.status == StatusMatricula.em_andamento)
        .order_by(Aluno.ordenamento)).all()
    for m in mats:
        if _tem_aloc_ativa(db, m.id):
            continue
        aluno_id = m.aluno_id
        comp = mv.compromissos(aluno_id)
        bloq = _bloqueados(db, aluno_id)
        cands = sorted([(gid, cx) for gid, cx in mv.por_area(m.area_id)
                        if cx.data_inicio > hoje and cx.tem_vaga()], key=lambda t: t[1].data_inicio)
        colocado = False
        for gid, cx in cands:
            if viola_restricoes(comp, cx, bloq) is None:
                estado.sentar(db, aluno_id, cx, gid, m.id, fixado=False)
                cx.ocupantes.append(aluno_id)
                resumo.colocados.append({"aluno": _nome_aluno(db, aluno_id),
                                         "local": cx.local.campo, "data_inicio": cx.data_inicio})
                colocado = True
                break
        if not colocado:
            resumo.aguardando.append({"aluno": _nome_aluno(db, aluno_id),
                                      "area_id": m.area_id, "motivo": "sem caixa futura viável"})


def _processar_pendencias(db: Session, ciclo, hoje: date | None = None) -> ResumoImpacto:
    """Reconcilia a escala com o estado atual da infraestrutura, PONTUALMENTE (§7.3):
    materializa caixas faltantes, reflui/descarta as afetadas e coloca a fila em caixas
    futuras. Não commita — quem chama decide (aplicar = commit; simular = rollback)."""
    hoje = hoje or date.today()
    ctx = calendario.carregar_contexto(db, ciclo)
    resumo = ResumoImpacto()
    resumo.novas_caixas = _materializar_faltantes(db, ciclo, ctx, hoje)
    local_ids = sorted({g.local_id for g in db.scalars(
        select(Grupo).where(Grupo.ciclo_id == ciclo.id)).all()})
    for lid in local_ids:
        local = db.get(Local, lid)
        if local is not None:
            _redistribuir_local(db, ciclo, local, ctx, hoje, resumo)
    _colocar_aguardando(db, ciclo, ctx, hoje, resumo)
    return resumo


def simular_impacto(db: Session, ciclo=None) -> ResumoImpacto:
    """DRY-RUN (§7.3): calcula o impacto de aplicar as pendências SEM persistir.
    Usa um savepoint que é revertido no fim — reaproveita exatamente a lógica do apply."""
    ciclo = ciclo or common.exigir_ciclo_ativo(db)
    sp = db.begin_nested()
    try:
        return _processar_pendencias(db, ciclo)
    finally:
        sp.rollback()


def aplicar_pendencias(db: Session, ciclo=None) -> ResumoImpacto:
    """Aplica as pendências PONTUALMENTE (§7.3) e limpa a fila + o banner."""
    ciclo = ciclo or common.exigir_ciclo_ativo(db)
    resumo = _processar_pendencias(db, ciclo)
    db.execute(delete(FilaRemanejo).where(FilaRemanejo.ciclo_id == ciclo.id))
    ciclo.escala_desatualizada = False
    common.registrar_atividade(db, ciclo, "Remanejo aplicado (ajuste pontual).")
    common.commit(db, "Não foi possível aplicar o remanejo.")
    return resumo


def reflow_afastamento(db: Session, local_id: int, dia_afetado: date | None = None) -> dict:
    """Reflow pontual de UM local (§8.3) — usado pelo endpoint direto. Empurra as sessões
    futuras (a partir de hoje) e descarta com carry-forward se não fechar no ciclo."""
    local = common.obter_ou_404(db, Local, local_id, "Local")
    ciclo = local.ciclo
    ctx = calendario.carregar_contexto(db, ciclo)
    resumo = ResumoImpacto()
    _redistribuir_local(db, ciclo, local, ctx, date.today(), resumo)
    common.registrar_atividade(db, ciclo, f"Reflow em {local.campo}.")
    common.commit(db, "Não foi possível reprocessar as datas.")
    imp = resumo.locais[0] if resumo.locais else None
    return {"caixas_afetadas": imp.caixas_reflowadas if imp else 0,
            "sessoes_movidas": imp.sessoes_movidas if imp else 0,
            "descartes": len(imp.descartes) if imp else 0}
