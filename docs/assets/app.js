/* =================================================================
   Atlas de Vulnerabilidade em Saúde — Map Application
   Leaflet.js + TopoJSON + Canvas renderer for 5,570 municipalities
   ================================================================= */

// -- Color scale: continuous interpolation across 5 quintile anchors --
const QUINTIL_COLORS = ['#22c55e', '#86efac', '#fbbf24', '#f97316', '#ef4444'];
const QUINTIL_LABELS = ['Muito Baixa', 'Baixa', 'Moderada', 'Alta', 'Muito Alta'];
const INDICATOR_LABELS = {
  icvs: 'ICVS — Índice Composto',
  sub_desfechos: 'Sub-índice: Desfechos',
  sub_acesso: 'Sub-índice: Acesso',
  sub_qualidade: 'Sub-índice: Qualidade',
};

// -- Global state --
const state = {
  data: null,
  geoData: null,
  year: null,
  indicator: 'icvs',
  uf: '',
  map: null,
  geolayer: null,
  searchIndex: [],
};

// -- Initialization --
async function init() {
  try {
    // Initialize Leaflet with Canvas renderer for performance
    state.map = L.map('map', {
      center: [-14.5, -51.0],
      zoom: 4,
      minZoom: 3,
      maxZoom: 12,
      zoomControl: true,
      renderer: L.canvas({ padding: 0.5 }),
      preferCanvas: true,
    });

    // Dark tile layer
    L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
      {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OSM</a> © <a href="https://carto.com/">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 12,
      }
    ).addTo(state.map);

    // Load data in parallel
    const [icvsRes, geoRes] = await Promise.all([
      fetch('data/icvs_latest.json'),
      fetch('data/municipios_br.topojson'),
    ]);

    if (!icvsRes.ok) throw new Error(`Falha ao carregar dados ICVS: ${icvsRes.status}`);
    if (!geoRes.ok) throw new Error(`Falha ao carregar geometria: ${geoRes.status}`);

    state.data = await icvsRes.json();
    state.geoData = await geoRes.json();
    state.year = state.data.ano;

    // Build search index
    state.searchIndex = Object.entries(state.data.municipios).map(([code, m]) => ({
      code,
      name: m.nome,
      uf: m.uf,
      searchStr: `${m.nome} ${m.uf}`.toLowerCase(),
    }));

    populateControls();
    renderMap();
    setupEventListeners();

    // Hide loading overlay
    const overlay = document.getElementById('loading');
    overlay.classList.add('hidden');
    setTimeout(() => overlay.remove(), 500);

  } catch (err) {
    console.error('Erro ao inicializar:', err);
    const overlay = document.getElementById('loading');
    overlay.querySelector('.loading-text').textContent =
      `Erro: ${err.message}. Verifique se os dados estão em docs/data/`;
    overlay.querySelector('.loading-spinner').style.display = 'none';
  }
}

// -- Populate UI Controls --
function populateControls() {
  // Year
  const yearSelect = document.getElementById('year-select');
  yearSelect.innerHTML = `<option value="${state.year}">${state.year}</option>`;

  // If series data has multiple years, populate them
  if (state.data.anos_disponiveis) {
    yearSelect.innerHTML = '';
    state.data.anos_disponiveis.forEach(y => {
      const opt = document.createElement('option');
      opt.value = y;
      opt.textContent = y;
      if (y === state.year) opt.selected = true;
      yearSelect.appendChild(opt);
    });
  }

  // UF selector
  const ufs = [...new Set(Object.values(state.data.municipios).map(m => m.uf))].sort();
  const ufSelect = document.getElementById('uf-select');
  ufs.forEach(uf => {
    const opt = document.createElement('option');
    opt.value = uf;
    opt.textContent = uf;
    ufSelect.appendChild(opt);
  });
}

