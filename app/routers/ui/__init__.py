"""Camada de apresentação (FASE 5) — páginas server-rendered (Jinja2) + parciais HTMX.

Separada da API JSON (FASES 3/4), que continua existindo. As rotas UI chamam os
services diretamente e renderizam templates.
"""
from app.routers.ui import cadastros, escala, paginas

__all__ = ["paginas", "cadastros", "escala"]
