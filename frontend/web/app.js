(() => {
  const grid = document.getElementById('grid');
  const dot = document.getElementById('conn-dot');
  const ctext = document.getElementById('conn-text');
  const ts = document.getElementById('last-update');
  const kpiCrit = document.getElementById('kpi-critical');
  const kpiWarn = document.getElementById('kpi-warning');
  const kpiNorm = document.getElementById('kpi-normal');
  const kpiCount = document.getElementById('kpi-count');

  const socket = io('http://localhost:3000', { path: '/alerts' });

  // Per-sensor chart registry
  const MAX_POINTS = 120; // ~2 minutes history at 1s cadence
  const chartsRoot = document.getElementById('charts');
  /** @type {Record<string, {wrap:HTMLElement, bars:number[], container:HTMLElement}>} */
  const charts = {};

  function status(state) {
    dot.classList.remove('ok', 'warn', 'crit');
    if (state === 'connected') { dot.classList.add('ok'); ctext.textContent = 'Подключено'; }
    else { dot.classList.remove('ok'); ctext.textContent = 'Отключено'; }
  }

  function severityClass(s) {
    if (s === 'critical') return 'crit';
    if (s === 'warning') return 'warn';
    return 'ok';
  }

  const labelsRu = {
    rpm: 'Обороты (об/мин)',
    engine_temp_coolant: 'Температура ОЖ (°C)',
    oil_temp: 'Температура масла (°C)',
    oil_pressure: 'Давление масла (бар)',
    fuel_pressure: 'Давление топлива (бар)',
    fuel_level: 'Уровень топлива (%)',
    fuel_consumption: 'Расход топлива (л/ч)',
    voltage: 'Напряжение (В)',
    current: 'Ток (А)',
    ecu_errors: 'Ошибки ECU',
    fuel_leak: 'Утечка топлива',
    coolant_pressure: 'Давление ОЖ (бар)',
    overheat: 'Перегрев',
    vibration: 'Вибрация (м/с²)',
    emergency_stop: 'Аварийная остановка',
  };

  function render(sensors) {
    ts.textContent = new Date().toLocaleTimeString();
    grid.innerHTML = '';
    let c=0,w=0,n=0;
    (sensors || []).forEach(s => {
      const sev = s.severity || (s.critical ? 'critical' : 'normal');
      const pill = severityClass(sev);
      if (sev === 'critical') c++; else if (sev === 'warning') w++; else n++;
      const div = document.createElement('div');
      div.className = 'card';
      const name = labelsRu[s.id] || labelsRu[s.type] || (s.id || s.type);
      const statusRu = sev === 'critical' ? 'АВАРИЯ' : (sev === 'warning' ? 'ВНИМАНИЕ' : 'НОРМА');
      div.innerHTML = `
        <h3>${name}</h3>
        <div class="kv"><span>Значение</span><span>${s.value ?? '—'} ${s.unit || ''}</span></div>
        <div class="kv"><span>Диапазон</span><span>${s.min ?? '—'} .. ${s.max ?? '—'}</span></div>
        <div class="kv"><span>Вероятность</span><span>${(s.risk_probability ?? '')}</span></div>
        <div class="kv"><span>Статус</span><span class="pill ${pill}">${statusRu}</span></div>
      `;
      grid.appendChild(div);
    });
    kpiCrit.textContent = c; kpiWarn.textContent = w; kpiNorm.textContent = n; kpiCount.textContent = (sensors||[]).length;
  }

  function ensureChart(sensor) {
    const id = sensor.id || sensor.type;
    if (!id) return null;
    if (charts[id]) return charts[id];
    const wrap = document.createElement('div');
    wrap.className = 'card';
    wrap.innerHTML = `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px"><strong>${id}</strong><small>${sensor.unit||''}</small></div><div class="spark"></div>`;
    chartsRoot.appendChild(wrap);
    const container = wrap.querySelector('.spark');
    charts[id] = { wrap, bars: [], container };
    return charts[id];
  }

  function pushHistory(sensors){
    (sensors||[]).forEach(s => {
      if (typeof s.value !== 'number') return;
      const c = ensureChart(s); if (!c) return;
      // Normalize height per sensor range when available; fallback to rolling min/max
      const min = typeof s.min === 'number' ? s.min : undefined;
      const max = typeof s.max === 'number' ? s.max : undefined;
      let lo = min, hi = max;
      if (lo === undefined || hi === undefined) {
        // compute from existing bars values if we stored them; keep simple for perf
        const arr = c.bars;
        if (arr.length) {
          const mn = Math.min(...arr);
          const mx = Math.max(...arr);
          if (lo === undefined) lo = mn;
          if (hi === undefined) hi = mx;
        } else {
          lo = s.value - 1; hi = s.value + 1;
        }
      }
      const span = Math.max(1e-6, (hi - lo));
      const norm = Math.max(0, Math.min(1, (s.value - lo) / span));
      c.bars.push(norm);
      if (c.bars.length > MAX_POINTS) c.bars.shift();
      // render bars
      const frag = document.createDocumentFragment();
      for (let i = 0; i < c.bars.length; i++) {
        const h = Math.max(2, Math.round(58 * c.bars[i]));
        const el = document.createElement('div');
        const sev = (s.severity || (s.critical ? 'critical' : 'normal'));
        el.className = 'bar' + (i === c.bars.length - 1 ? (' last ' + sev.replace('critical','crit').replace('warning','warn').replace('normal','ok')) : '');
        el.style.height = h + 'px';
        frag.appendChild(el);
      }
      c.container.innerHTML = '';
      c.container.appendChild(frag);
    });
  }

  socket.on('connect', () => status('connected'));
  socket.on('disconnect', () => status('disconnected'));
  socket.on('sensors:update', (payload) => {
    try { render(payload); } catch (e) { /* noop */ }
    try { pushHistory(payload); } catch (e) { /* noop */ }
  });
})();


