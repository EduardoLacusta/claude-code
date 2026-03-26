// ======= State =======
let map, heatLayer, markersGroup, favelasGroup;
let currentView = 'heat';
let activeLayers = { criminais: true, celulares: true, veiculos: true, favelas: true };
let rawData = { criminais: [], celulares: [], veiculos: [] };
let comunidades = [];
let allMunicipios = [];
let selectedMunicipios = new Set();
let activeNaturezas = new Set(['FURTO', 'ROUBO', 'HOMICÍDIO', 'TRÁFICO', 'LESÃO']);
const ALL_NATUREZAS = ['FURTO', 'ROUBO', 'HOMICÍDIO', 'TRÁFICO', 'LESÃO'];

const COLORS = { criminais: '#ef4444', celulares: '#f59e0b', veiculos: '#3b82f6' };

const BAIXADA_SANTISTA = [
  'SANTOS', 'S.VICENTE', 'SAO VICENTE', 'GUARUJA', 'GUARUJÁ',
  'PRAIA GRANDE', 'CUBATAO', 'CUBATÃO', 'ITANHAEM', 'ITANHAÉM',
  'MONGAGUA', 'MONGAGUÁ', 'PERUIBE', 'PERUÍBE', 'BERTIOGA',
];

let _debounceTimer = null;
function debouncedLoadData() {
  clearTimeout(_debounceTimer);
  _debounceTimer = setTimeout(() => loadData(), 400);
}

const TILE_URLS = {
  dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
  light: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
};

let tileLayer;

// ======= Theme =======
function getTheme() {
  return document.documentElement.getAttribute('data-theme') || 'dark';
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  document.getElementById('themeIcon').textContent = theme === 'dark' ? '\u2600\uFE0F' : '\uD83C\uDF19';
  if (tileLayer && map) {
    map.removeLayer(tileLayer);
    tileLayer = L.tileLayer(TILE_URLS[theme], {
      attribution: '&copy; OpenStreetMap &copy; CARTO | Dados: SSP-SP',
      maxZoom: 19,
    }).addTo(map);
  }
}

function toggleTheme() {
  setTheme(getTheme() === 'dark' ? 'light' : 'dark');
}

// ======= Multi-select Municipios =======
function isBaixada(mun) {
  const norm = mun.toUpperCase().replace(/[^A-Z ]/g, '');
  return BAIXADA_SANTISTA.some(b => b.replace(/[^A-Z ]/g, '') === norm);
}

function selectBaixada() {
  selectedMunicipios.clear();
  allMunicipios.forEach(m => {
    if (isBaixada(m)) selectedMunicipios.add(m);
  });
  renderMunicipioList();
  updateMunicipioLabel();
  debouncedLoadData();
}

function selectAll() {
  selectedMunicipios = new Set(allMunicipios);
  renderMunicipioList();
  updateMunicipioLabel();
  debouncedLoadData();
}

function selectNone() {
  selectedMunicipios.clear();
  renderMunicipioList();
  updateMunicipioLabel();
  debouncedLoadData();
}

function updateMunicipioLabel() {
  const label = document.getElementById('municipioLabel');
  const total = allMunicipios.length;
  const sel = selectedMunicipios.size;

  if (sel === 0) {
    label.textContent = 'Nenhum munic\u00edpio';
  } else if (sel === total) {
    label.textContent = `Todos os munic\u00edpios (${total})`;
  } else {
    // Check if selection matches Baixada
    const baixadaSet = new Set(allMunicipios.filter(m => isBaixada(m)));
    const isBaixadaSelection = sel === baixadaSet.size &&
      [...selectedMunicipios].every(m => baixadaSet.has(m));
    if (isBaixadaSelection) {
      label.textContent = `Baixada Santista (${sel})`;
    } else {
      label.textContent = `${sel} munic\u00edpio${sel > 1 ? 's' : ''}`;
    }
  }
}

