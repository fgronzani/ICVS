"""
Normalizer — Min-max normalization using robust percentiles.

Normalizes all indicators to [0, 1] using P5/P95 truncation
to handle outliers. Optionally inverts indicators where
"higher = better" (e.g., coverage, physicians per capita).
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Indicators where HIGHER values mean LOWER vulnerability
# These need to be inverted so that higher = more vulnerable in all indicators
INVERT_INDICATORS = {
    "leitos_sus_inv",    # More beds = less vulnerable
    "medicos_inv",       # More doctors = less vulnerable
}

# Indicators where the raw value is already "higher = worse"
# (no inversion needed)
DIRECT_INDICATORS = {
    "tmi", "rmm", "apvp_taxa", "mort_prematura_dcnt",
    "proporcao_obitos_evitaveis",
    "cobertura_esf_inv", "cobertura_acs_inv",  # Already inverted at collector level
    "distancia_hospital",
    "taxa_icsap", "taxa_cesareas_sus", "prenatal_inadequado",
    "internacao_dm", "obitos_sem_assistencia",
}


def normalize_indicators(
    df: pd.DataFrame,
    indicator_cols: list[str],
    p_low: int = 5,
    p_high: int = 95,
    use_smoothed: bool = True,
) -> pd.DataFrame:
    """
    Normalize indicator columns to [0, 1] using robust percentile scaling.

    Args:
        df: DataFrame with indicator columns
        indicator_cols: List of indicator column names
        p_low: Lower percentile for floor (default: 5)
        p_high: Upper percentile for ceiling (default: 95)
        use_smoothed: If True, use '{col}_suavizado' when available

    Returns:
        DataFrame with new columns '{col}_norm' for each indicator
    """
    result = df.copy()

    for col in indicator_cols:
        # Choose smoothed or raw
        source_col = f"{col}_suavizado" if (use_smoothed and f"{col}_suavizado" in df.columns) else col
        if source_col not in df.columns:
            logger.warning(f"Coluna {source_col} não encontrada, pulando")
            continue

        values = df[source_col].dropna()

        if len(values) < 10:
            result[f"{col}_norm"] = np.nan
            continue

        # Compute percentile bounds
        floor_val = np.percentile(values, p_low)
        ceil_val = np.percentile(values, p_high)

        if ceil_val == floor_val:
            result[f"{col}_norm"] = 0.5  # Constant indicator
            continue

        # Normalize to [0, 1]
        normalized = (df[source_col] - floor_val) / (ceil_val - floor_val)
        normalized = normalized.clip(0, 1)

        # Invert if needed (higher = better → higher = worse)
        if col in INVERT_INDICATORS:
            normalized = 1 - normalized

        result[f"{col}_norm"] = normalized

        logger.debug(
            f"  {col}: floor={floor_val:.4f}, ceil={ceil_val:.4f}, "
            f"invert={col in INVERT_INDICATORS}"
        )

    n_normalized = sum(1 for c in indicator_cols if f"{c}_norm" in result.columns)
    logger.info(f"Normalização: {n_normalized}/{len(indicator_cols)} indicadores normalizados")

    return result
