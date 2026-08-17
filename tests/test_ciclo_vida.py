"""Ciclo de vida (FASE 8): roteamento por estado, bootstrap, montagem, encerrar."""
from __future__ import annotations

from sqlalchemy import func, select

from app.core import passos
from app.models.catalogo import Docente
from app.models.enums import StatusCiclo
from app.models.escala import Grupo
from app.models.operacao import Historico
from app.services.common import get_ciclo_ativo
import tests.factories as f


def _login(client):
    client.post("/login")


def test_home_roteia_para_painel_em_andamento(client):
    _login(client)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/ui/painel"


def test_rascunho_roteia_para_bootstrap_e_navega(client, db_session):
    _login(client)
    cic = get_ciclo_ativo(db_session)
    cic.status = StatusCiclo.rascunho
    cic.passo_bootstrap = 1
    db_session.flush()

    r = client.get("/", follow_redirects=False)
    assert r.headers["location"] == "/ui/bootstrap"
    b = client.get("/ui/bootstrap")
    assert b.status_code == 200 and "Bootstrap · passo" in b.text
    rp = client.post("/ui/bootstrap/passo/2", follow_redirects=False)
    assert rp.status_code == 303
    db_session.refresh(cic)
    assert cic.passo_bootstrap == 2


def test_bootstrap_oferta_resumo_e_alunos_por_fase(client, db_session):
    """Passos referenciados pela CHAVE (`core/passos.py`) — a ordem pode mudar sem quebrar."""
    _login(client)
    cic = get_ciclo_ativo(db_session)
    cic.status = StatusCiclo.rascunho
    db_session.flush()
    ar = f.area(db_session, carga=16)
    f.local(db_session, cic, ar, capacidade=4)
    f.aluno(db_session, cic, nome="Fase Sete", semestre=7)

    cic.passo_bootstrap = passos.numero("oferta")
    db_session.flush()
    p3 = client.get("/ui/bootstrap")
    assert p3.status_code == 200 and "slot(s)" in p3.text and "area-pill" in p3.text

    cic.passo_bootstrap = passos.numero("alunos")
    db_session.flush()
    p7 = client.get("/ui/bootstrap")
    assert "7º semestre" in p7.text and "9º/10º semestre" in p7.text


def test_bootstrap_config_area_mae_sub_e_tema(client, db_session):
    _login(client)
    cic = get_ciclo_ativo(db_session)
    cic.status = StatusCiclo.rascunho
    cic.passo_bootstrap = passos.numero("campo")
    db_session.flush()
    b = client.get("/ui/bootstrap")
    assert b.status_code == 200
    assert "area-pill" in b.text          # área colorida na config de campo
    assert " - " in b.text                # rótulo Mãe - Sub (ex.: Hospitalar - Adulto)
    assert 'id="btn-tema"' in b.text       # ícone de tema (sol/lua)


def test_aluno_form_matriculas_coloridas_e_restricoes(client, db_session):
    _login(client)
    r = client.get("/ui/alunos/form")
    assert r.status_code == 200
    assert "area-pill" in r.text and "Disponibilidade por local" in r.text


def test_bootstrap_stepper_clicavel(client, db_session):
    _login(client)
    cic = get_ciclo_ativo(db_session)
    cic.status = StatusCiclo.rascunho
    cic.passo_bootstrap = 4
    db_session.flush()
    b = client.get("/ui/bootstrap")
    # passos já visitados viram formulários clicáveis (voltar)
    assert 'action="/ui/bootstrap/passo/1"' in b.text


def test_config_de_campo_define_docente(client, db_session):
    _login(client)
    cic = get_ciclo_ativo(db_session)
    cic.status = StatusCiclo.rascunho
    db_session.flush()
    ar = f.area(db_session, carga=16)
    loc = f.local(db_session, cic, ar)
    doc = db_session.scalars(select(Docente)).first()
    r = client.post(f"/ui/locais/{loc.id}/config", data={"docente_id": doc.id, "preceptor": ""})
    assert r.status_code == 204
    db_session.refresh(loc)
    assert loc.docente_id == doc.id


def test_montagem_colocar_gerar_confirmar(client, db_session):
    _login(client)
    cic = get_ciclo_ativo(db_session)
    cic.status = StatusCiclo.rascunho
    cic.passo_bootstrap = passos.numero("montagem")
    db_session.flush()
    ar = f.area(db_session, carga=16)
    loc = f.local(db_session, cic, ar, capacidade=4)
    al = f.aluno(db_session, cic, nome="Prio Mont", prioridade=True)
    f.matricular(db_session, al, ar)
    db_session.flush()

    b = client.get("/ui/bootstrap")
    assert "Prio Mont" in b.text and "data-grupo" in b.text

    g = db_session.scalars(select(Grupo).where(Grupo.local_id == loc.id).order_by(Grupo.onda)).first()
    rc = client.post("/ui/montagem/colocar", data={"grupo_id": g.id, "aluno_id": al.id})
    assert rc.status_code == 200 and "Prio Mont" in rc.text

    rg = client.post("/ui/bootstrap/gerar")
    assert rg.status_code == 200 and "gerada" in rg.text.lower()
    assert "Grupos formados por área" in rg.text  # relatório = view de Grupos (bootstrap.js §10)

    rf = client.post("/ui/bootstrap/confirmar")
    assert rf.status_code == 204 and rf.headers.get("HX-Redirect") == "/ui/painel"
    db_session.refresh(cic)
    assert cic.status == StatusCiclo.em_andamento


