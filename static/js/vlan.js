/* H3C Monitor — VLAN 划分 */

let _devices = [], _selectedId = null, _vlans = [];

document.addEventListener('DOMContentLoaded', async () => {
    _devices = await API.get('/api/devices') || [];
    const sel = document.getElementById('deviceSelect');
    _devices.forEach(d => {
        const n = d.device_name || d.hostname || d.ip;
        sel.innerHTML += `<option value="${d.id}">${Util.escapeHtml(n)} (${d.ip})</option>`;
    });
});

/* === Toast === */
function toast(msg, type) {
    const t = document.createElement('div');
    t.style.cssText = [
        'position:fixed;top:60px;right:20px;z-index:9999;padding:12px 20px',
        'border-radius:6px;font-size:13px;font-weight:500;color:#fff',
        'animation:toastIn 0.3s ease;max-width:360px;box-shadow:0 4px 12px rgba(0,0,0,0.3)',
        type === 'success' ? 'background:#2b8a3e' : 'background:#c92a2a',
    ].join(';');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; }, 2500);
    setTimeout(() => t.remove(), 3000);
}
if (!document.getElementById('toastAnim')) {
    const s = document.createElement('style'); s.id = 'toastAnim';
    s.textContent = '@keyframes toastIn { from{opacity:0;transform:translateY(-10px)} to{opacity:1;transform:translateY(0)} }';
    document.head.appendChild(s);
}

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
        if (!_vlans.length) {
            tbody.innerHTML = '<tr class="table-empty"><td colspan="4">暂无 VLAN（设备可能不支持 NETCONF，确保 SSH 可达）</td></tr>';
            return;
        }
        tbody.innerHTML = _vlans.map(v => `<tr>
            <td><span class="badge badge-info">${v.vlan_id}</span></td>
            <td>${Util.escapeHtml(v.name || '-')}</td>
            <td>${Util.escapeHtml(v.description || '-')}</td>
            <td><button class="btn btn-sm btn-outline" style="color:var(--danger)" onclick="deleteVlan(${v.vlan_id})"><i class="bi bi-trash"></i> 删除</button></td>
        </tr>`).join('');
    } catch(e) {
        tbody.innerHTML = `<tr class="table-empty"><td colspan="4">读取失败: ${Util.escapeHtml(e.message)}</td></tr>`;
    }
}

function showVlanForm() { document.getElementById('vlanModal').classList.add('open'); }
function closeVlanForm() { document.getElementById('vlanModal').classList.remove('open'); }

document.getElementById('vlanForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const vlanId = parseInt(document.getElementById('vlanId').value);
    const body = {
        vlan_id: vlanId,
        name: document.getElementById('vlanName').value,
        description: document.getElementById('vlanDesc').value,
    };
    const btn = document.querySelector('#vlanForm button[type="submit"]');
    btn.disabled = true; btn.textContent = '下发中...';
    try {
        const resp = await fetch(`/api/vlans/${_selectedId}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
        if (!resp.ok) throw new Error((await resp.json().catch(()=>({}))).detail || '创建失败');
        toast(`VLAN ${vlanId} 创建成功`, 'success');
        closeVlanForm();
        document.getElementById('vlanForm').reset();
        await loadVlans();
    } catch (err) {
        toast('创建失败: ' + err.message, 'error');
    }
    btn.disabled = false; btn.textContent = '创建';
});

async function deleteVlan(vlanId) {
    if (!confirm(`确认删除 VLAN ${vlanId}？设备上的 VLAN 及其中端口配置将被清除。`)) return;
    try {
        const resp = await fetch(`/api/vlans/${_selectedId}/${vlanId}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error((await resp.json().catch(()=>({}))).detail || '删除失败');
        toast(`VLAN ${vlanId} 已删除`, 'success');
        await loadVlans();
    } catch (err) {
        toast('删除失败: ' + err.message, 'error');
    }
}
