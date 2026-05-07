/* H3C Monitor — 告警中心 */

document.addEventListener('DOMContentLoaded', loadAlarms);

async function loadAlarms() {
    const status = document.getElementById('alarmStatusFilter')?.value || '';
    const url = status ? `/api/alarms?status=${status}` : '/api/alarms';
    const alarms = await API.get(url) || [];

    const tbody = document.getElementById('alarmsTable');
    if (!alarms.length) {
        tbody.innerHTML = '<tr class="table-empty"><td colspan="7">暂无告警</td></tr>';
        return;
    }

    tbody.innerHTML = alarms.map(a => `
        <tr>
            <td>${Util.escapeHtml(a.device_name || a.device_ip || '-')}</td>
            <td>${a.metric}</td>
            <td><strong>${a.value}</strong></td>
            <td>${a.operator || '>'} ${a.threshold}</td>
            <td>${Util.formatDatetime(a.triggered_at)}</td>
            <td><span class="badge ${a.status === 'active' ? 'badge-danger' : a.status === 'acknowledged' ? 'badge-warning' : 'badge-success'}">${a.status}</span></td>
            <td>
                ${a.status === 'active' ? `<button class="btn btn-sm btn-outline" onclick="ackAlarm(${a.id})">确认</button>` : ''}
            </td>
        </tr>
    `).join('');
}

async function ackAlarm(id) {
    try {
        await API.post(`/api/alarms/${id}/acknowledge`);
        loadAlarms();
    } catch(e) {
        alert('操作失败: ' + e.message);
    }
}
