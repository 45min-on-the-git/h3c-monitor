/* H3C Monitor — 配置模板 */

let _templates = [], _currentId = null;

document.addEventListener('DOMContentLoaded', loadTemplates);

async function loadTemplates() {
    _templates = await API.get('/api/templates') || [];
    const el = document.getElementById('templateList');
    if (!_templates.length) {
        el.innerHTML = '<div class="text-center text-muted" style="padding:20px">暂无模板</div>';
        return;
    }
    el.innerHTML = _templates.map(t => `
        <div onclick="selectTemplate(${t.id})" style="padding:10px 12px;border-bottom:1px solid var(--border-color);cursor:pointer;
            ${_currentId===t.id?'background:rgba(77,171,247,0.08);border-left:3px solid var(--accent)':'border-left:3px solid transparent'}">
            <strong>${Util.escapeHtml(t.name)}</strong>
            <div style="font-size:11px;color:var(--text-secondary)">${Util.escapeHtml(t.description||'')}</div>
        </div>
    `).join('');
}

async function selectTemplate(id) {
    _currentId = id;
    const t = _templates.find(x => x.id === id);
    if (!t) return;
    const full = await API.get(`/api/templates/${id}`);
    if (!full) return;
    document.getElementById('editId').value = full.id;
    document.getElementById('editName').value = full.name || '';
    document.getElementById('editDesc').value = full.description || '';
    document.getElementById('editText').value = full.template_text || '';
    document.getElementById('editTitle').textContent = '编辑: ' + full.name;
    document.getElementById('btnDelete').style.display = '';
    document.getElementById('editCard').style.display = '';
    document.getElementById('editPlaceholder').style.display = 'none';
    document.getElementById('previewCard').style.display = 'none';
    loadTemplates();
}

function newTemplate() {
    _currentId = null;
    document.getElementById('editId').value = '';
    document.getElementById('editName').value = '';
    document.getElementById('editDesc').value = '';
    document.getElementById('editText').value = '';
    document.getElementById('editTitle').textContent = '新建模板';
    document.getElementById('btnDelete').style.display = 'none';
    document.getElementById('editCard').style.display = '';
    document.getElementById('editPlaceholder').style.display = 'none';
    document.getElementById('previewCard').style.display = 'none';
}

async function saveTemplate() {
    const body = {
        name: document.getElementById('editName').value,
        description: document.getElementById('editDesc').value,
        template_text: document.getElementById('editText').value,
    };
    const id = document.getElementById('editId').value;
    try {
        if (id) { await API.put(`/api/templates/${id}`, body); }
        else {
            const r = await API.post('/api/templates', body);
            _currentId = r.id; document.getElementById('editId').value = r.id;
            document.getElementById('btnDelete').style.display = '';
        }
        await loadTemplates();
    } catch(e) { alert('保存失败: '+e.message); }
}

async function deleteTemplate() {
    if (!_currentId || !confirm('确认删除此模板？')) return;
    await API.del(`/api/templates/${_currentId}`);
    _currentId = null;
    document.getElementById('editCard').style.display = 'none';
    document.getElementById('editPlaceholder').style.display = '';
    await loadTemplates();
}

async function previewTemplate() {
    const body = {
        template_text: document.getElementById('editText').value,
        variables: {},
    };
    try {
        const r = await API.post('/api/templates/render', body);
        document.getElementById('previewContent').textContent = r.rendered;
        document.getElementById('previewCard').style.display = '';
    } catch(e) { alert('渲染失败: '+e.message); }
}
