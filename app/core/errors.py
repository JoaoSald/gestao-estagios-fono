"""Exceções de domínio — regras de negócio violadas viram HTTP amigável.

Os services levantam `DomainError` (e subclasses); o `main.py` registra um
handler que traduz para JSON `{"detail": "<mensagem pt-BR>"}` com o status certo.
Assim o service não depende do FastAPI e fica testável isolado.
"""
from __future__ import annotations


class DomainError(Exception):
    """Erro de regra de negócio. `status` vira o código HTTP (default 400)."""

    status_code: int = 400

    def __init__(self, mensagem: str, status_code: int | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        if status_code is not None:
            self.status_code = status_code


class NaoEncontrado(DomainError):
    """Recurso inexistente (HTTP 404)."""

    status_code = 404


class Conflito(DomainError):
    """Viola unicidade ou invariante de estado (HTTP 409)."""

    status_code = 409
