#!/usr/bin/env python3
"""
Generate realistic synthetic ICVS data for all Brazilian municipalities.
Used for frontend development without waiting for real DATASUS pipeline.

Usage:
    python tools/generate_synthetic.py

Output:
    docs/data/icvs_latest.json
    docs/data/icvs_series.json
    docs/data/municipios/{code}.json  (one per municipality)
"""
import json
import math
import random
import sys
import time
from pathlib import Path

import requests

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"
MUN_DIR = OUTPUT_DIR / "municipios"

# Regional vulnerability baselines (higher = more vulnerable)
REGION_BASELINES = {
    "Norte": {"mean": 62, "std": 14},
    "Nordeste": {"mean": 58, "std": 16},
    "Centro-Oeste": {"mean": 42, "std": 12},
    "Sudeste": {"mean": 35, "std": 15},
    "Sul": {"mean": 30, "std": 13},
}

UF_REGION = {
    "AC": "Norte", "AL": "Nordeste", "AM": "Norte", "AP": "Norte",
    "BA": "Nordeste", "CE": "Nordeste", "DF": "Centro-Oeste",
    "ES": "Sudeste", "GO": "Centro-Oeste", "MA": "Nordeste",
    "MG": "Sudeste", "MS": "Centro-Oeste", "MT": "Centro-Oeste",
    "PA": "Norte", "PB": "Nordeste", "PE": "Nordeste", "PI": "Nordeste",
    "PR": "Sul", "RJ": "Sudeste", "RN": "Nordeste", "RO": "Norte",
    "RR": "Norte", "RS": "Sul", "SC": "Sul", "SE": "Nordeste",
    "SP": "Sudeste", "TO": "Norte",
}

# Approximate state centroids for lat/lon when no geometry is available
STATE_CENTROIDS = {
    "AC": (-9.97, -67.81), "AL": (-9.57, -36.78), "AM": (-3.47, -65.10),
    "AP": (1.41, -51.77), "BA": (-12.97, -41.68), "CE": (-5.50, -39.32),
    "DF": (-15.83, -47.86), "ES": (-19.19, -40.34), "GO": (-15.83, -49.84),
    "MA": (-5.42, -45.44), "MG": (-18.51, -44.55), "MS": (-20.77, -54.79),
    "MT": (-12.64, -55.42), "PA": (-3.79, -52.48), "PB": (-7.28, -36.72),
    "PE": (-8.28, -37.86), "PI": (-7.72, -42.73), "PR": (-24.89, -51.55),
    "RJ": (-22.25, -42.66), "RN": (-5.81, -36.59), "RO": (-10.83, -63.34),
    "RR": (1.99, -61.33), "RS": (-29.75, -53.25), "SC": (-27.24, -50.22),
    "SE": (-10.57, -37.38), "SP": (-22.19, -48.79), "TO": (-10.18, -48.33),
}

INDICATOR_DEFS = [
    "tmi", "rmm", "apvp_taxa", "mort_prematura_dcnt", "proporcao_obitos_evitaveis",
    "cobertura_esf_inv", "cobertura_acs_inv", "leitos_sus_inv", "medicos_inv",
    "distancia_hospital", "taxa_icsap", "taxa_cesareas_sus", "prenatal_inadequado",
    "internacao_dm", "obitos_sem_assistencia",
]

YEARS = list(range(2014, 2024))  # 10-year series


def fetch_municipality_list() -> list[dict]:
    """Fetch all municipalities from IBGE localidades API."""
    url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    print("📡 Baixando lista de municípios do IBGE...")

    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            print(f"  ✓ {len(data)} municípios obtidos")
            return data
        except Exception as e:
            print(f"  ⚠ Tentativa {attempt + 1} falhou: {e}")
            time.sleep(2 ** attempt)

    print("  ✗ Falha ao obter lista de municípios. Usando lista mínima de fallback.")
    return []


