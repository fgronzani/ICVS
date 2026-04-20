#!/usr/bin/env python3
"""
Atlas de Vulnerabilidade em Saúde — Pipeline Principal

Uso:
    python main.py                       # Ano atual, todos UFs
    python main.py --year 2022           # Ano específico
    python main.py --ufs SC PR RS        # Apenas essas UFs (desenvolvimento)
    python main.py --skip-download       # Reusar dados já baixados
    python main.py --years 2020 2021 2022  # Múltiplos anos
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Add pipeline directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline ICVS — Índice Composto de Vulnerabilidade em Saúde"
    )
    parser.add_argument("--year", type=int, default=2022,
                        help="Ano mais recente a processar")
    parser.add_argument("--years", type=int, nargs="+", default=None,
                        help="Lista de anos a processar")
    parser.add_argument("--ufs", nargs="+", default=None,
                        help="UFs a processar (default: todas)")
    parser.add_argument("--skip-download", action="store_true",
                        help="Pular download, usar dados em cache")
    parser.add_argument("--output", default=None,
                        help="Diretório de saída (default: docs/data/)")
    parser.add_argument("--data-dir", default=None,
                        help="Diretório para cache PySUS")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
    logger = logging.getLogger("pipeline")

    # Resolve paths
    project_root = Path(__file__).resolve().parent.parent
    output_dir = Path(args.output) if args.output else project_root / "docs" / "data"
    data_dir = args.data_dir or str(Path.home() / "pysus")

    from config import (
        ALL_UFS, DESFECHO_INDICATORS, ACESSO_INDICATORS,
        QUALIDADE_INDICATORS, ALL_INDICATORS, ICSAP_CODES,
        N_CLUSTERS_DEFAULT, NORM_P_LOW, NORM_P_HIGH,
    )

    ufs = args.ufs or ALL_UFS
    years = args.years or [args.year]

    start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"Pipeline ICVS — Anos: {years}, UFs: {len(ufs)}")
    logger.info("=" * 60)

    # ================================================================
    # FASE 1: COLETA
    # ================================================================
    logger.info("\n=== FASE 1: COLETA ===")

    import pandas as pd

    sim_raw = pd.DataFrame()
    sinasc_raw = pd.DataFrame()
    sih_raw = pd.DataFrame()
    leitos_df = pd.DataFrame()
    medicos_df = pd.DataFrame()
    population_df = pd.DataFrame()
    metadata_df = pd.DataFrame()

    if not args.skip_download:
        # SIM — Mortality
        try:
            from collectors.sim_collector import collect_sim, aggregate_mortality
            sim_raw = collect_sim(ufs, years, data_dir=data_dir)
            sim_agg = aggregate_mortality(sim_raw) if not sim_raw.empty else pd.DataFrame()
        except Exception as e:
            logger.error(f"SIM: {e}")
            sim_agg = pd.DataFrame()

        # SINASC — Live births
        try:
            from collectors.sinasc_collector import collect_sinasc, aggregate_births
            sinasc_raw = collect_sinasc(ufs, years, data_dir=data_dir)
            births_agg = aggregate_births(sinasc_raw) if not sinasc_raw.empty else pd.DataFrame()
        except Exception as e:
            logger.error(f"SINASC: {e}")
            births_agg = pd.DataFrame()

        # SIH — Hospitalizations
        try:
            from collectors.sih_collector import collect_sih, aggregate_hospitalizations
            sih_raw = collect_sih(ufs, years, data_dir=data_dir)
            hosp_agg = aggregate_hospitalizations(sih_raw, ICSAP_CODES) if not sih_raw.empty else pd.DataFrame()
        except Exception as e:
            logger.error(f"SIH: {e}")
            hosp_agg = pd.DataFrame()

        # CNES — Infrastructure (latest year only)
        try:
            from collectors.cnes_collector import collect_cnes_leitos, collect_cnes_profissionais
            leitos_df = collect_cnes_leitos(ufs, years[-1], data_dir=data_dir)
            medicos_df = collect_cnes_profissionais(ufs, years[-1], data_dir=data_dir)
        except Exception as e:
            logger.error(f"CNES: {e}")

        # IBGE — Population & metadata
        try:
            from collectors.ibge_collector import collect_population, collect_municipality_metadata
            population_df = collect_population(years)
            metadata_df = collect_municipality_metadata()
        except Exception as e:
            logger.error(f"IBGE: {e}")

    else:
        logger.info("Download pulado (--skip-download)")
        # Load from cache if available
        sim_agg = pd.DataFrame()
        births_agg = pd.DataFrame()
        hosp_agg = pd.DataFrame()

    # ================================================================
    # FASE 2: PROCESSAMENTO
    # ================================================================
    logger.info("\n=== FASE 2: PROCESSAMENTO ===")

    if population_df.empty:
        logger.error("Sem dados de população. Pipeline não pode continuar.")
        sys.exit(1)

    # 2a. Compute rates
    from processors.rate_processor import compute_all_indicators
    indicators = compute_all_indicators(
        mortality=sim_agg,
        births=births_agg,
        hospitalizations=hosp_agg,
        leitos=leitos_df,
        medicos=medicos_df,
        population=population_df,
    )

    if indicators.empty:
        logger.error("Sem indicadores calculados. Pipeline não pode continuar.")
        sys.exit(1)

    # 2b. Bayesian smoothing
    from processors.bayesian_smoothing import smooth_all_indicators

    # Merge UF info for regional smoothing
    if not metadata_df.empty:
        indicators = indicators.merge(
            metadata_df[["codmun", "uf"]], on="codmun", how="left"
        )

    indicators = smooth_all_indicators(indicators)

    # 2c. Normalization
    from processors.normalizer import normalize_indicators
    indicators = normalize_indicators(
        indicators,
        ALL_INDICATORS,
        p_low=NORM_P_LOW,
        p_high=NORM_P_HIGH,
    )

    # ================================================================
    # FASE 3: ÍNDICE
    # ================================================================
    logger.info("\n=== FASE 3: ÍNDICE ===")

    from index.icvs_calculator import compute_icvs, compute_clusters

    # Process each year
    all_years_results = []
    for year in years:
        year_data = indicators[indicators["ano"] == year].copy()
        if year_data.empty:
            logger.warning(f"Sem dados para o ano {year}")
            continue

        # Compute ICVS
        year_result = compute_icvs(
            year_data,
            DESFECHO_INDICATORS,
            ACESSO_INDICATORS,
            QUALIDADE_INDICATORS,
        )

        # Compute clusters (only for latest year)
        if year == years[-1]:
            year_result["cluster"] = compute_clusters(
                year_result, n_clusters=N_CLUSTERS_DEFAULT
            )

        all_years_results.append(year_result)

    if not all_years_results:
        logger.error("Nenhum resultado ICVS gerado.")
        sys.exit(1)

    df_all = pd.concat(all_years_results, ignore_index=True)

    # ================================================================
    # FASE 4: EXPORTAÇÃO
    # ================================================================
    logger.info("\n=== FASE 4: EXPORTAÇÃO ===")

    from exporters.json_exporter import (
        export_latest_json, export_municipality_jsons, export_series_json,
    )

    latest_year = years[-1]
    latest_df = df_all[df_all["ano"] == latest_year]

    # Export icvs_latest.json
    export_latest_json(
        latest_df, metadata_df, latest_year, output_dir,
        years_available=years,
    )

    # Export per-municipality JSONs
    export_municipality_jsons(
        df_all, metadata_df, indicators, output_dir,
    )

    # Export aggregated series
    export_series_json(df_all, metadata_df, output_dir)

    # ================================================================
    # SUMÁRIO
    # ================================================================
    elapsed = time.time() - start_time
    logger.info(f"\n{'=' * 60}")
    logger.info(f"✓ Pipeline concluído em {elapsed:.0f}s")
    logger.info(f"  Anos: {years}")
    logger.info(f"  UFs: {len(ufs)}")
    logger.info(f"  Municípios: {len(latest_df)}")
    logger.info(f"  Indicadores: {len(ALL_INDICATORS)}")
    logger.info(f"  Saída: {output_dir}")
    logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    main()
