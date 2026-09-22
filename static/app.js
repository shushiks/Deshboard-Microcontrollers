const state = {
  devices: [], selectedId: sessionStorage.getItem("selectedDeviceId"), history: [], metric: "air_temperature", detailPoints: [],
  compareMode: false, compareIds: [], compareHistory: {}, compareRequest: 0,
};
const metricInfo = {
  air_temperature: ["Температура воздуха", "°C", "#64f4bd"],
  air_pressure: ["Атмосферное давление", "гПа", "#ddacff"],
  water_temperature: ["Температура воды", "°C", "#a99bff"],
  humidity: ["Влажность воздуха", "%", "#54d7ef"],
  air_quality: ["Газовый сигнал MQ-5", "raw", "#f7bf64"],
  ph: ["Кислотность", "pH", "#ff8fc7"],
  raindrop: ["Интенсивность дождя", "raw", "#7ea7ff"],
};
const metricDescriptions = {
  air_temperature: "Температура окружающего воздуха возле контроллера.",
  air_pressure: "Атмосферное давление по BMP280 в гектопаскалях (гПа). Не влажность и не плотность воздуха.",
  water_temperature: "Температура воды внутри контролируемого резервуара.",
  humidity: "Относительная влажность воздуха: 100% означает максимально насыщенный влагой воздух.",
  air_quality: "Сырое значение газового датчика. Это не проценты: закономерность важнее отдельного числа, а направление зависит от модели датчика.",
  ph: "Кислотность воды: 7 — нейтральная среда, меньше 7 — кислая, больше 7 — щелочная.",
  raindrop: "Сырое значение датчика капель. Направление шкалы зависит от модуля и требует калибровки.",
};
const el = {
  row: document.querySelector("#device-row"), details: document.querySelector("#details"),
  online: document.querySelector("#online-count"), name: document.querySelector("#selected-name"),
  total: document.querySelector("#total-count"), offline: document.querySelector("#offline-count"),
  location: document.querySelector("#selected-location"), threshold: document.querySelector("#selected-threshold"),
  range: document.querySelector("#history-range"), date: document.querySelector("#history-date"),
  historyMetrics: document.querySelector("#history-metrics"), detail: document.querySelector("#metric-detail"),
  detailTitle: document.querySelector("#detail-title"), detailStats: document.querySelector("#detail-stats"),
  detailChart: document.querySelector("#detail-chart"), detailValues: document.querySelector("#detail-values"),
  explanation: document.querySelector("#metric-explanation"), chartFrom: document.querySelector("#chart-from"),
  chartTo: document.querySelector("#chart-to"), tooltip: document.querySelector("#chart-tooltip"),
  dateControl: document.querySelector("#history-date-control"), compareToggle: document.querySelector("#compare-toggle"),
  compareClose: document.querySelector("#compare-close"), comparison: document.querySelector("#comparison"),
  comparisonContent: document.querySelector("#comparison-content"), deviceHint: document.querySelector("#device-hint"),
  compareChartSection: document.querySelector("#comparison-chart-section"), compareMetric: document.querySelector("#compare-metric"),
  compareRange: document.querySelector("#compare-range"), compareChart: document.querySelector("#compare-chart"),
  compareLegendA: document.querySelector("#compare-legend-a"), compareLegendB: document.querySelector("#compare-legend-b"),
  compareChartNote: document.querySelector("#compare-chart-note"),
};
const show = (value, digits = 1) => value == null ? "—" : Number(value).toFixed(digits);
const sampleTime = item => item.measured_at || item.received_at;
const escapeHtml = value => String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
function formatAge(value) {
  if (!value) return "никогда";
  const seconds = Math.max(0, Math.floor((Date.now()-new Date(value).getTime())/1000));
  if (seconds < 60) return `${seconds} сек назад`;
  if (seconds < 3600) return `${Math.floor(seconds/60)} мин назад`;
  if (seconds < 86400) return `${Math.floor(seconds/3600)} ч назад`;
  return `${Math.floor(seconds/86400)} дн назад`;
}

