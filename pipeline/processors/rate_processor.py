"""
Rate Processor — Computes all 15 health indicators from raw aggregated data.

Takes aggregated counts from collectors and population data,
computes per-capita rates, and merges into a single indicator matrix.
"""
from __future__ import annotations

import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def compute_all_indicators(
    mortality: pd.DataFrame,
    births: pd.DataFrame,
    hospitalizations: pd.DataFrame,
    leitos: pd.DataFrame,
    medicos: pd.DataFrame,
    population: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute all 15 ICVS indicators for each municipality-year.

    Returns DataFrame indexed by (codmun, ano) with one column per indicator.
    """
    # Start with population base
    df = population[["codmun", "ano", "populacao"]].copy()

    # ---- Merge aggregated data ----
    if not mortality.empty:
        df = df.merge(mortality, left_on=["codmun", "ano"],
                      right_on=["codmunres", "ano"], how="left")
        if "codmunres" in df.columns:
            df.drop(columns=["codmunres"], inplace=True)

    if not births.empty:
        df = df.merge(births, left_on=["codmun", "ano"],
                      right_on=["codmunres", "ano"], how="left")
        if "codmunres" in df.columns:
            df.drop(columns=["codmunres"], inplace=True)

    if not hospitalizations.empty:
        df = df.merge(hospitalizations, left_on=["codmun", "ano"],
                      right_on=["codmunres", "ano"], how="left")
        if "codmunres" in df.columns:
            df.drop(columns=["codmunres"], inplace=True)

    # ---- Compute indicators ----

    # Fill NaN counts with 0
    count_cols = [
        "obitos_total", "obitos_infantis", "obitos_maternos", "apvp",
        "obitos_dcnt_30_69", "obitos_evitaveis", "obitos_sem_assist",
        "obitos_mal_definidos",
        "nascidos_vivos", "partos_cesareos", "prenatal_inadequado",
        "internacoes_total", "internacoes_icsap", "internacoes_dm",
    ]
    for col in count_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)
        else:
            df[col] = 0

    pop = df["populacao"].replace(0, np.nan)
    nv = df["nascidos_vivos"].replace(0, np.nan)

    # --- Sub-índice A: Desfechos em Saúde ---

    # TMI: óbitos infantis / nascidos vivos × 1000
    df["tmi"] = (df["obitos_infantis"] / nv) * 1000

    # RMM: óbitos maternos / nascidos vivos × 100.000
    df["rmm"] = (df["obitos_maternos"] / nv) * 100_000

    # APVP por 1.000 hab
    df["apvp_taxa"] = (df["apvp"] / pop) * 1000

    # Mortalidade prematura DCNT (30-69 anos) por 100.000
    # Ideally we'd use pop_30_69, but approximation: pop * 0.45
    pop_30_69 = pop * 0.45  # Approximate fraction
    df["mort_prematura_dcnt"] = (df["obitos_dcnt_30_69"] / pop_30_69) * 100_000

    # Proporção de óbitos evitáveis
    obitos_total = df["obitos_total"].replace(0, np.nan)
    df["proporcao_obitos_evitaveis"] = df["obitos_evitaveis"] / obitos_total

    # --- Sub-índice B: Acesso e Capacidade ---

    # ESF/ACS coverage will be merged from separate collector (placeholder)
    df["cobertura_esf_inv"] = np.nan  # Will be filled from eGestor
    df["cobertura_acs_inv"] = np.nan

    # Leitos SUS por 1.000 hab
    if not leitos.empty:
        df = df.merge(leitos, on="codmun", how="left")
        df["leitos_sus_per_1000"] = (df["leitos_sus"].fillna(0) / pop) * 1000
        # Invert: higher is better, so 1 - normalized value
        # Will be normalized later, for now store raw
        df["leitos_sus_inv"] = df["leitos_sus_per_1000"]
    else:
        df["leitos_sus_inv"] = np.nan

    # Médicos por 1.000 hab
    if not medicos.empty:
        df = df.merge(medicos, on="codmun", how="left")
        df["medicos_per_1000"] = (df["medicos"].fillna(0) / pop) * 1000
        df["medicos_inv"] = df["medicos_per_1000"]
    else:
        df["medicos_inv"] = np.nan

    # Distância ao hospital — would need geocoding (placeholder)
    df["distancia_hospital"] = np.nan

    # --- Sub-índice C: Qualidade da Atenção ---

    # ICSAP por 10.000 hab
    df["taxa_icsap"] = (df["internacoes_icsap"] / pop) * 10_000

    # Taxa de cesáreas SUS
    df["taxa_cesareas_sus"] = df["partos_cesareos"] / nv

    # Pré-natal inadequado (proporção)
    df["prenatal_inadequado"] = df["prenatal_inadequado"] / nv

    # Internações por complicações de DM por 10.000 hab
    df["internacao_dm"] = (df["internacoes_dm"] / pop) * 10_000

    # Óbitos sem assistência médica (proporção)
    df["obitos_sem_assistencia"] = df["obitos_sem_assist"] / obitos_total

    # --- Quality flag ---
    df["flag_mal_definidos"] = df["obitos_mal_definidos"] / obitos_total

    # Select only indicator columns
    from config import ALL_INDICATORS
    indicator_cols = ["codmun", "ano", "populacao"] + ALL_INDICATORS + ["flag_mal_definidos"]
    available = [c for c in indicator_cols if c in df.columns]

    result = df[available].copy()
    logger.info(f"Indicadores calculados: {len(result)} registros, {len(available) - 3} indicadores")
    return result
