/* H3C Monitor — 配置备份 */

let _devices = [];
let _selectedDeviceId = null;

document.addEventListener('DOMContentLoaded', async () => {
    _devices = await API.get('/api/devices') || [];
    const sel = document.getElementById('deviceSelect');
    _devices.forEach(d => {
        const name = d.device_name || d.hostname || d.ip;
        sel.innerHTML += `<option value="${d.id}">${Util.escapeHtml(name)} (${d.ip})</option>`;
    });
});

function onDeviceChange() {
    _selectedDeviceId = parseInt(document.getElementById('deviceSelect').value);
    document.getElementById('btnBackup').disabled = !_selectedDeviceId;
    document.getElementById('backupCard').style.display = _selectedDeviceId ? '' : 'none';
    if (_selectedDeviceId) loadBackups();
}

async function loadBackups() {
    const tbody = document.getElementById('backupTable');
    tbody.innerHTML = Util.skeleton(3, 3);
    try {
        const list = await API.get(`/api/config-backups/${_selectedDeviceId}`) || [];
        document.getElementById('backupCount').textContent = `${list.length} 条记录`;
        if (!list.length) { tbody.innerHTML = '<tr class="table-empty"><td colspan="3">暂无备份</td></tr>'; return; }
        tbody.innerHTML = list.map(b => `
            <tr>
                <td>${Util.formatDatetime(b.backup_time)}</td>
                <td><code style="font-size:11px">${b.config_hash || '-'}</code></td>
                <td><button class="btn btn-sm btn-outline" onclick="viewConfig(${b.id})"><i class="bi bi-eye"></i> 查看</button></td>
            </tr>
        `).join('');
    } catch(e) { tbody.innerHTML = '<tr class="table-empty"><td colspan="3">加载失败</td></tr>'; }
}

async function doBackup() {
    const btn = document.getElementById('btnBackup');
    btn.disabled = true; btn.textContent = '备份中...';
    try {
        const r = await API.post(`/api/config-backups/${_selectedDeviceId}/backup`);
        if (r.success) { await loadBackups(); alert('备份成功'); }
    } catch(e) { alert('备份失败: ' + e.message); }
    btn.disabled = false; btn.innerHTML = '<i class="bi bi-cloud-upload"></i> 立即备份';
}

async function viewConfig(id) {
    try {
        const r = await API.get(`/api/config-backups/${_selectedDeviceId}/${id}`);
        document.getElementById('configContent').textContent = r.config_text || '';
        document.getElementById('configModalTitle').textContent = `配置备份 #${id} — ${Util.formatDatetime(r.backup_time)}`;
        document.getElementById('configModal').classList.add('open');
    } catch(e) { alert('加载失败: ' + e.message); }
}