def parse_municipalities(ibge_data: list[dict]) -> list[dict]:
    """Parse IBGE API response into our municipality format."""
    result = []
    for m in ibge_data:
        code = str(m["id"])

        # Extract UF from nested structure (handle multiple API formats)
        uf_sigla = None
        try:
            uf_sigla = m["microrregiao"]["mesorregiao"]["UF"]["sigla"]
        except (KeyError, TypeError):
            pass

        if not uf_sigla:
            try:
                uf_sigla = m["municipio"]["microrregiao"]["mesorregiao"]["UF"]["sigla"]
            except (KeyError, TypeError):
                pass

        if not uf_sigla:
            # Derive UF from code (first 2 digits = UF IBGE code)
            uf_ibge_code = int(code[:2])
            code_to_uf = {v: k for k, v in {
                "AC": 12, "AL": 27, "AM": 13, "AP": 16, "BA": 29, "CE": 23,
                "DF": 53, "ES": 32, "GO": 52, "MA": 21, "MG": 31, "MS": 50,
                "MT": 51, "PA": 15, "PB": 25, "PE": 26, "PI": 22, "PR": 41,
                "RJ": 33, "RN": 24, "RO": 11, "RR": 14, "RS": 43, "SC": 42,
                "SE": 28, "SP": 35, "TO": 17,
            }.items()}
            uf_sigla = code_to_uf.get(uf_ibge_code, "SP")

        regiao = UF_REGION.get(uf_sigla, "Desconhecida")

        # Approximate lat/lon with jitter from state centroid
        base_lat, base_lon = STATE_CENTROIDS.get(uf_sigla, (-15.0, -47.0))
        lat = base_lat + random.gauss(0, 1.5)
        lon = base_lon + random.gauss(0, 1.8)

        # Synthetic population (log-normal distribution)
        pop = int(random.lognormvariate(math.log(15000), 1.2))
        pop = max(800, min(pop, 12_500_000))

        result.append({
            "codmunicipio": code,
            "nome": m["nome"],
            "uf": uf_sigla,
            "regiao": regiao,
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "populacao": pop,
        })

    return result


def generate_icvs_for_municipality(mun: dict, year: int) -> dict:
    """Generate synthetic ICVS values for one municipality in one year."""
    regiao = mun["regiao"]
    baseline = REGION_BASELINES.get(regiao, {"mean": 50, "std": 15})

    # Base vulnerability with regional pattern
    base_vuln = random.gauss(baseline["mean"], baseline["std"])

    # Small municipalities have higher variance
    pop = mun["populacao"]
    if pop < 5000:
        base_vuln += random.gauss(5, 8)
    elif pop < 20000:
        base_vuln += random.gauss(2, 5)
    elif pop > 500000:
        base_vuln += random.gauss(-8, 6)  # Capitals tend to have better access

    # Sub-indices with correlated noise
    sub_desfechos = base_vuln + random.gauss(0, 10)
    sub_acesso = base_vuln + random.gauss(0, 12)
    sub_qualidade = base_vuln + random.gauss(0, 8)

    # Temporal trend: slight improvement over years
    year_effect = (2023 - year) * 0.5
    sub_desfechos += year_effect
    sub_acesso += year_effect * 0.3
    sub_qualidade += year_effect * 0.7

    # Clamp to [0, 100]
    sub_desfechos = max(0, min(100, sub_desfechos))
    sub_acesso = max(0, min(100, sub_acesso))
    sub_qualidade = max(0, min(100, sub_qualidade))

    # ICVS = weighted combination
    icvs = sub_desfechos * 0.40 + sub_acesso * 0.35 + sub_qualidade * 0.25
    icvs = max(0, min(100, icvs))

    return {
        "icvs": round(icvs, 2),
        "sub_desfechos": round(sub_desfechos, 2),
        "sub_acesso": round(sub_acesso, 2),
        "sub_qualidade": round(sub_qualidade, 2),
    }


def assign_quintiles(municipios: dict) -> None:
    """Assign quintile labels (1-5) based on ICVS ranking."""
    sorted_codes = sorted(
        municipios.keys(),
        key=lambda c: municipios[c].get("icvs", 0)
    )
    n = len(sorted_codes)
    for i, code in enumerate(sorted_codes):
        quintil = min(5, int(i / n * 5) + 1)
        municipios[code]["icvs_quintil"] = quintil


def assign_clusters(municipios: dict, n_clusters: int = 6) -> None:
    """Assign synthetic cluster labels based on population and region."""
    for code, m in municipios.items():
        pop = m.get("populacao", 10000)
        regiao = m.get("regiao", "Sudeste")

        if pop > 500000:
            cluster = 0  # Metrópoles
        elif pop > 100000:
            cluster = 1  # Municípios médios
        elif regiao in ("Norte", "Nordeste") and pop < 20000:
            cluster = 3  # Pequenos vulneráveis N/NE
        elif regiao in ("Sul", "Sudeste") and pop < 20000:
            cluster = 2  # Pequenos rurais S/SE
        elif pop < 50000:
            cluster = 4  # Transição
        else:
            cluster = 5  # Periurbanos

        m["cluster"] = cluster


def generate_indicators_for_municipality(mun: dict, icvs_data: dict, year: int) -> list[dict]:
    """Generate synthetic indicator values for one municipality-year."""
    indicators = []
    vuln = icvs_data["icvs"] / 100  # Normalized 0-1

    for ind_name in INDICATOR_DEFS:
        # Base value correlated with vulnerability
        base = vuln * random.gauss(0.7, 0.15) + random.gauss(0.15, 0.1)
        valor = max(0, min(1, base))

        # Smoothed value close to raw
        suavizado = valor + random.gauss(0, 0.02)
        suavizado = max(0, min(1, suavizado))

        indicators.append({
            "ano": year,
            "indicador": ind_name,
            "valor": round(valor, 4),
            "valor_suavizado": round(suavizado, 4),
        })

    return indicators


