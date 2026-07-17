"""Seed reproduzível dos catálogos (ciclo 2026, áreas, docentes, locais).

Executa o SQL canônico `docs/seed_v2.sql` (fonte de verdade, derivado do
ESPELHO 2026) contra o banco apontado por DATABASE_URL (.env).

- Re-executável: limpa os catálogos (TRUNCATE ... RESTART IDENTITY CASCADE)
  antes de inserir. CUIDADO: o CASCADE em `ciclos` apaga também alunos,
  matrículas, eventos etc. — use só para (re)semear um banco de catálogo.

Uso: 
    python scripts/seed.py
"""
import sys
from pathlib import Path

from sqlalchemy import text

# Permite rodar como "python scripts/seed.py" a partir da raiz do repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine  # noqa: E402

SEED_SQL = Path(__file__).resolve().parents[1] / "docs" / "seed_v2.sql"

# Ordem de TRUNCATE (filhos antes; CASCADE cobre dependentes de ciclos).
TABELAS_CATALOGO = ["locais", "preceptores", "docentes", "areas", "ciclos"]


def _corpo_sql() -> str:
    """Lê o seed_v2.sql e remove comentários e o BEGIN/COMMIT (a transação
    é controlada aqui). Sobram só os INSERTs e os setval()."""
    linhas = []
    for raw in SEED_SQL.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s.startswith("--") or s == "":
            continue
        if s.upper() in ("BEGIN;", "COMMIT;"):
            continue
        linhas.append(raw)
    return "\n".join(linhas)


def main() -> None:
    corpo = _corpo_sql()
    with engine.begin() as conn:
        print("Limpando catálogos (TRUNCATE ... RESTART IDENTITY CASCADE)…")
        conn.execute(text(
            "TRUNCATE TABLE " + ", ".join(TABELAS_CATALOGO) + " RESTART IDENTITY CASCADE"
        ))
        print("Inserindo seed de docs/seed_v2.sql…")
        conn.exec_driver_sql(corpo)

    # Conferência
    with engine.connect() as conn:
        print("\n[OK] Seed aplicado. Contagens:")
        for t in ["ciclos", "areas", "docentes", "preceptores", "locais"]:
            n = conn.execute(text(f"SELECT count(*) FROM {t}")).scalar()
            print(f"   - {t:12s}: {n}")


if __name__ == "__main__":
    main()
