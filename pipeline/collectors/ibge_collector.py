"""
IBGE Population Data Collector

Fetches population estimates from IBGE SIDRA API (Table 6579).
Also provides municipality metadata (name, region, etc.).
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# IBGE SIDRA API — Tabela 6579: Estimativas de população
# https://sidra.ibge.gov.br/tabela/6579
SIDRA_POP_TABLE = 6579

# Fallback: IBGE localidades API for municipality metadata
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
        try:
            df = _fetch_sidra_population(year)
            if df is not None and not df.empty:
                all_dfs.append(df)
                logger.info(f"  ✓ {len(df)} municípios")
        except Exception as e:
            logger.error(f"  Erro ao buscar população {year}: {e}")

    if not all_dfs:
        logger.warning("IBGE: nenhum dado de população obtido. Usando fallback.")
        return _fallback_population(years)

    return pd.concat(all_dfs, ignore_index=True)


def _fetch_sidra_population(year: int) -> Optional[pd.DataFrame]:
    """
    Fetch from IBGE SIDRA API — Table 6579 (population estimates).

    API format:
    /t/6579/n6/all/v/all/p/{year}/f/n
    """
    url = (
        f"https://apisidra.ibge.gov.br/values"
        f"/t/{SIDRA_POP_TABLE}"
        f"/n6/all"     # All municipalities (nível 6 = município)
        f"/v/9324"     # Variable: population
        f"/p/{year}"   # Period
        f"/f/n"        # Without header
    )

    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        if not data or len(data) <= 1:
            logger.warning(f"  SIDRA: sem dados para {year}")
            return None

        # First row is header, skip it
        rows = data[1:]  # Skip header row

        records = []
        for row in rows:
            try:
                codmun = str(row.get("D1C", row.get("Município (Código)", "")))[:6]
                pop_str = row.get("V", row.get("Valor", "0"))
                pop = int(pop_str) if pop_str and pop_str != "-" else 0

                if codmun and len(codmun) >= 6 and pop > 0:
                    records.append({
                        "codmun": codmun,
                        "ano": year,
                        "populacao": pop,
                    })
            except (ValueError, TypeError):
                continue

        return pd.DataFrame(records)

    except requests.RequestException as e:
        logger.error(f"  SIDRA API error: {e}")
        return None


def _fallback_population(years: list[int]) -> pd.DataFrame:
    """
    Simple fallback: fetch municipality list from IBGE and assign
    estimated populations from a simpler API.
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
                    "populacao": None,  # Will need to be filled
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

        records = []
        for m in municipios:
            codmun = str(m["id"])[:6]

            # Parse UF from nested structure
            uf_sigla = None
            try:
                uf_sigla = m["microrregiao"]["mesorregiao"]["UF"]["sigla"]
            except (KeyError, TypeError):
                # Derive from code
                from config import UF_CODES
                uf_ibge_code = int(codmun[:2])
                code_to_uf = {v: k for k, v in UF_CODES.items()}
                uf_sigla = code_to_uf.get(uf_ibge_code, "??")

            from config import UF_REGION
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
