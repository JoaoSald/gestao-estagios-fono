"""Diagnóstico da OFERTA antes de gerar a escala.

Três coisas que a comissão só conseguia saber gerando a escala inteira:

  1. **este slot fecha grupo?** — `numero_encontros` do espelho × datas viáveis do ciclo
     (feriados/afastamentos/recesso derrubam datas; bloco incompleto é descartado, §4
     passo 5). Um local que não fecha nenhum grupo é capacidade perdida.
  2. **quando cada estágio acontece** — a semana desenhada por hora, para ver de relance
     o que cai no mesmo horário.
  3. **as vagas cobrem as matrículas?** — vagas reais do ciclo (grupos que fecham ×
     alunos por grupo) contra a demanda de cada área.

Roda **só a Fase 1** do motor (`molde.materializar_molde`/`caixas_do_local` são puros: não
tocam o banco, não persistem grupo nenhum), então pode ser chamado a cada render do wizard.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from math import ceil
from time import monotonic         # `time` aqui é o datetime.time — o relógio vem separado

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rotulos import rotulo
from app.models.aluno import Aluno, Matricula
from app.models.catalogo import Area
from app.models.ciclo import Ciclo
from app.models.enums import DiaSemana, StatusMatricula
from app.models.local import Local
from app.services import area as area_service
from app.services.motor import calendario, molde

# Ordem de exibição (a do calendário, não a alfabética do enum).
ORDEM_DIA = list(calendario.IDX_DIA.keys())
# Dias em que o curso PODE ofertar estágio. Segunda a sexta sempre entram como hipótese
# de "que dia abrir", mesmo que o ciclo ainda não use nenhum local naquele dia — era esse
# o furo do painel: um ciclo que só ofertava terça e quarta não recebia sugestão nenhuma
# (a área da fila já existia nos dois dias), e a tela caía num "nenhum dia livre resolve"
# que na verdade queria dizer "não testei nenhum dia novo". Sábado/domingo continuam fora
# a menos que o ciclo já oferte lá — sugerir fim de semana nunca foi resposta.
DIAS_LETIVOS = (DiaSemana.segunda, DiaSemana.terca, DiaSemana.quarta,
                DiaSemana.quinta, DiaSemana.sexta)


# ============================ Validador de locais ============================
@dataclass
class SlotValidado:
    """Veredito de um slot: fecha grupo? quantos? com que capacidade e que CH?"""
    local: Local
    area_nome: str
    area_cor: str | None
    area_carga_exigida: int
    ocorrencias: int              # ocorrências do dia no ciclo, antes dos bloqueios
    viaveis: int                  # datas que sobraram
    ondas: int                    # grupos COMPLETOS que fecham no ciclo
    capacidade_efetiva: int       # ondas × capacidade = vagas reais do slot no ciclo
    ch_derivada: float            # encontros × horas por encontro
    ch_sugerida: float            # o mesmo, com o nº de encontros sugerido
    status: str                   # 'ok' | 'atencao' | 'falha'
    # 'sem_docente' | 'encontros_invalidos' | 'datas_insuficientes' | 'ch_abaixo' | None
    causa: str | None = None
    motivos: list[str] = field(default_factory=list)

    @property
    def bloqueadas(self) -> int:
        return max(0, self.ocorrencias - self.viaveis)

    @property
    def encontros(self) -> int:
        return self.local.numero_encontros

    @property
    def sugerido(self) -> int:
        """Maior nº de encontros que ainda fecha 1 grupo neste slot (= datas viáveis)."""
        return self.viaveis

    @property
    def pode_sugerir(self) -> bool:
        """O atalho "↧ usar N" só existe para o slot que NÃO fecha por falta de datas.

        Em slot saudável ele seria um desserviço: um campo de 14 encontros com 40 datas
        viáveis fecha 2 grupos; subir para 40 encontros faria UM grupo ocupando o ciclo
        inteiro — menos vagas, não mais. A sugestão é conserto de falha, não otimização.
        """
        return self.causa == "datas_insuficientes" and self.viaveis > 0

    @property
    def ch_abaixo(self) -> float:
        """Quanto a CH do slot fica abaixo do exigido pela área (0 = em dia)."""
        return max(0.0, self.area_carga_exigida - self.ch_derivada)

    @property
    def ch_abaixo_sugerido(self) -> float:
        return max(0.0, self.area_carga_exigida - self.ch_sugerida)


def _validar_slot(local: Local, ciclo: Ciclo, ctx: calendario.ContextoCalendario,
                  area: Area | None, areas_map: dict[int, Area]) -> SlotValidado:
    ocorrencias = len(calendario.ocorrencias_dia(
        local.dia_semana, ciclo.data_inicio, ciclo.data_fim))
    sem_docente = local.docente_id is None
    # Sem docente o slot cai por cobertura em todas as datas (§4/§8.3) — não vale varrer.
    viaveis = 0 if sem_docente else len(ctx.datas_viaveis(local, ciclo))
    caixas = [] if sem_docente else molde.caixas_do_local(local, ciclo, ctx)
    horas = calendario.horas_sessao(local)
    carga_area = area.carga_exigida if area else 0

    sv = SlotValidado(
        local=local,
        area_nome=(area_service.nome_completo(area, areas_map) if area else "?"),
        area_cor=(area_service.cor_efetiva(area, areas_map) if area else None),
        area_carga_exigida=carga_area,
        ocorrencias=ocorrencias, viaveis=viaveis,
        ondas=len(caixas),
        capacidade_efetiva=len(caixas) * local.capacidade,
        ch_derivada=round(local.numero_encontros * horas, 1),
        ch_sugerida=round(viaveis * horas, 1),
        status="ok",
    )

    if sem_docente:
        sv.status, sv.causa = "falha", "sem_docente"
        sv.motivos.append("Sem docente responsável — o slot é pulado pelo motor.")
    elif local.numero_encontros <= 0:
        sv.status, sv.causa = "falha", "encontros_invalidos"
        sv.motivos.append(f"Número de encontros inválido ({local.numero_encontros}).")
    elif not caixas:
        sv.status, sv.causa = "falha", "datas_insuficientes"
        sv.motivos.append(
            f"Precisa de {local.numero_encontros} encontros e só há {viaveis} data(s) "
            f"viável(is) no ciclo — nenhum grupo fecha."
        )
    if sv.status != "falha" and sv.ch_abaixo > 0:
        sv.status, sv.causa = "atencao", "ch_abaixo"
        sv.motivos.append(
            f"CH do slot ({sv.ch_derivada:g}h) abaixo da exigida pela área "
            f"({carga_area}h) — faltam {sv.ch_abaixo:g}h."
        )
    return sv


def validar_locais(db: Session, ciclo: Ciclo) -> dict:
    """Veredito de todos os slots ativos + contagem por status. Não persiste nada."""
    ctx = calendario.carregar_contexto(db, ciclo)
    areas_map = {a.id: a for a in db.scalars(select(Area)).all()}
    slots = [
        _validar_slot(l, ciclo, ctx, areas_map.get(l.area_id), areas_map)
        for l in molde.locais_ativos(db, ciclo)
    ]
    slots.sort(key=lambda s: (s.area_nome, s.local.campo,
                              calendario.IDX_DIA[s.local.dia_semana], s.local.hora_inicio))
    # A tela lista só `problemas`: quem já está resolvido não precisa de conferência, e
    # 34 linhas verdes escondem as 3 que importam. Falha primeiro (não gera grupo nenhum).
    problemas = sorted([s for s in slots if s.status != "ok"],
                       key=lambda s: (s.status != "falha", s.area_nome, s.local.campo))
    return {
        "slots": slots,
        "problemas": problemas,
        "n_falha": sum(1 for s in slots if s.status == "falha"),
        "n_atencao": sum(1 for s in slots if s.status == "atencao"),
        "n_ok": sum(1 for s in slots if s.status == "ok"),
        "vagas_totais": sum(s.capacidade_efetiva for s in slots),
    }


# ============================ Análise da grade ============================
def _rotulo_faixa(ini: time, fim: time) -> str:
    return f"{ini.strftime('%H:%M')}–{fim.strftime('%H:%M')}"


def _hora_decimal(t: time) -> float:
    return t.hour + t.minute / 60.0


def linha_do_tempo(slots: list[SlotValidado]) -> dict:
    """T1b — cada dia como uma régua de horas, com um bloco colorido por estágio.

    Blocos que se cruzam na vertical (mesma faixa) são a imagem direta do conflito: o
    aluno só pode pegar um deles. Faixas são calculadas em % sobre a janela [min, max] de
    horários do ciclo, e slots sobrepostos são empilhados em "pistas" (greedy por hora de
    início) para nenhum bloco cobrir o outro.
    """
    if not slots:
        return {"dias": [], "horas": [], "ini": 0, "fim": 0}
    ini = int(min(_hora_decimal(s.local.hora_inicio) for s in slots))
    fim = int(-(-max(_hora_decimal(s.local.hora_fim) for s in slots) // 1))  # ceil
    span = max(1, fim - ini)

    dias = []
    for d in ORDEM_DIA:
        do_dia = sorted([s for s in slots if s.local.dia_semana == d],
                        key=lambda s: (s.local.hora_inicio, s.local.hora_fim))
        if not do_dia:
            continue
        pistas: list[float] = []          # hora de fim do último bloco de cada pista
        blocos = []
        for s in do_dia:
            h0, h1 = _hora_decimal(s.local.hora_inicio), _hora_decimal(s.local.hora_fim)
            alvo = next((i for i, ate in enumerate(pistas) if ate <= h0), None)
            if alvo is None:
                pistas.append(h1)
                alvo = len(pistas) - 1
            else:
                pistas[alvo] = h1
            blocos.append({
                "slot": s, "pista": alvo,
                "esquerda": round((h0 - ini) / span * 100, 3),
                "largura": round((h1 - h0) / span * 100, 3),
                "faixa": _rotulo_faixa(s.local.hora_inicio, s.local.hora_fim),
            })
        dias.append({"dia": rotulo(d), "blocos": blocos, "pistas": len(pistas)})
    return {"dias": dias, "horas": list(range(ini, fim + 1)), "ini": ini, "fim": fim}


def capacidade_vs_demanda(db: Session, ciclo: Ciclo, slots: list[SlotValidado]) -> list[dict]:
    """T4 — por área: matrículas em andamento × vagas que a oferta realmente fecha.

    É a tabela que antecipa a fila: saldo negativo = alunos que vão sobrar, calculado
    ANTES de gerar a escala. Conta matrículas `em_andamento`, a mesma base do motor
    (`escala._mapear_matriculas`).
    """
    areas_map = {a.id: a for a in db.scalars(select(Area)).all()}
    demanda: dict[int, int] = {}
    for area_id, n in db.execute(
        select(Matricula.area_id, func.count())
        .join(Aluno, Matricula.aluno_id == Aluno.id)
        .where(Aluno.ciclo_id == ciclo.id, Matricula.status == StatusMatricula.em_andamento)
        .group_by(Matricula.area_id)
    ).all():
        demanda[area_id] = n

    por_area: dict[int, dict] = {}
    for s in slots:
        r = por_area.setdefault(s.local.area_id, {
            "nome": s.area_nome, "cor": s.area_cor, "slots": 0, "sem_grupo": 0,
            "ondas": 0, "vagas": 0,
        })
        r["slots"] += 1
        r["ondas"] += s.ondas
        r["vagas"] += s.capacidade_efetiva
        if s.ondas == 0:
            r["sem_grupo"] += 1

    # Áreas com demanda e NENHUM slot ativo também precisam aparecer (saldo = −demanda).
    for area_id, n in demanda.items():
        if area_id not in por_area:
            ar = areas_map.get(area_id)
            por_area[area_id] = {
                "nome": (area_service.nome_completo(ar, areas_map) if ar else "?"),
                "cor": (area_service.cor_efetiva(ar, areas_map) if ar else None),
                "slots": 0, "sem_grupo": 0, "ondas": 0, "vagas": 0,
            }

    linhas = []
    for area_id, r in por_area.items():
        dem = demanda.get(area_id, 0)
        linhas.append({**r, "area_id": area_id, "demanda": dem,
                       "saldo": r["vagas"] - dem})
    # Pior saldo primeiro — é o que a comissão precisa resolver.
    linhas.sort(key=lambda r: (r["saldo"], r["nome"]))
    return linhas


def analise_oferta(db: Session, ciclo: Ciclo, com_demanda: bool = False,
                   validacao: dict | None = None) -> dict:
    """Pacote pronto para a tela: validador + régua de horários (+ demanda quando pedido).

    `validacao` evita revalidar quando quem chama já rodou `validar_locais`.
    """
    val = validacao or validar_locais(db, ciclo)
    ctx = {"validacao": val, "timeline": linha_do_tempo(val["slots"])}
    if com_demanda:
        ctx["demanda"] = capacidade_vs_demanda(db, ciclo, val["slots"])
    return ctx


# ============================ Fecha o ciclo? (por aluno) ============================
# A pergunta que importa NÃO é "há vagas suficientes": é "cada aluno consegue fazer TODAS
# as suas áreas dentro do ano?". São coisas diferentes, e a diferença é o relógio.
#
# Por que vagas × demanda engana: a capacidade já conta as ONDAS (4 vagas × 2 ondas = 8
# alunos atendidos no ciclo), então "mais matrículas que vagas iniciais" não é problema —
# eles se distribuem no ano. O que a soma não vê é que as áreas de UM aluno precisam caber
# juntas no relógio dele: uma área pode ter 22 vagas livres e nenhuma servir, porque todas
# caem no dia que as outras áreas dele já ocupam.
#
# Aqui a resposta é exata (busca com poda por aluno, capacidade ignorada de propósito):
# isola a FORMA da oferta (dia/horário/período) da disputa por assento.

@dataclass
class ViabilidadeAluno:
    aluno_id: int
    nome: str
    matriculadas: int
    fecham: int                       # máximo de áreas que cabem juntas
    faltam: list[str] = field(default_factory=list)     # nomes das que sobram
    pico: float = 0.0                 # CH da semana de pico da melhor combinação

    @property
    def completo(self) -> bool:
        return self.fecham >= self.matriculadas


@dataclass(frozen=True)
class Hipotese:
    """Uma mudança na oferta a ser MEDIDA com o motor (uma rodada por hipótese).

    Duas famílias, porque a fila tem duas causas com remédios diferentes (§ fila com CAUSA):
    - `dia`: acrescenta à área, num dia novo, uma cópia dos locais que ela já tem. Nunca
      MOVE o local existente — os dias atuais continuam (decisão da comissão).
    - `capacidade`: `delta` alunos a mais em CADA grupo da área, sem local novo. É o remédio
      de quem está na fila por "grupos cheios", em que abrir dia não resolve nada.

    Existe como tipo (e não como tupla) porque a busca combina as duas famílias na mesma
    escada: "abrir Voz na segunda + 2 vagas por grupo em Fono Hospitalar" é uma resposta
    legítima, e antes nem cabia na estrutura.
    """
    tipo: str                    # 'dia' | 'capacidade'
    area_id: int
    dia: object = None           # DiaSemana, quando tipo == 'dia'
    delta: int = 0               # alunos a mais por grupo, quando tipo == 'capacidade'

    @classmethod
    def normalizar(cls, h) -> "Hipotese":
        """Aceita `(area_id, dia)` — a forma antiga, ainda usada por `simular_oferta`."""
        return h if isinstance(h, cls) else cls("dia", h[0], dia=h[1])


@dataclass
class Destrava:
    """Mudança na oferta que faria alunos passarem a fechar o ciclo.

    É sempre **acrescentar** um dia, nunca mover o existente: a hipótese clona os grupos
    que a área já tem para o dia novo e mantém os atuais (`por_area[a] + extra`). Por isso
    `dias_atuais` viaja junto — sem ele a tabela dizia só "Hospitalar - Pediatria · Quinta"
    e a comissão não sabia se era para mudar o dia do local ou cadastrar um a mais.
    """
    area_nome: str
    dia: str
    alunos: int
    area_id: int = 0
    dia_enum: object = None      # DiaSemana — para simular a oferta com esse dia
    dias_atuais: list[str] = field(default_factory=list)
    carga: int = 0               # grupos que o dia sugerido já carrega (desempate)


def _maior_combinacao(areas, por_area, bloq) -> dict:
    """Maior conjunto de áreas que cabem juntas (busca com poda). Ignora capacidade."""
    from app.services.motor.restricoes import viola_restricoes
    cands = {a: sorted(por_area.get(a, []), key=lambda c: c.data_inicio) for a in areas}
    ordem = sorted(areas, key=lambda a: len(cands[a]))
    melhor: dict = {}

    def rec(i, atual, escolha) -> bool:
        nonlocal melhor
        if len(escolha) > len(melhor):
            melhor = dict(escolha)
            if len(melhor) == len(ordem):
                return True
        if i == len(ordem) or len(escolha) + (len(ordem) - i) <= len(melhor):
            return False
        a = ordem[i]
        for c in cands[a]:
            if viola_restricoes(atual, c, bloq) is None:
                escolha[a] = c
                if rec(i + 1, atual + [c], escolha):
                    return True
                del escolha[a]
        return rec(i + 1, atual, escolha)

    rec(0, [], {})
    return melhor


MAX_DESTRAVAS = 8      # o bastante para decidir; buscar todas custa segundos a mais
MAX_SIMULACOES = 3     # degraus da escada "e se abrirmos estes dias?"
MAX_CANDIDATOS = 40    # hipóteses avaliadas uma a uma com o motor
# Teto do "+N alunos por grupo": acima disso a hipótese deixa de ser um ajuste de vaga e
# vira outra conversa (o campo comporta uma turma inteira a mais?). O delta real é
# dimensionado pela fila da área, não fixo.
MAX_DELTA_CAPACIDADE = 4
# Orçamento de tempo da busca de sugestões, em SEGUNDOS: o custo de uma rodada do motor
# cresce com a turma e com o molde (~1,2s no ciclo real de 11 áreas / 37 locais), então
# contar rodadas não protege — contar segundos protege.
#
# O teto é alto de propósito. Com 12s a tela mostrava UMA linha num ciclo em que 4 áreas
# tinham dia útil a sugerir: medir os 14 candidatos custa ~24s e o corte deixava 4 de fora.
# Decisão da comissão (03/08/2026): preferir a resposta completa e esperar ~25s a receber
# rápido uma lista que esconde metade das providências. Os tetos continuam existindo como
# proteção para ciclo patológico (muitas áreas × muitos dias), não como corte de rotina —
# e quando cortam, o rodízio abaixo garante que o que sobra são ALTERNATIVAS de área já
# coberta, nunca uma área inteira sem sugestão.
ORCAMENTO_CANDIDATOS = 40.0   # avaliação individual: é ela que preenche a tabela
ORCAMENTO_SUGESTOES = 60.0    # total; a escada fica com o que sobrar


def _dias_candidatos(por_area: dict[int, list]) -> list[object]:
    """Universo de hipóteses do "que dia abrir": seg–sex + qualquer dia já ofertado."""
    ja_usados = {cx.local.dia_semana for cxs in por_area.values() for cx in cxs}
    return [d for d in ORDEM_DIA if d in DIAS_LETIVOS or d in ja_usados]


def _carga_por_dia(por_area: dict[int, list]) -> dict[object, int]:
    """Quantos grupos cada dia da semana já carrega — desempate dos candidatos: entre dias
    que rendem o mesmo, abrir no dia mais vazio espalha a grade em vez de amontoar tudo numa
    terça (e é justamente o amontoado que gera o conflito de 1h30)."""
    carga: dict[object, int] = {}
    for cxs in por_area.values():
        for cx in cxs:
            carga[cx.local.dia_semana] = carga.get(cx.local.dia_semana, 0) + 1
    return carga


def _dias_da_area(caixas: list) -> list[str]:
    """Dias em que a área JÁ é ofertada, na ordem do calendário (rótulos pt-BR)."""
    dias = {cx.local.dia_semana for cx in caixas}
    return [rotulo(d) for d in ORDEM_DIA if d in dias]


def _locais_da_area(caixas: list) -> list[dict]:
    """O que exatamente cadastrar: os locais (campo + turno + horário) que a área já tem.

    A hipótese clona ESTES locais no dia novo, então é isto que a comissão vai digitar no
    passo Áreas e Locais. Sem eles a sugestão dizia só "abrir na sexta" — e um local é
    campo + dia + **turno**: sem o turno e o horário a linha não é uma providência, é um
    palpite.

    Dedup pela ASSINATURA do slot (campo+turno+horário), não por local.id: a mesma sala no
    mesmo turno ofertada na terça e na quarta são dois locais, mas viram UMA cópia no dia
    novo — no dia novo elas seriam o mesmo slot. É a mesma dedup que `Simulador.rodar` faz,
    para a linha da tela descrever exatamente a oferta que foi medida.
    """
    vistos: dict[tuple, dict] = {}
    for cx in caixas:
        lo = cx.local
        vistos.setdefault((lo.campo, lo.turno, lo.hora_inicio, lo.hora_fim), {
            "campo": lo.campo,
            "turno": rotulo(lo.turno),
            "horario": f"{lo.hora_inicio:%H:%M}–{lo.hora_fim:%H:%M}",
            "encontros": lo.numero_encontros,
            "capacidade": lo.capacidade,
        })
    return list(vistos.values())


def _fila_agrupada(fila, nomes: dict[int, str]) -> dict:
    """Fila da simulação somada por CAUSA e por área.

    A causa é o que decide o remédio: `conflito` pede outro DIA, `capacidade` pede mais
    VAGA, `sem_grupo` pede cadastrar o local. Somar tudo como "sem vaga" mandava a
    comissão consertar capacidade num problema que era de dia da semana.
    """
    por_tipo: dict[str, int] = {}
    por_area: dict[str, int] = {}
    for g in fila:
        por_tipo[g.tipo] = por_tipo.get(g.tipo, 0) + 1
        nome = nomes.get(g.area_id, "?")
        por_area[nome] = por_area.get(nome, 0) + 1
    return {
        "por_tipo": por_tipo,
        "por_area": sorted(por_area.items(), key=lambda kv: -kv[1]),
        "conflito": por_tipo.get("conflito", 0),
        "capacidade": por_tipo.get("capacidade", 0),
        "sem_grupo": por_tipo.get("sem_grupo", 0),
    }


def _rodizio(por_candidato: dict[int, list]) -> list:
    """Ordem de medição: a 1ª hipótese de CADA área primeiro, depois a 2ª de cada, etc.

    Área-a-área (todos os dias da 1ª, depois a 2ª…) parece razoável e é a ordem errada
    quando o corte chega. Medido no ciclo real: as 14 hipóteses custam ~24s e o orçamento
    era de 6s, então as ~5 rodadas que cabiam gastavam-se TODAS na primeira área — a tela
    listava "Hospitalar na sexta / na segunda / na quinta" e não dizia uma palavra sobre as
    outras cinco áreas da fila. Parecia lista cheia cobrindo uma área só; agrupada por
    área, virou UMA linha, e foi essa a reclamação de "poucas sugestões".

    No rodízio, o que fica de fora quando o tempo acaba é sempre ALTERNATIVA de uma área já
    listada — nunca uma área inteira sem sugestão.
    """
    candidatos: list = []
    for i in range(max((len(h) for h in por_candidato.values()), default=0)):
        candidatos.extend(hips[i] for hips in por_candidato.values() if i < len(hips))
    return candidatos


def sugerir_dias(sim: "Simulador", base: dict, por_area: dict[int, list]) -> dict:
    """"Que oferta abrir para os que sobraram?" — medido com o MOTOR, um candidato por vez.

    Existe porque a análise por FORMA (`destravas`, capacidade ignorada) não vê o caso mais
    comum na prática: todos os currículos cabem no relógio, mas os assentos acabam e quem
    chega depois só encontra grupo em dia que conflita com o que ele já pegou. Aí a forma
    diz "10 de 10" e a geração entrega 6 — e a comissão fica sem saber o que abrir.

    Cada candidato é (área da fila, dia útil em que ela ainda não é ofertada) e vale uma
    rodada do motor sobre o molde hipotético: a resposta é o ganho REAL em alunos que
    concluem, já com a disputa por assento. Depois monta a escada acumulando os melhores.
    """
    nomes = sim.nomes
    na_fila: dict[int, int] = {}
    causa_area: dict[int, dict[str, int]] = {}
    for g in base["aguardando"]:
        na_fila[g.area_id] = na_fila.get(g.area_id, 0) + 1
        causa = causa_area.setdefault(g.area_id, {})
        causa[g.tipo] = causa.get(g.tipo, 0) + 1
    fila_areas = sorted(na_fila, key=lambda aid: -na_fila[aid])
    dias_uteis = _dias_candidatos(por_area)
    carga_dia = _carga_por_dia(por_area)

    por_candidato: dict[int, list[Hipotese]] = {}
    # Áreas da fila que já são ofertadas em TODOS os dias testáveis. Elas continuam sendo
    # nomeadas na tela ("não há dia novo para testar"), mas NÃO saem mais da busca: sem dia
    # a testar ainda resta a hipótese de capacidade, que é justamente o remédio delas.
    saturadas: list[dict] = []
    for aid in fila_areas:
        caixas_area = por_area.get(aid)
        if not caixas_area:
            continue          # área sem grupo nenhum: não há o que clonar (é cadastro)
        dias_atuais = {cx.local.dia_semana for cx in caixas_area}
        # dia mais VAZIO primeiro dentro da área: é o que a tela vai recomendar, e amontoar
        # mais um grupo no dia já cheio é o que cria o próximo conflito de 1h30
        novos = sorted((d for d in dias_uteis if d not in dias_atuais),
                       key=lambda d: (carga_dia.get(d, 0), ORDEM_DIA.index(d)))
        if not novos:
            saturadas.append({"area_nome": nomes.get(aid, "?"),
                              "dias_atuais": _dias_da_area(caixas_area),
                              "na_fila": na_fila[aid]})
        hips = [Hipotese("dia", aid, dia=d) for d in novos]
        # Capacidade DIMENSIONADA pela fila da área: `delta` por grupo × nº de grupos ≈ o
        # tamanho da fila. Testar "+1" fixo mediria uma providência que não resolve, e "+4"
        # fixo pediria à comissão mais do que o necessário.
        cap = Hipotese("capacidade", aid,
                       delta=min(MAX_DELTA_CAPACIDADE,
                                 max(1, ceil(na_fila[aid] / len(caixas_area)))))
        # Ordem DENTRO da área: primeiro o remédio que casa com a causa da fila dela. Numa
        # área que está na fila por grupo cheio, abrir dia novo não resolve — e é a primeira
        # hipótese de cada área que o rodízio garante medir.
        cheio = causa_area.get(aid, {}).get("capacidade", 0)
        conflito = causa_area.get(aid, {}).get("conflito", 0)
        por_candidato[aid] = [cap] + hips if (cheio >= conflito or not hips) else \
            hips[:1] + [cap] + hips[1:]
    candidatos = _rodizio(por_candidato)
    truncou = len(candidatos) > MAX_CANDIDATOS
    candidatos = candidatos[:MAX_CANDIDATOS]

    t0 = monotonic()
    avaliados = []
    for h in candidatos:
        if avaliados and monotonic() - t0 > ORCAMENTO_CANDIDATOS:
            truncou = True                # orçamento: o resto dos candidatos fica de fora
            break
        r = sim.rodar([h])
        caixas_area = por_area[h.area_id]
        avaliados.append({
            "hip": h, "tipo": h.tipo, "area_id": h.area_id,
            "area_nome": nomes.get(h.area_id, "?"),
            # --- hipótese de DIA ---
            "dia_enum": h.dia, "dia": rotulo(h.dia) if h.dia is not None else "",
            # os dias que a área JÁ tem: a sugestão é ACRESCENTAR um dia, não mudar o
            # existente, e sem isto na linha a tabela não dizia qual das duas coisas fazer
            "dias_atuais": _dias_da_area(caixas_area),
            "locais": _locais_da_area(caixas_area),    # campo/turno/horário a cadastrar
            # --- hipótese de CAPACIDADE ---
            "delta": h.delta, "grupos": len(caixas_area),
            "capacidades": sorted({cx.capacidade for cx in caixas_area}),
            "vagas_extra": h.delta * len(caixas_area),
            # --- medição ---
            "completos": r["completos"], "total": r["total"], "fila": r["fila"],
            "ganho": r["completos"] - base["completos"],
            "libera": base["fila"] - r["fila"],
            "carga_dia": carga_dia.get(h.dia, 0) if h.dia is not None else 0,
            "res": _numeros(r),        # a rodada inteira, para o 1º degrau da escada
            # áreas que continuam na fila DEPOIS desta mudança — poda da escada, de graça
            "areas_fila": {g.area_id for g in r["aguardando"]},
        })
    # Quem faz mais aluno CONCLUIR primeiro; empate por quem tira mais gente da fila e,
    # ainda empatado, pelo dia mais vazio. Ordenar por nome no fim seria escolher por
    # alfabeto uma decisão de grade.
    avaliados.sort(key=lambda s: (-s["ganho"], -s["libera"], s["carga_dia"],
                                  ORDEM_DIA.index(s["dia_enum"]) if s["dia_enum"] else 9,
                                  s["area_nome"]))
    uteis = [s for s in avaliados if s["ganho"] > 0 or s["libera"] > 0]

    # Escada acumulada por SELEÇÃO PROGRESSIVA: a cada degrau TODOS os candidatos restantes
    # são medidos JUNTO com o que já foi escolhido, e vence quem mais melhora dali.
    #
    # Somar os ganhos individuais não funciona: aqui NENHUMA mudança isolada fazia um aluno
    # concluir (ganho 0 em todas as 11) e três combinadas fecham o ciclo — quem cursa 8 áreas
    # só conclui quando a última destrava. E o dia importa por combinação, não isoladamente:
    # escolher o "melhor dia" de cada área pela tabela individual dava 8 de 10 onde medir a
    # combinação dá 10 de 10.
    #
    # **A escada parte de TODAS as hipóteses medidas, inclusive as que sozinhas valem zero.**
    # Antes ela só via `uteis` (ganho>0 ou libera>0), e isso derrotava o próprio motivo de
    # existir: a mudança que não move nada sozinha e só paga junto com outra era filtrada
    # ANTES de haver com quem combinar. Num ciclo em que todas as hipóteses davam +0 — o
    # caso da comissão — sobrava uma escada de um degrau que já estava na tabela.
    #
    # O que substitui o filtro é uma PODA de graça: a cada degrau só continuam as hipóteses
    # de área que AINDA tem alguém na fila naquele cenário (`areas_fila`, que já veio da
    # rodada). Abrir dia/vaga para área sem ninguém esperando não faz ninguém concluir.
    # Uma área entra uma vez POR TIPO: "abrir na quinta" e "+2 por grupo" são providências
    # diferentes e podem conviver; um 2º dia da mesma área é alternativa, não degrau.
    # O degrau 0 ("como está hoje") é a LINHA DE BASE, não uma sugestão: fica em `base_hoje`
    # e a tela o mostra como referência acima da tabela. Dentro da tabela ele enganava —
    # lido como opção, "4 de 10, 10 na fila" parecia uma alternativa a escolher.
    escada = []
    acumulado: list[Hipotese] = []
    rotulos: list[str] = []
    pendentes = list(avaliados)
    fila_atual = {g.area_id for g in base["aguardando"]}
    while pendentes and len(acumulado) < MAX_SIMULACOES:
        if acumulado and monotonic() - t0 > ORCAMENTO_SUGESTOES:
            truncou = True                # escada incompleta — melhor curta que errada
            break
        elegiveis = [p for p in pendentes if p["area_id"] in fila_atual]
        if not elegiveis:
            break                         # ninguém mais esperando nas áreas que sobraram
        if not acumulado:
            opcoes = [(s, s["res"], s["areas_fila"]) for s in elegiveis]   # já medido acima
        else:
            opcoes = [(s, *_rodada(sim, acumulado + [s["hip"]])) for s in elegiveis]
        ultimo = escada[-1] if escada else base
        s, r, areas = max(opcoes, key=lambda o: (o[1]["completos"], -o[1]["fila"],
                                                 na_fila.get(o[0]["area_id"], 0),
                                                 -o[0]["carga_dia"]))
        # DEGRAU DE APOSTA: um passo que não melhora nada sozinho é aceito **se ainda há
        # espaço para o passo que o redime**. Sem isto, o filtro que tirei acima voltava
        # pela porta dos fundos: a escada abortava no 1º degrau justamente no ciclo em que
        # nenhuma mudança isolada muda nada — que é o caso em que combinar é a única saída.
        # A aposta é revertida no fim: escada que não bate a linha de base é descartada.
        if (r["completos"] <= ultimo["completos"] and r["fila"] >= ultimo["fila"]
                and len(acumulado) >= MAX_SIMULACOES - 1):
            break
        acumulado.append(s["hip"])
        rotulos.append(_rotulo_hipotese(s))
        fila_atual = areas
        escada.append({
            "mudancas": list(rotulos), "n": len(acumulado),
            # ganho/libera contra a linha de base: é o delta que a comissão compara, e ele
            # só faz sentido explícito agora que "como está hoje" saiu da tabela
            "ganho": r["completos"] - base["completos"],
            "libera": base["fila"] - r["fila"],
            **_numeros(r),
        })
        pendentes = [p for p in pendentes
                     if not (p["area_id"] == s["area_id"] and p["tipo"] == s["tipo"])]
        if r["completos"] == r["total"]:
            break
    # A aposta revertida: escada que, somada, não bate a linha de base não é plano nenhum —
    # e mostrá-la seria pior que não mostrar, porque cada degrau parece uma providência.
    if escada and escada[-1]["ganho"] <= 0 and escada[-1]["libera"] <= 0:
        escada = []
    return {
        "sugestoes": uteis,
        # a mesma medição com uma linha por ÁREA — é o que a tela mostra
        "sugestoes_agrupadas": _agrupar_sugestoes(uteis),
        "descartadas": [s for s in avaliados if s["ganho"] <= 0 and s["libera"] <= 0],
        "escada": escada,
        "base_hoje": _numeros(base),   # a linha de base da escada, fora da tabela
        "areas_saturadas": saturadas,
        "avaliados": len(avaliados),
        "rodadas": sim.rodadas,
        "truncou": truncou,
    }


def _agrupar_sugestoes(uteis: list[dict]) -> list[dict]:
    """Uma linha por ÁREA, com os outros dias como ALTERNATIVAS medidas.

    A tabela crua repetia a mesma área em três linhas seguidas ("Hospitalar - Pediatria
    também na Sexta / na Segunda / na Quinta") e a comissão lia três providências quando
    qualquer UMA delas resolve — pior, a escada logo abaixo repetia a mesma área numa
    quarta linha. Agrupado, a área aparece UMA vez: o dia recomendado é o que mais rende
    (a lista já chega ordenada por efeito) e os outros ficam ao lado, cada um com o seu
    número, como escolha — não como tarefa a mais.
    """
    grupos: dict[tuple, dict] = {}
    for s in uteis:                       # já ordenado: melhor efeito primeiro
        # a chave inclui o TIPO: "abrir X na quinta" e "+2 vagas por grupo em X" são duas
        # providências distintas para a mesma área, não alternativas uma da outra
        chave = (s["area_nome"], s["tipo"])
        g = grupos.get(chave)
        if g is None:
            grupos[chave] = {**s, "alternativas": []}
        else:
            g["alternativas"].append({"dia": s["dia"], "libera": s["libera"],
                                      "ganho": s["ganho"]})
    return list(grupos.values())


def _rodada(sim: "Simulador", hips: list) -> tuple[dict, set]:
    """Uma rodada da escada: os números + as áreas que continuam na fila (para a poda)."""
    r = sim.rodar(hips)
    return r, {g.area_id for g in r["aguardando"]}


def _rotulo_hipotese(s: dict) -> str:
    """A mudança em uma frase — é o que a escada lista como passo do plano."""
    if s["tipo"] == "capacidade":
        alunos = "aluno" if s["delta"] == 1 else "alunos"
        grupos = "grupo" if s["grupos"] == 1 else "grupos"
        return (f"+{s['delta']} {alunos} por grupo em {s['area_nome']} "
                f"({s['grupos']} {grupos})")
    return f"{s['area_nome']} também na {s['dia']}"


def _numeros(r: dict) -> dict:
    """Só os escalares da simulação — a escada da tela não precisa da fila detalhada."""
    return {k: v for k, v in r.items() if k not in ("aguardando", "fila_agrupada")}


def _agrupar_destravas(destravas: list[Destrava], locais_por_area: dict[int, list]) -> list[dict]:
    """Uma linha por ÁREA, com os dias como ALTERNATIVAS — não como lista de tarefas.

    A tabela crua repetia "Hospitalar - Pediatria · Quinta · 10", "…· Segunda · 10",
    "…· Sexta · 10" e a comissão lia oito providências a tomar quando qualquer UMA delas
    resolve o mesmo grupo de alunos. Agrupado, a linha vira uma decisão: abrir esta área
    também neste dia (e estes são os outros dias que servem igual).
    """
    grupos: dict[str, dict] = {}
    for d in destravas:                      # já vem ordenado: melhor dia da área primeiro
        g = grupos.setdefault(d.area_nome, {
            "area_nome": d.area_nome, "dias_atuais": d.dias_atuais,
            "alunos": 0, "dia": d.dia, "_outros": [],
            "locais": _locais_da_area(locais_por_area.get(d.area_id, [])),
        })
        g["alunos"] = max(g["alunos"], d.alunos)
        if d.dia != g["dia"]:
            g["_outros"].append(d)
    for g in grupos.values():
        # o dia recomendado é o mais VAZIO (vem de `destravas`); as alternativas ficam na
        # ordem do calendário, que é como se lê uma lista de dias
        g["alternativas"] = [d.dia for d in sorted(g.pop("_outros"),
                                                   key=lambda d: ORDEM_DIA.index(d.dia_enum))]
    return sorted(grupos.values(), key=lambda g: (-g["alunos"], g["area_nome"]))


def fecha_o_ciclo(db: Session, ciclo: Ciclo) -> dict:
    """Quantos alunos conseguem fazer TODAS as suas áreas — e o que destravaria os demais.

    `destravas` responde a pergunta acionável para os professores: *que dia abrir*. Testa,
    para cada área que sobra, oferecê-la em cada dia da semana em que ela ainda não existe
    (mesma duração e período dos grupos atuais) e recontar — a hipótese entra DENTRO da
    busca, não colada numa solução já escolhida.
    """
    import copy

    from app.models.aluno import RestricaoAlunoLocal
    from app.services.motor.restricoes import ch_pico

    ctx = calendario.carregar_contexto(db, ciclo)
    por_area: dict[int, list] = {}
    for cx in molde.materializar_molde(db, ciclo, ctx):
        por_area.setdefault(cx.area_id, []).append(cx)
    areas_map = {a.id: a for a in db.scalars(select(Area)).all()}
    nomes = {i: area_service.nome_completo(a, areas_map) for i, a in areas_map.items()}

    mats: dict[int, list[int]] = {}
    for m in db.scalars(select(Matricula).join(Aluno, Matricula.aluno_id == Aluno.id).where(
        Aluno.ciclo_id == ciclo.id, Matricula.status == StatusMatricula.em_andamento
    )).all():
        mats.setdefault(m.aluno_id, []).append(m.area_id)
    bloqs: dict[int, set[int]] = {}
    for r in db.scalars(select(RestricaoAlunoLocal).join(
        Aluno, RestricaoAlunoLocal.aluno_id == Aluno.id
    ).where(Aluno.ciclo_id == ciclo.id)).all():
        bloqs.setdefault(r.aluno_id, set()).add(r.local_id)

    # Universo de hipóteses do "que dia abrir": seg–sex (mesmo dia ainda sem local nenhum)
    # + qualquer dia que o ciclo já use. Nunca sábado/domingo por conta própria.
    dias_uteis = _dias_candidatos(por_area)
    carga_dia = _carga_por_dia(por_area)

    # Currículos repetem MUITO (uma turma inteira do 9º/10º cursa as mesmas áreas). A
    # resposta só depende de (áreas, blocklist), então memoizar colapsa 10 buscas em 1 —
    # é o que torna a análise barata o suficiente para rodar a cada render do wizard.
    cache_sol: dict[tuple, dict] = {}
    cache_destrava: dict[tuple, list[tuple[int, object]]] = {}

    linhas: list[ViabilidadeAluno] = []
    destravam: dict[tuple[int, object], int] = {}
    for al in db.scalars(select(Aluno).where(Aluno.ciclo_id == ciclo.id)
                         .order_by(Aluno.nome)).all():
        areas = mats.get(al.id, [])
        if not areas:
            continue
        bloq = bloqs.get(al.id, set())
        assinatura = (tuple(sorted(areas)), tuple(sorted(bloq)))
        if assinatura not in cache_sol:
            cache_sol[assinatura] = _maior_combinacao(areas, por_area, bloq)
        sol = cache_sol[assinatura]
        fora = [a for a in areas if a not in sol]
        linhas.append(ViabilidadeAluno(
            aluno_id=al.id, nome=al.nome, matriculadas=len(areas), fecham=len(sol),
            faltam=sorted(nomes.get(a, "?") for a in fora),
            pico=ch_pico(list(sol.values())),
        ))
        # que dia abrir? testa cada dia útil do ciclo em que a área que sobra ainda não
        # é ofertada. A hipótese entra DENTRO da busca — colá-la numa solução já escolhida
        # dá resposta errada (a solução escolhida pode ter pico alto por acidente).
        #
        # Só para quem NÃO fecha: para o aluno que já fecha, qualquer hipótese "destrava"
        # trivialmente (a condição `cabe tudo` já era verdadeira sem mudar nada), e a tela
        # enchia de sugestões inúteis — 19 "destravas" num ciclo em que 10 de 10 fechavam.
        if not fora:
            continue
        if assinatura not in cache_destrava:
            achados: list[tuple[int, object]] = []
            # Testa TODAS as áreas do aluno, não só a que sobrou: quando várias áreas
            # são intercambiáveis, qual delas "sobra" é acidente da busca, e o remédio
            # pode estar em abrir outra. Perguntar só pela que sobrou dava "nenhuma
            # solução" tendo solução.
            for a in areas:
                if not por_area.get(a):
                    continue
                dias_atuais = {cx.local.dia_semana for cx in por_area[a]}
                for dia in dias_uteis:
                    if dia in dias_atuais:
                        continue
                    hip = dict(por_area)
                    extra = []
                    for cx in por_area[a]:
                        falso = copy.copy(cx.local)
                        falso.dia_semana = dia
                        extra.append(molde.Caixa(
                            local=falso, area_id=cx.area_id, onda=cx.onda, datas=cx.datas,
                            data_inicio=cx.data_inicio, data_fim=cx.data_fim,
                            capacidade=cx.capacidade, horas=cx.horas))
                    hip[a] = por_area[a] + extra
                    if len(_maior_combinacao(areas, hip, bloq)) == len(areas):
                        achados.append((a, dia))
                        if len(achados) >= MAX_DESTRAVAS:
                            break
                if len(achados) >= MAX_DESTRAVAS:
                    break
            cache_destrava[assinatura] = achados
        for a, dia in cache_destrava[assinatura]:
            destravam[(a, dia)] = destravam.get((a, dia), 0) + 1

    # Teto GLOBAL da oferta: soma das vagas de todos os grupos do ciclo (já inclui as
    # ondas) contra a soma das matrículas. Medido: a entrega cresce proporcional à turma
    # até a oferta saturar, e depois cada aluno a mais é fila. Ter o teto à vista é o que
    # permite decidir "quantos alunos esta oferta sustenta" antes de começar o ciclo.
    vagas_ciclo = sum(cx.capacidade for cxs in por_area.values() for cx in cxs)
    demanda_total = sum(len(a) for a in mats.values())

    incompletos = [l for l in linhas if not l.completo]
    faltam_por_area: dict[str, int] = {}
    for l in incompletos:
        for nome in l.faltam:
            faltam_por_area[nome] = faltam_por_area.get(nome, 0) + 1
    destravas = sorted(
        (Destrava(area_nome=nomes.get(aid, "?"), dia=rotulo(dia), alunos=n,
                  area_id=aid, dia_enum=dia,
                  dias_atuais=_dias_da_area(por_area.get(aid, [])),
                  carga=carga_dia.get(dia, 0))
         for (aid, dia), n in destravam.items()),
        # o dia mais VAZIO primeiro dentro da mesma área: é ele que a tela recomenda, e
        # amontoar mais um grupo no dia já cheio é o que cria o conflito de 1h30 seguinte
        key=lambda x: (-x.alunos, x.area_nome, x.carga, ORDEM_DIA.index(x.dia_enum)),
    )

    # O NÚMERO HONESTO: a simulação da oferta como está hoje, rodando o motor de verdade.
    #
    # Sempre — não só quando a forma reprova alguém. A checagem por forma ignora capacidade
    # de propósito (é o que isola "impossível pelo relógio" de "perdeu o assento"), então ela
    # dizia "10 de 10 fecham" e a geração entregava 6 sem que a tela explicasse a diferença.
    # Rodar o motor custa ~0,3s no molde real; é o mesmo código que gera a escala, então este
    # é o número que a comissão vai ver depois de clicar em Gerar.
    # O molde já materializado acima é reaproveitado como base das rodadas (cada rodada clona).
    sim = Simulador(db, ciclo, caixas=[cx for cxs in por_area.values() for cx in cxs])
    real = sim.rodar([])
    # "E se eu abrir estes dias?" — sugestões medidas com o motor, para os que sobraram NA
    # SIMULAÇÃO (não na forma): é o caso real em que todos os currículos cabem e ainda assim
    # sobra gente porque os assentos acabaram.
    sug = (sugerir_dias(sim, real, por_area)
           if real["completos"] < real["total"] else
           {"sugestoes": [], "sugestoes_agrupadas": [], "descartadas": [], "escada": [],
            "base_hoje": _numeros(real), "areas_saturadas": [], "avaliados": 0,
            "rodadas": sim.rodadas, "truncou": False})
    return {
        "linhas": sorted(linhas, key=lambda l: (l.completo, l.nome)),
        "total": len(linhas),
        "vagas_ciclo": vagas_ciclo,
        "demanda_total": demanda_total,
        "saldo_ciclo": vagas_ciclo - demanda_total,
        # quantos alunos do currículo médio a oferta sustenta
        "sustenta": (int(vagas_ciclo / (demanda_total / len(linhas)))
                     if linhas and demanda_total else 0),
        # `completos`/`incompletos` são da FORMA da oferta (capacidade ignorada). O número
        # que casa com a geração é `real.completos` — a tela lidera com ele.
        "completos": len(linhas) - len(incompletos),
        "incompletos": len(incompletos),
        "faltam_por_area": sorted(faltam_por_area.items(), key=lambda kv: -kv[1]),
        "destravas": destravas,
        # a mesma coisa por ÁREA, com os dias como alternativas — é o que a tela mostra
        "destravas_agrupadas": _agrupar_destravas(destravas, por_area),
        "real": real,
        "gargalo": _gargalo(len(incompletos), real),
        **sug,
    }


def _gargalo(incompletos_forma: int, real: dict) -> str:
    """Onde o ciclo trava, em uma palavra — é isso que escolhe o remédio na tela.

    'nenhum'     — a simulação fecha para todos;
    'forma'      — há currículo que não cabe no relógio nem com assento sobrando;
    'capacidade' — cabe, mas os grupos enchem (mais vaga / mais um dia);
    'conflito'   — cabe e há vaga, mas não no dia que sobrou para o aluno (outro dia).
    """
    if real["completos"] >= real["total"]:
        return "nenhum"
    if incompletos_forma:
        return "forma"
    ag = real["fila_agrupada"]
    return "capacidade" if ag["capacidade"] >= ag["conflito"] else "conflito"


def _turma(db: Session, ciclo: Ciclo):
    """(alunos na ordem da fila, áreas por aluno, blocklist por aluno) — carregado 1×."""
    from app.models.aluno import RestricaoAlunoLocal
    alunos = list(db.scalars(select(Aluno).where(Aluno.ciclo_id == ciclo.id)
                             .order_by(Aluno.ordenamento)).all())
    mats: dict[int, list[int]] = {}
    for m in db.scalars(select(Matricula).join(Aluno, Matricula.aluno_id == Aluno.id).where(
        Aluno.ciclo_id == ciclo.id, Matricula.status == StatusMatricula.em_andamento
    )).all():
        mats.setdefault(m.aluno_id, []).append(m.area_id)
    bloqs: dict[int, set[int]] = {}
    for r in db.scalars(select(RestricaoAlunoLocal).join(
        Aluno, RestricaoAlunoLocal.aluno_id == Aluno.id
    ).where(Aluno.ciclo_id == ciclo.id)).all():
        bloqs.setdefault(r.aluno_id, set()).add(r.local_id)
    return alunos, mats, bloqs


class Simulador:
    """Roda o MOTOR sobre ofertas hipotéticas — de novo e de novo, sem repetir o preparo.

    Uma rodada = `aplicar_pins` + `preencher` + `consolidar`, o mesmo código e a mesma ordem
    de `gerar_escala`, sobre uma CÓPIA do molde. Então a resposta não é estimativa nem regra
    de três: é o que aconteceria de fato, incluindo a disputa por assento entre os alunos —
    que a verificação de viabilidade por aluno ignora de propósito. Os pins da montagem
    entram porque a geração também os aplica; sem eles a simulação divergiria da geração
    justamente no ciclo em que a comissão montou grupos à mão.

    Existe como objeto porque a busca de sugestões roda o motor uma dúzia de vezes: molde,
    turma, pins e catálogo são carregados UMA vez e cada rodada só clona as caixas (o estado
    mutável é `ocupantes`/`fixos`). Nada é persistido — o molde é puro e os pins são só lidos.
    """

    def __init__(self, db: Session, ciclo: Ciclo, turma=None, caixas=None):
        from app.services.motor import persistencia
        self.db, self.ciclo = db, ciclo
        self.alunos, self.mats, self.bloqs = turma or _turma(db, ciclo)
        self.pins = persistencia.capturar_pins(db, ciclo)
        if caixas is None:
            caixas = molde.materializar_molde(db, ciclo, calendario.carregar_contexto(db, ciclo))
        self.base = caixas
        areas_map = {a.id: a for a in db.scalars(select(Area)).all()}
        self.nomes = {i: area_service.nome_completo(a, areas_map) for i, a in areas_map.items()}
        self.rodadas = 0

    def rodar(self, extras: list) -> dict:
        """Roda o motor sobre a oferta atual + as `extras` (`Hipotese`, ver a classe).

        Ordem deliberada: primeiro os dias novos, depois as vagas. Assim, se as duas
        hipóteses da mesma área entrarem juntas, os grupos do dia novo já nascem com a
        capacidade aumentada — que é o que a comissão faria ao cadastrar.
        """
        import copy
        from dataclasses import replace

        from app.services.motor import consolidacao, preenchimento

        hips = [Hipotese.normalizar(h) for h in extras]
        caixas = [replace(c, ocupantes=[], fixos=set()) for c in self.base]
        for h in [x for x in hips if x.tipo == "dia"]:
            area_id, dia = h.area_id, h.dia
            origem = [c for c in caixas if c.area_id == area_id and c.local.dia_semana != dia]
            # UMA cópia por slot distinto (campo+turno+horário). A mesma sala no mesmo turno
            # ofertada na terça E na quarta são dois locais hoje; clonar os dois punha DOIS
            # locais idênticos na sexta — o dobro da capacidade, num slot que a comissão não
            # conseguiria cadastrar duas vezes (1 local = campo + dia + turno). A simulação
            # media então um ganho que a oferta sugerida não entregaria.
            rep: dict[tuple, int] = {}
            for c in origem:
                rep.setdefault((c.local.campo, c.local.turno, c.local.hora_inicio,
                                c.local.hora_fim), c.local.id)
            manter = set(rep.values())
            for cx in [c for c in origem if c.local.id in manter]:
                falso = copy.copy(cx.local)
                falso.dia_semana = dia
                caixas.append(replace(cx, local=falso, ocupantes=[], fixos=set()))
        # Vagas a mais em CADA grupo da área — inclusive nos grupos do dia novo, se as duas
        # hipóteses vieram juntas. Não cria local nenhum: é o mesmo campo recebendo mais um
        # aluno por grupo, que é o remédio de quem está na fila com os grupos cheios.
        for h in [x for x in hips if x.tipo == "capacidade"]:
            for cx in [c for c in caixas if c.area_id == h.area_id]:
                cx.capacidade += h.delta

        comp: dict[int, list] = {}
        fila: list = []
        preenchimento.aplicar_pins(caixas, self.pins, self.bloqs, comp)
        preenchimento.preencher(caixas, self.alunos, self.mats, self.bloqs, comp, fila)
        consolidacao.consolidar(caixas, self.bloqs, comp)
        self.rodadas += 1

        com_mat = [a for a in self.alunos if self.mats.get(a.id)]
        completos = sum(1 for a in com_mat
                        if len({cx.area_id for cx in comp.get(a.id, [])}) == len(self.mats[a.id]))
        return {
            "completos": completos,
            "total": len(com_mat),
            "alocados": sum(len(c.ocupantes) for c in caixas),
            "fila": len(fila),
            "vagas": sum(c.capacidade for c in caixas),
            "aguardando": fila,                      # list[Aguardando] — com tipo e motivo
            "fila_agrupada": _fila_agrupada(fila, self.nomes),
        }


def simular_oferta(db: Session, ciclo: Ciclo, extras: list[tuple[int, object]],
                   turma=None) -> dict:
    """"Se eu abrir estes dias, quantos alunos concluem o ciclo?" — uma rodada do motor."""
    return Simulador(db, ciclo, turma).rodar(extras)


def prever_geracao(db: Session, ciclo: Ciclo) -> dict:
    """O que a geração vai entregar, com a oferta como está — UMA rodada (~0,3s).

    Barato o suficiente para entrar no render da Revisão, e é o que impede a tela de
    prometer o que a geração não cumpre: a revisão de completude só sabia contar vagas
    (capacidade), então mostrava "2 matrículas sem vaga" num ciclo que gerou com 10 na fila
    por conflito de horário. O diagnóstico completo (o que abrir) continua sob demanda.
    """
    return Simulador(db, ciclo).rodar([])
