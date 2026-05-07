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

/* === Toast === */
function showToast(msg, type) {
    const t = document.createElement('div');
    t.className = 'acl-toast';
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

// Add animation
if (!document.getElementById('toastStyle')) {
    const s = document.createElement('style');
    s.id = 'toastStyle';
    s.textContent = '@keyframes toastIn { from{opacity:0;transform:translateY(-10px)} to{opacity:1;transform:translateY(0)} }';
    document.head.appendChild(s);
}

/* === Device change === */
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

/* === Load ACLs === */
async function loadAcls() {
    document.getElementById('aclListCard').style.display = '';
    const tbody = document.getElementById('aclTable');
    tbody.innerHTML = Util.skeleton(7, 3);

    try {
        const resp = await fetch(`/api/acl/${_selectedDeviceId}`);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            tbody.innerHTML = `<tr class="table-empty"><td colspan="7">读取失败: ${Util.escapeHtml(err.detail || 'SSH 不可达')}</td></tr>`;
            document.getElementById('aclCount').textContent = '读取失败';
            return;
        }
        const result = await resp.json();
        _acls = result.rules || [];
        renderAcls();
    } catch(e) {
        tbody.innerHTML = `<tr class="table-empty"><td colspan="7">网络错误: ${Util.escapeHtml(e.message)}</td></tr>`;
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
            <td>${Util.escapeHtml(a.protocol || 'ip')}</td>
            <td>${Util.escapeHtml(a.source || 'any')}</td>
            <td>${Util.escapeHtml(a.destination || 'any')}</td>
            <td>
                <div class="flex gap-2">
                    <button class="btn btn-sm btn-outline" onclick="editAcl('${a.acl_number}', '${a.rule_id}', '${a.action}', '${a.protocol || 'ip'}', '${Util.escapeHtml(a.source || 'any')}', '${Util.escapeHtml(a.destination || 'any')}')">
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

/* === Form === */
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
    const aclNumber = parseInt(document.getElementById('aclNumber').value);
    const ruleId = parseInt(document.getElementById('aclRuleId').value);

    const body = {
        acl_number: aclNumber,
        rule_id: ruleId,
        action: document.getElementById('aclAction').value,
        protocol: document.getElementById('aclProtocol').value,
        source: document.getElementById('aclSrc').value || 'any',
        destination: document.getElementById('aclDst').value || 'any',
        description: document.getElementById('aclDesc').value,
    };

    const existingId = document.getElementById('aclFormId').value;
    const opLabel = existingId ? '更新' : '创建';
    const btn = document.querySelector('#aclForm button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '下发中...';

    try {
        let resp;
        if (existingId) {
            resp = await fetch(
                `/api/acl/${_selectedDeviceId}/${existingId.split(':')[0]}/${existingId.split(':')[1]}`,
                { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
            );
        } else {
            resp = await fetch(
                `/api/acl/${_selectedDeviceId}`,
                { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
            );
        }

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `${opLabel}失败 (${resp.status})`);
        }

        showToast(`ACL ${aclNumber} rule ${ruleId} ${opLabel}成功`, 'success');
        closeAclForm();
        await loadAcls();
    } catch(err) {
        showToast(`${opLabel}失败: ${err.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '保存';
    }
});

/* === Delete === */
async function deleteAcl(aclNum, ruleId) {
    if (!confirm(`确认删除 ACL ${aclNum} rule ${ruleId}？`)) return;
    try {
        const resp = await fetch(`/api/acl/${_selectedDeviceId}/${aclNum}/${ruleId}`, { method: 'DELETE' });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `删除失败 (${resp.status})`);
        }
        showToast(`ACL ${aclNum} rule ${ruleId} 已删除`, 'success');
        await loadAcls();
    } catch(err) {
        showToast(`删除失败: ${err.message}`, 'error');
    }
}

async function refreshAcl() {
    await loadAcls();
    showToast('已刷新', 'success');
}
