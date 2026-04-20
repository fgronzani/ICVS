# Atlas de Vulnerabilidade em Saúde dos Municípios Brasileiros

**ICVS — Índice Composto de Vulnerabilidade em Saúde**

Atlas interativo nacional que classifica os 5.570 municípios brasileiros por vulnerabilidade em saúde, usando exclusivamente bases públicas do DATASUS e IBGE.

## 🚀 Executando Localmente

### Pré-requisitos
- Python 3.9+
- Conexão à internet (para baixar dados do IBGE)

### Setup Rápido

```bash
# 1. Criar ambiente virtual e instalar dependências das ferramentas
python3 -m venv .venv
source .venv/bin/activate
pip install -r tools/requirements.txt

# 2. Baixar geometria dos municípios (IBGE API)
python tools/download_geo.py

# 3. Gerar dados sintéticos (para desenvolvimento)
python tools/generate_synthetic.py

# 4. Servir o site localmente
cd docs && python3 -m http.server 8080
# Abrir http://localhost:8080
```

### Pipeline de Dados Reais (futuro)

```bash
pip install -r pipeline/requirements.txt

# Executar pipeline completo (1 UF para teste)
python pipeline/main.py --ufs SC --year 2022

# Executar pipeline completo (todos os UFs)
python pipeline/main.py --year 2023 --output docs/data/
```

## 📊 Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Pipeline de dados | Python, PySUS, pandas, scikit-learn |
| Banco de dados | SQLite |
| Frontend | HTML, CSS, JavaScript (Vanilla) |
| Mapa interativo | Leaflet.js + TopoJSON |
| Gráficos | Chart.js |
| Hospedagem | Cloudflare Pages |
| CI/CD | GitHub Actions |

## 🗂️ Estrutura do Projeto

```
atlas-saude/
├── pipeline/                   # Python — coleta, processamento, índice
│   ├── collectors/             # Coletores DATASUS (SIM, SINASC, SIH, CNES)
│   ├── processors/             # Cálculo de taxas, suavização, ICSAP
│   ├── index/                  # PCA, ICVS, clustering
│   ├── validation/             # Validação externa e temporal
│   ├── exporters/              # SQLite e JSON
│   ├── config.py               # Configuração centralizada
│   └── main.py                 # Orquestrador
├── docs/                       # Site estático
│   ├── index.html              # Mapa principal
│   ├── municipio.html          # Drill-down por município
│   ├── metodologia.html        # Metodologia detalhada
│   ├── sobre.html              # Sobre o projeto
│   ├── assets/                 # CSS e JS
│   └── data/                   # Dados (JSON, TopoJSON)
├── tools/                      # Ferramentas de desenvolvimento
│   ├── download_geo.py         # Download de geometrias IBGE
│   └── generate_synthetic.py   # Gerador de dados sintéticos
└── .github/workflows/          # CI/CD
```

## 📈 Indicadores (15 total)

### Sub-índice A: Desfechos em Saúde (40%)
- Taxa de Mortalidade Infantil (TMI)
- Razão de Mortalidade Materna (RMM)
- Anos Potenciais de Vida Perdidos (APVP)
- Mortalidade Prematura por DCNT
- Proporção de Óbitos Evitáveis

### Sub-índice B: Acesso e Capacidade (35%)
- Cobertura ESF / ACS
- Leitos SUS por 1.000 hab
- Médicos por 1.000 hab
- Distância ao hospital mais próximo

### Sub-índice C: Qualidade da Atenção (25%)
- Taxa de ICSAP
- Taxa de Cesáreas SUS
- Pré-natal adequado (≥6 consultas)
- Internações por Diabetes
- Óbitos sem assistência médica

## 📝 Licença

Código: MIT License  
Dados: Seguem as políticas de dados abertos do DATASUS e IBGE.
