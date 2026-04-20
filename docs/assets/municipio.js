/* =================================================================
   Municipality Detail Page Logic
   Loads per-municipality JSON and renders all detail panels
   ================================================================= */

const QUINTIL_COLORS = ['#22c55e', '#86efac', '#fbbf24', '#f97316', '#ef4444'];
const QUINTIL_LABELS = ['Muito Baixa', 'Baixa', 'Moderada', 'Alta', 'Muito Alta'];

const INDICATOR_NAMES = {
  tmi: 'Taxa de Mortalidade Infantil',
  rmm: 'Razão de Mortalidade Materna',
  apvp_taxa: 'Anos Pot. de Vida Perdidos (por 1.000)',
  mort_prematura_dcnt: 'Mortalidade Prematura DCNT',
  proporcao_obitos_evitaveis: 'Prop. Óbitos Evitáveis',
  cobertura_esf_inv: 'Déficit Cobertura ESF',
  cobertura_acs_inv: 'Déficit Cobertura ACS',
  leitos_sus_inv: 'Déficit Leitos SUS',
  medicos_inv: 'Déficit Médicos',
  distancia_hospital: 'Distância ao Hospital (km)',
  taxa_icsap: 'Internações Sensíveis APS',
  taxa_cesareas_sus: 'Taxa Cesáreas SUS',
  prenatal_inadequado: 'Pré-natal Inadequado',
  internacao_dm: 'Internações por Diabetes',
  obitos_sem_assistencia: 'Óbitos sem Assistência',
};

let latestData = null; // icvs_latest.json cache for similar municipalities

async function init() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('cod');

  if (!code) {
    showError('Código do município não informado na URL.');
    return;
  }

  try {
    // Load municipality data and latest data in parallel
    const [munRes, latestRes] = await Promise.all([
      fetch(`data/municipios/${code}.json`),
      fetch('data/icvs_latest.json'),
    ]);

    if (!munRes.ok) throw new Error(`Dados não encontrados para o município ${code}`);
    if (!latestRes.ok) throw new Error('Falha ao carregar dados nacionais');

    const munData = await munRes.json();
    latestData = await latestRes.json();

    renderPage(munData, code);

    // Hide loading
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

  // Update page title
  document.title = `${info.nome} — Atlas de Vulnerabilidade em Saúde`;

  // Header
  document.getElementById('mun-name').textContent = info.nome;
  document.getElementById('mun-uf').textContent = `📍 ${info.uf}`;
  document.getElementById('mun-regiao').textContent = `🌍 ${info.regiao}`;
  document.getElementById('mun-pop').textContent =
    `👥 ${(info.populacao || 0).toLocaleString('pt-BR')} hab.`;
  document.getElementById('mun-cluster').textContent =
    info.cluster != null ? `🏷️ Cluster ${info.cluster}` : '';

  // ICVS Hero
  const score = info.icvs;
  const quintil = info.icvs_quintil;
  document.getElementById('icvs-score').textContent =
    score != null ? score.toFixed(1) : 'N/D';
  document.getElementById('icvs-score').style.color =
    quintil ? QUINTIL_COLORS[quintil - 1] : '#94a3b8';

  const qlabel = document.getElementById('quintil-label');
  qlabel.textContent = QUINTIL_LABELS[quintil - 1] || 'N/D';
  qlabel.style.background = quintil ? QUINTIL_COLORS[quintil - 1] + '22' : 'transparent';
  qlabel.style.color = quintil ? QUINTIL_COLORS[quintil - 1] : '#94a3b8';

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

  // Radar chart with national and cluster medians
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
      // For vulnerability, up is worse
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

  // Get the latest year indicators
  const latestYear = indicadores.length > 0
    ? Math.max(...indicadores.map(i => i.ano))
    : null;

  const latestIndicators = indicadores.filter(i => i.ano === latestYear);

  if (latestIndicators.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">Sem dados de indicadores</td></tr>';
    return;
  }

  // Calculate percentiles from national data
  const allMunicipios = Object.values(latestData.municipios);

  tbody.innerHTML = latestIndicators.map(ind => {
    const name = INDICATOR_NAMES[ind.indicador] || ind.indicador;
    const valor = ind.valor != null ? ind.valor.toFixed(2) : 'N/D';
    const suavizado = ind.valor_suavizado != null ? ind.valor_suavizado.toFixed(2) : '—';

    // Calculate percentile (approximate from national data, using normalized value)
    const percentile = ind.valor != null ? Math.round(ind.valor * 100) : null;
    const pctColor = percentile != null ? getPercentileColor(percentile) : '#666';

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

function getPercentileColor(p) {
  if (p <= 20) return '#22c55e';
  if (p <= 40) return '#86efac';
  if (p <= 60) return '#fbbf24';
  if (p <= 80) return '#f97316';
  return '#ef4444';
}

function renderSimilarMunicipalities(info, currentCode) {
  const grid = document.getElementById('similar-grid');

  // Find municipalities in the same cluster, sorted by closest ICVS
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
      <div class="sim-uf">${m.uf} — ${m.regiao}</div>
      <div class="sim-icvs" style="color:${QUINTIL_COLORS[(m.icvs_quintil || 1) - 1]}">
        ${m.icvs?.toFixed(1) ?? 'N/D'}
      </div>
    </div>
  `).join('');
}

document.addEventListener('DOMContentLoaded', init);
