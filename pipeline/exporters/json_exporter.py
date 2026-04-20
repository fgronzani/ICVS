"""
JSON Exporter — Generates frontend-compatible JSON files.

Produces:
- icvs_latest.json — All municipalities for the latest year
- municipios/{code}.json — Per-municipality detailed files
- icvs_series.json — Aggregated time series
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class NpEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            if np.isnan(obj):
                return None
            return round(float(obj), 4)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        return super().default(obj)


def export_latest_json(
    df: pd.DataFrame,
    metadata: pd.DataFrame,
    year: int,
    output_dir: Path,
    years_available: list[int] = None,
) -> None:
    """
    Export icvs_latest.json — the main data file for the map page.

    Args:
        df: DataFrame with ICVS scores (one row per municipality)
        metadata: Municipality metadata (nome, uf, regiao)
        year: The latest year
        output_dir: Output directory
        years_available: List of available years
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Merge metadata
    merged = df.merge(metadata, on="codmun", how="left")

    municipios = {}
    for _, row in merged.iterrows():
        code = str(row["codmun"])
        municipios[code] = {
            "codmunicipio": code,
            "nome": row.get("nome", f"Município {code}"),
            "uf": row.get("uf", "??"),
            "regiao": row.get("regiao", "Desconhecida"),
            "populacao": _safe_int(row.get("populacao")),
            "icvs": _safe_float(row.get("icvs")),
            "sub_desfechos": _safe_float(row.get("sub_desfechos")),
            "sub_acesso": _safe_float(row.get("sub_acesso")),
            "sub_qualidade": _safe_float(row.get("sub_qualidade")),
            "icvs_quintil": _safe_int(row.get("icvs_quintil")),
            "cluster": _safe_int(row.get("cluster")),
        }

    output = {
        "ano": year,
        "anos_disponiveis": years_available or [year],
        "municipios": municipios,
    }

    path = output_dir / "icvs_latest.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, cls=NpEncoder)

    logger.info(f"Exportado: {path} ({len(municipios)} municípios)")


