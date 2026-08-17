"""Cria (ou atualiza) uma conta de acesso — FASE 6.

Fica fora do `seed.py` de propósito: `usuarios` NÃO está na lista de TRUNCATE do seed,
então as contas sobrevivem a um re-semeio dos catálogos. Semear usuário junto perderia
essa propriedade (e colocaria senha em arquivo versionado).

Uso:
    python scripts/criar_usuario.py "Nome Sobrenome" email@ufcspa.edu.br coordenacao
    python scripts/criar_usuario.py "Ana Souza" ana@aluno.ufcspa.edu.br aluno --matricula 20231234

A senha é pedida no terminal (não vai em argumento, que ficaria no histórico do shell).
Perfis: administrador | coordenacao | docente | aluno.
"""
import argparse
import getpass
import sys
from pathlib import Path

# Permite rodar como "python scripts/criar_usuario.py" a partir da raiz do repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.core.errors import DomainError  # noqa: E402
from app.models.enums import PerfilUsuario  # noqa: E402
from app.services import usuario as usuario_service  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Cria ou atualiza um usuário do sistema.")
    ap.add_argument("nome")
    ap.add_argument("email")
    ap.add_argument("perfil", choices=[p.value for p in PerfilUsuario])
    ap.add_argument("--matricula", default=None, help="Só para perfil aluno.")
    args = ap.parse_args()

    senha = getpass.getpass("Senha (mín. 8 caracteres): ")
    if senha != getpass.getpass("Repita a senha: "):
        print("As senhas não coincidem.", file=sys.stderr)
        return 1

    perfil = PerfilUsuario(args.perfil)
    db = SessionLocal()
    try:
        existente = usuario_service.por_email(db, args.email)
        if existente is not None:
            # Reexecutar o script troca senha/perfil em vez de estourar unique — é assim
            # que se recupera o acesso de alguém que esqueceu a senha.
            usuario_service.trocar_senha(db, existente.id, senha)
            usuario_service.definir_perfil(db, existente.id, perfil)
            print(f"Usuário {args.email} atualizado (perfil {perfil.value}, senha trocada).")
            return 0
        u = usuario_service.criar(
            db, nome=args.nome, email=args.email, perfil=perfil,
            senha=senha, matricula=args.matricula,
        )
        print(f"Usuário criado: #{u.id} {u.email} · perfil {u.perfil.value}")
        return 0
    except DomainError as exc:
        print(f"Erro: {exc.mensagem}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
