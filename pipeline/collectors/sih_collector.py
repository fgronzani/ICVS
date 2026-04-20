"""
SIH — Sistema de Informações Hospitalares

Downloads hospitalization records for:
- ICSAP: Internações por Condições Sensíveis à Atenção Primária
- Internações por complicações de diabetes
- Total de internações (denominador para taxas)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from pysus.online_data import SIH
from collectors.utils import ensure_file_list

logger = logging.getLogger(__name__)


def collect_sih(
    ufs: list[str],
    years: list[int],
    data_dir: Optional[str] = None,
) -> pd.DataFrame:
    """
    Download and parse SIH (hospitalization) data.

    Uses group='RD' (Autorização de Internação Hospitalar - Reduzida).

    Returns DataFrame with columns:
        codmunres, ano, mes, diag_princ, val_tot
    """
    data_dir = data_dir or str(Path.home() / "pysus")
    all_dfs = []

    for year in years:
        # Download all 12 months
        months = list(range(1, 13))
        logger.info(f"SIH: baixando ano {year} ({len(months)} meses) para {len(ufs)} UFs...")
        try:
            files = ensure_file_list(SIH.download(
                states=ufs,
                years=year,
                months=months,
                group="RD",
                data_dir=data_dir,
            ))
            for fpath in files:
                try:
                    df = pd.read_parquet(fpath)
                    df.columns = [c.upper() for c in df.columns]

                    cols_map = {
                        "MUNIC_RES": "codmunres",   # Municipality of residence
                        "DIAG_PRINC": "diag_princ",  # Primary diagnosis (ICD-10)
                        "VAL_TOT": "val_tot",         # Total value
                        "QT_DIARIAS": "dias",         # Length of stay
                    }

                    available_cols = {k: v for k, v in cols_map.items() if k in df.columns}
                    df_sel = df[list(available_cols.keys())].rename(columns=available_cols)
                    df_sel["ano"] = year

                    # Municipality code: keep 6 digits
                    if "codmunres" in df_sel.columns:
                        df_sel["codmunres"] = (
                            df_sel["codmunres"].astype(str).str[:6]
                        )

                    all_dfs.append(df_sel)
                except Exception as e:
                    logger.warning(f"  Erro lendo {fpath}: {e}")
        except Exception as e:
            logger.error(f"SIH: erro no download ano {year}: {e}")

    if not all_dfs:
        logger.warning("SIH: nenhum dado obtido")
        return pd.DataFrame()

    result = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"SIH: {len(result)} internações carregadas ({years[0]}-{years[-1]})")
    return result


def aggregate_hospitalizations(
    sih_df: pd.DataFrame,
    icsap_codes: list[str],
) -> pd.DataFrame:
    """
    Aggregate raw SIH records into municipality-year hospitalization indicators.

    Args:
        sih_df: Raw SIH data
        icsap_codes: List of ICD-10 3-char codes from ICSAP list (Portaria 221/2008)

    Returns DataFrame indexed by (codmunres, ano) with columns:
        internacoes_total, internacoes_icsap, internacoes_dm
    """
    if sih_df.empty:
        return pd.DataFrame()

    df = sih_df.copy()

    # Extract 3-char ICD-10 code
    df["cid3"] = df["diag_princ"].astype(str).str[:3].str.upper()

    groups = df.groupby(["codmunres", "ano"])

    icsap_set = set(icsap_codes)
    dm_codes = {"E10", "E11", "E12", "E13", "E14"}

    agg = pd.DataFrame()

    # Total hospitalizations
    agg["internacoes_total"] = groups.size()

    # ICSAP hospitalizations
    agg["internacoes_icsap"] = groups.apply(
        lambda g: g["cid3"].isin(icsap_set).sum()
    )

    # Diabetes complications
    agg["internacoes_dm"] = groups.apply(
        lambda g: g["cid3"].isin(dm_codes).sum()
    )

    return agg.reset_index()
