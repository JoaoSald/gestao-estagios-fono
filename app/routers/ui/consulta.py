"""Superfície de LEITURA — o que se alcança sem poder editar (FASE 6).

Dois alcances, porque leitura não é um bloco só:
  * `router`       — a ESCALA (3 abas, calendário do aluno, downloads): todo perfil;
  * `router_amplo` — a OPERAÇÃO em leitura (painel, histórico): comissão + docente. Fala de
    fila, pendências e egressos, que não são assunto do aluno.


Existe como router próprio porque o gate é de rota: `paginas.py` e `escala.py` penduram
`exigir_coordenacao` no router inteiro, e a escala (a aba de Estágios, o modal de
encontros e os downloads) é justamente o que precisa ficar de fora desse gate. Juntar as
duas coisas no mesmo router obrigaria a repetir permissão rota por rota — e a primeira
rota nova esquecida vazaria a comissão inteira ou trancaria o aluno.

Coordenação também passa por aqui (é a mesma tela): o que muda é `pode_editar`, que
libera as ações no template. Aluno e docente veem a escala COMPLETA da turma, sem ações.

As rotas são um espelho fino: a montagem do contexto continua em `escala.py`,
`aluno_dados.py` e `services/exportacao.py`, para não haver duas versões da mesma tela.
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.templates import templates
from app.routers.ui.deps import (
    destino_por_estado, exigir_leitura_ampla, exigir_operacao, exigir_sessao, render,
    sessao_opcional,
)
from app.services import common, exportacao

# Escala + downloads: qualquer perfil autenticado, mas só com ciclo `em_andamento`.
router = APIRouter(prefix="/ui", tags=["ui-consulta"],
                   dependencies=[Depends(exigir_sessao), Depends(exigir_operacao)])

# Operação em leitura (painel, histórico): comissão + docente.
router_amplo = APIRouter(prefix="/ui", tags=["ui-consulta"],
                         dependencies=[Depends(exigir_leitura_ampla), Depends(exigir_operacao)])

# Fora do gate de operação (senão a espera viraria um laço de redirect).
router_livre = APIRouter(prefix="/ui", tags=["ui-consulta"],
                         dependencies=[Depends(exigir_sessao)])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _anexo(nome: str) -> str:
    """Content-Disposition com fallback ASCII + filename* (RFC 5987) p/ acentos."""
    return f"attachment; filename={exportacao.slug(nome)}; filename*=UTF-8''{quote(nome)}"


# ============================ Estágios (as 3 abas) ============================
@router.get("/estagios")
def pagina_estagios(request: Request, vista: str = "aluno", local: str | None = None,
                    area: str | None = None, mes: str | None = None, fase: str = "todos",
                    db: Session = Depends(get_db)):
    from app.routers.ui.escala import _ctx_conteudo
    dados = _ctx_conteudo(db, vista, local, area, mes, fase)
    return render(request, db, "estagios.html", "estagios", **dados)


@router.get("/estagios/conteudo")
def estagios_conteudo(request: Request, vista: str = "aluno", local: str | None = None,
                      area: str | None = None, mes: str | None = None, fase: str = "todos",
                      db: Session = Depends(get_db)):
    from app.routers.ui.escala import _ctx_conteudo
    return templates.TemplateResponse(request, "partials/estagios_conteudo.html",
                                      _ctx_conteudo(db, vista, local, area, mes, fase))


@router.get("/estagios/campo-cal")
def estagios_campo_cal(request: Request, local: int, mes: str | None = None,
                       db: Session = Depends(get_db)):
    from app.routers.ui.escala import _cal_campo
    from app.routers.ui import estagios_dados as ed
    ciclo = common.exigir_ciclo_ativo(db)
    campo = ed.dados_por_campo(db, ciclo, local)
    return templates.TemplateResponse(request, "partials/_cal.html",
                                      {"cal": _cal_campo(db, ciclo, campo, mes)})


# ============================ Calendário do aluno (modal da aba "Por aluno") ============================
@router.get("/alunos/{aluno_id:int}/encontros")
def aluno_encontros(aluno_id: int, request: Request, db: Session = Depends(get_db)):
    from app.routers.ui.aluno_dados import montar_encontros
    return templates.TemplateResponse(request, "partials/encontros_modal.html",
                                      montar_encontros(db, aluno_id, None))


@router.get("/alunos/{aluno_id:int}/encontros-cal")
def aluno_encontros_cal(aluno_id: int, request: Request, mes: str | None = None,
                        db: Session = Depends(get_db)):
    from app.routers.ui.aluno_dados import montar_encontros
    return templates.TemplateResponse(request, "partials/_cal.html",
                                      {"cal": montar_encontros(db, aluno_id, mes)["cal"]})


# ============================ Downloads ============================
# São a MESMA informação já visível nas 3 abas, em outro formato — por isso seguem o
# gate da tela, e não o de escrita.
@router.get("/estagios/grupos.xlsx")
def exportar_grupos(db: Session = Depends(get_db)) -> Response:
    ciclo = common.exigir_ciclo_ativo(db)
    conteudo = exportacao.grupos_xlsx(db, ciclo)
    nome = f"grupos_{ciclo.data_inicio.year}.xlsx"
    return Response(content=conteudo, media_type=XLSX_MIME,
                    headers={"Content-Disposition": _anexo(nome)})


@router.get("/estagios/grupos.pdf")
def exportar_grupos_pdf(db: Session = Depends(get_db)) -> Response:
    ciclo = common.exigir_ciclo_ativo(db)
    conteudo = exportacao.grupos_pdf(db, ciclo)
    nome = f"grupos_{ciclo.data_inicio.year}.pdf"
    return Response(content=conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": _anexo(nome)})


@router.get("/alunos/{aluno_id:int}/calendario.ics")
def exportar_calendario_aluno(aluno_id: int, db: Session = Depends(get_db)) -> Response:
    nome, conteudo = exportacao.calendario_aluno_ics(db, aluno_id)
    return Response(content=conteudo, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": _anexo(nome)})


@router.get("/alunos/{aluno_id:int}/calendario.pdf")
def exportar_calendario_aluno_pdf(aluno_id: int, db: Session = Depends(get_db)) -> Response:
    nome, conteudo = exportacao.calendario_aluno_pdf(db, aluno_id)
    return Response(content=conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": _anexo(nome)})


# ============================ Operação em leitura (comissão + docente) ============================
@router_amplo.get("/painel")
def painel(request: Request, db: Session = Depends(get_db)):
    from app.routers.ui.painel_dados import montar_painel
    return render(request, db, "painel.html", "painel", **montar_painel(db))


@router_amplo.get("/historico")
def pagina_historico(request: Request, ano: int | None = None, db: Session = Depends(get_db)):
    from app.routers.ui.paginas import _ctx_historico
    return render(request, db, "historico.html", "historico", **_ctx_historico(db, ano))


@router_amplo.get("/historico/{hist_id}")
def historico_detalhe(hist_id: int, request: Request, db: Session = Depends(get_db)):
    from app.models.operacao import Historico
    h = db.get(Historico, hist_id)
    return templates.TemplateResponse(request, "partials/historico_detalhe.html", {"h": h})


# ============================ Espera (escala não publicada) ============================
@router_livre.get("/aguarde")
def aguarde(request: Request, db: Session = Depends(get_db)):
    """"A escala ainda não foi publicada" — destino de leitura fora de `em_andamento`.

    Quem tem para onde ir é mandado para lá (coordenação → bootstrap/bem-vindo; leitor com
    ciclo já em andamento → a escala). Só quem realmente não tem nada para ver fica nesta
    tela — o destino é calculado pela mesma função do resto do gate, então não há como as
    duas leituras divergirem.
    """
    sessao = sessao_opcional(request)
    destino = destino_por_estado(db, sessao)
    if destino != "/ui/aguarde":
        return RedirectResponse(destino, status_code=303)
    ciclo = common.get_ciclo_ativo(db)
    return templates.TemplateResponse(request, "aguarde.html", {
        "ciclo": ciclo,
        "titulo": "Aguardando publicação · Gestão de Estágios",
    })
