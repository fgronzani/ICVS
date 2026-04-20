#!/usr/bin/env python3
"""
Download and simplify Brazilian municipality geometries from IBGE API.
Produces a TopoJSON file for the frontend choropleth map.

Usage:
    pip install -r tools/requirements.txt
    python tools/download_geo.py

Output:
    docs/data/municipios_br.topojson  (~3-8 MB)
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from tqdm import tqdm

# IBGE state numeric codes
UF_CODES = {
    "AC": 12, "AL": 27, "AM": 13, "AP": 16, "BA": 29, "CE": 23,
    "DF": 53, "ES": 32, "GO": 52, "MA": 21, "MG": 31, "MS": 50,
    "MT": 51, "PA": 15, "PB": 25, "PE": 26, "PI": 22, "PR": 41,
    "RJ": 33, "RN": 24, "RO": 11, "RR": 14, "RS": 43, "SC": 42,
    "SE": 28, "SP": 35, "TO": 17,
}

IBGE_MALHAS_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf_code}"
    "?resolucao=5&formato=application/vnd.geo+json&intrarregiao=municipio"
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "geo"


def download_state_geojson(uf: str, uf_code: int, max_retries: int = 3) -> dict | None:
    """Download GeoJSON for a single state's municipalities."""
    url = IBGE_MALHAS_URL.format(uf_code=uf_code)

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data
        except (requests.RequestException, json.JSONDecodeError) as e:
            wait = 2 ** attempt
            print(f"  ⚠ {uf}: tentativa {attempt + 1} falhou ({e}). Aguardando {wait}s...")
            time.sleep(wait)

    print(f"  ✗ {uf}: falhou após {max_retries} tentativas")
    return None


def reduce_precision(coords, precision: int = 5):
    """Recursively reduce coordinate precision to save space."""
    if isinstance(coords, list):
        if len(coords) > 0 and isinstance(coords[0], (int, float)):
            return [round(c, precision) for c in coords]
        return [reduce_precision(c, precision) for c in coords]
    return coords


def merge_geojsons(geojsons: list[dict]) -> dict:
    """Merge multiple GeoJSON FeatureCollections into one."""
    all_features = []
    for gj in geojsons:
        if gj and "features" in gj:
            for feature in gj["features"]:
                # Reduce coordinate precision
                if "geometry" in feature and feature["geometry"]:
                    feature["geometry"]["coordinates"] = reduce_precision(
                        feature["geometry"]["coordinates"], 4
                    )
                all_features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": all_features,
    }


def convert_to_topojson(geojson: dict) -> dict:
    """Convert GeoJSON to TopoJSON using the topojson library."""
    try:
        import topojson as tp

        topology = tp.Topology(
            geojson,
            toposimplify=0.001,   # Simplify geometries (higher = more simplification)
            topoquantize=1e4,     # Quantize coordinates (fewer decimal places)
            presimplify=False,
        )
        return json.loads(topology.to_json())
    except ImportError:
        print("⚠ Pacote 'topojson' não instalado. Salvando como GeoJSON.")
        return None
    except Exception as e:
        print(f"⚠ Erro na conversão TopoJSON: {e}")
        return None


def main():
    print("=" * 60)
    print("Download de geometrias municipais — IBGE API v3")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Check if raw files exist (resume support)
    cached_states = {}
    for uf, code in UF_CODES.items():
        cache_file = RAW_DIR / f"{uf}.geojson"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    cached_states[uf] = json.load(f)
                print(f"  ✓ {uf}: usando cache local")
            except json.JSONDecodeError:
                pass

    states_to_download = {
        uf: code for uf, code in UF_CODES.items()
        if uf not in cached_states
    }

    print(f"\n{len(cached_states)} estados em cache, {len(states_to_download)} para baixar\n")

    # Download remaining states with parallelism
    if states_to_download:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(download_state_geojson, uf, code): uf
                for uf, code in states_to_download.items()
            }

            pbar = tqdm(total=len(futures), desc="Baixando", unit="UF")
            for future in as_completed(futures):
                uf = futures[future]
                result = future.result()
                if result:
                    cached_states[uf] = result
                    # Save to cache
                    cache_file = RAW_DIR / f"{uf}.geojson"
                    with open(cache_file, "w") as f:
                        json.dump(result, f)
                pbar.update(1)
            pbar.close()

    print(f"\n✓ {len(cached_states)}/27 estados carregados")

    # Merge all into one GeoJSON
    print("\nMergeando geometrias...")
    merged = merge_geojsons(list(cached_states.values()))
    n_features = len(merged["features"])
    print(f"  Total de feições: {n_features}")

    # Save merged GeoJSON (for reference)
    geojson_path = OUTPUT_DIR / "municipios_br.geojson"
    with open(geojson_path, "w") as f:
        json.dump(merged, f)
    geojson_size = geojson_path.stat().st_size / (1024 * 1024)
    print(f"  GeoJSON salvo: {geojson_path} ({geojson_size:.1f} MB)")

    # Convert to TopoJSON
    print("\nConvertendo para TopoJSON...")
    topojson_data = convert_to_topojson(merged)

    if topojson_data:
        topojson_path = OUTPUT_DIR / "municipios_br.topojson"
        with open(topojson_path, "w") as f:
            json.dump(topojson_data, f)
        topo_size = topojson_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ TopoJSON salvo: {topojson_path} ({topo_size:.1f} MB)")
        print(f"  Redução: {((1 - topo_size / geojson_size) * 100):.0f}%")

        # Remove raw GeoJSON if TopoJSON was successful
        geojson_path.unlink()
        print(f"  GeoJSON removido (usando TopoJSON)")
    else:
        # Rename GeoJSON to topojson path for frontend compatibility
        # Frontend will detect it's not TopJSON and handle accordingly
        print("  ⚠ Usando GeoJSON como fallback (instale 'topojson' para otimizar)")

    print(f"\n{'=' * 60}")
    print(f"✓ Concluído! {n_features} municípios processados.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
