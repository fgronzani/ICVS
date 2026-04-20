"""
IBGE Population Data Collector

Fetches population estimates from IBGE SIDRA API.
Also provides municipality metadata (name, region, etc.).
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# IBGE SIDRA API tables for population
# 6579: Estimativas 2001-2021 (single variable)
# 9514: Censo 2022 (multiple dimensions — needs filtering)
SIDRA_TABLES = [
    {"table": 6579, "variable": "9324", "years": range(2013, 2022)},
    {"table": 9514, "variable": "93", "years": [2022]},
]

# IBGE localidades API
LOCALIDADES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"


def collect_population(years: list[int]) -> pd.DataFrame:
    """
    Fetch population estimates from IBGE SIDRA for all municipalities.

    Returns DataFrame with columns:
        codmun (6-digit str), ano, populacao
    """
    all_dfs = []

    for year in years:
        logger.info(f"IBGE: buscando população {year}...")
        df = None

        # Try table 6579 first (2001-2021)
        if year <= 2021:
            df = _fetch_sidra_table(6579, "9324", year)

        # Then try table 9514 (2022 Census)
        if df is None and year == 2022:
            df = _fetch_sidra_census_2022()

        # Fallback: use the closest available year
        if df is None:
            closest = min([2021, 2022], key=lambda y: abs(y - year))
            logger.warning(f"  Sem dados para {year}, usando {closest} como proxy")
            if closest <= 2021:
                df = _fetch_sidra_table(6579, "9324", closest)
            else:
                df = _fetch_sidra_census_2022()

            if df is not None:
                df["ano"] = year  # Override year

        if df is not None and not df.empty:
            all_dfs.append(df)
            logger.info(f"  ✓ {len(df)} municípios")

    if not all_dfs:
        logger.warning("IBGE: nenhum dado de população obtido. Usando fallback.")
        return _fallback_population(years)

    return pd.concat(all_dfs, ignore_index=True)


def _fetch_sidra_table(table: int, variable: str, year: int) -> Optional[pd.DataFrame]:
    """
    Fetch from IBGE SIDRA API — generic table.

    Uses default format (with codes) to get D1C (municipality code).
    """
    url = (
        f"https://apisidra.ibge.gov.br/values"
        f"/t/{table}"
        f"/n6/all"
        f"/v/{variable}"
        f"/p/{year}"
    )

    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        if not data or len(data) <= 1:
            return None

        # First row is header, skip it
        rows = data[1:]
        records = []

        for row in rows:
            try:
                codmun = str(row.get("D1C", ""))[:6]
                pop_str = row.get("V", "0")
                pop = int(float(pop_str)) if pop_str and pop_str not in ("-", "...", "X") else 0

                if len(codmun) == 6 and pop > 0:
                    records.append({
                        "codmun": codmun,
                        "ano": year,
                        "populacao": pop,
                    })
            except (ValueError, TypeError):
                continue

        return pd.DataFrame(records) if records else None

    except requests.RequestException as e:
        logger.error(f"  SIDRA table {table} error: {e}")
        return None


def _fetch_sidra_census_2022() -> Optional[pd.DataFrame]:
    """
    Fetch 2022 Census data from SIDRA table 9514.

    Table 9514 has multiple variables (absolute + percentage).
    We filter for variable 93 (População residente) with all demographic breakdowns = Total.
    """
    # Variable 93 = População residente (absoluto), with demographic filters = Total
    url = (
        "https://apisidra.ibge.gov.br/values"
        "/t/9514"
        "/n6/all"
        "/v/93"
        "/p/2022"
        "/c2/6794"    # Sexo = Total
        "/c287/100362" # Idade = Total
        "/c286/113635" # Cor/Raça = Total
    )

    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        if not data or len(data) <= 1:
            # Fallback: try simpler query
            url_simple = (
                "https://apisidra.ibge.gov.br/values"
                "/t/9514/n6/all/v/93/p/2022"
            )
            resp = requests.get(url_simple, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            if not data or len(data) <= 1:
                return None

        rows = data[1:]
        records = []

        for row in rows:
            try:
                codmun = str(row.get("D1C", ""))[:6]
                pop_str = row.get("V", "0")
                pop = int(float(pop_str)) if pop_str and pop_str not in ("-", "...", "X") else 0

                if len(codmun) == 6 and pop > 0:
                    records.append({
                        "codmun": codmun,
                        "ano": 2022,
                        "populacao": pop,
                    })
            except (ValueError, TypeError):
                continue

        # Deduplicate (table 9514 may have multiple rows per municipality)
        if records:
            df = pd.DataFrame(records)
            df = df.drop_duplicates(subset=["codmun"], keep="first")
            return df

        return None

    except requests.RequestException as e:
        logger.error(f"  SIDRA Census 2022 error: {e}")
        return None


def _fallback_population(years: list[int]) -> pd.DataFrame:
    """
    Fallback: fetch municipality list from IBGE localidades and use
    IBGE estimated population from the API's population field if available.
    """
    try:
        resp = requests.get(LOCALIDADES_URL, timeout=30)
        resp.raise_for_status()
        municipios = resp.json()

        records = []
        for m in municipios:
            codmun = str(m["id"])[:6]
            for year in years:
                records.append({
                    "codmun": codmun,
                    "ano": year,
                    "populacao": None,
                })

        df = pd.DataFrame(records)
        logger.warning(f"  Fallback: {len(municipios)} municípios sem população real")
        return df

    except Exception as e:
        logger.error(f"  Fallback também falhou: {e}")
        return pd.DataFrame()


def collect_municipality_metadata() -> pd.DataFrame:
    """
    Fetch municipality metadata from IBGE localidades API.

    Returns DataFrame with columns:
        codmun, nome, uf, regiao
    """
    logger.info("IBGE: buscando metadados de municípios...")

    try:
        resp = requests.get(LOCALIDADES_URL, timeout=30)
        resp.raise_for_status()
        municipios = resp.json()

        from config import UF_CODES, UF_REGION
        code_to_uf = {v: k for k, v in UF_CODES.items()}

        records = []
        for m in municipios:
            codmun = str(m["id"])[:6]

            # Parse UF from nested structure
            uf_sigla = None
            try:
                uf_sigla = m["microrregiao"]["mesorregiao"]["UF"]["sigla"]
            except (KeyError, TypeError):
                uf_ibge_code = int(codmun[:2])
                uf_sigla = code_to_uf.get(uf_ibge_code, "??")

            regiao = UF_REGION.get(uf_sigla, "Desconhecida")

            records.append({
                "codmun": codmun,
                "nome": m["nome"],
                "uf": uf_sigla,
                "regiao": regiao,
            })

        df = pd.DataFrame(records)
        logger.info(f"  ✓ {len(df)} municípios")
        return df

    except Exception as e:
        logger.error(f"  Erro: {e}")
        return pd.DataFrame()
