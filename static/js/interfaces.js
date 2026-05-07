/* H3C Monitor — 端口管理 */

let _devices = [], _ifaces = [], _selectedId = null;

document.addEventListener('DOMContentLoaded', async () => {
    _devices = await API.get('/api/devices') || [];
    const sel = document.getElementById('deviceSelect');
    _devices.forEach(d => {
        const name = d.device_name || d.hostname || d.ip;
        sel.innerHTML += `<option value="${d.id}">${Util.escapeHtml(name)} (${d.ip})</option>`;
    });
});

async function onDeviceChange() {
    _selectedId = parseInt(document.getElementById('deviceSelect').value);
    document.getElementById('ifCard').style.display = _selectedId ? '' : 'none';
    if (!_selectedId) return;
    _ifaces = await API.get(`/api/interfaces/${_selectedId}`) || [];
    renderIfTable();
}

function renderIfTable() {
    const search = (document.getElementById('ifSearch')?.value || '').toLowerCase();
    const tbody = document.getElementById('ifTable');
    let f = _ifaces;
    if (search) f = f.filter(i => (i.if_name || '').toLowerCase().includes(search));
    if (!f.length) { tbody.innerHTML = '<tr class="table-empty"><td colspan="5">暂无接口</td></tr>'; return; }
    tbody.innerHTML = f.map(i => {
        const actionBtns = i.status === 'UP'
            ? `<button class="btn btn-sm btn-outline" style="color:var(--danger)" onclick="doShutdown('${Util.escapeHtml(i.if_name)}')" title="Shutdown"><i class="bi bi-power"></i></button>`
            : `<button class="btn btn-sm btn-outline" style="color:var(--success)" onclick="doUndoShutdown('${Util.escapeHtml(i.if_name)}')" title="Undo Shutdown"><i class="bi bi-power"></i></button>`;
        return `<tr>
            <td><strong>${Util.escapeHtml(i.if_name)}</strong></td>
            <td><span class="badge ${i.status==='UP'?'badge-success':'badge-danger'}">${i.status}</span></td>
            <td><span class="text-muted">${Util.escapeHtml(i.description||'-')}</span></td>
            <td style="font-size:12px">${Util.formatBytes(i.in_bytes)} / ${Util.formatBytes(i.out_bytes)}</td>
            <td><div class="flex gap-2">
                ${actionBtns}
                <button class="btn btn-sm btn-outline" onclick="showDescForm('${Util.escapeHtml(i.if_name)}','${Util.escapeHtml(i.description||'')}')" title="修改描述"><i class="bi bi-pencil"></i></button>
                <button class="btn btn-sm btn-outline" onclick="showVlanForm('${Util.escapeHtml(i.if_name)}')" title="VLAN 配置"><i class="bi bi-diagram-3"></i></button>
            </div></td>
        </tr>`;
    }).join('');
}

/* Shutdown / Undo */
async function doAction(ifName, action) {
    try { await API.post(`/api/interfaces/${_selectedId}/${encodeURIComponent(ifName)}/${action}`); onDeviceChange(); }
    catch(e) { alert('操作失败: '+e.message); }
}
async function doShutdown(n) { await doAction(n, 'shutdown'); }
async function doUndoShutdown(n) { await doAction(n, 'undo-shutdown'); }

/* Description */
function showDescForm(ifName, desc) {
    document.getElementById('descIfName').textContent = ifName;
    document.getElementById('descIfHidden').value = ifName;
    document.getElementById('descInput').value = desc;
    document.getElementById('descModal').classList.add('open');
}
function closeDescForm() { document.getElementById('descModal').classList.remove('open'); }
document.getElementById('descForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const ifName = document.getElementById('descIfHidden').value;
    const desc = document.getElementById('descInput').value;
    try {
        await fetch(`/api/interfaces/${_selectedId}/${encodeURIComponent(ifName)}/description`, {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({description: desc}),
        }).then(r => r.ok ? r.json() : Promise.reject(new Error('Failed')));
        closeDescForm(); onDeviceChange();
    } catch(err) { alert('修改失败'); }
});

/* VLAN */
function showVlanForm(ifName) {
    document.getElementById('vlanIfName').textContent = ifName;
    document.getElementById('vlanIfHidden').value = ifName;
    document.getElementById('vlanModal').classList.add('open');
    toggleVlanMode();
}
function closeVlanForm() { document.getElementById('vlanModal').classList.remove('open'); }
function toggleVlanMode() {
    const m = document.getElementById('vlanMode').value;
    document.getElementById('vlanAccessGroup').style.display = m === 'access' ? '' : 'none';
    document.getElementById('vlanTrunkGroup').style.display = m === 'trunk' ? '' : 'none';
}
document.getElementById('vlanForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const ifName = document.getElementById('vlanIfHidden').value;
    const mode = document.getElementById('vlanMode').value;
    const body = { mode };
    if (mode === 'access') { body.vlan_id = parseInt(document.getElementById('vlanAccessId').value); }
    else { body.pvid = parseInt(document.getElementById('vlanPvid').value); body.vlan_list = document.getElementById('vlanList').value || 'all'; }
    try {
        await fetch(`/api/interfaces/${_selectedId}/${encodeURIComponent(ifName)}/vlan`, {
            method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body),
        }).then(r => r.ok ? r.json() : Promise.reject(new Error('Failed')));
        closeVlanForm();
    } catch(err) { alert('下发失败'); }
});
