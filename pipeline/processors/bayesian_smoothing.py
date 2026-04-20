"""
Bayesian Smoothing — Empirical Bayes estimation for small-area rates.

Municipalities with < 10,000 inhabitants produce unstable rates
(a single additional death can triple the infant mortality rate).

This module applies Empirical Bayes shrinkage to stabilize rates,
pulling extreme values from small municipalities toward regional means.

Method: James-Stein / Empirical Bayes with Gamma-Poisson model.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def bayesian_smooth(
    df: pd.DataFrame,
    rate_col: str,
    numerator_col: str,
    denominator_col: str,
    group_col: str = "uf",
    pop_threshold: int = 10_000,
    reference_pop_threshold: int = 50_000,
) -> pd.Series:
    """
    Apply Empirical Bayes smoothing to a rate column.

    For municipalities with population < pop_threshold, the smoothed rate is:
        lambda_smooth = (events + alpha) / (population + beta)

    Where alpha, beta are estimated from municipalities with
    population > reference_pop_threshold within the same region/UF.

    Args:
        df: DataFrame with rate, numerator, and denominator columns
        rate_col: Name of the rate column to smooth
        numerator_col: Name of the event count column
        denominator_col: Name of the population/denominator column
        group_col: Column to group by for regional priors (default: 'uf')
        pop_threshold: Below this, apply smoothing
        reference_pop_threshold: Use these municipalities to estimate priors

    Returns:
        Smoothed rate series, same index as df
    """
    result = df[rate_col].copy()

    # Process each regional group
    for group_val, group_df in df.groupby(group_col):
        # Reference municipalities (large pop, stable rates)
        ref_mask = group_df[denominator_col] >= reference_pop_threshold
        ref_rates = group_df.loc[ref_mask, rate_col].dropna()

        if len(ref_rates) < 3:
            # Not enough reference municipalities in this group,
            # use all municipalities in the group as reference
            ref_rates = group_df[rate_col].dropna()

        if len(ref_rates) < 2:
            continue  # Skip if still not enough data

        # Estimate hyperparameters from reference population
        mu = ref_rates.mean()
        sigma2 = ref_rates.var()

        if sigma2 == 0 or mu == 0:
            continue

        # Gamma-Poisson: alpha = mu^2 / sigma^2, beta = mu / sigma^2
        alpha = mu ** 2 / sigma2
        beta = mu / sigma2

        # Apply smoothing to small municipalities
        small_mask = (group_df[denominator_col] < pop_threshold) & group_df.index.isin(df.index)
        small_idx = group_df.loc[small_mask].index

        for idx in small_idx:
            events = df.loc[idx, numerator_col]
            pop = df.loc[idx, denominator_col]

            if pd.isna(events) or pd.isna(pop) or pop == 0:
                continue

            # Empirical Bayes estimate
            smoothed = (events + alpha) / (pop + beta)
            result.loc[idx] = smoothed

    n_smoothed = (result != df[rate_col]).sum()
    logger.info(f"Suavização bayesiana [{rate_col}]: {n_smoothed} municípios suavizados")

    return result


def smooth_all_indicators(
    indicators: pd.DataFrame,
    population_col: str = "populacao",
    uf_col: str = None,
) -> pd.DataFrame:
    """
    Apply Bayesian smoothing to all rate indicators.

    For each indicator, creates a new column '{indicator}_suavizado'.

    Args:
        indicators: DataFrame with indicator columns
        population_col: Column name for population
        uf_col: Column for regional grouping (if not provided, uses 'uf')
    """
    df = indicators.copy()

    # Add UF from municipality code if not present
    if uf_col is None and "uf" not in df.columns:
        from config import UF_CODES
        code_to_uf = {v: k for k, v in UF_CODES.items()}
        df["uf"] = df["codmun"].astype(str).str[:2].astype(int).map(code_to_uf)
        uf_col = "uf"
    elif uf_col is None:
        uf_col = "uf"

    # Define which indicators can be smoothed
    # (rate-type indicators with known numerator/denominator)
    smoothing_config = {
        "tmi": {
            "numerator": "obitos_infantis",
            "denominator": "nascidos_vivos",
            "multiplier": 1000,
        },
        "rmm": {
            "numerator": "obitos_maternos",
            "denominator": "nascidos_vivos",
            "multiplier": 100_000,
        },
        "apvp_taxa": {
            "numerator": "apvp",
            "denominator": population_col,
            "multiplier": 1000,
        },
        "taxa_icsap": {
            "numerator": "internacoes_icsap",
            "denominator": population_col,
            "multiplier": 10_000,
        },
        "internacao_dm": {
            "numerator": "internacoes_dm",
            "denominator": population_col,
            "multiplier": 10_000,
        },
    }

    for indicator, config in smoothing_config.items():
        if indicator not in df.columns:
            continue
        if config["numerator"] not in df.columns:
            # If numerator not available, use approximation
            df[f"{indicator}_suavizado"] = df[indicator]
            continue

        try:
            smoothed = bayesian_smooth(
                df,
                rate_col=indicator,
                numerator_col=config["numerator"],
                denominator_col=config["denominator"],
                group_col=uf_col,
            )
            df[f"{indicator}_suavizado"] = smoothed
        except Exception as e:
            logger.warning(f"Erro na suavização de {indicator}: {e}")
            df[f"{indicator}_suavizado"] = df[indicator]

    # For indicators without explicit smoothing, copy raw value
    from config import ALL_INDICATORS
    for ind in ALL_INDICATORS:
        suav_col = f"{ind}_suavizado"
        if ind in df.columns and suav_col not in df.columns:
            df[suav_col] = df[ind]

    logger.info(f"Suavização concluída: {len(smoothing_config)} indicadores processados")
    return df
