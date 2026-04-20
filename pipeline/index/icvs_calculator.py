"""
PCA-based ICVS Index Computation

Computes the Índice Composto de Vulnerabilidade em Saúde using:
1. PCA within each sub-index (desfechos, acesso, qualidade)
2. Weighted combination of sub-indices (40/35/25)
3. K-Means clustering for municipality typology (6 clusters)
4. Quintile classification
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer

logger = logging.getLogger(__name__)


def compute_subindex_pca(
    df: pd.DataFrame,
    indicator_cols: list[str],
    subindex_name: str,
    min_variance_explained: float = 0.25,
) -> pd.Series:
    """
    Compute a sub-index score via PCA.

    Steps:
    1. Standardize indicators (z-score)
    2. Run PCA, extract PC1 loadings
    3. If PC1 explains >= min_variance_explained, use it as weights
    4. Otherwise, use equal weights

    Args:
        df: DataFrame with normalized indicator columns ('{col}_norm')
        indicator_cols: List of indicator names (without '_norm' suffix)
        subindex_name: Name for logging
        min_variance_explained: Minimum variance for PC1 (default: 0.25)

    Returns:
        Series with sub-index scores scaled to [0, 100]
    """
    # Use normalized columns
    norm_cols = [f"{c}_norm" for c in indicator_cols]
    available = [c for c in norm_cols if c in df.columns]

    if len(available) < 2:
        logger.warning(f"PCA [{subindex_name}]: apenas {len(available)} indicadores disponíveis, usando média simples")
        if available:
            return df[available].mean(axis=1) * 100
        return pd.Series(50.0, index=df.index)

    # Extract data matrix
    X = df[available].copy()

    # Drop columns that are entirely NaN (can't be imputed)
    valid_cols = [c for c in available if X[c].notna().any()]
    if len(valid_cols) < 2:
        logger.warning(f"PCA [{subindex_name}]: apenas {len(valid_cols)} indicadores com dados, usando média simples")
        if valid_cols:
            return df[valid_cols].mean(axis=1) * 100
        return pd.Series(50.0, index=df.index)

    X = X[valid_cols]
    available = valid_cols

    # Impute missing values (median strategy)
    imputer = SimpleImputer(strategy="median")
    X_imputed = pd.DataFrame(
        imputer.fit_transform(X),
        columns=available,
        index=X.index,
    )

    # Standardize
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(
        scaler.fit_transform(X_imputed),
        columns=available,
        index=X.index,
    )

    # PCA
    pca = PCA()
    pca.fit(X_scaled)

    variance_explained = pca.explained_variance_ratio_[0]
    logger.info(
        f"PCA [{subindex_name}]: PC1 explica {variance_explained:.1%} da variância"
        f" ({len(available)} indicadores)"
    )

    if variance_explained >= min_variance_explained:
        # Use PC1 loadings as weights
        loadings = pca.components_[0]

        # Ensure positive direction (higher = more vulnerable)
        # If most loadings are negative, flip the sign
        if np.mean(loadings) < 0:
            loadings = -loadings

        # Normalize to sum to 1
        weights = np.abs(loadings) / np.abs(loadings).sum()

        logger.info(f"  Pesos PCA: {dict(zip(available, weights.round(3)))}")

        # Weighted sum on normalized (not standardized) values
        score = X_imputed.values @ weights
    else:
        logger.warning(
            f"PCA [{subindex_name}]: PC1 < {min_variance_explained:.0%}, "
            f"usando pesos iguais"
        )
        score = X_imputed.mean(axis=1).values

    # Scale to [0, 100]
    score_min = np.nanpercentile(score, 1)
    score_max = np.nanpercentile(score, 99)
    if score_max > score_min:
        score = (score - score_min) / (score_max - score_min) * 100
    score = np.clip(score, 0, 100)

    return pd.Series(score, index=df.index)


def compute_icvs(
    df: pd.DataFrame,
    desfecho_indicators: list[str],
    acesso_indicators: list[str],
    qualidade_indicators: list[str],
    weights: dict[str, float] = None,
) -> pd.DataFrame:
    """
    Compute the full ICVS index.

    Args:
        df: DataFrame with normalized indicator columns
        desfecho_indicators: Indicator names for sub-index A
        acesso_indicators: Indicator names for sub-index B
        qualidade_indicators: Indicator names for sub-index C
        weights: Dict with keys 'desfechos', 'acesso', 'qualidade'

    Returns:
        DataFrame with new columns: sub_desfechos, sub_acesso,
        sub_qualidade, icvs, icvs_quintil
    """
    if weights is None:
        from config import SUBINDEX_WEIGHTS
        weights = SUBINDEX_WEIGHTS

    result = df.copy()

    # Compute sub-indices via PCA
    result["sub_desfechos"] = compute_subindex_pca(
        df, desfecho_indicators, "Desfechos"
    )
    result["sub_acesso"] = compute_subindex_pca(
        df, acesso_indicators, "Acesso"
    )
    result["sub_qualidade"] = compute_subindex_pca(
        df, qualidade_indicators, "Qualidade"
    )

    # Weighted combination
    result["icvs"] = (
        result["sub_desfechos"] * weights["desfechos"]
        + result["sub_acesso"] * weights["acesso"]
        + result["sub_qualidade"] * weights["qualidade"]
    )

    # Clip to [0, 100]
    for col in ["sub_desfechos", "sub_acesso", "sub_qualidade", "icvs"]:
        result[col] = result[col].clip(0, 100).round(2)

    # Quintile classification (robust: rank-based)
    valid_mask = result["icvs"].notna()
    result["icvs_quintil"] = 3  # Default middle quintile
    if valid_mask.sum() >= 5:
        ranks = result.loc[valid_mask, "icvs"].rank(pct=True)
        result.loc[valid_mask, "icvs_quintil"] = pd.cut(
            ranks, bins=[0, 0.2, 0.4, 0.6, 0.8, 1.0],
            labels=[1, 2, 3, 4, 5], include_lowest=True,
        ).astype(int)

    logger.info(
        f"ICVS calculado: média={result['icvs'].mean():.1f}, "
        f"mediana={result['icvs'].median():.1f}, "
        f"std={result['icvs'].std():.1f}"
    )

    return result


def compute_clusters(
    df: pd.DataFrame,
    n_clusters: int = 6,
    features: list[str] = None,
) -> pd.Series:
    """
    Cluster municipalities into typologies using K-Means.

    Default features: population (log), sub-indices, region.

    Returns:
        Series with cluster labels (0 to n_clusters-1)
    """
    if features is None:
        features = []

        # Population (log-scaled)
        if "populacao" in df.columns:
            df = df.copy()  # avoid SettingWithCopyWarning
            df["log_pop"] = pd.to_numeric(df["populacao"], errors="coerce").fillna(10000).apply(lambda x: float(x)).pipe(np.log1p)
            features.append("log_pop")

        # Sub-indices
        for sub in ["sub_desfechos", "sub_acesso", "sub_qualidade"]:
            if sub in df.columns:
                features.append(sub)

    if len(features) < 2:
        logger.warning("Clustering: features insuficientes")
        return pd.Series(0, index=df.index)

    X = df[features].copy()

    # Impute and scale
    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imputed)

    # K-Means
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    # Order clusters by mean ICVS (0 = least vulnerable)
    if "icvs" in df.columns:
        cluster_means = df.groupby(labels)["icvs"].mean().sort_values()
        label_map = {old: new for new, old in enumerate(cluster_means.index)}
        labels = pd.Series(labels).map(label_map).values

    logger.info(f"Clustering: {n_clusters} clusters, distribuição: {np.bincount(labels)}")

    return pd.Series(labels, index=df.index)
