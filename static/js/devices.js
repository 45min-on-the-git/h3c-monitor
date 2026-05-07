/* H3C Monitor — 设备台账 */

let _allDevices = [];

document.addEventListener('DOMContentLoaded', loadDeviceList);

async function loadDeviceList() {
    _allDevices = await API.get('/api/devices') || [];
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

/* === 设备编辑 === */
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

    try {
        if (id) {
            await API.put(`/api/devices/${id}`, body);
        } else {
            await API.post('/api/devices', body);
        }
        closeDeviceForm();
        await loadDeviceList();
    } catch (err) {
        alert('保存失败: ' + err.message);
    }
});
