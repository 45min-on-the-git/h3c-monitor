/* H3C Monitor — 监控总览 */

let _devices = [];
let _metrics = [];
let _interfaces = [];
let _chart = null;
let _trafficChart = null;

document.addEventListener('DOMContentLoaded', async () => {
    await loadDevices();
    await loadAllCards();
    await loadAllInterfaces();

    const now = new Date();
    const ago = new Date(now.getTime() - 5 * 60 * 60 * 1000);
    document.getElementById('endTime').value = toDatetimeLocal(now);
    document.getElementById('startTime').value = toDatetimeLocal(ago);
});

function toDatetimeLocal(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${y}-${m}-${day}T${hh}:${mm}`;
}

/* === 设备列表 === */
async function loadDevices() {
    _devices = await API.get('/api/devices') || [];
    const sel = document.getElementById('deviceSelect');
    sel.innerHTML = '<option value="">全部设备</option>';
    _devices.forEach(d => {
        const name = d.device_name || d.hostname || d.ip;
        const cat = d.device_category === 'firewall' ? '防火墙' : '交换机';
        sel.innerHTML += `<option value="${d.id}">${Util.escapeHtml(name)} (${d.ip}) — ${cat}</option>`;
    });
}

/* === 设备卡片 === */
async function loadAllCards() {
    const container = document.getElementById('devicesContainer');
    container.innerHTML = '<div class="col-12 text-center text-muted" style="padding:40px">加载中...</div>';

    const cards = [];
    for (const d of _devices) {
        try {
            const m = await API.get(`/api/metrics/latest/${d.id}`);
            if (m) cards.push({ device: d, metric: m });
        } catch (e) { /* skip */ }
    }

    if (cards.length === 0) {
        container.innerHTML = '<div class="col-12 text-center text-muted" style="padding:40px">暂无设备数据</div>';
        return;
    }

    container.innerHTML = '';
    cards.forEach(({ device, metric }) => {
        const col = document.createElement('div');
        col.className = 'col-md-6 col-lg-3 mb-3';
        col.innerHTML = `
            <div class="card" style="margin-bottom:0;height:100%">
                <div class="card-body">
                    <div class="flex-between mb-2">
                        <strong style="font-size:14px">${Util.escapeHtml(device.device_name || device.hostname || device.ip)}</strong>
                        <span class="badge ${device.device_category === 'firewall' ? 'badge-danger' : 'badge-info'}">
                            ${device.device_category === 'firewall' ? '防火墙' : '交换机'}
                        </span>
                    </div>
                    <div class="text-muted mb-2" style="font-size:12px">${Util.escapeHtml(device.ip)}</div>
                    <div class="flex-between">
                        <div><div class="form-label mb-0">CPU</div>
                            <strong style="font-size:18px;${metric.cpu_usage > 80 ? 'color:var(--danger)' : ''}">
                                ${metric.cpu_usage !== null ? metric.cpu_usage.toFixed(1) + '%' : '-'}
                            </strong></div>
                        <div><div class="form-label mb-0">内存</div>
                            <strong style="font-size:18px;${metric.mem_usage > 80 ? 'color:var(--danger)' : ''}">
                                ${metric.mem_usage !== null ? metric.mem_usage.toFixed(1) + '%' : '-'}
                            </strong></div>
                    </div>
                    <div class="text-muted mt-2" style="font-size:11px">${Util.formatDatetime(metric.collect_time)}</div>
                </div>
            </div>`;
        container.appendChild(col);
    });
}

/* === 设备选择 === */
async function onDeviceChanged() {
    const id = document.getElementById('deviceSelect').value;
    if (!id) {
        showChartPlaceholder(true);
        await loadAllCards();
        await loadAllInterfaces();
        return;
    }
    await loadDeviceDetail(id);
    await loadMetrics(id);
}

function showChartPlaceholder(show) {
    document.getElementById('chartPlaceholder').style.display = show ? 'block' : 'none';
    document.getElementById('metricsChart').style.display = show ? 'none' : 'block';
}

async function onTimeRangeChanged() {
    const id = document.getElementById('deviceSelect').value;
    if (!id) return;
    await loadMetrics(id);
}

/* === 设备详情 === */
async function loadDeviceDetail(deviceId) {
    const device = _devices.find(d => d.id == deviceId);
    if (!device) return;
    try {
        const [m, ifs] = await Promise.all([
            API.get(`/api/metrics/latest/${deviceId}`),
            API.get(`/api/interfaces/${deviceId}`)
        ]);
        _interfaces = ifs || [];
        renderInterfaces();
        const container = document.getElementById('devicesContainer');
        container.innerHTML = `<div class="col-12"><div class="card"><div class="card-body">
            <div class="flex-between mb-3"><div>
                <h5 style="margin:0">${Util.escapeHtml(device.device_name || device.hostname || device.ip)}</h5>
                <div class="text-muted" style="font-size:12px">${Util.escapeHtml(device.ip)}</div>
                <span class="badge ${device.device_category === 'firewall' ? 'badge-danger' : 'badge-info'} mt-2">
                    ${device.device_category === 'firewall' ? '防火墙' : '交换机'}</span>
            </div>
            <div class="text-end text-muted" style="font-size:12px">
                <div>型号：${device.model || '-'}</div><div>版本：${device.sw_version || '-'}</div>
            </div></div>
            <div class="row text-center">
                <div class="col-3"><div class="form-label">CPU</div>
                    <strong style="font-size:24px;${m.cpu_usage > 80 ? 'color:var(--danger)' : ''}">${m.cpu_usage !== null ? m.cpu_usage.toFixed(1) + '%' : '-'}</strong></div>
                <div class="col-3"><div class="form-label">内存</div>
                    <strong style="font-size:24px;${m.mem_usage > 80 ? 'color:var(--danger)' : ''}">${m.mem_usage !== null ? m.mem_usage.toFixed(1) + '%' : '-'}</strong></div>
                <div class="col-3"><div class="form-label">温度</div>
                    <strong style="font-size:24px">${m.temperature !== null ? m.temperature.toFixed(1) + '°C' : '-'}</strong></div>
                <div class="col-3"><div class="form-label">会话数</div>
                    <strong style="font-size:24px">${m.session_count !== null ? m.session_count : '-'}</strong></div>
            </div><hr>
            <div class="text-muted" style="font-size:11px">运行时间：${m.uptime || '-'}</div>
            <div class="text-muted mt-1" style="font-size:11px">更新时间：${Util.formatDatetime(m.collect_time)}</div>
        </div></div></div>`;
    } catch (e) { /* skip */ }
}

/* === 指标图表 === */
async function loadMetrics(deviceId) {
    document.getElementById('chartPlaceholder').textContent = '加载中...';
    showChartPlaceholder(true);
    const start = document.getElementById('startTime').value;
    const end = document.getElementById('endTime').value;
    let url = `/api/metrics?device_id=${deviceId}`;
    if (start) url += `&start_time=${start.replace('T', ' ')}`;
    if (end) url += `&end_time=${end.replace('T', ' ')}`;
    _metrics = await API.get(url) || [];
    renderChart();
}

function renderChart() {
    if (!_metrics.length) {
        document.getElementById('chartPlaceholder').textContent = '该时间范围内暂无数据';
        showChartPlaceholder(true);
        return;
    }
    showChartPlaceholder(false);
    const showCpu = document.getElementById('showCpu').checked;
    const showMem = document.getElementById('showMem').checked;
    const showTemp = document.getElementById('showTemp').checked;
    const sorted = [..._metrics].sort((a, b) => new Date(a.collect_time) - new Date(b.collect_time));
    const labels = sorted.map(m => {
        const d = new Date(m.collect_time);
        return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`;
    });
    const datasets = [];
    if (showCpu) datasets.push({ label: 'CPU %', data: sorted.map(m => m.cpu_usage), borderColor: '#ff6b6b', backgroundColor: 'rgba(255,107,107,0.08)', tension: 0.3, fill: true, pointRadius: 2 });
    if (showMem) datasets.push({ label: '内存 %', data: sorted.map(m => m.mem_usage), borderColor: '#4dabf7', backgroundColor: 'rgba(77,171,247,0.08)', tension: 0.3, fill: true, pointRadius: 2 });
    if (showTemp) datasets.push({ label: '温度 °C', data: sorted.map(m => m.temperature), borderColor: '#ffd43b', backgroundColor: 'rgba(255,212,59,0.08)', tension: 0.3, fill: true, pointRadius: 2, yAxisID: 'y_temp' });

    if (_chart) _chart.destroy();
    _chart = new Chart(document.getElementById('metricsChart').getContext('2d'), {
        type: 'line', data: { labels, datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            scales: {
                x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } },
                y: { type: 'linear', position: 'left', min: 0, max: 100, title: { display: true, text: '%' } },
                y_temp: { type: 'linear', position: 'right', min: 0, title: { display: showTemp, text: '°C' }, grid: { drawOnChartArea: false } }
            }
        }
    });
}