function renderDevices() {
  const onlineCount = state.devices.filter(device => device.online).length;
  el.total.textContent = state.devices.length; el.online.textContent = onlineCount; el.offline.textContent = state.devices.length-onlineCount;
  if (!state.devices.length) { el.row.innerHTML = '<div class="empty-state">Ожидание первого устройства…</div>'; return; }
  const columns = [["air_temperature","Воздух","°C"],["air_pressure","Давление","гПа"],["water_temperature","Вода","°C"],["humidity","Влажность воздуха","%"],["air_quality","Газ MQ-5","raw"],["ph","Кислотность","pH"] ,["raindrop","Интенсивность дождя","raw"]];
  el.row.innerHTML = `<div class="fleet-head"><span>Резервуар / ESP</span>${columns.map(([,label]) => `<span>${label}</span>`).join("")}</div>` + state.devices.map(device => `
    <article class="device-card ${device.temperature_alert ? "alert" : ""} ${!state.compareMode && device.device_id === state.selectedId ? "active" : ""} ${state.compareIds.includes(device.device_id) ? "compare-selected" : ""}" data-id="${escapeHtml(device.device_id)}" role="button" tabindex="0" title="Порог температуры: ${show(device.temperature_threshold)} °C; красный цвет — только при свежем превышении" aria-label="${state.compareMode ? "Выбрать для сравнения" : "Открыть историю"} ${escapeHtml(device.name)}">
      <div class="device-identity"><i class="status ${device.online ? "online" : ""}" title="${device.online ? "На связи" : `Нет heartbeat: ${formatAge(device.last_seen)}`}"></i><div><h3>${escapeHtml(device.name)}</h3></div></div>
      ${columns.map(([key,,unit]) => `<div class="device-value" title="Последнее обновление: ${formatTime(device[`${key}_at`], true)}"><strong>${show(device[key], key === "air_quality" || key === "raindrop" ? 0 : 1)}</strong><small>${unit}${device[key] == null ? "" : ` · ${formatAge(device[`${key}_at`])}`}</small></div>`).join("")}
      ${state.compareMode ? `<span class="compare-marker">${state.compareIds.indexOf(device.device_id) + 1 || "+"}</span>` : ""}
    </article>`).join("");
  el.row.querySelectorAll(".device-card").forEach(card => {
    card.addEventListener("click", () => activateDevice(card.dataset.id));
    card.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activateDevice(card.dataset.id); } });
  });
}

function activateDevice(deviceId) {
  if (!state.compareMode) { selectDevice(deviceId); return; }
  const index = state.compareIds.indexOf(deviceId);
  if (index >= 0) state.compareIds.splice(index, 1);
  else if (state.compareIds.length < 2) state.compareIds.push(deviceId);
  else state.compareIds[1] = deviceId;
  state.compareRequest++;
  state.compareHistory = {};
  renderDevices(); renderComparison(); loadComparisonHistory();
}

function setCompareMode(enabled) {
  state.compareMode = enabled;
  if (!enabled) { state.compareIds = []; state.compareHistory = {}; state.compareRequest++; }
  el.comparison.hidden = !enabled; el.details.hidden = enabled;
  el.compareToggle.classList.toggle("active", enabled);
  el.deviceHint.textContent = enabled ? "Выберите две строки ESP" : "Нажмите на строку ESP, чтобы посмотреть её историю";
  renderDevices();
  if (enabled) renderComparison(); else renderSelected();
}

function renderComparison() {
  const selected = state.compareIds.map(id => state.devices.find(device => device.device_id === id)).filter(Boolean);
  if (selected.length < 2) {
    el.compareChartSection.hidden = true;
    el.comparisonContent.innerHTML = `<div class="comparison-empty">Выбрано ${selected.length} из 2 устройств. Нажмите ещё ${2-selected.length} ${selected.length ? "строку" : "строки"}.</div>`;
    return;
  }
  const [first, second] = selected;
  el.compareChartSection.hidden = false;
  el.compareLegendA.textContent = first.name;
  el.compareLegendB.textContent = second.name;
  el.comparisonContent.innerHTML = `<div class="comparison-names"><strong>${escapeHtml(first.name)}</strong><span>против</span><strong>${escapeHtml(second.name)}</strong></div>
    <div class="comparison-table"><div class="comparison-row comparison-header"><span>Метрика</span><span>${escapeHtml(first.name)}</span><span>${escapeHtml(second.name)}</span><span>Разница B − A</span></div>
    ${Object.entries(metricInfo).map(([key,[label,unit]]) => {
      const a = first[key], b = second[key], digits = key === "air_quality" || key === "raindrop" ? 0 : 1;
      const difference = Number.isFinite(a) && Number.isFinite(b) ? b-a : null;
      return `<div class="comparison-row"><span>${label}</span><strong>${show(a,digits)} ${a == null ? "" : unit}</strong><strong>${show(b,digits)} ${b == null ? "" : unit}</strong><b>${difference == null ? "—" : `${difference > 0 ? "+" : ""}${show(difference,digits)} ${unit}`}</b></div>`;
    }).join("")}</div>`;
  drawComparisonChart();
}