function renderMunicipioList(filter) {
  const list = document.getElementById('municipioList');
  const search = (filter || '').toLowerCase();

  list.innerHTML = '';

  // Sort: Baixada first, then alphabetical
  const sorted = [...allMunicipios].sort((a, b) => {
    const aB = isBaixada(a);
    const bB = isBaixada(b);
    if (aB && !bB) return -1;
    if (!aB && bB) return 1;
    return a.localeCompare(b);
  });

  sorted.forEach(mun => {
    if (search && !mun.toLowerCase().includes(search)) return;

    const item = document.createElement('div');
    item.className = 'ms-item' + (selectedMunicipios.has(mun) ? ' selected' : '');

    const check = document.createElement('span');
    check.className = 'ms-check';
    check.textContent = '\u2713';

    const name = document.createElement('span');
    name.textContent = mun;

    item.appendChild(check);
    item.appendChild(name);

    if (isBaixada(mun)) {
      const badge = document.createElement('span');
      badge.className = 'ms-badge baixada';
      badge.textContent = 'Baixada';
      item.appendChild(badge);
    }

    item.addEventListener('click', () => {
      if (selectedMunicipios.has(mun)) {
        selectedMunicipios.delete(mun);
      } else {
        selectedMunicipios.add(mun);
      }
      item.classList.toggle('selected');
      updateMunicipioLabel();
      debouncedLoadData();
    });

    list.appendChild(item);
  });
}

async function loadMunicipios() {
  try {
    allMunicipios = await apiFetch('/api/municipios');
    selectBaixada();
  } catch (e) {
    console.warn('Erro ao carregar munic\u00edpios:', e);
  }
}

function initMunicipioSelect() {
  const toggle = document.getElementById('municipioToggle');
  const dropdown = document.getElementById('municipioDropdown');
  const search = document.getElementById('municipioSearch');

  toggle.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('hidden');
    if (!dropdown.classList.contains('hidden')) {
      search.focus();
    }
  });

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#municipioSelect')) {
      dropdown.classList.add('hidden');
    }
  });

  search.addEventListener('input', () => {
    renderMunicipioList(search.value);
  });

  document.getElementById('btnBaixada').addEventListener('click', selectBaixada);
  document.getElementById('btnSelectAll').addEventListener('click', selectAll);
  document.getElementById('btnSelectNone').addEventListener('click', selectNone);
}

// ======= Map Init =======
function initMap() {
  const savedTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  document.getElementById('themeIcon').textContent = savedTheme === 'dark' ? '\u2600\uFE0F' : '\uD83C\uDF19';

  map = L.map('map', {
    center: [-23.98, -46.35],
    zoom: 11,
    zoomControl: true,
    attributionControl: true,
  });

  tileLayer = L.tileLayer(TILE_URLS[savedTheme], {
    attribution: '&copy; OpenStreetMap &copy; CARTO | Dados: SSP-SP',
    maxZoom: 19,
  }).addTo(map);

  markersGroup = L.layerGroup();
  favelasGroup = L.layerGroup();

  map.on('zoomend', () => {
    if (currentView === 'cluster') renderView();
  });

  // Load initial data
  loadDateRange();
  loadComunidades();
  loadMunicipios().then(() => loadData());
  loadImportLog();
}

