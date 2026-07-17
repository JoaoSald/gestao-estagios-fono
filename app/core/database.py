"""Conexão com o banco: engine, sessão e Base declarativa (SQLAlchemy 2.x, síncrono)."""
from collections.abc import Generator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Convenção de nomes para constraints/índices → migrations estáveis e previsíveis.
NAMING_CONVENTION = {
    "ix": "idx_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    # CHECKs já têm nome explícito nos models (ck_area_carga, ck_ciclo_datas…) → passa verbatim.
    "ck": "%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# echo=True só em dev para ver o SQL gerado.
engine = create_engine(
    settings.DATABASE_URL,
    echo=(settings.APP_ENV == "dev" and False),  # ligue trocando para True quando quiser depurar SQL
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency do FastAPI: abre uma sessão por request e fecha no fim."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
