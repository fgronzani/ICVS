/* =================================================================
   Chart.js Helper Functions
   Consistent dark-theme styling for all charts
   ================================================================= */

// Register defaults for dark theme
function configureChartDefaults() {
  if (typeof Chart === 'undefined') return;

  Chart.defaults.color = '#94a3b8';
  Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.06)';
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.plugins.legend.labels.padding = 16;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(17, 24, 39, 0.95)';
  Chart.defaults.plugins.tooltip.titleColor = '#f0f2f5';
  Chart.defaults.plugins.tooltip.bodyColor = '#94a3b8';
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(255, 255, 255, 0.06)';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.elements.point.radius = 4;
  Chart.defaults.elements.point.hoverRadius = 6;
}

// ICVS Evolution Line Chart
function createEvolutionChart(ctx, historico) {
  configureChartDefaults();

  const years = historico.map(h => h.ano);
  const icvsValues = historico.map(h => h.icvs);
  const desfechos = historico.map(h => h.sub_desfechos);
  const acesso = historico.map(h => h.sub_acesso);
  const qualidade = historico.map(h => h.sub_qualidade);

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: years,
      datasets: [
        {
          label: 'ICVS',
          data: icvsValues,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          borderWidth: 3,
          fill: true,
          tension: 0.35,
          pointBackgroundColor: '#3b82f6',
        },
        {
          label: 'Desfechos',
          data: desfechos,
          borderColor: '#ef4444',
          borderWidth: 1.5,
          borderDash: [4, 4],
          tension: 0.35,
          pointRadius: 2,
        },
        {
          label: 'Acesso',
          data: acesso,
          borderColor: '#22c55e',
          borderWidth: 1.5,
          borderDash: [4, 4],
          tension: 0.35,
          pointRadius: 2,
        },
        {
          label: 'Qualidade',
          data: qualidade,
          borderColor: '#fbbf24',
          borderWidth: 1.5,
          borderDash: [4, 4],
          tension: 0.35,
          pointRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: 'index',
      },
      plugins: {
        legend: {
          position: 'bottom',
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { maxRotation: 0 },
        },
        y: {
          min: 0,
          max: 100,
          grid: { color: 'rgba(255, 255, 255, 0.04)' },
          ticks: {
            callback: v => v.toFixed(0),
          },
        },
      },
    },
  });
}

// Radar Chart: sub-indices vs national median & cluster median
function createRadarChart(ctx, municipio, nationalMedian, clusterMedian) {
  configureChartDefaults();

  const labels = ['Desfechos em Saúde', 'Acesso e Capacidade', 'Qualidade da Atenção'];

  return new Chart(ctx, {
    type: 'radar',
    data: {
      labels,
      datasets: [
        {
          label: municipio.nome,
          data: [municipio.sub_desfechos, municipio.sub_acesso, municipio.sub_qualidade],
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.15)',
          borderWidth: 2.5,
          pointBackgroundColor: '#3b82f6',
          pointRadius: 5,
        },
        {
          label: 'Mediana Nacional',
          data: [nationalMedian.sub_desfechos, nationalMedian.sub_acesso, nationalMedian.sub_qualidade],
          borderColor: '#94a3b8',
          backgroundColor: 'rgba(148, 163, 184, 0.05)',
          borderWidth: 1.5,
          borderDash: [5, 5],
          pointRadius: 3,
          pointBackgroundColor: '#94a3b8',
        },
        {
          label: 'Mediana do Cluster',
          data: [clusterMedian.sub_desfechos, clusterMedian.sub_acesso, clusterMedian.sub_qualidade],
          borderColor: '#fbbf24',
          backgroundColor: 'rgba(251, 191, 36, 0.05)',
          borderWidth: 1.5,
          borderDash: [3, 3],
          pointRadius: 3,
          pointBackgroundColor: '#fbbf24',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
        },
      },
      scales: {
        r: {
          angleLines: { color: 'rgba(255, 255, 255, 0.06)' },
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          pointLabels: {
            font: { size: 11, weight: '500' },
            color: '#94a3b8',
          },
          ticks: {
            backdropColor: 'transparent',
            color: '#64748b',
            font: { size: 10 },
          },
          suggestedMin: 0,
          suggestedMax: 100,
        },
      },
    },
  });
}

// Horizontal bar chart for indicator comparison
function createIndicatorChart(ctx, indicators, labels, colors) {
  configureChartDefaults();

  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: indicators,
        backgroundColor: colors || indicators.map(v => getIndicatorColor(v)),
        borderRadius: 4,
        barThickness: 18,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          min: 0,
          max: 100,
          grid: { color: 'rgba(255, 255, 255, 0.04)' },
        },
        y: {
          grid: { display: false },
          ticks: {
            font: { size: 11 },
          },
        },
      },
    },
  });
}

function getIndicatorColor(value) {
  if (value <= 20) return '#22c55e';
  if (value <= 40) return '#86efac';
  if (value <= 60) return '#fbbf24';
  if (value <= 80) return '#f97316';
  return '#ef4444';
}