// ======= API Calls =======
async function apiFetch(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

async function loadDateRange() {
  try {
    const range = await apiFetch('/api/date-range');
    document.getElementById('filterDataInicio').value = range.min || '';
    document.getElementById('filterDataFim').value = range.max || '';
  } catch (e) {
    console.warn('Erro ao carregar range de datas:', e);
  }
}

async function loadComunidades() {
  try {
    comunidades = await apiFetch('/api/comunidades');
    favelasGroup.clearLayers();
    comunidades.forEach(f => {
      const marker = L.circleMarker([f.lat, f.lon], {
        radius: 8, fillColor: '#a855f7', fillOpacity: 0.7,
        color: '#a855f7', weight: 2, opacity: 0.9,
      });
      marker.bindPopup(`
        <div class="popup-title">\u26A0 ${f.nome}</div>
        <div class="popup-row"><span class="popup-label">Munic\u00edpio</span><span class="popup-val">${f.municipio}</span></div>
        <div class="popup-row"><span class="popup-label">Obs</span><span class="popup-val">${f.descricao}</span></div>
      `);
      favelasGroup.addLayer(marker);
    });
    document.getElementById('cnt-favelas').textContent = comunidades.length || '\u2014';
    if (activeLayers.favelas) favelasGroup.addTo(map);
  } catch (e) {
    console.warn('Erro ao carregar comunidades:', e);
  }
}

async function loadData() {
  showLoading(true);
  try {
    const params = buildFilterParams();
    const [data, stats] = await Promise.all([
      apiFetch('/api/ocorrencias?' + params),
      apiFetch('/api/stats?' + params),
    ]);

    rawData = {
      criminais: data.criminais || [],
      celulares: data.celulares || [],
      veiculos: data.veiculos || [],
    };

    // Update counts
    document.getElementById('cnt-criminais').textContent = rawData.criminais.length.toLocaleString('pt-BR');
    document.getElementById('cnt-celulares').textContent = rawData.celulares.length.toLocaleString('pt-BR');
    document.getElementById('cnt-veiculos').textContent = rawData.veiculos.length.toLocaleString('pt-BR');

    // Update stats
    document.getElementById('stat-total').textContent = (stats.total || 0).toLocaleString('pt-BR');
    document.getElementById('stat-roubos').textContent = (stats.roubos || 0).toLocaleString('pt-BR');
    document.getElementById('stat-furtos').textContent = (stats.furtos || 0).toLocaleString('pt-BR');
    document.getElementById('stat-homicidios').textContent = (stats.homicidios || 0).toLocaleString('pt-BR');

    renderView();
  } catch (e) {
    console.error('Erro ao carregar dados:', e);
  } finally {
    showLoading(false);
  }
}

function buildFilterParams() {
  const params = new URLSearchParams();
  const di = document.getElementById('filterDataInicio').value;
  const df = document.getElementById('filterDataFim').value;

  if (selectedMunicipios.size > 0 && selectedMunicipios.size < allMunicipios.length) {
    params.set('municipios', [...selectedMunicipios].join(','));
  }
  // Only send naturezas filter if not all are active
  if (activeNaturezas.size > 0 && activeNaturezas.size < ALL_NATUREZAS.length) {
    params.set('naturezas', [...activeNaturezas].join(','));
  } else if (activeNaturezas.size === 0) {
    params.set('naturezas', '__NONE__');
  }
  if (di) params.set('data_inicio', di);
  if (df) params.set('data_fim', df);

  return params.toString();
}

// ======= Rendering =======
function getActivePoints() {
  const pts = [];
  if (activeLayers.criminais) {
    rawData.criminais.forEach(d => pts.push({ lat: d[0], lon: d[1], src: 'criminais', d }));
  }
  if (activeLayers.celulares) {
    rawData.celulares.forEach(d => pts.push({ lat: d[0], lon: d[1], src: 'celulares', d }));
  }
  if (activeLayers.veiculos) {
    rawData.veiculos.forEach(d => pts.push({ lat: d[0], lon: d[1], src: 'veiculos', d }));
  }
  return pts;
}

function renderView() {
  if (heatLayer) { map.removeLayer(heatLayer); heatLayer = null; }
  markersGroup.clearLayers();
  map.removeLayer(markersGroup);

  const pts = getActivePoints();

  if (currentView === 'heat') {
    const heatPts = pts.map(p => [p.lat, p.lon, 0.6]);
    heatLayer = L.heatLayer(heatPts, {
      radius: 18, blur: 22, maxZoom: 15, max: 1.0,
      gradient: { 0.1: '#064e3b', 0.3: '#22c55e', 0.5: '#eab308', 0.7: '#f97316', 0.9: '#ef4444', 1.0: '#7f1d1d' },
    }).addTo(map);
  } else if (currentView === 'points') {
    pts.forEach(p => {
      const color = COLORS[p.src];
      const cm = L.circleMarker([p.lat, p.lon], {
        radius: 4, fillColor: color, fillOpacity: 0.6,
        color, weight: 1, opacity: 0.8,
      });
      cm.bindPopup(makePopup(p));
      markersGroup.addLayer(cm);
    });
    markersGroup.addTo(map);
  } else if (currentView === 'cluster') {
    const grid = {};
    const zoom = map.getZoom();
    const cellSize = zoom < 12 ? 0.02 : zoom < 14 ? 0.005 : 0.002;

    pts.forEach(p => {
      const key = Math.round(p.lat / cellSize) + ',' + Math.round(p.lon / cellSize);
      if (!grid[key]) grid[key] = { lat: 0, lon: 0, count: 0 };
      grid[key].lat += p.lat;
      grid[key].lon += p.lon;
      grid[key].count++;
    });

    Object.values(grid).forEach(g => {
      const lat = g.lat / g.count;
      const lon = g.lon / g.count;
      const r = Math.min(Math.max(Math.sqrt(g.count) * 3, 6), 35);
      const color = g.count > 20 ? '#ef4444' : g.count > 10 ? '#f97316' : g.count > 5 ? '#eab308' : '#22c55e';
      const cm = L.circleMarker([lat, lon], {
        radius: r, fillColor: color, fillOpacity: 0.6,
        color, weight: 1.5, opacity: 0.8,
      });
      cm.bindPopup(`<div class="popup-title">${g.count} ocorr\u00eancias nesta \u00e1rea</div>`);
      markersGroup.addLayer(cm);
    });
    markersGroup.addTo(map);
  }

  // Favelas layer
  if (activeLayers.favelas) {
    favelasGroup.addTo(map);
  } else {
    map.removeLayer(favelasGroup);
  }
}

function makePopup(p) {
  const d = p.d;
  const none = v => (!v || v === 'None' || v === 'NULL') ? '' : v;

  if (p.src === 'criminais') {
    return `<div class="popup-title">${none(d[3]) || none(d[2])}</div>
      <div class="popup-row"><span class="popup-label">Rubrica</span><span class="popup-val">${none(d[2])}</span></div>
      <div class="popup-row"><span class="popup-label">Data</span><span class="popup-val">${none(d[4])} ${none(d[5])}</span></div>
      <div class="popup-row"><span class="popup-label">Local</span><span class="popup-val">${none(d[7])}</span></div>
      <div class="popup-row"><span class="popup-label">Bairro</span><span class="popup-val">${none(d[6])}</span></div>
      <div class="popup-row"><span class="popup-label">Munic\u00edpio</span><span class="popup-val">${none(d[8])}</span></div>
      <div class="popup-row"><span class="popup-label">Tipo Local</span><span class="popup-val">${none(d[9])}</span></div>`;
  } else if (p.src === 'celulares') {
    return `<div class="popup-title">Celular Subtra\u00eddo</div>
      <div class="popup-row"><span class="popup-label">Rubrica</span><span class="popup-val">${none(d[2])}</span></div>
      <div class="popup-row"><span class="popup-label">Data</span><span class="popup-val">${none(d[3])} ${none(d[4])}</span></div>
      <div class="popup-row"><span class="popup-label">Local</span><span class="popup-val">${none(d[6])}</span></div>
      <div class="popup-row"><span class="popup-label">Bairro</span><span class="popup-val">${none(d[5])}</span></div>
      <div class="popup-row"><span class="popup-label">Munic\u00edpio</span><span class="popup-val">${none(d[7])}</span></div>`;
  } else {
    return `<div class="popup-title">Ve\u00edculo Subtra\u00eddo</div>
      <div class="popup-row"><span class="popup-label">Rubrica</span><span class="popup-val">${none(d[2])}</span></div>
      <div class="popup-row"><span class="popup-label">Data</span><span class="popup-val">${none(d[3])} ${none(d[4])}</span></div>
      <div class="popup-row"><span class="popup-label">Local</span><span class="popup-val">${none(d[6])}</span></div>
      <div class="popup-row"><span class="popup-label">Bairro</span><span class="popup-val">${none(d[5])}</span></div>
      <div class="popup-row"><span class="popup-label">Munic\u00edpio</span><span class="popup-val">${none(d[7])}</span></div>
      <div class="popup-row"><span class="popup-label">Tipo Ve\u00edculo</span><span class="popup-val">${none(d[9])}</span></div>`;
  }
}

// ======= Loading =======
function showLoading(show) {
  const el = document.getElementById('loadingOverlay');
  if (show) el.classList.remove('hidden');
  else el.classList.add('hidden');
}

// ======= Import =======
async function triggerImport(tipo, ano) {
  const statusEl = document.getElementById('importStatus');
  statusEl.className = 'import-status running';
  statusEl.textContent = 'Iniciando importa\u00e7\u00e3o...';

  try {
    const body = { ano };
    if (tipo) body.tipo = tipo;
    const resp = await fetch('/api/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await resp.json();

    if (!data.ok) {
      statusEl.className = 'import-status error';
      statusEl.textContent = data.error || 'Erro na importa\u00e7\u00e3o';
      return;
    }

    pollImportStatus();
  } catch (e) {
    statusEl.className = 'import-status error';
    statusEl.textContent = 'Erro: ' + e.message;
  }
}

async function pollImportStatus() {
  const statusEl = document.getElementById('importStatus');
  const check = async () => {
    try {
      const data = await apiFetch('/api/import-status');
      statusEl.textContent = data.progress || '';

      if (data.running) {
        statusEl.className = 'import-status running';
        setTimeout(check, 2000);
      } else {
        if (data.result) {
          const hasError = Object.values(data.result).some(r => r.ok === false);
          statusEl.className = hasError ? 'import-status error' : 'import-status success';

          let msg = '';
          for (const [k, v] of Object.entries(data.result)) {
            if (v.ok === false) {
              msg += `${k}: ${v.error}\n`;
            } else if (v.registros !== undefined) {
              msg += `${k}: ${v.registros} registros importados\n`;
            }
          }
          statusEl.textContent = msg || 'Conclu\u00eddo';
        }
        // Refresh data, municipios list, and log
        loadMunicipios();
        loadData();
        loadImportLog();
      }
    } catch (e) {
      statusEl.className = 'import-status error';
      statusEl.textContent = 'Erro ao verificar status';
    }
  };
  check();
}

async function loadImportLog() {
  try {
    const log = await apiFetch('/api/import-log');
    const el = document.getElementById('importLog');
    if (log.length === 0) {
      el.innerHTML = '<div class="import-log-item">Nenhuma importa\u00e7\u00e3o realizada</div>';
      return;
    }
    el.innerHTML = log.map(l =>
      `<div class="import-log-item">${l.tipo} ${l.ano}: ${(l.registros || 0).toLocaleString('pt-BR')} reg. (${l.importado_em || ''})</div>`
    ).join('');
  } catch (e) {
    // silent
  }
}

// ======= Event Listeners =======
document.addEventListener('DOMContentLoaded', () => {
  initMunicipioSelect();
  initMap();

  // Theme toggle
  document.getElementById('themeToggle').addEventListener('click', toggleTheme);

  // View buttons
  document.querySelectorAll('.view-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentView = btn.dataset.view;
      renderView();
    });
  });

  // Layer toggles
  document.querySelectorAll('.layer-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const layer = btn.dataset.layer;
      activeLayers[layer] = !activeLayers[layer];
      btn.classList.toggle('active');
      renderView();
    });
  });

  // Natureza toggles
  document.querySelectorAll('.natureza-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const nat = btn.dataset.natureza;
      if (activeNaturezas.has(nat)) {
        activeNaturezas.delete(nat);
      } else {
        activeNaturezas.add(nat);
      }
      btn.classList.toggle('active');
      debouncedLoadData();
    });
  });

  // Date inputs
  document.getElementById('filterDataInicio').addEventListener('change', debouncedLoadData);
  document.getElementById('filterDataFim').addEventListener('change', debouncedLoadData);

  // Import buttons
  document.getElementById('btnUpdate').addEventListener('click', () => triggerImport(null, 2026));
  document.getElementById('btnImportAll').addEventListener('click', () => {
    if (confirm('Importar todos os dados 2025-2026? Isso pode levar alguns minutos.')) {
      triggerImport(null, 2025);
    }
  });
});
