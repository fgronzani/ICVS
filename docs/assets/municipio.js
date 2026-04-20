/* =================================================================
   Municipality Detail Page — Professional light theme
   ================================================================= */

const VULN_SCALE = ['#2a9d8f', '#8ab17d', '#e9c46a', '#e76f51', '#c1121f'];
const QUINTIL_LABELS = ['Muito Baixa', 'Baixa', 'Moderada', 'Alta', 'Muito Alta'];

const INDICATOR_NAMES = {
  tmi: 'Taxa de Mortalidade Infantil (‰)',
  rmm: 'Razão de Mortalidade Materna',
  apvp_taxa: 'Anos Pot. Vida Perdidos (por 1.000 hab)',
  mort_prematura_dcnt: 'Mortalidade Prematura DCNT (30–69a)',
  proporcao_obitos_evitaveis: 'Proporção de Óbitos Evitáveis',
  cobertura_esf_inv: 'Déficit Cobertura ESF',
  cobertura_acs_inv: 'Déficit Cobertura ACS',
  leitos_sus_inv: 'Leitos SUS por 1.000 hab',
  medicos_inv: 'Médicos por 1.000 hab',
  distancia_hospital: 'Distância ao Hospital (km)',
  taxa_icsap: 'Internações Sensíveis à APS (por 10.000)',
  taxa_cesareas_sus: 'Taxa de Cesáreas SUS',
  prenatal_inadequado: 'Pré-natal Inadequado',
  internacao_dm: 'Internações Diabetes (por 10.000)',
  obitos_sem_assistencia: 'Óbitos sem Assistência Médica',
};

const INDICATOR_SUBINDEX = {
  tmi: 'Desfechos', rmm: 'Desfechos', apvp_taxa: 'Desfechos',
  mort_prematura_dcnt: 'Desfechos', proporcao_obitos_evitaveis: 'Desfechos',
  cobertura_esf_inv: 'Acesso', cobertura_acs_inv: 'Acesso',
  leitos_sus_inv: 'Acesso', medicos_inv: 'Acesso', distancia_hospital: 'Acesso',
  taxa_icsap: 'Qualidade', taxa_cesareas_sus: 'Qualidade',
  prenatal_inadequado: 'Qualidade', internacao_dm: 'Qualidade',
  obitos_sem_assistencia: 'Qualidade',
};

let latestData = null;

async function init() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('cod');

  if (!code) {
    showError('Código do município não informado na URL.');
    return;
  }

  try {
    const [munRes, latestRes] = await Promise.all([
      fetch(`data/municipios/${code}.json`),
      fetch('data/icvs_latest.json'),
    ]);

    if (!munRes.ok) throw new Error(`Dados não encontrados para ${code}`);
    if (!latestRes.ok) throw new Error('Falha ao carregar dados nacionais');

    const munData = await munRes.json();
    latestData = await latestRes.json();

    renderPage(munData, code);

    const overlay = document.getElementById('loading');
    overlay.classList.add('hidden');
    setTimeout(() => overlay.remove(), 500);

  } catch (err) {
    showError(err.message);
  }
}

function showError(msg) {
  const overlay = document.getElementById('loading');
  overlay.querySelector('.loading-text').textContent = `Erro: ${msg}`;
  overlay.querySelector('.loading-spinner').style.display = 'none';
}

function renderPage(data, code) {
  const info = data.info;
  const historico = data.icvs_historico || [];
  const indicadores = data.indicadores || [];

  document.title = `${info.nome} — ICVS Atlas`;

  // Header
  document.getElementById('mun-name').textContent = info.nome;
  document.getElementById('mun-uf').textContent = info.uf;
  document.getElementById('mun-regiao').textContent = info.regiao;
  document.getElementById('mun-pop').textContent =
    `${(info.populacao || 0).toLocaleString('pt-BR')} habitantes`;
  document.getElementById('mun-cluster').textContent =
    info.cluster != null ? `Tipologia ${info.cluster + 1}` : '';

  // ICVS Score
  const score = info.icvs;
  const quintil = info.icvs_quintil;
  const scoreEl = document.getElementById('icvs-score');
  scoreEl.textContent = score != null ? score.toFixed(1) : 'N/D';
  scoreEl.style.color = quintil ? VULN_SCALE[quintil - 1] : '#868e96';

  const qlabel = document.getElementById('quintil-label');
  qlabel.textContent = QUINTIL_LABELS[quintil - 1] || 'N/D';
  qlabel.style.background = quintil ? VULN_SCALE[quintil - 1] + '18' : 'transparent';
  qlabel.style.color = quintil ? VULN_SCALE[quintil - 1] : '#868e96';

  // Metric cards
  renderMetricCard('card-icvs', 'trend-icvs', info.icvs, historico, 'icvs');
  renderMetricCard('card-desfechos', 'trend-desfechos', info.sub_desfechos, historico, 'sub_desfechos');
  renderMetricCard('card-acesso', 'trend-acesso', info.sub_acesso, historico, 'sub_acesso');
  renderMetricCard('card-qualidade', 'trend-qualidade', info.sub_qualidade, historico, 'sub_qualidade');

  // Charts
  if (historico.length > 0) {
    createEvolutionChart(
      document.getElementById('chart-evolution').getContext('2d'),
      historico
    );
  }

  const nationalMedian = computeMedian(Object.values(latestData.municipios));
  const clusterMunicipios = Object.values(latestData.municipios)
    .filter(m => m.cluster === info.cluster);
  const clusterMedian = computeMedian(clusterMunicipios);

  createRadarChart(
    document.getElementById('chart-radar').getContext('2d'),
    info,
    nationalMedian,
    clusterMedian
  );

  // Indicator table
  renderIndicatorTable(indicadores, info);

  // Similar municipalities
  renderSimilarMunicipalities(info, code);
}

