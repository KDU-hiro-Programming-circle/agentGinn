const REFRESH_MS = 60_000;
const COLORS = { temperature: "#4da3ff", humidity: "#4dd4ac", co2: "#f2b84b", cpu: "#f2617a" };

function fmt(value, digits = 1) {
  return typeof value === "number" ? value.toFixed(digits) : "--";
}

function makeLineChart(ctx, labels, datasets) {
  return new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      animation: false,
      scales: {
        x: { ticks: { color: "#8a8f98", maxTicksLimit: 8 } },
        y: { ticks: { color: "#8a8f98" } },
      },
      plugins: {
        legend: { labels: { color: "#e6e8eb" } },
      },
    },
  });
}

let sensors = [];
const charts = {}; // canvas element id -> Chart instance

// One stat card + two chart cards (temp/humidity, CO2) per sensor, plus a
// fixed card for the host PC. Built once at load -- a newly-registered
// sensor shows up after the dashboard page is reloaded.
function buildLayout() {
  const statGrid = document.getElementById("stat-grid");
  const chartGrid = document.getElementById("chart-grid");

  for (const s of sensors) {
    statGrid.insertAdjacentHTML(
      "beforeend",
      `<div class="stat-card">
        <h2>${s.name}</h2>
        <p class="stat-value"><span id="stat-temp-${s.key}">--</span> ℃</p>
        <p class="stat-sub">湿度 <span id="stat-hum-${s.key}">--</span>% / CO2 <span id="stat-co2-${s.key}">--</span>ppm</p>
      </div>`
    );
    chartGrid.insertAdjacentHTML(
      "beforeend",
      `<div class="chart-card">
        <h2>${s.name} - 気温 / 湿度</h2>
        <canvas id="chart-th-${s.key}"></canvas>
      </div>
      <div class="chart-card">
        <h2>${s.name} - CO2</h2>
        <canvas id="chart-co2-${s.key}"></canvas>
      </div>`
    );
  }

  statGrid.insertAdjacentHTML(
    "beforeend",
    `<div class="stat-card">
      <h2>部室PC</h2>
      <p class="stat-value"><span id="stat-cpu">--</span> ℃</p>
    </div>`
  );
  chartGrid.insertAdjacentHTML(
    "beforeend",
    `<div class="chart-card">
      <h2>CPU温度</h2>
      <canvas id="chart-cpu"></canvas>
    </div>`
  );
}

async function loadSensors() {
  const res = await fetch("/sesami/api/sensors");
  sensors = await res.json();
  buildLayout();
}

async function refreshLatest() {
  const res = await fetch("/sesami/api/latest");
  const { sensors: latestByKey, system } = await res.json();

  const times = [];
  for (const s of sensors) {
    const row = latestByKey[s.key];
    document.getElementById(`stat-temp-${s.key}`).textContent = row ? fmt(row.temperature_c) : "--";
    document.getElementById(`stat-hum-${s.key}`).textContent = row ? fmt(row.humidity_pct) : "--";
    document.getElementById(`stat-co2-${s.key}`).textContent = row ? fmt(row.co2_ppm, 0) : "--";
    if (row?.recorded_at) times.push(row.recorded_at);
  }

  document.getElementById("stat-cpu").textContent = system ? fmt(system.cpu_temperature_c) : "--";
  if (system?.recorded_at) times.push(system.recorded_at);

  document.getElementById("last-updated").textContent = times.length
    ? `最終更新: ${times.sort().at(-1)}`
    : "データがありません";
}

function updateChart(canvasId, labels, datasets) {
  if (!charts[canvasId]) {
    charts[canvasId] = makeLineChart(document.getElementById(canvasId), labels, datasets);
    return;
  }
  charts[canvasId].data.labels = labels;
  datasets.forEach((ds, i) => {
    charts[canvasId].data.datasets[i].data = ds.data;
  });
  charts[canvasId].update();
}

async function refreshHistory() {
  const res = await fetch("/sesami/api/history?limit=144");
  const { sensors: historyByKey, system } = await res.json();

  for (const s of sensors) {
    const rows = historyByKey[s.key] || [];
    const labels = rows.map((r) => r.recorded_at);
    updateChart(`chart-th-${s.key}`, labels, [
      { label: "気温 (℃)", data: rows.map((r) => r.temperature_c), borderColor: COLORS.temperature, tension: 0.3 },
      { label: "湿度 (%)", data: rows.map((r) => r.humidity_pct), borderColor: COLORS.humidity, tension: 0.3 },
    ]);
    updateChart(`chart-co2-${s.key}`, labels, [
      { label: "CO2 (ppm)", data: rows.map((r) => r.co2_ppm), borderColor: COLORS.co2, tension: 0.3 },
    ]);
  }

  updateChart(
    "chart-cpu",
    system.map((r) => r.recorded_at),
    [{ label: "CPU温度 (℃)", data: system.map((r) => r.cpu_temperature_c), borderColor: COLORS.cpu, tension: 0.3 }]
  );
}

async function refreshAll() {
  await Promise.all([refreshLatest(), refreshHistory()]);
}

async function init() {
  await loadSensors();
  await refreshAll();
  setInterval(refreshAll, REFRESH_MS);
}

init();
