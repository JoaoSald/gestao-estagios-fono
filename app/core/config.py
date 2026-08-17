"""Configurações da aplicação — lidas do arquivo .env (nunca hardcoded)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do repositório (…/gestao-estagios-fono). Este arquivo é app/core/config.py.
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Conexão com o PostgreSQL. Vem do .env; sem valor padrão de propósito
    # (se faltar, a aplicação falha cedo e com mensagem clara).
    DATABASE_URL: str

    # Chave de assinatura de tokens (FASE 6). Padrão só serve pra dev.
    SECRET_KEY: str = "dev-inseguro-trocar"

    # Validade do cookie de sessão, em horas (cobre um dia de trabalho da comissão).
    SESSAO_HORAS: int = 12

    # dev | prod
    APP_ENV: str = "dev"

    @property
    def em_producao(self) -> bool:
        """Cookie `secure`, CORS fechado e afins dependem disto — um lugar só."""
        return self.APP_ENV != "dev"


settings = Settings()
