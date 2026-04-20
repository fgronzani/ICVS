/* =================================================================
   Chart.js — Professional light-theme styling
   ================================================================= */

function configureChartDefaults() {
  if (typeof Chart === 'undefined') return;

  Chart.defaults.color = '#6c757d';
  Chart.defaults.borderColor = '#e9ecef';
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.plugins.legend.labels.padding = 16;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;
  Chart.defaults.plugins.tooltip.backgroundColor = '#212529';
  Chart.defaults.plugins.tooltip.titleColor = '#f8f9fa';
  Chart.defaults.plugins.tooltip.bodyColor = '#dee2e6';
  Chart.defaults.plugins.tooltip.borderColor = '#495057';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.cornerRadius = 6;
  Chart.defaults.plugins.tooltip.padding = 10;
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
          borderColor: '#155d8b',
          backgroundColor: 'rgba(21, 93, 139, 0.08)',
          borderWidth: 2.5,
          fill: true,
          tension: 0.3,
          pointBackgroundColor: '#155d8b',
        },
        {
          label: 'Desfechos',
          data: desfechos,
          borderColor: '#c0392b',
          borderWidth: 1.5,
          borderDash: [4, 4],
          tension: 0.3,
          pointRadius: 2,
          pointBackgroundColor: '#c0392b',
        },
        {
          label: 'Acesso',
          data: acesso,
          borderColor: '#2a9d8f',
          borderWidth: 1.5,
          borderDash: [4, 4],
          tension: 0.3,
          pointRadius: 2,
          pointBackgroundColor: '#2a9d8f',
        },
        {
          label: 'Qualidade',
          data: qualidade,
          borderColor: '#d4841a',
          borderWidth: 1.5,
          borderDash: [4, 4],
          tension: 0.3,
          pointRadius: 2,
          pointBackgroundColor: '#d4841a',
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
          grid: { color: '#f1f3f5' },
          ticks: {
            callback: v => v.toFixed(0),
          },
        },
      },
    },
  });
}

// Radar Chart
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
          borderColor: '#155d8b',
          backgroundColor: 'rgba(21, 93, 139, 0.1)',
          borderWidth: 2.5,
          pointBackgroundColor: '#155d8b',
          pointRadius: 5,
        },
        {
          label: 'Mediana Nacional',
          data: [nationalMedian.sub_desfechos, nationalMedian.sub_acesso, nationalMedian.sub_qualidade],
          borderColor: '#adb5bd',
          backgroundColor: 'rgba(173, 181, 189, 0.05)',
          borderWidth: 1.5,
          borderDash: [5, 5],
          pointRadius: 3,
          pointBackgroundColor: '#adb5bd',
        },
        {
          label: 'Mediana do Cluster',
          data: [clusterMedian.sub_desfechos, clusterMedian.sub_acesso, clusterMedian.sub_qualidade],
          borderColor: '#d4841a',
          backgroundColor: 'rgba(212, 132, 26, 0.05)',
          borderWidth: 1.5,
          borderDash: [3, 3],
          pointRadius: 3,
          pointBackgroundColor: '#d4841a',
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
          angleLines: { color: '#e9ecef' },
          grid: { color: '#e9ecef' },
          pointLabels: {
            font: { size: 11, weight: '500' },
            color: '#495057',
          },
          ticks: {
            backdropColor: 'transparent',
            color: '#868e96',
            font: { size: 10 },
          },
          suggestedMin: 0,
          suggestedMax: 100,
        },
      },
    },
  });
}

// Horizontal bar chart
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
          grid: { color: '#f1f3f5' },
        },
        y: {
          grid: { display: false },
          ticks: { font: { size: 11 } },
        },
      },
    },
  });
}

function getIndicatorColor(value) {
  if (value <= 20) return '#2a9d8f';
  if (value <= 40) return '#8ab17d';
  if (value <= 60) return '#e9c46a';
  if (value <= 80) return '#e76f51';
  return '#c1121f';
}
