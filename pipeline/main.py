#!/usr/bin/env python3
"""
Atlas de Vulnerabilidade em Saúde — Pipeline Principal

Uso:
    python main.py                      # Ano atual, todos UFs
    python main.py --year 2022          # Ano específico
    python main.py --ufs SP RJ MG       # Apenas essas UFs (para desenvolvimento)
    python main.py --skip-download      # Reusar dados já baixados
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add pipeline directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline ICVS — Índice Composto de Vulnerabilidade em Saúde"
    )
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--ufs", nargs="+", default=None)  # None = todos
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--output", default="docs/data/")
    parser.add_argument("--db", default="atlas.db")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
    logger = logging.getLogger("main")

    from config import ALL_UFS

    ufs = args.ufs or ALL_UFS

    logger.info(f"Pipeline ICVS — Ano: {args.year}, UFs: {len(ufs)}")

    # 1. Coleta
    if not args.skip_download:
        logger.info("=== FASE 1: COLETA ===")
        # TODO: Implementar coletores
        # from collectors.sim_collector import collect_sim
        # from collectors.sinasc_collector import collect_sinasc
        # from collectors.sih_collector import collect_sih
        # from collectors.cnes_collector import collect_cnes
        # from collectors.aps_collector import collect_aps_coverage
        # from collectors.ibge_collector import collect_population
        logger.warning("Coletores ainda não implementados — usar dados sintéticos")

    # 2. Processamento
    logger.info("=== FASE 2: PROCESSAMENTO ===")
    # TODO: Implementar processadores
    logger.warning("Processadores ainda não implementados")

    # 3. Índice
    logger.info("=== FASE 3: ÍNDICE ===")
    # TODO: Implementar cálculo do ICVS
    logger.warning("Cálculo do ICVS ainda não implementado")

    # 4. Validação
    logger.info("=== FASE 4: VALIDAÇÃO ===")
    # TODO: Implementar validação
    logger.warning("Validação ainda não implementada")

    # 5. Exportação
    logger.info("=== FASE 5: EXPORTAÇÃO ===")
    # TODO: Implementar exportador JSON
    logger.warning("Exportador ainda não implementado")

    logger.info("=== PIPELINE COMPLETO (modo stub) ===")


if __name__ == "__main__":
    main()
