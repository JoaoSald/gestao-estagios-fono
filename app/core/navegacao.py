"""Menu lateral — quem vê o quê, numa fonte só (FASE 6).

Mesma ideia de `passos.py`: a lista sai do template e vira dado, para que "o aluno vê
Estágios e mais nada" seja UMA linha auditável em vez de `{% if %}` espalhado pelo HTML.

O menu não é segurança — é cortesia (não oferecer o que a rota vai recusar). Quem protege
é o gate do router (`routers/acesso.py`). Por isso a regra aqui é a mesma dos gates: item
sem `perfis` vale para todos os perfis autenticados, e o resto é lista explícita.

Perfil novo ⇒ revisar esta lista (e `rotulos.py`, que dá nome a ele na tela).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import PERFIS_EDICAO, PerfilUsuario

# Quem lê o painel/histórico além da comissão. O aluno fica de fora de propósito:
# ele vê a escala publicada, não a operação (fila, pendências, egressos).
LEITURA_AMPLA: frozenset[PerfilUsuario] = frozenset(PERFIS_EDICAO | {PerfilUsuario.docente})


@dataclass(frozen=True)
class Item:
    chave: str          # casa com `ativo` do contexto do shell
    label: str
    icone: str
    url: str
    perfis: frozenset[PerfilUsuario] | None = None   # None = todos os autenticados

    def visivel_para(self, perfil: PerfilUsuario | None) -> bool:
        if perfil is None:
            return False
        return self.perfis is None or perfil in self.perfis


@dataclass(frozen=True)
class Grupo:
    titulo: str
    itens: list[Item] = field(default_factory=list)


MENU: list[Grupo] = [
    Grupo("CADASTROS", [
        Item("alunos", "Alunos", "users", "/ui/alunos", PERFIS_EDICAO),
        Item("areas", "Áreas", "layers", "/ui/areas", PERFIS_EDICAO),
        Item("docentes", "Docentes", "teacher", "/ui/docentes", PERFIS_EDICAO),
        Item("preceptores", "Preceptores", "user", "/ui/preceptores", PERFIS_EDICAO),
        Item("afastamentos", "Afastamentos", "calendarOff", "/ui/afastamentos", PERFIS_EDICAO),
        Item("locais", "Locais", "building", "/ui/locais", PERFIS_EDICAO),
        Item("eventos", "Eventos", "calendar", "/ui/eventos", PERFIS_EDICAO),
    ]),
    Grupo("VISUALIZAÇÕES", [
        Item("painel", "Painel", "dashboard", "/ui/painel", LEITURA_AMPLA),
        Item("estagios", "Estágios", "grid", "/ui/estagios"),          # todos os perfis
        Item("historico", "Histórico", "history", "/ui/historico", LEITURA_AMPLA),
    ]),
    Grupo("OPERAÇÕES", [
        Item("remanejar", "Remanejar", "shuffle", "/ui/remanejar", PERFIS_EDICAO),
        Item("encerrar", "Encerrar ciclo", "power", "/ui/encerrar", PERFIS_EDICAO),
    ]),
]


def menu_de(perfil: PerfilUsuario | None) -> list[Grupo]:
    """Menu filtrado. Grupo que ficou sem item nenhum não aparece — senão o aluno veria
    o cabeçalho "CADASTROS" vazio, sugerindo que algo falhou ao carregar."""
    saida = []
    for grupo in MENU:
        itens = [i for i in grupo.itens if i.visivel_para(perfil)]
        if itens:
            saida.append(Grupo(grupo.titulo, itens))
    return saida
