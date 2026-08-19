const REFRESH_MS = 60_000;

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

let sensorChart, co2Chart, cpuChart;

async function refreshLatest() {
  const res = await fetch("/sesami/api/latest");
  const { sensor, system } = await res.json();

  document.getElementById("stat-temperature").textContent = sensor ? `${fmt(sensor.temperature_c)} ℃` : "-- ℃";
  document.getElementById("stat-humidity").textContent = sensor ? `${fmt(sensor.humidity_pct)} %` : "-- %";
  document.getElementById("stat-co2").textContent = sensor ? `${fmt(sensor.co2_ppm, 0)} ppm` : "-- ppm";
  document.getElementById("stat-cpu-temperature").textContent = system
    ? `${fmt(system.cpu_temperature_c)} ℃`
    : "-- ℃";

  const latestTime = sensor?.recorded_at ?? system?.recorded_at;
  document.getElementById("last-updated").textContent = latestTime
    ? `最終更新: ${latestTime}`
    : "データがありません";
}

async function refreshHistory() {
  const res = await fetch("/sesami/api/history?limit=144");
  const { sensor, system } = await res.json();

  const sensorLabels = sensor.map((row) => row.recorded_at);
  const systemLabels = system.map((row) => row.recorded_at);

  const temperatureData = sensor.map((row) => row.temperature_c);
  const humidityData = sensor.map((row) => row.humidity_pct);
  const co2Data = sensor.map((row) => row.co2_ppm);
  const cpuTempData = system.map((row) => row.cpu_temperature_c);

  if (!sensorChart) {
    sensorChart = makeLineChart(document.getElementById("chart-sensor"), sensorLabels, [
      { label: "気温 (℃)", data: temperatureData, borderColor: "#4da3ff", tension: 0.3 },
      { label: "湿度 (%)", data: humidityData, borderColor: "#4dd4ac", tension: 0.3 },
    ]);
    co2Chart = makeLineChart(document.getElementById("chart-co2"), sensorLabels, [
      { label: "CO2 (ppm)", data: co2Data, borderColor: "#f2b84b", tension: 0.3 },
    ]);
    cpuChart = makeLineChart(document.getElementById("chart-cpu"), systemLabels, [
      { label: "CPU温度 (℃)", data: cpuTempData, borderColor: "#f2617a", tension: 0.3 },
    ]);
  } else {
    sensorChart.data.labels = sensorLabels;
    sensorChart.data.datasets[0].data = temperatureData;
    sensorChart.data.datasets[1].data = humidityData;
    sensorChart.update();

    co2Chart.data.labels = sensorLabels;
    co2Chart.data.datasets[0].data = co2Data;
    co2Chart.update();

    cpuChart.data.labels = systemLabels;
    cpuChart.data.datasets[0].data = cpuTempData;
    cpuChart.update();
  }
}

async function refreshAll() {
  await Promise.all([refreshLatest(), refreshHistory()]);
}

refreshAll();
setInterval(refreshAll, REFRESH_MS);
