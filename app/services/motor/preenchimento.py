"""Fase 3 — Preenchimento automático do molde (§6).

Objetivo lexicográfico: (1) COBERTURA — máximo de alunos concluindo suas áreas; depois
(2) LOTAÇÃO — empacotar caixas. Dois botões: ordem dos alunos = `ordenamento`; escolha da
caixa = empacotamento (mais cheia com vaga). As áreas de cada aluno são resolvidas da MAIS
escassa para a menos (most-constrained-first), evitando fila por conflito evitável (§6.4).

`compromissos` (dict aluno_id → list[Caixa]) é o estado partilhado: começa com os pins
já aplicados (§5) e vai crescendo a cada colocação. As 4 restrições duras
(`restricoes.py`) já consideram esse estado.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.aluno import Aluno
from app.services.motor.molde import Caixa
from app.services.motor.restricoes import caixas_viaveis, viola_restricoes


@dataclass
class Aguardando:
    """Par (aluno, área) que não coube — fila do próximo ciclo, com o motivo (§6.5).

    `tipo` é a CAUSA em forma de chave, para a tela poder somar por causa em vez de
    reinterpretar a frase. Sem ela a tela chamava tudo de "sem vaga" — inclusive o aluno
    que ficou de fora por conflito de horário, com vaga sobrando na área. As causas são
    remédios diferentes (mais capacidade × outro dia), então precisam aparecer separadas.
    """
    aluno_id: int
    area_id: int
    motivo: str
    tipo: str = "conflito"      # 'sem_grupo' | 'capacidade' | 'conflito'


def indexar_por_area(caixas: list[Caixa]) -> dict[int, list[Caixa]]:
    idx: dict[int, list[Caixa]] = {}
    for c in caixas:
        idx.setdefault(c.area_id, []).append(c)
    return idx


def _escolher_caixa(
    viaveis: list[Caixa],
    comp: list[Caixa],
    bloq: set[int],
    pendentes: set[int],
    por_area: dict[int, list[Caixa]],
) -> Caixa:
    """Escolhe a caixa desta área subordinando o empacotamento à COBERTURA (§6.2).

    Objetivo lexicográfico por candidata:
      1. **Preservar cobertura** — nº de áreas AINDA pendentes do aluno que continuam
         com ≥1 caixa viável DEPOIS de ocupar esta candidata. Evita a "fila evitável"
         do §6.4: o motor não queima o dia/horário que é a única opção de outra área
         pendente (caso clássico: pôr Linguagem Infantil na terça-tarde mata ORL-TAN,
         que só existe terça-tarde). Também favorece o encadeamento no tempo (§6.1) —
         quando a caixa mais cedo satura as 30h e barraria outra área, uma caixa mais
         tardia (que preserva mais pendências) vence.
      2. **Empacotar** — caixa mais cheia com vaga (§6.4).
      3. **Conforto** — início mais cedo.
    """
    def preservadas(c: Caixa) -> int:
        comp_c = comp + [c]
        return sum(
            1 for a in pendentes
            if caixas_viaveis(por_area.get(a, []), comp_c, bloq)
        )

    return max(viaveis, key=lambda c: (preservadas(c), len(c.ocupantes), -c.data_inicio.toordinal()))


def classificar_sem_vaga(
    caixas_area: list[Caixa], comp: list[Caixa], bloqueados: set[int],
) -> tuple[str, str]:
    """(tipo, motivo) de por que esta área não coube para este aluno (§6.5).

    As 3 causas reais, e cada uma tem um remédio diferente:
      `sem_grupo`   — a área não fechou grupo nenhum no ciclo → oferta/nº de encontros;
      `capacidade`  — há grupo, todos cheios → mais vaga (outro dia, outra capacidade);
      `conflito`    — há vaga, mas nenhuma passa nas restrições do aluno → outro DIA.

    Pública para quem precisa recalcular fora da geração (diagnóstico da oferta): o
    motivo do relatório é um retrato do instante em que a escala foi gerada.
    """
    if not caixas_area:
        return "sem_grupo", "sem grupo para esta área no ciclo (refaz no próximo)"
    com_vaga = [c for c in caixas_area if c.tem_vaga()]
    if not com_vaga:
        return "capacidade", "todos os grupos da área estão cheios"
    for c in com_vaga:
        m = viola_restricoes(comp, c, bloqueados)
        if m:
            return "conflito", m
    return "conflito", "sem vaga viável"


def motivo_sem_vaga(caixas_area: list[Caixa], comp: list[Caixa], bloqueados: set[int]) -> str:
    """Só a frase pt-BR de `classificar_sem_vaga`."""
    return classificar_sem_vaga(caixas_area, comp, bloqueados)[1]


def _qualidade(escolha: dict[int, Caixa]) -> tuple[int, int]:
    """Objetivo lexicográfico do §6.2, como número: (COBERTURA, LOTAÇÃO).

    Cobertura = quantas áreas do aluno fecharam. Lotação = quão cheias já estavam as
    caixas escolhidas (empacotar deixa caixas vazias livres para os alunos seguintes).
    """
    return (len(escolha), sum(len(c.ocupantes) for c in escolha.values()))


def _atribuir_guloso(
    pendentes: list[int],
    por_area: dict[int, list[Caixa]],
    comp: list[Caixa],
    bloq: set[int],
) -> dict[int, Caixa]:
    """A escolha histórica: most-constrained-first + `_escolher_caixa`, sem voltar atrás."""
    restantes = set(pendentes)
    escolha: dict[int, Caixa] = {}
    atual = list(comp)
    while restantes:
        # Escassez: resolve antes a área com MENOS caixas viáveis para este aluno.
        area_id = min(restantes, key=lambda a: len(caixas_viaveis(por_area.get(a, []), atual, bloq)))
        restantes.discard(area_id)
        viaveis = caixas_viaveis(por_area.get(area_id, []), atual, bloq)
        if not viaveis:
            continue
        escolhida = _escolher_caixa(viaveis, atual, bloq, restantes, por_area)
        escolha[area_id] = escolhida
        atual.append(escolhida)
    return escolha


def _atribuir_busca(
    pendentes: list[int],
    por_area: dict[int, list[Caixa]],
    comp: list[Caixa],
    bloq: set[int],
    limite_nos: int = 40_000,
) -> dict[int, Caixa]:
    """Melhor atribuição do aluno por BUSCA COM PODA, em vez de escolha gulosa.

    Por que existe: o guloso não desfaz uma escolha própria. Ele resolve as áreas uma a
    uma e prefere começar cedo, o que concentra tudo nas mesmas semanas — e aí a última
    área não acha dia. `_escolher_caixa` olha só UM passo à frente ("a área pendente
    continua com ≥1 caixa viável?"), o que não é o mesmo que "ainda existe atribuição
    completa". Medido no molde real: o guloso fechava 8 de 11 áreas onde 10 eram
    possíveis.

    A busca é exata dentro do teto de nós: percorre as áreas da mais escassa para a menos
    (poda mais cedo), tenta as caixas mais cheias e mais antigas primeiro (a 1ª solução já
    é boa, o que também poda), e pode DESISTIR de uma área — é o que permite descobrir que
    sacrificar a área X fecha as outras duas.

    `limite_nos` é rede de segurança contra explosão combinatória num molde patológico.
    Estourar não estraga nada: `preencher` compara com o guloso e fica com o melhor, então
    o resultado nunca é pior que o de antes desta função existir.
    """
    cands: dict[int, list[Caixa]] = {}
    for a in pendentes:
        # empacotar primeiro, depois começar cedo: mesma preferência do §6.2/§6.4
        cands[a] = sorted(
            (c for c in por_area.get(a, []) if c.tem_vaga()),
            key=lambda c: (-len(c.ocupantes), c.data_inicio.toordinal()),
        )
    ordem = sorted(pendentes, key=lambda a: len(cands[a]))

    melhor: dict[int, Caixa] = {}
    melhor_n = -1
    nos = 0
    total = len(ordem)

    def rec(i: int, atual: list[Caixa], escolha: dict[int, Caixa]) -> bool:
        """Devolve True quando pode parar (cobertura total atingida ou teto de nós)."""
        nonlocal melhor, melhor_n, nos
        nos += 1
        if nos > limite_nos:
            return True
        # Só a COBERTURA é otimizada aqui; o empacotamento entra pela ORDEM das
        # candidatas (mais cheias primeiro), não como objetivo a maximizar. Buscar o
        # melhor empacotamento entre soluções de mesma cobertura fazia a geração passar
        # de 0,3s para 26s no molde real, para ganho nenhum de cobertura.
        if len(escolha) > melhor_n:
            melhor_n, melhor = len(escolha), dict(escolha)
            if melhor_n == total:
                return True                     # não existe cobertura melhor
        if i == total:
            return False
        # Poda: se nem fechando todas as restantes dá para SUPERAR o melhor, não vale
        # descer. `<=` (e não `<`) é o que corta o ramo que só empataria.
        if len(escolha) + (total - i) <= melhor_n:
            return False
        area_id = ordem[i]
        for c in cands[area_id]:
            if viola_restricoes(atual, c, bloq) is None:
                escolha[area_id] = c
                parar = rec(i + 1, atual + [c], escolha)
                del escolha[area_id]
                if parar:
                    return True
        return rec(i + 1, atual, escolha)   # ou desiste desta área

    rec(0, list(comp), {})
    return melhor


def preencher(
    caixas: list[Caixa],
    alunos_ordenados: list[Aluno],
    areas_por_aluno: dict[int, list[int]],
    bloqueados_por_aluno: dict[int, set[int]],
    compromissos: dict[int, list[Caixa]],
    aguardando: list[Aguardando],
) -> None:
    """Preenche as caixas in-place. `areas_por_aluno` = áreas `em_andamento` a alocar.

    Por aluno, calcula a atribuição pelas DUAS estratégias (gulosa e busca) e aplica a
    melhor pelo objetivo do §6.2. Comparar em vez de substituir é o que garante que a
    escala nunca piore em relação ao comportamento anterior — a busca só entra quando
    ganha.

    A ordem dos ALUNOS continua sendo a fila (§6.3): quem vem primeiro leva o assento
    escasso. A melhoria é dentro do aluno, não entre alunos.
    """
    por_area = indexar_por_area(caixas)
    for aluno in alunos_ordenados:
        comp = compromissos.setdefault(aluno.id, [])
        bloq = bloqueados_por_aluno.get(aluno.id, set())
        feitas = {c.area_id for c in comp}
        pendentes = [a for a in areas_por_aluno.get(aluno.id, []) if a not in feitas]
        if not pendentes:
            continue

        guloso = _atribuir_guloso(pendentes, por_area, comp, bloq)
        if len(guloso) == len(pendentes):
            escolha = guloso            # já fechou tudo: não há o que a busca melhore
        else:
            busca = _atribuir_busca(pendentes, por_area, comp, bloq)
            escolha = busca if _qualidade(busca) > _qualidade(guloso) else guloso

        for area_id in sorted(pendentes):
            caixa = escolha.get(area_id)
            if caixa is None:
                continue
            caixa.ocupantes.append(aluno.id)
            comp.append(caixa)
        # O motivo é apurado DEPOIS de aplicar as escolhas: é o estado real em que a área
        # ficou de fora, não um retrato de meio de caminho.
        for area_id in sorted(pendentes):
            if area_id not in escolha:
                tipo, motivo = classificar_sem_vaga(por_area.get(area_id, []), comp, bloq)
                aguardando.append(Aguardando(aluno.id, area_id, motivo, tipo))


def aplicar_pins(
    caixas: list[Caixa],
    pins: list[tuple[int, int, int]],
    bloqueados_por_aluno: dict[int, set[int]],
    compromissos: dict[int, list[Caixa]],
) -> None:
    """Coloca antes os assentos preservados/pinados (§5) como compromissos FIXOS.

    `pins` = lista de (aluno_id, local_id, onda). Casa com a caixa (local, onda); se a onda
    mudou (datas re-derivadas), cai para a caixa viável mais cedo daquele local. O motor
    honra o pin como intocável (não é removido pela consolidação nem pelo auto-preenchimento).
    """
    por_local: dict[int, list[Caixa]] = {}
    for c in caixas:
        por_local.setdefault(c.local.id, []).append(c)

    for aluno_id, local_id, onda in pins:
        comp = compromissos.setdefault(aluno_id, [])
        candidatos = por_local.get(local_id, [])
        if not candidatos:
            continue
        alvo = next((c for c in candidatos if c.onda == onda and c.tem_vaga()), None)
        if alvo is None:
            comvaga = [c for c in candidatos if c.tem_vaga()]
            comvaga.sort(key=lambda c: c.data_inicio)
            alvo = comvaga[0] if comvaga else None
        if alvo is None or aluno_id in alvo.ocupantes:
            continue
        alvo.ocupantes.append(aluno_id)
        alvo.fixos.add(aluno_id)
        comp.append(alvo)
