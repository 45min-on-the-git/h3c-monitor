/* H3C Monitor — 设备台账 */

let _allDevices = [];

document.addEventListener('DOMContentLoaded', loadDeviceList);

/* === Toast === */
function showToast(msg, type) {
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

if (!document.getElementById('toastStyle')) {
    const s = document.createElement('style');
    s.id = 'toastStyle';
    s.textContent = '@keyframes toastIn { from{opacity:0;transform:translateY(-10px)} to{opacity:1;transform:translateY(0)} }';
    document.head.appendChild(s);
}

/* === Load === */
async function loadDeviceList() {
    try {
        _allDevices = await API.get('/api/devices') || [];
    } catch(e) {
        _allDevices = [];
        showToast('加载设备列表失败: ' + e.message, 'error');
    }
    renderDeviceList();
}

function renderDeviceList() {
    const search = (document.getElementById('deviceSearch')?.value || '').toLowerCase();
    const category = document.getElementById('categoryFilter')?.value || '';

    let filtered = _allDevices;
    if (search) {
        filtered = filtered.filter(d =>
            (d.device_name || '').toLowerCase().includes(search) ||
            (d.ip || '').toLowerCase().includes(search) ||
            (d.hostname || '').toLowerCase().includes(search)
        );
    }
    if (category) filtered = filtered.filter(d => d.device_category === category);

    const tbody = document.getElementById('devicesTable');
    if (!filtered.length) {
        tbody.innerHTML = '<tr class="table-empty"><td colspan="8">暂无设备数据</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(d => `
        <tr>
            <td><strong>${Util.escapeHtml(d.device_name || d.hostname || d.ip)}</strong></td>
            <td>${Util.escapeHtml(d.ip)}</td>
            <td><span class="badge ${d.device_category === 'firewall' ? 'badge-danger' : 'badge-info'}">
                ${d.device_category === 'firewall' ? '防火墙' : '交换机'}</span></td>
            <td>${Util.escapeHtml(d.model || '-')}</td>
            <td>${Util.escapeHtml(d.serial_number || '-')}</td>
            <td>${Util.escapeHtml(d.location || '-')}</td>
            <td>${d.warranty_expiry || '-'}</td>
            <td>
                <div class="flex gap-2">
                    <button class="btn btn-sm btn-outline" onclick="editDevice(${d.id})">
                        <i class="bi bi-pencil"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

/* === Form === */
function showDeviceForm() {
    document.getElementById('deviceModalTitle').textContent = '添加设备';
    document.getElementById('deviceForm').reset();
    document.getElementById('deviceFormId').value = '';
    document.getElementById('deviceModal').classList.add('open');
}

function editDevice(id) {
    const d = _allDevices.find(x => x.id === id);
    if (!d) return;

    document.getElementById('deviceModalTitle').textContent = '编辑设备';
    document.getElementById('deviceFormId').value = d.id;
    document.getElementById('deviceFormName').value = d.device_name || '';
    document.getElementById('deviceFormIp').value = d.ip || '';
    document.getElementById('deviceFormCategory').value = d.device_category || 'switch';
    document.getElementById('deviceFormModel').value = d.model || '';
    document.getElementById('deviceFormSn').value = d.serial_number || '';
    document.getElementById('deviceFormAssetNo').value = d.asset_no || '';
    document.getElementById('deviceFormLocation').value = d.location || '';
    document.getElementById('deviceFormRack').value = d.rack || '';
    document.getElementById('deviceFormPurchaseDate').value = d.purchase_date || '';
    document.getElementById('deviceFormWarranty').value = d.warranty_expiry || '';
    document.getElementById('deviceFormSupplier').value = d.supplier || '';
    document.getElementById('deviceFormContract').value = d.contract_no || '';
    document.getElementById('deviceModal').classList.add('open');
}

function closeDeviceForm() {
    document.getElementById('deviceModal').classList.remove('open');
}

document.getElementById('deviceForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('deviceFormId').value;
    const body = {
        device_name: document.getElementById('deviceFormName').value,
        ip: document.getElementById('deviceFormIp').value,
        device_category: document.getElementById('deviceFormCategory').value,
        model: document.getElementById('deviceFormModel').value,
        serial_number: document.getElementById('deviceFormSn').value,
        asset_no: document.getElementById('deviceFormAssetNo').value,
        location: document.getElementById('deviceFormLocation').value,
        rack: document.getElementById('deviceFormRack').value,
        purchase_date: document.getElementById('deviceFormPurchaseDate').value,
        warranty_expiry: document.getElementById('deviceFormWarranty').value,
        supplier: document.getElementById('deviceFormSupplier').value,
        contract_no: document.getElementById('deviceFormContract').value,
    };

    const opLabel = id ? '更新' : '添加';
    const btn = document.querySelector('#deviceForm button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '保存中...';

    try {
        let resp;
        if (id) {
            resp = await fetch(`/api/devices/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
        } else {
            resp = await fetch('/api/devices', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
        }

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `${opLabel}失败 (${resp.status})`);
        }

        showToast(`设备 ${opLabel}成功`, 'success');
        closeDeviceForm();
        await loadDeviceList();
    } catch (err) {
        showToast(`${opLabel}失败: ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '保存';
    }
});
