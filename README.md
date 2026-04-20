# ICVS — Índice Composto de Vulnerabilidade em Saúde

Atlas interativo que classifica 5.570 municípios brasileiros por vulnerabilidade em saúde, usando exclusivamente bases públicas do DATASUS e IBGE.

## 🗺️ Live Demo

Deploy via Cloudflare Pages (diretório `docs/`).

## Arquitetura

```
atlas-saude/
├── docs/                    # Site estático (Leaflet.js + Chart.js)
│   ├── index.html           # Mapa coroplético interativo
│   ├── municipio.html       # Drill-down por município
│   ├── metodologia.html     # Documentação metodológica
│   ├── sobre.html           # Sobre o projeto
│   ├── assets/              # CSS, JS
│   └── data/                # JSONs + TopoJSON
│
├── pipeline/                # Pipeline Python completo
│   ├── main.py              # Orquestrador
│   ├── config.py            # Configuração centralizada
│   ├── collectors/          # Coletores DATASUS + IBGE
│   │   ├── sim_collector.py     # SIM — Mortalidade
│   │   ├── sinasc_collector.py  # SINASC — Nascidos vivos
│   │   ├── sih_collector.py     # SIH — Internações
│   │   ├── cnes_collector.py    # CNES — Leitos e médicos
│   │   └── ibge_collector.py    # IBGE — População (SIDRA)
│   ├── processors/          # Processamento de indicadores
│   │   ├── rate_processor.py        # Cálculo de taxas
│   │   ├── bayesian_smoothing.py    # Suavização para municípios pequenos
│   │   └── normalizer.py           # Normalização P5/P95
│   ├── index/               # Cálculo do índice
│   │   └── icvs_calculator.py   # PCA + clustering + quintis
│   └── exporters/           # Exportação
│       └── json_exporter.py     # Geração de JSONs para frontend
│
├── tools/                   # Scripts auxiliares
│   ├── download_geo.py      # Download geometrias IBGE → TopoJSON
│   └── generate_synthetic.py # Gerador de dados sintéticos
│
└── .github/workflows/       # CI/CD
    ├── update_pipeline.yml  # Atualização mensal automática
    └── deploy.yml           # Deploy Cloudflare Pages
```

## Dados e Fontes

| Sistema | Fonte | Uso |
|---|---|---|
| **SIM** | DATASUS/PySUS | Mortalidade: TMI, RMM, APVP, DCNT, óbitos evitáveis |
| **SINASC** | DATASUS/PySUS | Nascidos vivos: pré-natal, cesáreas |
| **SIH** | DATASUS/PySUS | Internações: ICSAP (Portaria 221/2008), diabetes |
| **CNES** | DATASUS/PySUS | Infraestrutura: leitos SUS, médicos (CBO 225) |
| **IBGE** | SIDRA API | População estimada, metadados municipais |

## 15 Indicadores

### Desfechos em Saúde (peso 40%)
- Taxa de Mortalidade Infantil (TMI)
- Razão de Mortalidade Materna (RMM)
- Anos Potenciais de Vida Perdidos (APVP)
- Mortalidade prematura por DCNT (30-69 anos)
- Proporção de óbitos evitáveis

### Acesso e Capacidade (peso 35%)
- Déficit de Cobertura ESF
- Déficit de Cobertura ACS
- Déficit de Leitos SUS per capita
- Déficit de Médicos per capita
- Distância ao Hospital

### Qualidade da Atenção (peso 25%)
- Internações por Causas Sensíveis à APS (ICSAP)
- Taxa de Cesáreas SUS
- Pré-natal Inadequado
- Internações por Diabetes
- Óbitos sem Assistência Médica

## Metodologia

1. **Coleta**: PySUS para download automático dos microdados do DATASUS
2. **Taxas**: Cálculo de taxas per capita por município-ano
3. **Suavização**: Empirical Bayes (Gamma-Poisson) para municípios com <10k habitantes
4. **Normalização**: Min-max robusta com truncamento nos percentis P5/P95
5. **PCA**: Análise de Componentes Principais por sub-índice para pesos data-driven
6. **ICVS**: Média ponderada dos 3 sub-índices (40/35/25)
7. **Clustering**: K-Means com 6 tipologias municipais
8. **Classificação**: Quintis rank-based

## Instalação e Uso

### Pré-requisitos
- Python 3.9+
- pip

### Setup
```bash
# Clone
git clone https://github.com/fgronzani/ICVS.git
cd ICVS

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Dependências do pipeline
pip install -r pipeline/requirements.txt

# Dependências de ferramentas (TopoJSON, dados sintéticos)
pip install -r tools/requirements.txt
```

### Executar Pipeline
```bash
cd pipeline

# Teste rápido (1 UF, ~13s)
python main.py --ufs SC --year 2021

# Sul completo (~3 min)
python main.py --ufs SC PR RS --year 2021

# Brasil inteiro (~30 min)
python main.py --year 2021

# Múltiplos anos
python main.py --years 2018 2019 2020 2021

# Com saída personalizada
python main.py --ufs SC --year 2021 --output ../docs/data
```

### Visualizar Frontend
```bash
cd docs
python3 -m http.server 8080
# Abrir http://localhost:8080
```

### Gerar Dados Sintéticos (para desenvolvimento)
```bash
cd tools
python generate_synthetic.py
```

### Atualizar Geometrias
```bash
cd tools
python download_geo.py
```

## Resultados (Sul, 2021)

| Métrica | Valor |
|---|---|
| Municípios | 5.570 |
| PCA Desfechos (PC1) | 34.8% variância explicada |
| PCA Acesso (PC1) | 87.0% variância explicada |
| PCA Qualidade (PC1) | 43.3% variância explicada |
| ICVS médio nacional | 40.4 |
| Desvio padrão | 9.6 |
| Clusters | 6 tipologias |

## Stack

- **Pipeline**: Python, PySUS, pandas, scikit-learn, scipy
- **Frontend**: Leaflet.js (Canvas renderer), Chart.js, Vanilla JS
- **Geometria**: TopoJSON (5.3 MB, 90% redução)
- **CI/CD**: GitHub Actions + Cloudflare Pages
- **Design**: Dark theme, glassmorphism, Inter font, responsivo

## Licença

MIT
