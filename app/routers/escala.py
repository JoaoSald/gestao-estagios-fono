"""Rotas do motor de escala (FASE 4): geração, leitura, ajuste manual, montagem e
eventos de meio de ciclo. Tudo JSON — as telas são da FASE 5."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.aluno import Aluno, Matricula
from app.models.catalogo import Area
from app.models.ciclo import Ciclo
from app.models.enums import StatusAlocacao, StatusMatricula
from app.models.escala import Alocacao, Grupo, Sessao
from app.models.local import Local
from app.schemas.escala import (
    AdicionarBody, AjusteResultado, AlocacaoOut, BancoItemOut, CHSemanalOut,
    DeltaBody, EncontrosOut, EscalaAlunoOut, GrupoOut, MembroOut, MoverBody,
    PrioridadeBody, ReflowBody, RelatorioGeracao, RemoverBody, SessaoOut, SubstituirBody,
)
from app.services import aluno as aluno_service
from app.services import common
from app.services.motor import ajuste, encontros, escala, eventos_ciclo, montagem
from app.schemas.aluno import AlunoUpdate

router = APIRouter(tags=["escala"])


def _resultado(r: ajuste.ResultadoAjuste) -> AjusteResultado:
    return AjusteResultado(ok=r.ok, motivos=r.motivos, sugestao=r.sugestao)


# ============================ Geração ============================
@router.post("/ciclos/{ciclo_id}/escala/gerar", response_model=RelatorioGeracao)
def gerar(ciclo_id: int, db: Session = Depends(get_db)):
    ciclo = common.obter_ou_404(db, Ciclo, ciclo_id, "Ciclo")
    rel = escala.gerar_escala(db, ciclo)
    return RelatorioGeracao.model_validate(rel)


# ============================ Leitura ============================
@router.get("/ciclos/{ciclo_id}/grupos", response_model=list[GrupoOut])
def listar_grupos(ciclo_id: int, db: Session = Depends(get_db)):
    common.obter_ou_404(db, Ciclo, ciclo_id, "Ciclo")
    grupos = db.scalars(
        select(Grupo).where(Grupo.ciclo_id == ciclo_id).order_by(Grupo.area_id, Grupo.local_id, Grupo.onda)
    ).all()
    nomes = {a.id: a.nome for a in db.scalars(select(Aluno).where(Aluno.ciclo_id == ciclo_id)).all()}
    saida: list[GrupoOut] = []
    for g in grupos:
        area = db.get(Area, g.area_id)
        local = db.get(Local, g.local_id)
        membros = [
            MembroOut(aluno_id=m.aluno_id, nome=nomes.get(m.aluno_id, "?"),
                      fixado=m.fixado, aviso=m.aviso)
            for m in g.membros
        ]
        saida.append(GrupoOut(
            id=g.id, local_id=g.local_id, local_campo=local.campo if local else "?",
            area_id=g.area_id, area_nome=area.nome if area else "?", onda=g.onda,
            status=g.status.value, data_inicio=g.data_inicio, data_fim=g.data_fim,
            capacidade=local.capacidade if local else len(membros),
            ocupacao=len(membros), membros=membros,
        ))
    return saida


@router.get("/alunos/{aluno_id}/escala", response_model=EscalaAlunoOut)
def escala_do_aluno(aluno_id: int, db: Session = Depends(get_db)):
    aluno = common.obter_ou_404(db, Aluno, aluno_id, "Aluno")
    alocs = db.scalars(select(Alocacao).where(
        Alocacao.aluno_id == aluno_id, Alocacao.status == StatusAlocacao.ativa
    )).all()
    saida_alocs: list[AlocacaoOut] = []
    areas_alocadas: set[int] = set()
    for a in alocs:
        area = db.get(Area, a.local.area_id) if a.local else None
        areas_alocadas.add(a.matricula.area_id)
        cont = encontros.contar_encontros(db, a.matricula)
        sess = db.scalars(select(Sessao).where(Sessao.alocacao_id == a.id).order_by(Sessao.data)).all()
        saida_alocs.append(AlocacaoOut(
            id=a.id, local_id=a.local_id, local_campo=a.local.campo if a.local else "?",
            area_id=a.matricula.area_id, area_nome=area.nome if area else "?",
            data_inicio=a.data_inicio, data_fim_prevista=a.data_fim_prevista,
            travada=a.travada, status=a.status.value,
            total=cont["total"], feitos=cont["feitos"],
            sessoes=[SessaoOut(id=s.id, data=s.data, hora_inicio=s.hora_inicio,
                               hora_fim=s.hora_fim, horas=s.horas, status=s.status.value)
                     for s in sess],
        ))
    aguardando = [
        m.area_id for m in db.scalars(select(Matricula).where(
            Matricula.aluno_id == aluno_id, Matricula.status == StatusMatricula.em_andamento
        )).all()
        if m.area_id not in areas_alocadas
    ]
    return EscalaAlunoOut(
        aluno_id=aluno.id, nome=aluno.nome, ordenamento=aluno.ordenamento,
        alocacoes=saida_alocs, aguardando_areas=aguardando,
    )


# ======================= Ajuste manual (§9) =======================
@router.post("/escala/mover", response_model=AjusteResultado)
def mover(body: MoverBody, db: Session = Depends(get_db)):
    return _resultado(ajuste.mover(db, body.aluno_id, body.grupo_origem, body.grupo_destino))


@router.post("/escala/adicionar", response_model=AjusteResultado)
def adicionar(body: AdicionarBody, db: Session = Depends(get_db)):
    return _resultado(ajuste.adicionar_da_fila(db, body.aluno_id, body.grupo_id))


@router.post("/escala/remover", response_model=AjusteResultado)
def remover(body: RemoverBody, db: Session = Depends(get_db)):
    return _resultado(ajuste.remover(db, body.aluno_id, body.grupo_id))


@router.post("/escala/substituir", response_model=AjusteResultado)
def substituir(body: SubstituirBody, db: Session = Depends(get_db)):
    return _resultado(ajuste.substituir(db, body.aluno_a, body.grupo_a, body.aluno_b, body.grupo_b))


@router.post("/grupos/{grupo_id}/membros/{aluno_id}/travar", status_code=204)
def travar(grupo_id: int, aluno_id: int, db: Session = Depends(get_db)):
    ajuste.travar(db, grupo_id, aluno_id, True)


@router.post("/grupos/{grupo_id}/membros/{aluno_id}/destravar", status_code=204)
def destravar(grupo_id: int, aluno_id: int, db: Session = Depends(get_db)):
    ajuste.travar(db, grupo_id, aluno_id, False)


# ======================= Encontros (§10.5) =======================
@router.post("/alocacoes/{alocacao_id}/encontros", response_model=EncontrosOut)
def ajustar_encontros(alocacao_id: int, body: DeltaBody, db: Session = Depends(get_db)):
    cont = encontros.ajustar_encontros(db, alocacao_id, body.delta)
    return EncontrosOut(total=cont["total"], feitos=cont["feitos"])


# ==================== Eventos de meio de ciclo (§10) ====================
@router.post("/alunos/{aluno_id}/matriculas/{area_id}/encaixar", response_model=AjusteResultado)
def encaixar(aluno_id: int, area_id: int, db: Session = Depends(get_db)):
    return _resultado(eventos_ciclo.nova_matricula(db, aluno_id, area_id))


@router.post("/locais/{local_id}/materializar")
def materializar_local(local_id: int, db: Session = Depends(get_db)):
    return eventos_ciclo.novo_local(db, local_id)


@router.post("/escala/reflow")
def reflow(body: ReflowBody, db: Session = Depends(get_db)):
    return eventos_ciclo.reflow_afastamento(db, body.local_id, body.dia_afetado)


# ======================= Montagem dos grupos (AR-8) =======================
@router.post("/ciclos/{ciclo_id}/montagem/materializar", response_model=list[GrupoOut])
def montagem_materializar(ciclo_id: int, db: Session = Depends(get_db)):
    ciclo = common.obter_ou_404(db, Ciclo, ciclo_id, "Ciclo")
    montagem.materializar(db, ciclo)
    return listar_grupos(ciclo_id, db)


@router.get("/ciclos/{ciclo_id}/montagem/banco", response_model=list[BancoItemOut])
def montagem_banco(ciclo_id: int, db: Session = Depends(get_db)):
    ciclo = common.obter_ou_404(db, Ciclo, ciclo_id, "Ciclo")
    return [BancoItemOut(**item) for item in montagem.banco_prioridade(db, ciclo)]


@router.post("/grupos/{grupo_id}/colocar/{aluno_id}", response_model=AjusteResultado)
def montagem_colocar(grupo_id: int, aluno_id: int, db: Session = Depends(get_db)):
    return _resultado(montagem.colocar(db, aluno_id, grupo_id))


@router.delete("/grupos/{grupo_id}/colocar/{aluno_id}", status_code=204)
def montagem_descolocar(grupo_id: int, aluno_id: int, db: Session = Depends(get_db)):
    montagem.descolocar(db, aluno_id, grupo_id)


@router.get("/alunos/{aluno_id}/ch-semanal", response_model=CHSemanalOut)
def ch_semanal(aluno_id: int, db: Session = Depends(get_db)):
    return CHSemanalOut(aluno_id=aluno_id, ch_semanal=montagem.ch_semanal(db, aluno_id))


@router.post("/alunos/{aluno_id}/prioridade", status_code=204)
def definir_prioridade(aluno_id: int, body: PrioridadeBody, db: Session = Depends(get_db)):
    aluno_service.atualizar(db, aluno_id, AlunoUpdate(prioridade=body.prioridade))
