/* H3C Monitor — VLAN 管理 */

let _devices = [], _selectedId = null, _vlans = [];

document.addEventListener('DOMContentLoaded', async () => {
    _devices = await API.get('/api/devices') || [];
    const sel = document.getElementById('deviceSelect');
    _devices.forEach(d => {
        const n = d.device_name || d.hostname || d.ip;
        sel.innerHTML += `<option value="${d.id}">${Util.escapeHtml(n)} (${d.ip})</option>`;
    });
});

async function onDeviceChange() {
    _selectedId = parseInt(document.getElementById('deviceSelect').value);
    document.getElementById('btnNew').disabled = !_selectedId;
    document.getElementById('btnRefresh').disabled = !_selectedId;
    document.getElementById('vlanCard').style.display = _selectedId ? '' : 'none';
    if (_selectedId) await loadVlans();
}

async function loadVlans() {
    const tbody = document.getElementById('vlanTable');
    tbody.innerHTML = Util.skeleton(4, 3);
    try {
        const resp = await fetch(`/api/vlans/${_selectedId}`);
        if (!resp.ok) throw new Error((await resp.json().catch(()=>({}))).detail || '读取失败');
        _vlans = await resp.json() || [];
        document.getElementById('vlanCount').textContent = `${_vlans.length} 个 VLAN`;
        if (!_vlans.length) { tbody.innerHTML = '<tr class="table-empty"><td colspan="4">暂无 VLAN</td></tr>'; return; }
        tbody.innerHTML = _vlans.map(v => `<tr>
            <td><span class="badge badge-info">${v.vlan_id}</span></td>
            <td>${Util.escapeHtml(v.name || '-')}</td>
            <td>${Util.escapeHtml(v.description || '-')}</td>
            <td><button class="btn btn-sm btn-outline" style="color:var(--danger)" onclick="deleteVlan(${v.vlan_id})"><i class="bi bi-trash"></i> 删除</button></td>
        </tr>`).join('');
    } catch(e) {
        tbody.innerHTML = `<tr class="table-empty"><td colspan="4">${Util.escapeHtml(e.message)}</td></tr>`;
    }
}

function showVlanForm() { document.getElementById('vlanModal').classList.add('open'); }
function closeVlanForm() { document.getElementById('vlanModal').classList.remove('open'); }

document.getElementById('vlanForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = {
        vlan_id: parseInt(document.getElementById('vlanId').value),
        name: document.getElementById('vlanName').value,
        description: document.getElementById('vlanDesc').value,
    };
    const btn = document.querySelector('#vlanForm button[type="submit"]');
    btn.disabled = true; btn.textContent = '下发中...';
    try {
        const resp = await fetch(`/api/vlans/${_selectedId}`, {
            method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body),
        });
        if (!resp.ok) throw new Error((await resp.json().catch(()=>({}))).detail || '创建失败');
        closeVlanForm();
        document.getElementById('vlanForm').reset();
        await loadVlans();
    } catch(err) { alert('创建失败: ' + err.message); }
    btn.disabled = false; btn.textContent = '创建';
});

async function deleteVlan(vlanId) {
    if (!confirm(`确认删除 VLAN ${vlanId}？此操作将永久删除设备上的 VLAN。`)) return;
    try {
        const resp = await fetch(`/api/vlans/${_selectedId}/${vlanId}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error((await resp.json().catch(()=>({}))).detail || '删除失败');
        await loadVlans();
    } catch(err) { alert('删除失败: ' + err.message); }
}