function renderMetricCard(valueId, trendId, value, historico, key) {
  const el = document.getElementById(valueId);
  el.textContent = value != null ? value.toFixed(1) : 'N/D';

  if (historico.length >= 2) {
    const prev = historico[historico.length - 2][key];
    const curr = historico[historico.length - 1][key];
    if (prev != null && curr != null) {
      const diff = curr - prev;
      const trendEl = document.getElementById(trendId);
      const arrow = diff > 0 ? '↑' : diff < 0 ? '↓' : '→';
      const cls = diff > 0.5 ? 'up' : diff < -0.5 ? 'down' : 'neutral';
      trendEl.className = `metric-trend ${cls}`;
      trendEl.textContent = `${arrow} ${Math.abs(diff).toFixed(1)} vs ano anterior`;
    }
  }
}

function computeMedian(municipios) {
  const sorted = (key) => {
    const vals = municipios.map(m => m[key]).filter(v => v != null).sort((a, b) => a - b);
    if (vals.length === 0) return 50;
    const mid = Math.floor(vals.length / 2);
    return vals.length % 2 ? vals[mid] : (vals[mid - 1] + vals[mid]) / 2;
  };

  return {
    sub_desfechos: sorted('sub_desfechos'),
    sub_acesso: sorted('sub_acesso'),
    sub_qualidade: sorted('sub_qualidade'),
  };
}

function renderIndicatorTable(indicadores, info) {
  const tbody = document.getElementById('indicator-tbody');

  const latestYear = indicadores.length > 0
    ? Math.max(...indicadores.map(i => i.ano))
    : null;

  const latestIndicators = indicadores.filter(i => i.ano === latestYear);

  if (latestIndicators.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">Sem dados de indicadores disponíveis</td></tr>';
    return;
  }

  tbody.innerHTML = latestIndicators.map(ind => {
    const name = INDICATOR_NAMES[ind.indicador] || ind.indicador;
    const subindex = INDICATOR_SUBINDEX[ind.indicador] || '';
    const valor = ind.valor != null ? formatIndicatorValue(ind.indicador, ind.valor) : 'N/D';
    const suavizado = ind.valor_suavizado != null ? formatIndicatorValue(ind.indicador, ind.valor_suavizado) : '—';

    // Approximate percentile from value (0-1 range normalized → 0-100)
    const percentile = ind.valor != null ? Math.min(99, Math.max(1, Math.round(ind.valor * 100))) : null;
    const pctColor = percentile != null ? getPercentileColor(percentile) : '#dee2e6';

    return `
      <tr>
        <td class="indicator-name">${name}</td>
        <td>${valor}</td>
        <td>${suavizado}</td>
        <td>${percentile != null ? `P${percentile}` : '—'}</td>
        <td>
          <div class="percentile-bar">
            <div class="fill" style="width:${percentile || 0}%;background:${pctColor}"></div>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function formatIndicatorValue(indicator, value) {
  if (value === null || value === undefined) return 'N/D';
  // Proportions (0–1): show as percentage
  if (['proporcao_obitos_evitaveis', 'taxa_cesareas_sus', 'prenatal_inadequado', 'obitos_sem_assistencia'].includes(indicator)) {
    return (value * 100).toFixed(1) + '%';
  }
  return value.toFixed(2);
}

function getPercentileColor(p) {
  if (p <= 20) return '#2a9d8f';
  if (p <= 40) return '#8ab17d';
  if (p <= 60) return '#e9c46a';
  if (p <= 80) return '#e76f51';
  return '#c1121f';
}

function renderSimilarMunicipalities(info, currentCode) {
  const grid = document.getElementById('similar-grid');

  const similar = Object.entries(latestData.municipios)
    .filter(([code, m]) => code !== currentCode && m.cluster === info.cluster)
    .map(([code, m]) => ({
      code,
      ...m,
      distance: Math.abs(m.icvs - info.icvs),
    }))
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 6);

  if (similar.length === 0) {
    grid.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">Nenhum município similar encontrado.</p>';
    return;
  }

  grid.innerHTML = similar.map(m => `
    <div class="similar-card" onclick="window.location.href='municipio.html?cod=${m.code}'">
      <div class="sim-name">${m.nome}</div>
      <div class="sim-uf">${m.uf} — ${(m.populacao || 0).toLocaleString('pt-BR')} hab.</div>
      <div class="sim-icvs" style="color:${VULN_SCALE[(m.icvs_quintil || 1) - 1]}">
        ${m.icvs?.toFixed(1) ?? 'N/D'}
      </div>
    </div>
  `).join('');
}

document.addEventListener('DOMContentLoaded', init);
