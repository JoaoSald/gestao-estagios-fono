"""Sessão e senha — as primitivas de autenticação (FASE 6).

Este módulo é PURO: não conhece FastAPI, request nem cookie (quem cuida do cookie é
`app/routers/ui/deps.py`). Aqui só existem três coisas:

  * `Sessao` — quem está logado, do jeito que o resto do sistema pergunta ("pode editar?");
  * token — um JWT assinado com `SECRET_KEY` que vai dentro do cookie, com validade;
  * senha — hash bcrypt (só a coordenação/admin usa senha local; aluno e docente entram
    pelo SSO institucional na FASE B).

Por que JWT e não sessão em banco: são ~5 coordenadores e leitores; guardar sessão em
tabela custaria um SELECT por request para resolver um problema (revogação imediata) que
`usuarios.ativo` + validade curta já cobrem bem o suficiente aqui.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.rotulos import rotulo
from app.models.enums import PERFIS_EDICAO, PerfilUsuario

ALGORITMO = "HS256"

# Nome do cookie que carrega o token. Vive aqui (e não na camada de rotas) porque o
# processador de contexto do Jinja também precisa dele — ver `core/templates.py`.
COOKIE_SESSAO = "sessao"

# bcrypt ignora o que passa de 72 bytes (e a versão 5 levanta erro em vez de truncar).
MAX_BYTES_SENHA = 72


@dataclass(frozen=True)
class Sessao:
    """Identidade do request corrente. É o que as dependências e os templates leem."""

    usuario_id: int
    nome: str
    email: str
    perfil: PerfilUsuario
    matricula: str | None = None

    @property
    def pode_editar(self) -> bool:
        """Única pergunta que decide escrita no sistema todo."""
        return self.perfil in PERFIS_EDICAO

    @property
    def rotulo_perfil(self) -> str:
        return rotulo(self.perfil)

    @property
    def iniciais(self) -> str:
        """Avatar da sidebar: 'Maria Silva' → 'MS'."""
        partes = [p for p in self.nome.split() if p]
        if not partes:
            return "?"
        if len(partes) == 1:
            return partes[0][:2].upper()
        return (partes[0][0] + partes[-1][0]).upper()


# ============================ Senha ============================
def hash_senha(senha: str) -> str:
    """Hash bcrypt (salt embutido). Levanta ValueError se passar do limite do bcrypt."""
    bruto = senha.encode("utf-8")
    if len(bruto) > MAX_BYTES_SENHA:
        raise ValueError("senha acima do limite do bcrypt")
    return bcrypt.hashpw(bruto, bcrypt.gensalt()).decode("ascii")


def hash_sem_senha() -> str:
    """Hash que NENHUMA senha digitada casa — para conta que só entra por SSO.

    `senha_hash` é NOT NULL; deixar string vazia ali seria um hash inválido que
    `senha_confere` recusa por acidente. Aqui a recusa é por construção.
    """
    return bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode("ascii")


def senha_confere(senha: str, hash_guardado: str | None) -> bool:
    """Compara em tempo constante. Hash ausente/corrompido é FALSO, não exceção —
    um registro estranho no banco não pode virar erro 500 na tela de login."""
    if not hash_guardado:
        return False
    try:
        return bcrypt.checkpw(senha.encode("utf-8")[:MAX_BYTES_SENHA], hash_guardado.encode("ascii"))
    except (ValueError, TypeError):
        return False


# ============================ Token de sessão ============================
def criar_token(sessao: Sessao, horas: int | None = None) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=horas or settings.SESSAO_HORAS)
    corpo = {
        "sub": str(sessao.usuario_id),
        "nome": sessao.nome,
        "email": sessao.email,
        "perfil": sessao.perfil.value,
        "mat": sessao.matricula,
        "exp": exp,
    }
    return jwt.encode(corpo, settings.SECRET_KEY, algorithm=ALGORITMO)


def ler_token(token: str | None) -> Sessao | None:
    """Devolve a `Sessao` do token, ou `None` se ausente/expirado/adulterado/de perfil
    que não existe mais (enum mudou entre deploys). Nunca levanta."""
    if not token:
        return None
    try:
        corpo = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITMO])
        return Sessao(
            usuario_id=int(corpo["sub"]),
            nome=corpo.get("nome") or "",
            email=corpo.get("email") or "",
            perfil=PerfilUsuario(corpo["perfil"]),
            matricula=corpo.get("mat"),
        )
    except (JWTError, KeyError, ValueError, TypeError):
        return None
