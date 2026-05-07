/* H3C Monitor — IPAM */

let _subnets = [];
let _selectedSubnetId = null;
let _allocations = [];

document.addEventListener('DOMContentLoaded', loadSubnets);

/* === Subnets === */
async function loadSubnets() {
    _subnets = await API.get('/api/ipam/subnets') || [];
    renderSubnets();
}

function renderSubnets() {
    const el = document.getElementById('subnetList');
    if (!_subnets.length) {
        el.innerHTML = '<div class="text-center text-muted" style="padding:20px">暂无子网</div>';
        return;
    }
    el.innerHTML = _subnets.map(s => `
        <div onclick="selectSubnet(${s.id})"
             style="padding:10px 12px;border-bottom:1px solid var(--border-color);cursor:pointer;
                    ${_selectedSubnetId === s.id ? 'background:rgba(77,171,247,0.08);border-left:3px solid var(--accent)' : 'border-left:3px solid transparent'}">
            <strong>${Util.escapeHtml(s.name)}</strong>
            <div style="font-size:11px;color:var(--text-secondary)">${s.network}/${s.cidr}</div>
        </div>
    `).join('');
}

async function selectSubnet(id) {
    _selectedSubnetId = id;
    const s = _subnets.find(x => x.id === id);
    document.getElementById('ipamSubnetName').textContent = s ? `${s.network}/${s.cidr}` : '-';

    // Load usage
    try {
        const u = await API.get(`/api/ipam/subnets/${id}/usage`);
        document.getElementById('ipamUsage').textContent = `已用 ${u.used}/${u.total} (${u.utilization}%)`;
    } catch(e) { }

    _allocations = await API.get(`/api/ipam/subnets/${id}/allocations`) || [];
    renderIps();
    renderSubnets();
}

function renderIps() {
    const search = (document.getElementById('ipamSearch')?.value || '').toLowerCase();
    const tbody = document.getElementById('ipamTable');

    let filtered = _allocations;
    if (search) filtered = filtered.filter(a => (a.ip_address || '').toLowerCase().includes(search));

    if (!filtered.length) {
        tbody.innerHTML = '<tr class="table-empty"><td colspan="4">暂无分配记录</td></tr>';
        return;
    }
    tbody.innerHTML = filtered.map(a => {
        const statusBadge = {
            'used': 'badge-success', 'reserved': 'badge-warning', 'free': 'badge-secondary'
        }[a.status] || 'badge-secondary';
        return `<tr>
            <td><code>${Util.escapeHtml(a.ip_address)}</code></td>
            <td>${Util.escapeHtml(a.device_name || '-')}</td>
            <td><span class="badge ${statusBadge}">${a.status}</span></td>
            <td>
                <button class="btn btn-sm btn-outline" onclick="editIp('${a.ip_address}','${a.status}','${Util.escapeHtml(a.device_name||'')}','${Util.escapeHtml(a.interface_name||'')}')">
                    <i class="bi bi-pencil"></i>
                </button>
            </td>
        </tr>`;
    }).join('');
}

function editIp(ip, status, dev, iface) {
    const newStatus = status === 'used' ? 'free' : 'used';
    const devName = prompt('设备名称:', dev) || '';
    database.ipam_set_allocation(_selectedSubnetId, ip, newStatus, devName, iface);
    // Use API
    fetch(`/api/ipam/subnets/${_selectedSubnetId}/allocations`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ip_address: ip, status: newStatus, device_name: devName, interface_name: iface}),
    }).then(r => r.json()).then(() => selectSubnet(_selectedSubnetId));
}

/* === Subnet form === */
function showSubnetForm() {
    document.getElementById('subnetModal').classList.add('open');
}
function closeSubnetForm() {
    document.getElementById('subnetModal').classList.remove('open');
}
document.getElementById('subnetForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = {
        name: document.getElementById('subnetName').value,
        network: document.getElementById('subnetNetwork').value,
        cidr: parseInt(document.getElementById('subnetCidr').value),
        gateway: document.getElementById('subnetGateway').value,
        vlan_id: document.getElementById('subnetVlan').value ? parseInt(document.getElementById('subnetVlan').value) : null,
    };
    try {
        await API.post('/api/ipam/subnets', body);
        closeSubnetForm();
        document.getElementById('subnetForm').reset();
        document.getElementById('subnetCidr').value = '24';
        await loadSubnets();
    } catch(e) {
        alert('创建失败: ' + e.message);
    }
});
