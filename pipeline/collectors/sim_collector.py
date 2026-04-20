"""
SIM — Sistema de Informação sobre Mortalidade

Downloads mortality records from DATASUS via PySUS and computes:
- TMI: Taxa de Mortalidade Infantil (infant mortality rate)
- RMM: Razão de Mortalidade Materna (maternal mortality ratio)
- APVP: Anos Potenciais de Vida Perdidos
- Mortalidade prematura por DCNT
- Proporção de óbitos evitáveis
- Óbitos sem assistência médica
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from pysus.online_data import SIM
from collectors.utils import ensure_file_list

logger = logging.getLogger(__name__)

# CID-10 chapters for DCNT (Doenças Crônicas Não Transmissíveis)
# I = Cardiovascular, C = Neoplasms, E = Endocrine, J = Respiratory
DCNT_CID_PREFIXES = ("I", "C", "E1", "J4")

# CID-10 codes for maternal deaths (O00-O99)
MATERNAL_CID_PREFIX = "O"

# CID-10 codes for ill-defined causes (R00-R99)
ILL_DEFINED_PREFIX = "R"

# Lista de causas evitáveis — simplified (CID-10 3-char prefixes)
# Based on Malta et al. (2007) classification
AVOIDABLE_PREFIXES = [
    # Immunization-preventable
    "A33", "A34", "A35", "A36", "A37", "A80", "B05", "B06", "B16", "B26",
    # Infectious/parasitic treatable
    "A00", "A01", "A02", "A03", "A04", "A05", "A15", "A16", "A17", "A18",
    "A19", "A50", "A51", "A52", "A53", "B50", "B51", "B52",
    # Respiratory treatable
    "J00", "J01", "J02", "J03", "J06", "J13", "J14", "J15", "J18",
    "J45", "J46",
    # Cardiovascular treatable
    "I10", "I11", "I50", "I20",
    # Diabetes
    "E10", "E11", "E12", "E13", "E14",
    # Perinatal
    "P00", "P01", "P02", "P03", "P04", "P05", "P07", "P08",
    "P20", "P21", "P22", "P23", "P24", "P25", "P26", "P27", "P28",
    "P35", "P36", "P37", "P38", "P39",
    # Maternal
    "O00", "O01", "O02", "O03", "O04", "O05", "O06", "O07", "O08",
    "O10", "O11", "O12", "O13", "O14", "O15", "O16",
    "O20", "O21", "O22", "O23", "O24", "O25", "O26",
    "O40", "O41", "O42", "O43", "O44", "O45", "O46",
    "O60", "O61", "O62", "O63", "O64", "O65", "O66", "O67", "O68",
    "O70", "O71", "O72", "O73", "O74", "O75",
    "O85", "O86", "O87", "O88", "O89", "O90", "O91",
]


def collect_sim(
    ufs: list[str],
    years: list[int],
    data_dir: Optional[str] = None,
) -> pd.DataFrame:
    """
    Download and parse SIM (mortality) data.

    Returns DataFrame with columns:
        codmunres, ano, idade, sexo, causabas, assistmed
    """
    data_dir = data_dir or str(Path.home() / "pysus")
    all_dfs = []

    for year in years:
        logger.info(f"SIM: baixando ano {year} para {len(ufs)} UFs...")
        try:
            files = ensure_file_list(SIM.download(states=ufs, years=year, data_dir=data_dir))
            for fpath in files:
                try:
                    df = pd.read_parquet(fpath)
                    # Standardize column names (PySUS uses uppercase)
                    df.columns = [c.upper() for c in df.columns]

                    # Extract relevant columns
                    cols_map = {
                        "CODMUNRES": "codmunres",  # Municipality of residence
                        "DTOBITO": "dtobito",
                        "IDADE": "idade_raw",
                        "SEXO": "sexo",
                        "CAUSABAS": "causabas",     # Underlying cause (ICD-10)
                        "ASSISTMED": "assistmed",   # Had medical assistance
                    }

                    available_cols = {k: v for k, v in cols_map.items() if k in df.columns}
                    df_sel = df[list(available_cols.keys())].rename(columns=available_cols)
                    df_sel["ano"] = year

                    # Parse municipality code (keep first 6 digits)
                    if "codmunres" in df_sel.columns:
                        df_sel["codmunres"] = (
                            df_sel["codmunres"].astype(str).str[:6]
                        )

                    # Parse age to years
                    if "idade_raw" in df_sel.columns:
                        df_sel["idade_anos"] = _parse_age_to_years(df_sel["idade_raw"])
                    else:
                        df_sel["idade_anos"] = None

                    all_dfs.append(df_sel)
                    logger.debug(f"  {fpath.name}: {len(df_sel)} registros")
                except Exception as e:
                    logger.warning(f"  Erro lendo {fpath}: {e}")
        except Exception as e:
            logger.error(f"SIM: erro no download ano {year}: {e}")

    if not all_dfs:
        logger.warning("SIM: nenhum dado obtido")
        return pd.DataFrame()

    result = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"SIM: {len(result)} óbitos carregados ({years[0]}-{years[-1]})")
    return result


def _parse_age_to_years(idade_series: pd.Series) -> pd.Series:
    """
    Parse SIM age encoding to years.

    SIM age format: 3-digit code where:
    - 0XX = minutes (ignore)
    - 1XX = hours (ignore)
    - 2XX = days (< 1 year)
    - 3XX = months (< 1 year)
    - 4XX = years (XX = age in years)
    - 5XX = > 100 years
    """
    idade = pd.to_numeric(idade_series, errors="coerce")

    result = pd.Series(index=idade.index, dtype="float64")

    # 4XX → XX years
    mask_years = (idade >= 400) & (idade < 500)
    result[mask_years] = idade[mask_years] - 400

    # 5XX → 100 + XX
    mask_100plus = idade >= 500
    result[mask_100plus] = 100 + (idade[mask_100plus] - 500)

    # 2XX, 3XX → 0 (less than 1 year)
    mask_infant = (idade >= 200) & (idade < 400)
    result[mask_infant] = 0

    # 0XX, 1XX → 0
    mask_neonate = idade < 200
    result[mask_neonate] = 0

    return result


def aggregate_mortality(sim_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate raw SIM records into municipality-year mortality indicators.

    Returns DataFrame indexed by (codmunres, ano) with columns:
        obitos_total, obitos_infantis, obitos_maternos,
        apvp, obitos_dcnt_30_69, obitos_evitaveis, obitos_sem_assist,
        obitos_mal_definidos
    """
    if sim_df.empty:
        return pd.DataFrame()

    df = sim_df.copy()

    # Ensure causabas is string for prefix matching
    df["cid3"] = df["causabas"].astype(str).str[:3].str.upper()

    groups = df.groupby(["codmunres", "ano"])

    agg = pd.DataFrame()

    # Total deaths
    agg["obitos_total"] = groups.size()

    # Infant deaths (age < 1 year old)
    agg["obitos_infantis"] = groups.apply(
        lambda g: (g["idade_anos"] == 0).sum()
    )

    # Maternal deaths (CID O00-O99)
    agg["obitos_maternos"] = groups.apply(
        lambda g: g["cid3"].str.startswith(MATERNAL_CID_PREFIX).sum()
    )

    # APVP — Anos Potenciais de Vida Perdidos (limit = 75)
    from config import APVP_MAX_AGE
    agg["apvp"] = groups.apply(
        lambda g: (APVP_MAX_AGE - g["idade_anos"].clip(upper=APVP_MAX_AGE)).sum()
    )

    # Premature DCNT deaths (30-69 years)
    agg["obitos_dcnt_30_69"] = groups.apply(
        lambda g: (
            (g["idade_anos"] >= 30)
            & (g["idade_anos"] <= 69)
            & g["cid3"].str[:1].isin(["I", "C", "J"])
            | g["cid3"].str[:2].isin(["E1"])
        ).sum()
    )

    # Avoidable deaths
    avoidable_set = set(AVOIDABLE_PREFIXES)
    agg["obitos_evitaveis"] = groups.apply(
        lambda g: g["cid3"].isin(avoidable_set).sum()
    )

    # Deaths without medical assistance
    agg["obitos_sem_assist"] = groups.apply(
        lambda g: (
            g["assistmed"].astype(str).isin(["2", "9", ""])  # 2=no, 9=ignored
        ).sum()
    )

    # Ill-defined deaths (quality flag)
    agg["obitos_mal_definidos"] = groups.apply(
        lambda g: g["cid3"].str.startswith(ILL_DEFINED_PREFIX).sum()
    )

    return agg.reset_index()
