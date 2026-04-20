"""
Atlas de Vulnerabilidade em Saúde — Configuração Centralizada
"""
from dataclasses import dataclass, field

# IDs das UFs brasileiras
ALL_UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
    "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
    "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]

# Mapeamento UF sigla → código IBGE (necessário para APIs)
UF_CODES = {
    "AC": 12, "AL": 27, "AM": 13, "AP": 16, "BA": 29, "CE": 23,
    "DF": 53, "ES": 32, "GO": 52, "MA": 21, "MG": 31, "MS": 50,
    "MT": 51, "PA": 15, "PB": 25, "PE": 26, "PI": 22, "PR": 41,
    "RJ": 33, "RN": 24, "RO": 11, "RR": 14, "RS": 43, "SC": 42,
    "SE": 28, "SP": 35, "TO": 17,
}

# Mapeamento UF sigla → Região
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

# ------------------------------------------------------------------
# Indicadores por sub-índice
# ------------------------------------------------------------------

DESFECHO_INDICATORS = [
    "tmi",                        # Taxa Mortalidade Infantil
    "rmm",                        # Razão Mortalidade Materna
    "apvp_taxa",                  # APVP / 1000 hab
    "mort_prematura_dcnt",        # Mortalidade prematura DCNT
    "proporcao_obitos_evitaveis", # Proporção de óbitos evitáveis
]

ACESSO_INDICATORS = [
    "cobertura_esf_inv",          # 1 - cobertura_esf (invertido: menor = pior)
    "cobertura_acs_inv",          # 1 - cobertura_acs (invertido)
    "leitos_sus_inv",             # 1 - leitos_sus_per_1000 normalizado (invertido)
    "medicos_inv",                # 1 - médicos per 1000 normalizado (invertido)
    "distancia_hospital",         # km ao hospital mais próximo
]

QUALIDADE_INDICATORS = [
    "taxa_icsap",                 # Internações evitáveis
    "taxa_cesareas_sus",          # Partos cesáreos SUS (acima de 50% = ruim)
    "prenatal_inadequado",        # 1 - proporção pré-natal >= 6 consultas
    "internacao_dm",              # Internações complicações DM
    "obitos_sem_assistencia",     # Óbitos sem assistência médica
]

ALL_INDICATORS = DESFECHO_INDICATORS + ACESSO_INDICATORS + QUALIDADE_INDICATORS

# Nomes legíveis para o frontend
INDICATOR_LABELS = {
    "tmi": "Taxa de Mortalidade Infantil",
    "rmm": "Razão de Mortalidade Materna",
    "apvp_taxa": "Anos Potenciais de Vida Perdidos",
    "mort_prematura_dcnt": "Mortalidade Prematura por DCNT",
    "proporcao_obitos_evitaveis": "Proporção de Óbitos Evitáveis",
    "cobertura_esf_inv": "Déficit de Cobertura ESF",
    "cobertura_acs_inv": "Déficit de Cobertura ACS",
    "leitos_sus_inv": "Déficit de Leitos SUS",
    "medicos_inv": "Déficit de Médicos",
    "distancia_hospital": "Distância ao Hospital",
    "taxa_icsap": "Internações por Causas Sensíveis à APS",
    "taxa_cesareas_sus": "Taxa de Cesáreas SUS",
    "prenatal_inadequado": "Pré-natal Inadequado",
    "internacao_dm": "Internações por Diabetes",
    "obitos_sem_assistencia": "Óbitos sem Assistência Médica",
}

# ------------------------------------------------------------------
# Pesos dos sub-índices (conceituais, não derivados de dado externo)
# ------------------------------------------------------------------

SUBINDEX_WEIGHTS = {
    "desfechos": 0.40,
    "acesso": 0.35,
    "qualidade": 0.25,
}

# ------------------------------------------------------------------
# Parâmetros de processamento
# ------------------------------------------------------------------

SMALL_POPULATION_THRESHOLD = 10_000  # Limiar para suavização bayesiana

APVP_MAX_AGE = 75  # Idade limite para cálculo do APVP

N_CLUSTERS_DEFAULT = 6  # Clusters para tipologia municipal

NORM_P_LOW = 5   # Percentil inferior para normalização
NORM_P_HIGH = 95  # Percentil superior para normalização

# ------------------------------------------------------------------
# Lista ICSAP — Portaria MS 221/2008 (CID-10, 3 caracteres)
# ------------------------------------------------------------------

ICSAP_CODES = [
    # Doenças preveníveis por imunização
    "A33", "A34", "A35", "A36", "A37", "A80", "B06", "B16", "B26",
    "B50", "B51", "B52", "B54",
    # Gastroenterites infecciosas
    "A00", "A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09",
    # Anemia por deficiência de ferro
    "D50",
    # Deficiências nutricionais
    "E40", "E41", "E42", "E43", "E44", "E45", "E46",
    # Pneumonias bacterianas
    "J13", "J14", "J15", "J18",
    # Asma
    "J45", "J46",
    # DPOC
    "J41", "J42", "J43", "J44",
    # Hipertensão
    "I10", "I11",
    # Angina
    "I20",
    # Insuficiência cardíaca
    "I50",
    # Diabetes mellitus
    "E10", "E11", "E12", "E13", "E14",
    # Epilepsia
    "G40", "G41",
    # Infecção do trato urinário
    "N10", "N11", "N12", "N13", "N30", "N34", "N39",
    # Úlcera gastrointestinal
    "K25", "K26", "K27", "K28",
    # Pré-natal e parto
    "O23",
    # Infecções de ouvido, nariz e garganta
    "H66", "J00", "J01", "J02", "J03", "J06", "J31",
    # Infecção da pele e subcutâneo
    "A46", "L01", "L02", "L03", "L04", "L08",
    # Doença inflamatória pélvica
    "N70", "N71", "N72", "N73", "N75", "N76",
]
