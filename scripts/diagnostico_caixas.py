"""Diagnóstico: lista os locais ATIVOS que NÃO geram nenhuma caixa no ciclo.

Um local que precisa de N encontros mas tem menos de N datas viáveis (feriados,
afastamentos, recesso, indisponibilidades) some da escala em silêncio — este script
mostra exatamente quais, com viáveis vs N. Somente leitura, não altera nada.

Uso: python scripts/diagnostico_caixas.py
"""
from __future__ import annotations

from app.core.database import SessionLocal
from app.models.ciclo import Ciclo
from app.services.motor.calendario import carregar_contexto, ocorrencias_dia
from app.services.motor.molde import caixas_do_local, locais_ativos


def main() -> None:
    db = SessionLocal()
    try:
        ciclo = db.query(Ciclo).order_by(Ciclo.id.desc()).first()
        if ciclo is None:
            print("Nenhum ciclo encontrado.")
            return
        ctx = carregar_contexto(db, ciclo)
        print(f"Ciclo {ciclo.id}: {ciclo.data_inicio} → {ciclo.data_fim}\n")
        problemas = 0
        for l in locais_ativos(db, ciclo):
            n = l.numero_encontros
            ocorr = len(ocorrencias_dia(l.dia_semana, ciclo.data_inicio, ciclo.data_fim))
            viaveis = len(ctx.datas_viaveis(l, ciclo))
            caixas = len(caixas_do_local(l, ciclo, ctx))
            if caixas == 0:
                problemas += 1
                print(f"❌ área {l.area_id} · '{l.campo}' · {l.dia_semana.value}/{l.turno.value}: "
                      f"ocorrências={ocorr} viáveis={viaveis} N={n} → 0 caixas "
                      f"(bloqueadas {ocorr - viaveis}; faltam {max(0, n - viaveis)})")
        if problemas == 0:
            print("✅ Todos os locais ativos geram ao menos uma caixa.")
        else:
            print(f"\n{problemas} local(is) sem caixa. Ajuste carga/horas_sessao, ofereça outro dia ou estenda o ciclo.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