// -- Color interpolation --
function getColor(value) {
  if (value === null || value === undefined || isNaN(value)) return '#333333';

  // Clamp to 0-100
  const v = Math.max(0, Math.min(100, value));

  // Map value to gradient position across 5 colors
  const t = v / 100; // 0 to 1
  const idx = t * (QUINTIL_COLORS.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.min(lo + 1, QUINTIL_COLORS.length - 1);
  const f = idx - lo;

  return interpolateColor(QUINTIL_COLORS[lo], QUINTIL_COLORS[hi], f);
}

function interpolateColor(c1, c2, t) {
  const r1 = parseInt(c1.slice(1, 3), 16);
  const g1 = parseInt(c1.slice(3, 5), 16);
  const b1 = parseInt(c1.slice(5, 7), 16);
  const r2 = parseInt(c2.slice(1, 3), 16);
  const g2 = parseInt(c2.slice(3, 5), 16);
  const b2 = parseInt(c2.slice(5, 7), 16);

  const r = Math.round(r1 + (r2 - r1) * t);
  const g = Math.round(g1 + (g2 - g1) * t);
  const b = Math.round(b1 + (b2 - b1) * t);

  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

function getBadgeColor(quintil) {
  if (quintil >= 1 && quintil <= 5) return QUINTIL_COLORS[quintil - 1];
  return '#666666';
}

function quintilLabel(q) {
  return QUINTIL_LABELS[q - 1] ?? 'N/D';
}

// -- Render Map --
function renderMap() {
  if (state.geolayer) {
    state.map.removeLayer(state.geolayer);
  }

  // Determine the TopoJSON object key
  const objectKeys = Object.keys(state.geoData.objects);
  const objectKey = objectKeys[0]; // Use first object
  const geojson = topojson.feature(state.geoData, state.geoData.objects[objectKey]);

  state.geolayer = L.geoJSON(geojson, {
    style: feature => styleFeature(feature),
    onEachFeature: (feature, layer) => bindFeatureEvents(feature, layer),
  }).addTo(state.map);

  updateStatPanel();
  updateSummaryStats();
}

function styleFeature(feature) {
  const code = getFeatureCode(feature);
  const mun = state.data.municipios[code];
  const value = mun ? mun[state.indicator] : null;

  // Dim features outside selected UF
  if (state.uf && mun && mun.uf !== state.uf) {
    return {
      fillColor: '#1a1a2e',
      fillOpacity: 0.4,
      weight: 0.2,
      color: '#2a2a3e',
    };
  }

  return {
    fillColor: getColor(value),
    fillOpacity: 0.85,
    weight: 0.3,
    color: 'rgba(255,255,255,0.15)',
  };
}

function getFeatureCode(feature) {
  // Handle different property names from IBGE API
  const props = feature.properties;
  const rawCode = props.codarea || props.CD_MUN || props.cod || props.id || '';
  return String(rawCode);
}

function bindFeatureEvents(feature, layer) {
  const code = getFeatureCode(feature);
  const mun = state.data.municipios[code];

  layer.on({
    mouseover: e => showTooltip(e, mun, code),
    mousemove: e => moveTooltip(e),
    mouseout: () => hideTooltip(),
    click: () => {
      if (code) openMunicipality(code);
    },
  });
}

// -- Tooltip --
function showTooltip(e, mun, code) {
  if (!mun) return;

  const tooltip = document.getElementById('tooltip');
  tooltip.style.display = 'block';

  const indicator = state.indicator;
  const val = mun[indicator];
  const icvs = mun.icvs;

  tooltip.innerHTML = `
    <div class="tooltip-title">${mun.nome} — ${mun.uf}</div>
    <div class="tooltip-row">
      <span>ICVS</span>
      <span class="value" style="color:${getColor(icvs)}">${icvs?.toFixed(1) ?? 'N/D'}</span>
    </div>
    <div class="tooltip-row">
      <span>Vulnerabilidade</span>
      <span class="value">${quintilLabel(mun.icvs_quintil)}</span>
    </div>
    ${indicator !== 'icvs' ? `
    <div class="tooltip-row">
      <span>${INDICATOR_LABELS[indicator]}</span>
      <span class="value">${val?.toFixed(1) ?? 'N/D'}</span>
    </div>
    ` : ''}
    <div class="tooltip-row">
      <span>Cluster</span>
      <span class="value">${mun.cluster ?? 'N/D'}</span>
    </div>
  `;

  positionTooltip(e.originalEvent);
}

function moveTooltip(e) {
  positionTooltip(e.originalEvent);
}

function positionTooltip(evt) {
  const tooltip = document.getElementById('tooltip');
  const x = evt.clientX + 16;
  const y = evt.clientY - 10;

  // Keep tooltip within viewport
  const rect = tooltip.getBoundingClientRect();
  const maxX = window.innerWidth - rect.width - 20;
  const maxY = window.innerHeight - rect.height - 20;

  tooltip.style.left = Math.min(x, maxX) + 'px';
  tooltip.style.top = Math.min(y, maxY) + 'px';
}

function hideTooltip() {
  document.getElementById('tooltip').style.display = 'none';
}

// -- Navigation --
function openMunicipality(code) {
  window.location.href = `municipio.html?cod=${code}`;
}

// -- Stats Panel --
function updateStatPanel() {
  const entries = Object.entries(state.data.municipios)
    .filter(([, m]) => !state.uf || m.uf === state.uf)
    .filter(([, m]) => m[state.indicator] != null)
    .sort(([, a], [, b]) => b[state.indicator] - a[state.indicator])
    .slice(0, 10);

  const panel = document.getElementById('stats-panel');
  panel.innerHTML = `
    <div class="stats-title">Top 10 mais vulneráveis${state.uf ? ` — ${state.uf}` : ''}</div>
    ${entries.length === 0 ? '<p style="color: var(--text-muted); font-size: 12px;">Sem dados</p>' : ''}
    ${entries.map(([code, m], i) => `
      <div class="stat-row" onclick="openMunicipality('${code}')">
        <span class="rank">${i + 1}</span>
        <span class="mun-name">${m.nome}</span>
        <span class="mun-uf">${m.uf}</span>
        <span class="icvs-badge" style="background:${getBadgeColor(m.icvs_quintil)}">${m[state.indicator]?.toFixed(1)}</span>
      </div>
    `).join('')}
  `;
}

function updateSummaryStats() {
  const filtered = Object.values(state.data.municipios)
    .filter(m => !state.uf || m.uf === state.uf)
    .filter(m => m[state.indicator] != null);

  document.getElementById('stat-count').textContent =
    filtered.length.toLocaleString('pt-BR');

  if (filtered.length > 0) {
    const mean = filtered.reduce((s, m) => s + m[state.indicator], 0) / filtered.length;
    document.getElementById('stat-mean').textContent = mean.toFixed(1);
  } else {
    document.getElementById('stat-mean').textContent = '—';
  }
}

// -- Search --
let searchDebounce = null;

function handleSearch(query) {
  clearTimeout(searchDebounce);
  const container = document.getElementById('search-results');

  if (!query || query.length < 2) {
    container.classList.remove('active');
    return;
  }

  searchDebounce = setTimeout(() => {
    const q = query.toLowerCase();
    const results = state.searchIndex
      .filter(item => item.searchStr.includes(q))
      .slice(0, 15);

    if (results.length === 0) {
      container.innerHTML = '<div class="search-result-item" style="color: var(--text-muted)">Nenhum resultado</div>';
    } else {
      container.innerHTML = results.map(r => `
        <div class="search-result-item" onclick="openMunicipality('${r.code}')">
          ${r.name} <span class="uf-tag">${r.uf}</span>
        </div>
      `).join('');
    }

    container.classList.add('active');
  }, 200);
}

// -- Event Listeners --
function setupEventListeners() {
  document.getElementById('indicator-select').addEventListener('change', e => {
    state.indicator = e.target.value;
    renderMap();
  });

  document.getElementById('uf-select').addEventListener('change', e => {
    state.uf = e.target.value;
    renderMap();

    // Zoom to UF if selected
    if (state.uf && state.geolayer) {
      const bounds = [];
      state.geolayer.eachLayer(layer => {
        const code = getFeatureCode(layer.feature);
        const mun = state.data.municipios[code];
        if (mun && mun.uf === state.uf) {
          bounds.push(layer.getBounds());
        }
      });
      if (bounds.length > 0) {
        let combined = bounds[0];
        bounds.forEach(b => combined.extend(b));
        state.map.fitBounds(combined, { padding: [20, 20], maxZoom: 8 });
      }
    } else {
      state.map.setView([-14.5, -51.0], 4);
    }
  });

  document.getElementById('search-input').addEventListener('input', e => {
    handleSearch(e.target.value);
  });

  document.getElementById('search-input').addEventListener('blur', () => {
    setTimeout(() => {
      document.getElementById('search-results').classList.remove('active');
    }, 200);
  });

  // Mobile sidebar toggle
  const toggle = document.getElementById('sidebar-toggle');
  if (toggle) {
    toggle.addEventListener('click', () => {
      document.getElementById('sidebar').classList.toggle('expanded');
    });
  }
}

// -- Start --
document.addEventListener('DOMContentLoaded', init);
