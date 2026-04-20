"""
SINASC — Sistema de Informação sobre Nascidos Vivos

Downloads live birth records to compute denominators for:
- TMI (nascidos vivos = denominador)
- RMM (nascidos vivos = denominador)
- Pré-natal inadequado (< 6 consultas)
- Taxa de cesáreas SUS
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from pysus.online_data.sinasc import download as sinasc_download
from collectors.utils import ensure_file_list

logger = logging.getLogger(__name__)


def collect_sinasc(
    ufs: list[str],
    years: list[int],
    data_dir: Optional[str] = None,
) -> pd.DataFrame:
    """
    Download and parse SINASC (live births) data.

    Returns DataFrame with columns:
        codmunres, ano, consultas, parto
    """
    data_dir = data_dir or str(Path.home() / "pysus")
    all_dfs = []

    for year in years:
        logger.info(f"SINASC: baixando ano {year} para {len(ufs)} UFs...")
        try:
            files = ensure_file_list(sinasc_download(states=ufs, years=year, data_dir=data_dir))
            for fpath in files:
                try:
                    df = pd.read_parquet(fpath)
                    df.columns = [c.upper() for c in df.columns]

                    cols_map = {
                        "CODMUNRES": "codmunres",  # Municipality of residence
                        "CONSULTAS": "consultas",  # Prenatal visits category
                        "PARTO": "parto",           # 1=vaginal, 2=cesarean
                        "GESTACAO": "gestacao",     # Gestational age
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
                    logger.debug(f"  {fpath.name}: {len(df_sel)} NV")
                except Exception as e:
                    logger.warning(f"  Erro lendo {fpath}: {e}")
        except Exception as e:
            logger.error(f"SINASC: erro no download ano {year}: {e}")

    if not all_dfs:
        logger.warning("SINASC: nenhum dado obtido")
        return pd.DataFrame()

    result = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"SINASC: {len(result)} nascidos vivos carregados ({years[0]}-{years[-1]})")
    return result


def aggregate_births(sinasc_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate raw SINASC records into municipality-year birth indicators.

    Returns DataFrame indexed by (codmunres, ano) with columns:
        nascidos_vivos, partos_cesareos, prenatal_inadequado
    """
    if sinasc_df.empty:
        return pd.DataFrame()

    df = sinasc_df.copy()
    groups = df.groupby(["codmunres", "ano"])

    agg = pd.DataFrame()

    # Total live births
    agg["nascidos_vivos"] = groups.size()

    # Cesarean deliveries (PARTO = 2)
    if "parto" in df.columns:
        agg["partos_cesareos"] = groups.apply(
            lambda g: (g["parto"].astype(str) == "2").sum()
        )
    else:
        agg["partos_cesareos"] = 0

    # Inadequate prenatal (< 6 visits)
    # CONSULTAS encoding: 1=none, 2=1-3, 3=4-6, 4=7+
    # Inadequate = categories 1, 2 (0-3 visits)
    if "consultas" in df.columns:
        agg["prenatal_inadequado"] = groups.apply(
            lambda g: g["consultas"].astype(str).isin(["1", "2"]).sum()
        )
    else:
        agg["prenatal_inadequado"] = 0

    return agg.reset_index()