async function loadComparisonHistory() {
  if (!state.compareMode || state.compareIds.length !== 2) return;
  const ids = [...state.compareIds], requestId = ++state.compareRequest;
  const params = new URLSearchParams({hours: el.compareRange.value, limit: "5000"});
  el.compareChartNote.textContent = "Загружаем историю…";
  try {
    const histories = await Promise.all(ids.map(async id => {
      const response = await fetch(`/api/devices/${encodeURIComponent(id)}/history?${params}`, {cache: "no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return (await response.json()).readings;
    }));
    if (requestId !== state.compareRequest || !state.compareMode) return;
    state.compareHistory = Object.fromEntries(ids.map((id, index) => [id, histories[index]]));
    drawComparisonChart();
  } catch (error) {
    if (requestId !== state.compareRequest) return;
    el.compareChartNote.textContent = "Не удалось загрузить историю для сравнения.";
    console.error("Не удалось загрузить сравнение", error);
  }
}

function drawComparisonChart() {
  if (!state.compareMode || state.compareIds.length !== 2 || el.compareChartSection.hidden) return;
  const metric = el.compareMetric.value, [label, unit] = metricInfo[metric];
  const ids = state.compareIds, series = ids.map(id => (state.compareHistory[id] || [])
    .filter(item => Number.isFinite(item[metric]) && Number.isFinite(Date.parse(sampleTime(item)))));
  const count = series.map(points => points.length);
  el.compareChartNote.textContent = `${label}, ${unit}: ${count[0]} и ${count[1]} замеров соответственно. Линии строятся по фактическому времени каждого устройства.`;
  const canvas = el.compareChart, width = canvas.clientWidth, height = canvas.clientHeight;
  if (!width || !height) return;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
  const ctx = canvas.getContext("2d"); ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  const margin = {left: 52, right: 15, top: 15, bottom: 30};
  const plotWidth = Math.max(1, width-margin.left-margin.right), plotHeight = Math.max(1, height-margin.top-margin.bottom);
  const values = series.flatMap(points => points.map(item => item[metric]));
  if (!values.length) { ctx.fillStyle = "#8fa9a0"; ctx.font = "12px Manrope, sans-serif"; ctx.fillText("Нет замеров этой метрики за выбранный период", 15, height/2); return; }
  const min = Math.min(...values), max = Math.max(...values), pad = Math.max((max-min)*.15, 1);
  const low = min-pad, high = max+pad;
  const stamps = series.flatMap(points => points.map(item => Date.parse(sampleTime(item))));
  const firstStamp = Math.min(...stamps), lastStamp = Math.max(...stamps);
  const timePad = Math.max((lastStamp-firstStamp)*.04, 1000);
  const start = firstStamp-timePad, end = lastStamp+timePad;
  ctx.font = "10px Manrope, sans-serif"; ctx.textAlign = "right"; ctx.textBaseline = "middle";
  for (let tick=0; tick<=4; tick++) {
    const y = margin.top+plotHeight*tick/4;
    ctx.strokeStyle = "rgba(195,255,230,.12)"; ctx.beginPath(); ctx.moveTo(margin.left,y); ctx.lineTo(width-margin.right,y); ctx.stroke();
    ctx.fillStyle = "#8fa9a0"; ctx.fillText(show(high-(high-low)*tick/4, metric === "air_quality" || metric === "raindrop" ? 0 : 1), margin.left-7,y);
  }
  ctx.textBaseline = "top";
  for (let tick=0; tick<=2; tick++) {
    const fraction = tick/2, stamp = new Date(start+(end-start)*fraction);
    ctx.textAlign = tick === 0 ? "left" : tick === 2 ? "right" : "center";
    ctx.fillStyle = "#8fa9a0"; ctx.fillText(formatTime(stamp), margin.left+plotWidth*fraction, height-margin.bottom+7);
  }
  ctx.save(); ctx.beginPath(); ctx.rect(margin.left,margin.top,plotWidth,plotHeight); ctx.clip();
  series.forEach((points,index) => {
    const coordinates = points.map(item => ({x: margin.left+(Date.parse(sampleTime(item))-start)/(end-start)*plotWidth,
      y: margin.top+(high-item[metric])/(high-low)*plotHeight})).filter(point => point.x >= margin.left && point.x <= margin.left+plotWidth);
    if (!coordinates.length) return;
    ctx.strokeStyle = index ? "#a99bff" : "#64f4bd"; ctx.fillStyle = ctx.strokeStyle; ctx.lineWidth = 2;
    ctx.beginPath(); coordinates.forEach((point,i) => i ? ctx.lineTo(point.x,point.y) : ctx.moveTo(point.x,point.y));
    if (coordinates.length > 1) ctx.stroke();
    if (coordinates.length === 1) { ctx.beginPath(); ctx.arc(coordinates[0].x,coordinates[0].y,3,0,Math.PI*2); ctx.fill(); }
  });
  ctx.restore();
}

function renderSelected() {
  if (state.compareMode) { el.details.hidden = true; return; }
  const device = state.devices.find(item => item.device_id === state.selectedId);
  if (!device) { el.details.hidden = true; return; }
  el.details.hidden = false; el.name.textContent = device.name;
  el.threshold.textContent = `Красный статус: температура воздуха или воды выше ${show(device.temperature_threshold)} °C (только свежий замер)`;
  if (device.latitude == null || device.longitude == null) {
    el.location.textContent = "Координаты не заданы";
  } else {
    const lat = device.latitude.toFixed(5), lon = device.longitude.toFixed(5);
    const yandex = `https://yandex.ru/maps/?pt=${lon},${lat}&z=14&l=map`;
    const google = `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
    const place = device.address
      ? `<strong>${escapeHtml(device.locality || "Местоположение")}</strong><p>${escapeHtml(device.address)}</p>`
      : "<em>Адрес определяется…</em>";
    el.location.innerHTML = `${place}<div class="location-bottom"><code>${lat}, ${lon}</code><span><a href="${yandex}" target="_blank" rel="noopener">Яндекс Карты ↗</a><a href="${google}" target="_blank" rel="noopener">Google Maps ↗</a></span></div><small>Адрес: © OpenStreetMap contributors</small>`;
  }
}

async function selectDevice(deviceId) {
  state.selectedId = deviceId; sessionStorage.setItem("selectedDeviceId", deviceId);
  state.history = []; renderDevices(); renderSelected(); renderMetricHistories(); await loadHistory();
}

async function loadDevices() {
  try {
    const response = await fetch("/api/devices", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.devices = await response.json();
    if (!state.devices.some(device => device.device_id === state.selectedId)) {
      state.selectedId = state.devices[0]?.device_id ?? null;
      if (state.selectedId) sessionStorage.setItem("selectedDeviceId", state.selectedId);
      else sessionStorage.removeItem("selectedDeviceId");
    }
    renderDevices(); renderSelected();
    if (state.compareMode) renderComparison();
  } catch (error) {
    console.error("Не удалось обновить список устройств", error);
  }
}

async function loadHistory() {
  if (!state.selectedId) return;
  const requestedId = state.selectedId;
  const isDay = el.range.value === "day";
  if (isDay && !el.date.value) return;
  const params = new URLSearchParams({ hours: isDay ? "24" : el.range.value, limit: "1000" });
  if (isDay) { params.set("day", el.date.value); params.set("timezone_offset", new Date().getTimezoneOffset()); }
  try {
    const response = await fetch(`/api/devices/${encodeURIComponent(requestedId)}/history?${params}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    if (requestedId !== state.selectedId) return;
    state.history = (await response.json()).readings; renderMetricHistories();
  } catch (error) {
    console.error("Не удалось загрузить историю", error);
  }
}

function formatTime(value, withDate = false) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU", withDate
    ? { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }
    : { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(value));
}

function renderMetricHistories() {
  el.historyMetrics.innerHTML = Object.entries(metricInfo).map(([key, [label, unit, color]]) => {
    const points = state.history.filter(item => Number.isFinite(item[key]));
    const digits = key === "air_quality" || key === "raindrop" ? 0 : 1;
    const values = points.map(item => item[key]);
    return `<button class="metric-selector ${key === state.metric ? "active" : ""}" data-metric="${key}">
      <span>${label}</span><strong>${points.length ? show(points.at(-1)[key], digits) : "—"} <small>${unit}</small></strong>
      <div><b>${points.length} замеров</b><i>${points.length ? `min ${show(Math.min(...values), digits)} · max ${show(Math.max(...values), digits)}` : "нет данных"}</i></div>
    </button>`;
  }).join("");
  renderMetricDetail();
}

function renderMetricDetail() {
  const [label, unit, color] = metricInfo[state.metric], digits = state.metric === "air_quality" || state.metric === "raindrop" ? 0 : 1;
  const points = state.history.filter(item => Number.isFinite(item[state.metric]));
  const values = points.map(item => item[state.metric]);
  el.detail.dataset.metric = state.metric; el.detailTitle.textContent = label;
  const average = points.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  el.detailStats.textContent = points.length ? `${points.length} замеров · среднее ${show(average, digits)} ${unit} · min ${show(Math.min(...values), digits)} · max ${show(Math.max(...values), digits)}` : "Нет данных";
  el.explanation.textContent = metricDescriptions[state.metric];
  el.chartFrom.textContent = points.length ? formatTime(sampleTime(points[0]), true) : "—";
  el.chartTo.textContent = points.length ? formatTime(sampleTime(points.at(-1)), true) : "—";
  el.detailValues.innerHTML = points.length ? `<div class="detail-values-head"><span>Дата и время замера</span><span>Значение</span></div>` + [...points].reverse().map(item => `<div><time>${formatTime(sampleTime(item), true)}</time><strong>${show(item[state.metric], digits)} ${unit}</strong></div>`).join("") : '<p>Эта метрика в выбранный период не поступала.</p>';
  drawMetricChart(el.detailChart, state.metric);
}

function drawMetricChart(canvas, metric) {
  const points = state.history.filter(item => Number.isFinite(item[metric]));
  if (canvas === el.detailChart) { state.detailPoints = []; el.tooltip.hidden = true; }
  const ratio = window.devicePixelRatio || 1, width = canvas.clientWidth, height = canvas.clientHeight;
  canvas.width = width * ratio; canvas.height = height * ratio;
  const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio); ctx.clearRect(0, 0, width, height);
  const margin = { left: 48, right: 14, top: 12, bottom: 28 };
  const plotWidth = Math.max(width-margin.left-margin.right, 1), plotHeight = Math.max(height-margin.top-margin.bottom, 1);
  ctx.font = "10px Manrope, sans-serif"; ctx.lineWidth = 1;
  if (!points.length) return;
  const values = points.map(item => item[metric]), min = Math.min(...values), max = Math.max(...values), pad = Math.max((max-min)*.15, 1), range = max-min+pad*2;
  ctx.textAlign = "right"; ctx.textBaseline = "middle";
  for (let tick = 0; tick <= 4; tick++) {
    const y = margin.top + plotHeight*tick/4, value = max+pad-range*tick/4;
    ctx.strokeStyle = tick === 4 ? "rgba(195,255,230,.25)" : "rgba(195,255,230,.09)";
    ctx.beginPath(); ctx.moveTo(margin.left,y); ctx.lineTo(width-margin.right,y); ctx.stroke();
    ctx.fillStyle = "#8fa9a0"; ctx.fillText(show(value, metric === "air_quality" || metric === "raindrop" ? 0 : 1), margin.left-7,y);
  }
  const span = new Date(sampleTime(points.at(-1)))-new Date(sampleTime(points[0]));
  const timeLabel = value => new Intl.DateTimeFormat("ru-RU", span > 2*86400000 ? {day:"2-digit",month:"2-digit"} : {hour:"2-digit",minute:"2-digit"}).format(new Date(value));
  ctx.textBaseline = "top";
  [[0,points[0]],[.5,points[Math.floor((points.length-1)/2)]],[1,points.at(-1)]].forEach(([fraction,point],index) => {
    const x = margin.left+plotWidth*fraction; ctx.textAlign = index === 0 ? "left" : index === 2 ? "right" : "center";
    ctx.fillStyle = "#8fa9a0"; ctx.fillText(timeLabel(sampleTime(point)),x,height-margin.bottom+7);
  });
  const firstTime = Date.parse(sampleTime(points[0])), lastTime = Date.parse(sampleTime(points.at(-1)));
  const coords = points.map(point => ({x: firstTime === lastTime ? margin.left+plotWidth/2 : margin.left+(Date.parse(sampleTime(point))-firstTime)/(lastTime-firstTime)*plotWidth, y: margin.top+(max+pad-point[metric])/range*plotHeight, item:point}));
  if (canvas === el.detailChart) state.detailPoints = coords;
  if (coords.length > 1) { ctx.beginPath(); ctx.strokeStyle = metricInfo[metric][2]; ctx.lineWidth = 2; coords.forEach((p,i) => i ? ctx.lineTo(p.x,p.y) : ctx.moveTo(p.x,p.y)); ctx.stroke(); }
  ctx.fillStyle = metricInfo[metric][2]; coords.forEach(point => { ctx.beginPath(); ctx.arc(point.x, point.y, 3, 0, Math.PI*2); ctx.fill(); });
}
el.range.addEventListener("change", () => { el.dateControl.hidden = el.range.value !== "day"; loadHistory(); });
el.date.addEventListener("change", loadHistory);
el.compareToggle.addEventListener("click", () => setCompareMode(!state.compareMode));
el.compareClose.addEventListener("click", () => setCompareMode(false));
el.compareMetric.innerHTML = Object.entries(metricInfo).map(([key,[label]]) => `<option value="${key}">${label}</option>`).join("");
el.compareMetric.value = "air_temperature";
el.compareMetric.addEventListener("change", drawComparisonChart);
el.compareRange.addEventListener("change", loadComparisonHistory);
el.historyMetrics.addEventListener("click", event => { const button = event.target.closest("[data-metric]"); if (!button) return; state.metric = button.dataset.metric; renderMetricHistories(); el.detail.scrollIntoView({behavior:"smooth", block:"nearest"}); });
el.detailChart.addEventListener("mousemove", event => {
  if (!state.detailPoints.length) return;
  const box = el.detailChart.getBoundingClientRect(), x = event.clientX - box.left;
  const point = state.detailPoints.reduce((best, current) => Math.abs(current.x-x) < Math.abs(best.x-x) ? current : best);
  const [, unit] = metricInfo[state.metric];
  el.tooltip.hidden = false;
  el.tooltip.innerHTML = `<strong>${show(point.item[state.metric])} ${unit}</strong><span>${formatTime(sampleTime(point.item), true)}</span>`;
});
el.detailChart.addEventListener("mouseleave", () => { el.tooltip.hidden = true; });
window.addEventListener("resize", () => { drawMetricChart(el.detailChart, state.metric); drawComparisonChart(); });

async function refresh() {
  const before = state.devices.find(item => item.device_id === state.selectedId)?.received_at;
  const comparedBefore = state.compareIds.map(id => state.devices.find(item => item.device_id === id)?.received_at);
  await loadDevices();
  const after = state.devices.find(item => item.device_id === state.selectedId)?.received_at;
  if (state.selectedId && before !== after) await loadHistory();
  if (state.compareMode && state.compareIds.length === 2 && state.compareIds.some((id,index) =>
    comparedBefore[index] !== state.devices.find(item => item.device_id === id)?.received_at)) await loadComparisonHistory();
}
el.date.value = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
refresh(); setInterval(refresh, 3000);