/* === 接口列表 === */
async function loadAllInterfaces() {
    _interfaces = [];
    for (const d of _devices) {
        try {
            const ifs = await API.get(`/api/interfaces/${d.id}`);
            if (ifs) _interfaces.push(...ifs.map(i => ({ ...i, _device_ip: d.ip, _device_id: d.id })));
        } catch (e) { /* skip */ }
    }
    renderInterfaces();
}

function renderInterfaces() {
    const tbody = document.getElementById('interfacesTable');
    const search = (document.getElementById('interfaceSearch')?.value || '').toLowerCase();
    const statusFilter = document.getElementById('interfaceStatusFilter')?.value || '';

    let filtered = _interfaces;
    if (search) filtered = filtered.filter(i => (i.if_name || '').toLowerCase().includes(search));
    if (statusFilter) filtered = filtered.filter(i => i.status === statusFilter);

    if (!filtered.length) {
        tbody.innerHTML = '<tr class="table-empty"><td colspan="6">暂无接口数据</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(i => {
        const util = i.in_util || 0;
        const utilColor = util > 80 ? 'var(--danger)' : util > 50 ? 'var(--warning)' : 'var(--success)';
        return `<tr style="cursor:pointer" onclick="showTrafficChart(${i._device_id}, '${Util.escapeHtml(i.if_name)}')">
            <td><strong>${Util.escapeHtml(i.if_name)}</strong></td>
            <td><span class="text-muted" style="font-size:12px">${Util.escapeHtml(i._device_ip || '')}</span></td>
            <td><span class="badge ${i.status === 'UP' ? 'badge-success' : 'badge-danger'}">${i.status}</span></td>
            <td>${Util.formatBytes(i.in_bytes)}</td>
            <td>${Util.formatBytes(i.out_bytes)}</td>
            <td><span style="color:${utilColor};font-weight:600">${util.toFixed(1)}%</span></td>
        </tr>`;
    }).join('');
}