def main():
    random.seed(42)  # Reproducible results

    print("=" * 60)
    print("Gerador de dados sintéticos — ICVS")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MUN_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Get municipality list from IBGE
    ibge_data = fetch_municipality_list()
    if not ibge_data:
        print("✗ Sem dados de municípios. Abortando.")
        sys.exit(1)

    municipios_list = parse_municipalities(ibge_data)
    print(f"\n✓ {len(municipios_list)} municípios processados\n")

    # Step 2: Generate ICVS data for the latest year
    print("🧮 Gerando dados ICVS para o ano mais recente (2023)...")
    latest_municipios = {}
    for mun in municipios_list:
        code = mun["codmunicipio"]
        icvs_data = generate_icvs_for_municipality(mun, 2023)
        latest_municipios[code] = {**mun, **icvs_data}

    # Assign quintiles and clusters
    assign_quintiles(latest_municipios)
    assign_clusters(latest_municipios)

    # Step 3: Write icvs_latest.json
    latest_output = {
        "ano": 2023,
        "anos_disponiveis": YEARS,
        "municipios": latest_municipios,
    }

    with open(OUTPUT_DIR / "icvs_latest.json", "w", encoding="utf-8") as f:
        json.dump(latest_output, f, ensure_ascii=False)
    print(f"  ✓ icvs_latest.json ({len(latest_municipios)} municípios)")

    # Step 4: Generate per-municipality detailed JSONs
    print(f"\n📊 Gerando dados detalhados por município ({len(municipios_list)} arquivos)...")
    count = 0
    for mun in municipios_list:
        code = mun["codmunicipio"]
        info = latest_municipios[code]

        # Historical series
        historico = []
        for year in YEARS:
            year_data = generate_icvs_for_municipality(mun, year)
            # Assign approximate quintile based on value
            q = min(5, int(year_data["icvs"] / 20) + 1)
            historico.append({
                "ano": year,
                "icvs": year_data["icvs"],
                "icvs_quintil": q,
                "sub_desfechos": year_data["sub_desfechos"],
                "sub_acesso": year_data["sub_acesso"],
                "sub_qualidade": year_data["sub_qualidade"],
            })

        # Indicators for latest year
        icvs_data = generate_icvs_for_municipality(mun, 2023)
        indicadores = generate_indicators_for_municipality(mun, icvs_data, 2023)

        mun_output = {
            "info": info,
            "icvs_historico": historico,
            "indicadores": indicadores,
        }

        with open(MUN_DIR / f"{code}.json", "w", encoding="utf-8") as f:
            json.dump(mun_output, f, ensure_ascii=False)

        count += 1
        if count % 500 == 0:
            print(f"  ... {count}/{len(municipios_list)}")

    print(f"  ✓ {count} arquivos individuais gerados")

    # Step 5: Generate icvs_series.json (aggregated by UF and region)
    print("\n📈 Gerando série histórica agregada...")
    series = {"por_uf": {}, "por_regiao": {}, "nacional": []}

    for year in YEARS:
        year_vals = []
        uf_vals = {}
        region_vals = {}

        for mun in municipios_list:
            icvs_data = generate_icvs_for_municipality(mun, year)
            val = icvs_data["icvs"]
            year_vals.append(val)

            uf = mun["uf"]
            uf_vals.setdefault(uf, []).append(val)

            regiao = mun["regiao"]
            region_vals.setdefault(regiao, []).append(val)

        series["nacional"].append({
            "ano": year,
            "icvs_medio": round(sum(year_vals) / len(year_vals), 2),
            "n_municipios": len(year_vals),
        })

        for uf, vals in uf_vals.items():
            series["por_uf"].setdefault(uf, []).append({
                "ano": year,
                "icvs_medio": round(sum(vals) / len(vals), 2),
                "n_municipios": len(vals),
            })

        for reg, vals in region_vals.items():
            series["por_regiao"].setdefault(reg, []).append({
                "ano": year,
                "icvs_medio": round(sum(vals) / len(vals), 2),
                "n_municipios": len(vals),
            })

    with open(OUTPUT_DIR / "icvs_series.json", "w", encoding="utf-8") as f:
        json.dump(series, f, ensure_ascii=False)
    print("  ✓ icvs_series.json")

    # Summary
    total_size = sum(
        f.stat().st_size for f in OUTPUT_DIR.rglob("*.json")
    ) / (1024 * 1024)

    print(f"\n{'=' * 60}")
    print(f"✓ Geração concluída!")
    print(f"  Municípios: {len(municipios_list)}")
    print(f"  Anos: {YEARS[0]}–{YEARS[-1]}")
    print(f"  Indicadores: {len(INDICATOR_DEFS)}")
    print(f"  Tamanho total: {total_size:.1f} MB")
    print(f"  Diretório: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
