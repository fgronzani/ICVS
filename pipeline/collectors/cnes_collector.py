"""
CNES — Cadastro Nacional de Estabelecimentos de Saúde

Downloads infrastructure data for:
- Leitos SUS por 1.000 hab
- Médicos por 1.000 hab
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from pysus.online_data import CNES
from collectors.utils import ensure_file_list

logger = logging.getLogger(__name__)


def collect_cnes_leitos(
    ufs: list[str],
    year: int,
    month: int = 12,
    data_dir: Optional[str] = None,
) -> pd.DataFrame:
    """
    Download CNES bed data (group='LT') for a specific month.

    Returns DataFrame with columns:
        codmun, leitos_sus
    """
    data_dir = data_dir or str(Path.home() / "pysus")

    logger.info(f"CNES-LT: baixando {year}/{month:02d} para {len(ufs)} UFs...")
    try:
        files = ensure_file_list(CNES.download(
            group="LT",
            states=ufs,
            years=year,
            months=month,
            data_dir=data_dir,
        ))
    except Exception as e:
        logger.error(f"CNES-LT: erro no download {year}/{month}: {e}")
        return pd.DataFrame()

    all_dfs = []
    for fpath in files:
        try:
            df = pd.read_parquet(fpath)
            df.columns = [c.upper() for c in df.columns]

            # CNES_LT has CODUFMUN (municipality code) and QT_SUS (SUS beds)
            cod_col = None
            for candidate in ["CODUFMUN", "MUNCODIG", "CO_MUNICIO"]:
                if candidate in df.columns:
                    cod_col = candidate
                    break

            qt_col = None
            for candidate in ["QT_SUS", "QT_EXIST"]:
                if candidate in df.columns:
                    qt_col = candidate
                    break

            if cod_col and qt_col:
                df_sel = df[[cod_col, qt_col]].copy()
                df_sel.columns = ["codmun", "leitos_sus"]
                df_sel["codmun"] = df_sel["codmun"].astype(str).str[:6]
                df_sel["leitos_sus"] = pd.to_numeric(df_sel["leitos_sus"], errors="coerce").fillna(0)

                # Aggregate by municipality (sum beds)
                agg = df_sel.groupby("codmun")["leitos_sus"].sum().reset_index()
                all_dfs.append(agg)
            else:
                logger.warning(f"  CNES-LT: colunas esperadas não encontradas em {fpath.name}. "
                               f"Colunas: {list(df.columns[:20])}")
        except Exception as e:
            logger.warning(f"  Erro lendo {fpath}: {e}")

    if not all_dfs:
        return pd.DataFrame()

    result = pd.concat(all_dfs, ignore_index=True)
    result = result.groupby("codmun")["leitos_sus"].sum().reset_index()
    logger.info(f"CNES-LT: {len(result)} municípios com dados de leitos")
    return result


def collect_cnes_profissionais(
    ufs: list[str],
    year: int,
    month: int = 12,
    data_dir: Optional[str] = None,
) -> pd.DataFrame:
    """
    Download CNES professional data (group='PF') for a specific month.

    Returns DataFrame with columns:
        codmun, medicos
    """
    data_dir = data_dir or str(Path.home() / "pysus")

    logger.info(f"CNES-PF: baixando {year}/{month:02d} para {len(ufs)} UFs...")
    try:
        files = ensure_file_list(CNES.download(
            group="PF",
            states=ufs,
            years=year,
            months=month,
            data_dir=data_dir,
        ))
    except Exception as e:
        logger.error(f"CNES-PF: erro no download {year}/{month}: {e}")
        return pd.DataFrame()

    all_dfs = []
    for fpath in files:
        try:
            df = pd.read_parquet(fpath)
            df.columns = [c.upper() for c in df.columns]

            # Find municipality column
            cod_col = None
            for candidate in ["CODUFMUN", "MUNCODIG", "CO_MUNICIO"]:
                if candidate in df.columns:
                    cod_col = candidate
                    break

            # CBO (Classificação Brasileira de Ocupações) for physicians
            # 225 = Médicos (prefix)
            cbo_col = None
            for candidate in ["CBO", "CBO_OCUPA", "CO_CBO"]:
                if candidate in df.columns:
                    cbo_col = candidate
                    break

            if cod_col and cbo_col:
                df["codmun"] = df[cod_col].astype(str).str[:6]
                df["cbo_str"] = df[cbo_col].astype(str)

                # Filter physicians (CBO starting with 225)
                medicos = df[df["cbo_str"].str.startswith("225")]

                # Count unique professionals per municipality
                agg = medicos.groupby("codmun").size().reset_index(name="medicos")
                all_dfs.append(agg)
            else:
                logger.warning(f"  CNES-PF: colunas esperadas não encontradas em {fpath.name}")
        except Exception as e:
            logger.warning(f"  Erro lendo {fpath}: {e}")

    if not all_dfs:
        return pd.DataFrame()

    result = pd.concat(all_dfs, ignore_index=True)
    result = result.groupby("codmun")["medicos"].sum().reset_index()
    logger.info(f"CNES-PF: {len(result)} municípios com dados de médicos")
    return result
