"""Regras de Usuários — autenticação e perfil de acesso (FASE 6).

Independente do FastAPI (testável isolado): fala `DomainError`, não HTTP. Quem traduz
para redirect/403 é `routers/ui/deps.py` + os handlers do `main.py`.

Senha local é acesso de EXCEÇÃO: serve à coordenação/admin (e aos testes) e para o dia
em que o SSO institucional estiver fora do ar. O caminho normal de aluno e docente é o
login institucional (FASE B) — por isso `criar` aceita `senha=None`, gravando um hash
impossível de casar em vez de deixar a coluna vazia.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import seguranca
from app.core.errors import Conflito, DomainError
from app.core.seguranca import Sessao
from app.models.enums import PerfilUsuario
from app.models.usuario import Usuario
from app.services import common

# Credenciais erradas devolvem SEMPRE a mesma frase: dizer "e-mail não existe" conta a
# quem tenta quais e-mails são válidos.
FALHA_LOGIN = "E-mail ou senha inválidos."


def listar(db: Session, incluir_inativos: bool = True) -> list[Usuario]:
    q = select(Usuario).order_by(Usuario.nome)
    if not incluir_inativos:
        q = q.where(Usuario.ativo.is_(True))
    return list(db.scalars(q).all())


def obter(db: Session, usuario_id: int) -> Usuario:
    return common.obter_ou_404(db, Usuario, usuario_id, "Usuário")


def por_email(db: Session, email: str) -> Usuario | None:
    """Busca sem diferenciar maiúsculas: e-mail digitado no login não é case-sensitive."""
    return db.scalars(
        select(Usuario).where(func.lower(Usuario.email) == (email or "").strip().lower())
    ).first()


def _validar_senha(senha: str) -> None:
    if len(senha) < 8:
        raise DomainError("A senha deve ter ao menos 8 caracteres.")
    if len(senha.encode("utf-8")) > seguranca.MAX_BYTES_SENHA:
        raise DomainError("A senha é longa demais (máximo de 72 caracteres).")


def criar(
    db: Session,
    nome: str,
    email: str,
    perfil: PerfilUsuario,
    senha: str | None = None,
    matricula: str | None = None,
) -> Usuario:
    email = (email or "").strip().lower()
    if not email:
        raise DomainError("Informe o e-mail do usuário.")
    if por_email(db, email) is not None:
        raise Conflito(f"Já existe um usuário com o e-mail '{email}'.")
    if senha is not None:
        _validar_senha(senha)

    usuario = Usuario(
        nome=(nome or "").strip(),
        email=email,
        # Sem senha → hash de um valor aleatório: a coluna é NOT NULL e nenhuma senha
        # digitada pode casar com ele (só o SSO ou um reset abre esta conta).
        senha_hash=seguranca.hash_senha(senha) if senha else seguranca.hash_sem_senha(),
        perfil=perfil,
        matricula=(matricula or None),
        created_at=datetime.now(),
    )
    db.add(usuario)
    common.commit(db, f"Não foi possível criar o usuário '{email}'.")
    db.refresh(usuario)
    return usuario


def autenticar(db: Session, email: str, senha: str) -> Sessao:
    """Valida e-mail + senha e devolve a `Sessao`. Erro único para qualquer falha."""
    usuario = por_email(db, email)
    if usuario is None or not usuario.ativo:
        raise DomainError(FALHA_LOGIN, status_code=401)
    if not seguranca.senha_confere(senha, usuario.senha_hash):
        raise DomainError(FALHA_LOGIN, status_code=401)

    usuario.ultimo_acesso = datetime.now()
    common.commit(db, "Não foi possível registrar o acesso.")
    return sessao_de(usuario)


def sessao_de(usuario: Usuario) -> Sessao:
    return Sessao(
        usuario_id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
        perfil=usuario.perfil,
        matricula=usuario.matricula,
    )


def trocar_senha(db: Session, usuario_id: int, senha_nova: str) -> Usuario:
    usuario = obter(db, usuario_id)
    _validar_senha(senha_nova)
    usuario.senha_hash = seguranca.hash_senha(senha_nova)
    common.commit(db, "Não foi possível trocar a senha.")
    db.refresh(usuario)
    return usuario


def definir_perfil(db: Session, usuario_id: int, perfil: PerfilUsuario) -> Usuario:
    usuario = obter(db, usuario_id)
    usuario.perfil = perfil
    common.commit(db, "Não foi possível alterar o perfil.")
    db.refresh(usuario)
    return usuario


def desativar(db: Session, usuario_id: int) -> Usuario:
    """Soft-delete: revoga o acesso sem apagar o registro (preserva `ultimo_acesso`).

    A sessão já emitida continua válida até expirar — é o preço de não guardar sessão
    em banco (ver `core/seguranca.py`); por isso a validade do cookie é curta.
    """
    usuario = obter(db, usuario_id)
    usuario.ativo = False
    common.commit(db, "Não foi possível desativar o usuário.")
    db.refresh(usuario)
    return usuario


def existe_algum_editor(db: Session) -> bool:
    """Há alguém capaz de operar o sistema? Usado pelo script de bootstrap de contas
    para não deixar o sistema trancado sem nenhuma conta de coordenação."""
    return db.scalars(
        select(Usuario).where(
            Usuario.ativo.is_(True),
            Usuario.perfil.in_([PerfilUsuario.administrador, PerfilUsuario.coordenacao]),
        )
    ).first() is not None