def export_municipality_jsons(
    df_all_years: pd.DataFrame,
    metadata: pd.DataFrame,
    indicators_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """
    Export per-municipality JSON files with historical data.

    Args:
        df_all_years: DataFrame with ICVS scores for all years
        metadata: Municipality metadata
        indicators_df: Raw indicator values for detail tables
        output_dir: Output directory (municipios/ subdir)
    """
    mun_dir = output_dir / "municipios"
    mun_dir.mkdir(parents=True, exist_ok=True)

    # Get latest year data for 'info'
    latest_year = df_all_years["ano"].max()
    latest = df_all_years[df_all_years["ano"] == latest_year]

    # Merge metadata with latest year
    latest_merged = latest.merge(metadata, on="codmun", how="left")

    count = 0
    for codmun in df_all_years["codmun"].unique():
        code = str(codmun)

        # Info (latest year)
        info_row = latest_merged[latest_merged["codmun"] == codmun]
        if info_row.empty:
            continue
        info_row = info_row.iloc[0]

        info = {
            "codmunicipio": code,
            "nome": info_row.get("nome", f"Município {code}"),
            "uf": info_row.get("uf", "??"),
            "regiao": info_row.get("regiao", "Desconhecida"),
            "populacao": _safe_int(info_row.get("populacao")),
            "icvs": _safe_float(info_row.get("icvs")),
            "sub_desfechos": _safe_float(info_row.get("sub_desfechos")),
            "sub_acesso": _safe_float(info_row.get("sub_acesso")),
            "sub_qualidade": _safe_float(info_row.get("sub_qualidade")),
            "icvs_quintil": _safe_int(info_row.get("icvs_quintil")),
            "cluster": _safe_int(info_row.get("cluster")),
        }

        # Historical series
        mun_history = df_all_years[df_all_years["codmun"] == codmun].sort_values("ano")
        historico = []
        for _, row in mun_history.iterrows():
            historico.append({
                "ano": int(row["ano"]),
                "icvs": _safe_float(row.get("icvs")),
                "icvs_quintil": _safe_int(row.get("icvs_quintil")),
                "sub_desfechos": _safe_float(row.get("sub_desfechos")),
                "sub_acesso": _safe_float(row.get("sub_acesso")),
                "sub_qualidade": _safe_float(row.get("sub_qualidade")),
            })

        # Detailed indicators for latest year
        indicadores = []
        if not indicators_df.empty:
            from config import ALL_INDICATORS
            mun_ind = indicators_df[
                (indicators_df["codmun"] == codmun)
                & (indicators_df["ano"] == latest_year)
            ]
            if not mun_ind.empty:
                row = mun_ind.iloc[0]
                for ind_name in ALL_INDICATORS:
                    if ind_name in row.index:
                        suav_col = f"{ind_name}_suavizado"
                        indicadores.append({
                            "ano": int(latest_year),
                            "indicador": ind_name,
                            "valor": _safe_float(row.get(ind_name)),
                            "valor_suavizado": _safe_float(
                                row.get(suav_col, row.get(ind_name))
                            ),
                        })

        mun_output = {
            "info": info,
            "icvs_historico": historico,
            "indicadores": indicadores,
        }

        with open(mun_dir / f"{code}.json", "w", encoding="utf-8") as f:
            json.dump(mun_output, f, ensure_ascii=False, cls=NpEncoder)

        count += 1
        if count % 1000 == 0:
            logger.info(f"  ... {count} municípios exportados")

    logger.info(f"Exportados: {count} arquivos em {mun_dir}")


def export_series_json(
    df_all_years: pd.DataFrame,
    metadata: pd.DataFrame,
    output_dir: Path,
) -> None:
    """
    Export aggregated time series (national, by UF, by region).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Merge UF info (avoid duplicate columns from prior merges)
    merge_cols = ["codmun"]
    meta_cols = ["codmun"]
    for col in ["uf", "regiao"]:
        if col in metadata.columns:
            meta_cols.append(col)
        # Drop from df if it already exists to avoid _x/_y suffixes
        if col in df_all_years.columns:
            df_all_years = df_all_years.drop(columns=[col])

    merged = df_all_years.merge(
        metadata[meta_cols],
        on="codmun",
        how="left",
    )

    # Ensure uf and regiao exist
    if "uf" not in merged.columns:
        from config import UF_CODES
        code_to_uf = {v: k for k, v in UF_CODES.items()}
        merged["uf"] = merged["codmun"].astype(str).str[:2].astype(int).map(code_to_uf)
    if "regiao" not in merged.columns:
        from config import UF_REGION
        merged["regiao"] = merged["uf"].map(UF_REGION).fillna("Desconhecida")

    series = {"por_uf": {}, "por_regiao": {}, "nacional": []}

    for year in sorted(merged["ano"].unique()):
        year_df = merged[merged["ano"] == year]

        # National aggregate
        series["nacional"].append({
            "ano": int(year),
            "icvs_medio": _safe_float(year_df["icvs"].mean()),
            "n_municipios": len(year_df),
        })

        # By UF
        for uf, uf_df in year_df.groupby("uf"):
            if uf not in series["por_uf"]:
                series["por_uf"][uf] = []
            series["por_uf"][uf].append({
                "ano": int(year),
                "icvs_medio": _safe_float(uf_df["icvs"].mean()),
                "n_municipios": len(uf_df),
            })

        # By region
        for reg, reg_df in year_df.groupby("regiao"):
            if reg not in series["por_regiao"]:
                series["por_regiao"][reg] = []
            series["por_regiao"][reg].append({
                "ano": int(year),
                "icvs_medio": _safe_float(reg_df["icvs"].mean()),
                "n_municipios": len(reg_df),
            })

    path = output_dir / "icvs_series.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(series, f, ensure_ascii=False, cls=NpEncoder)

    logger.info(f"Exportado: {path}")


def _safe_float(val) -> float:
    """Convert to float, returning None for NaN."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int:
    """Convert to int, returning None for NaN."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
