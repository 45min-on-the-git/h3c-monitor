/* H3C Monitor — ACL 管理 */

let _devices = [];
let _selectedDeviceId = null;
let _acls = [];

document.addEventListener('DOMContentLoaded', async () => {
    _devices = await API.get('/api/devices') || [];
    const sel = document.getElementById('deviceSelect');
    _devices.forEach(d => {
        const name = d.device_name || d.hostname || d.ip;
        sel.innerHTML += `<option value="${d.id}">${Util.escapeHtml(name)} (${d.ip})</option>`;
    });
});

async function onDeviceChange() {
    _selectedDeviceId = parseInt(document.getElementById('deviceSelect').value);
    if (!_selectedDeviceId) {
        document.getElementById('aclListCard').style.display = 'none';
        document.getElementById('btnNewAcl').disabled = true;
        document.getElementById('btnRefresh').disabled = true;
        return;
    }
    document.getElementById('btnNewAcl').disabled = false;
    document.getElementById('btnRefresh').disabled = false;
    await loadAcls();
}

async function loadAcls() {
    document.getElementById('aclListCard').style.display = '';
    const tbody = document.getElementById('aclTable');
    tbody.innerHTML = Util.skeleton(7, 3);

    try {
        _acls = await API.get(`/api/acl/${_selectedDeviceId}`) || [];
        renderAcls();
    } catch(e) {
        tbody.innerHTML = `<tr class="table-empty"><td colspan="7">加载失败: ${e.message}</td></tr>`;
    }
}

function renderAcls() {
    const tbody = document.getElementById('aclTable');
    document.getElementById('aclCount').textContent = `${_acls.length} 条规则`;

    if (!_acls.length) {
        tbody.innerHTML = '<tr class="table-empty"><td colspan="7">暂无 ACL 规则（设备无 ACL 或 SSH 不可达）</td></tr>';
        return;
    }

    tbody.innerHTML = _acls.map(a => `
        <tr>
            <td><span class="badge badge-info">${a.acl_number}</span></td>
            <td>${a.rule_id}</td>
            <td><span class="badge ${a.action === 'permit' ? 'badge-success' : 'badge-danger'}">${a.action}</span></td>
            <td>${a.protocol || 'ip'}</td>
            <td>${a.source || 'any'}</td>
            <td>${a.destination || 'any'}</td>
            <td>
                <div class="flex gap-2">
                    <button class="btn btn-sm btn-outline" onclick="editAcl('${a.acl_number}', '${a.rule_id}', '${a.action}', '${a.protocol || 'ip'}', '${a.source || 'any'}', '${a.destination || 'any'}')">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline" onclick="deleteAcl('${a.acl_number}', '${a.rule_id}')" style="color:var(--danger)">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

function showNewAclForm() {
    document.getElementById('aclFormTitle').textContent = '新建 ACL 规则';
    document.getElementById('aclForm').reset();
    document.getElementById('aclFormId').value = '';
    document.getElementById('aclFormModal').classList.add('open');
}

function editAcl(num, rid, action, proto, src, dst) {
    document.getElementById('aclFormTitle').textContent = '编辑 ACL 规则';
    document.getElementById('aclFormId').value = num + ':' + rid;
    document.getElementById('aclNumber').value = num;
    document.getElementById('aclRuleId').value = rid;
    document.getElementById('aclAction').value = action;
    document.getElementById('aclProtocol').value = proto;
    document.getElementById('aclSrc').value = src === 'any' ? '' : src;
    document.getElementById('aclDst').value = dst === 'any' ? '' : dst;
    document.getElementById('aclFormModal').classList.add('open');
}

function closeAclForm() {
    document.getElementById('aclFormModal').classList.remove('open');
}

document.getElementById('aclForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = {
        device_id: _selectedDeviceId,
        acl_number: parseInt(document.getElementById('aclNumber').value),
        rule_id: parseInt(document.getElementById('aclRuleId').value),
        action: document.getElementById('aclAction').value,
        protocol: document.getElementById('aclProtocol').value,
        source: document.getElementById('aclSrc').value || 'any',
        destination: document.getElementById('aclDst').value || 'any',
        description: document.getElementById('aclDesc').value,
    };

    try {
        const existingId = document.getElementById('aclFormId').value;
        if (existingId) {
            await API.put(`/api/acl/${_selectedDeviceId}/${existingId.split(':')[0]}/${existingId.split(':')[1]}`, body);
        } else {
            await API.post(`/api/acl/${_selectedDeviceId}`, body);
        }
        closeAclForm();
        await loadAcls();
    } catch(err) {
        alert('操作失败: ' + err.message);
    }
});

async function deleteAcl(aclNum, ruleId) {
    if (!confirm(`确认删除 ACL ${aclNum} rule ${ruleId}？`)) return;
    try {
        await API.del(`/api/acl/${_selectedDeviceId}/${aclNum}/${ruleId}`);
        await loadAcls();
    } catch(err) {
        alert('删除失败: ' + err.message);
    }
}

async function refreshAcl() {
    await loadAcls();
}