/* === 接口流量图 === */
async function showTrafficChart(deviceId, ifName) {
    document.getElementById('trafficIfName').textContent = ifName;
    document.getElementById('trafficChartCard').style.display = '';

    const data = await API.get(`/api/interfaces/${deviceId}/traffic?if_name=${encodeURIComponent(ifName)}&hours=24`);
    if (!data || data.length < 2) {
        // fallback
        return;
    }

    const labels = data.map(d => {
        const dt = new Date(d.collect_time);
        return `${dt.getMonth()+1}/${dt.getDate()} ${dt.getHours()}:${String(dt.getMinutes()).padStart(2,'0')}`;
    });

    if (_trafficChart) _trafficChart.destroy();
    _trafficChart = new Chart(document.getElementById('trafficChart').getContext('2d'), {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'In (bps)', data: data.map(d => d.in_bps),
                    borderColor: '#51cf66', backgroundColor: 'rgba(81,207,102,0.08)',
                    tension: 0.3, fill: true, pointRadius: 1,
                },
                {
                    label: 'Out (bps)', data: data.map(d => d.out_bps),
                    borderColor: '#4dabf7', backgroundColor: 'rgba(77,171,247,0.08)',
                    tension: 0.3, fill: true, pointRadius: 1,
                },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            scales: {
                x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } },
                y: {
                    title: { display: true, text: 'bps' },
                    ticks: { callback: v => Util.formatBps(v) }
                }
            }
        }
    });

    document.getElementById('trafficChartCard').scrollIntoView({ behavior: 'smooth' });
}

function hideTrafficChart() {
    document.getElementById('trafficChartCard').style.display = 'none';
    if (_trafficChart) { _trafficChart.destroy(); _trafficChart = null; }
}

/* === 刷新 === */
async function refreshData() {
    const id = document.getElementById('deviceSelect').value;
    if (!id) {
        await loadAllCards();
        await loadAllInterfaces();
    } else {
        await loadDeviceDetail(id);
        await loadMetrics(id);
    }
}