def test_montagem_baixa_grade_das_ondas_em_pdf(client, db_session):
    """A grade que a tela desenha, em PDF, para levar impressa à reunião de prioridades.

    Sai com o ciclo em RASCUNHO (a Montagem é passo do bootstrap) — por isso a rota vive no
    router do bootstrap e não em `ui/exportacao.py`, que exige ciclo em andamento.
    """
    _login(client)
    cic = get_ciclo_ativo(db_session)
    cic.status = StatusCiclo.rascunho
    cic.passo_bootstrap = passos.numero("montagem")
    db_session.flush()
    ar = f.area(db_session, nome="Área PDF Montagem", carga=16)
    loc = f.local(db_session, cic, ar, capacidade=4, campo="Campo PDF")
    al = f.aluno(db_session, cic, nome="Prio PDF", prioridade=True)
    f.matricular(db_session, al, ar)
    db_session.flush()

    # o botão está na tela do passo
    b = client.get("/ui/bootstrap")
    assert "/ui/montagem/grade.pdf" in b.text

    g = db_session.scalars(select(Grupo).where(Grupo.local_id == loc.id)
                           .order_by(Grupo.onda)).first()
    client.post("/ui/montagem/colocar", data={"grupo_id": g.id, "aluno_id": al.id})

    r = client.get("/ui/montagem/grade.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "montagem_ondas_" in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF-") and len(r.content) > 1000
    # o PDF é gerado de verdade (reportlab), então o conteúdo é conferido no texto extraído
    texto = _texto_pdf(r.content)
    assert "grade das ondas por área" in texto
    assert "Área PDF Montagem" in texto and "Campo PDF" in texto
    assert "Onda 1" in texto
    assert "Prio PDF" in texto          # o aluno pinado à mão aparece no grupo


def _texto_pdf(conteudo: bytes) -> str:
    """Texto do PDF sem depender de leitor externo.

    O reportlab grava os content streams em ASCII85 + Flate (nesta ordem de decodificação),
    e o texto visível sai nos operadores Tj/TJ, entre parênteses. Cada tentativa de decode
    tem fallback porque isso depende da versão/configuração da lib.
    """
    import base64
    import re
    import zlib
    partes = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", conteudo, re.S):
        dado = m.group(1).strip()
        try:
            dado = base64.a85decode(dado, adobe=not dado.startswith(b"<~"))
        except ValueError:
            pass
        try:
            dado = zlib.decompress(dado)
        except zlib.error:
            pass
        partes.append(dado)
    bruto = b"\n".join(partes).decode("latin-1")

    def literal(m) -> str:
        # dentro do literal PDF, acento vem como \341 (octal, latin-1) e ( ) \ vêm escapados
        s = re.sub(r"\\([0-7]{1,3})", lambda o: chr(int(o.group(1), 8)), m.group(0)[1:-1])
        return s.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")

    # (texto) Tj  |  [(a) (b)] TJ — junta todos os literais na ordem em que aparecem
    return " ".join(literal(m) for m in re.finditer(r"\((?:\\.|[^()\\])*\)", bruto))


def test_encerrar_grava_historico(client, db_session):
    _login(client)
    cic = get_ciclo_ativo(db_session)
    ano = cic.data_inicio.year
    al = f.aluno(db_session, cic, nome="Enc Aluno")
    ar = f.area(db_session, carga=16)
    f.matricular(db_session, al, ar)
    db_session.flush()

    for e in (1, 2, 3):
        assert client.get(f"/ui/encerrar?etapa={e}").status_code == 200

    errado = client.post("/ui/ciclos/encerrar", data={"ano": "1999"})
    assert "field-err" in errado.text and cic.status == StatusCiclo.em_andamento

    ok = client.post("/ui/ciclos/encerrar", data={"ano": str(ano)}, follow_redirects=False)
    assert ok.status_code == 303 and ok.headers["location"] == "/ui/bem-vindo"
    db_session.refresh(cic)
    assert cic.status == StatusCiclo.encerrado
    n = db_session.scalar(select(func.count()).select_from(Historico).where(Historico.ciclo_id == cic.id))
    assert n >= 1
