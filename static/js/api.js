/* H3C Monitor — API 请求封装 */

const API = {
    async get(url) {
        const res = await fetch(url);
        if (!res.ok) {
            console.error(`GET ${url} failed: ${res.status}`);
            return null;
        }
        return res.json();
    },

    async post(url, body) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `POST ${url} failed: ${res.status}`);
        }
        return res.json();
    },

    async put(url, body) {
        const res = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `PUT ${url} failed: ${res.status}`);
        }
        return res.json();
    },

    async del(url) {
        const res = await fetch(url, { method: 'DELETE' });
        if (!res.ok) {
            throw new Error(`DELETE ${url} failed: ${res.status}`);
        }
        return res.json();
    }
};

/* 通用工具 */
const Util = {
    formatBytes(bytes) {
        if (bytes === null || bytes === undefined || bytes === 0) return '-';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
        return (bytes / 1073741824).toFixed(2) + ' GB';
    },

    formatBps(bps) {
        if (!bps || bps === 0) return '0 bps';
        if (bps < 1000) return bps + ' bps';
        if (bps < 1000000) return (bps / 1000).toFixed(1) + ' Kbps';
        if (bps < 1000000000) return (bps / 1000000).toFixed(1) + ' Mbps';
        return (bps / 1000000000).toFixed(2) + ' Gbps';
    },

    formatDatetime(isoStr) {
        if (!isoStr) return '-';
        return new Date(isoStr).toLocaleString('zh-CN');
    },

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    /* 生成骨架屏 HTML */
    skeleton(cols, rows) {
        let html = '';
        for (let r = 0; r < rows; r++) {
            html += '<tr>';
            for (let c = 0; c < cols; c++) {
                html += '<td><div class="skeleton" style="height:14px;width:' + (60 + Math.random() * 40) + '%"></div></td>';
            }
            html += '</tr>';
        }
        return html;
    }
};

/* === 主题切换 === */
function initTheme() {
    const saved = localStorage.getItem('h3c-theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    window._theme = saved;

    document.getElementById('themeToggle')?.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('h3c-theme', next);
        window._theme = next;
    });
}

/* === 实时时钟 === */
function initClock() {
    function tick() {
        const el = document.getElementById('topbarClock');
        if (el) el.textContent = new Date().toLocaleString('zh-CN');
    }
    tick();
    setInterval(tick, 1000);
}

/* === 侧边栏激活状态 === */
function setActiveNav(path) {
    document.querySelectorAll('.sidebar-link').forEach(link => {
        link.classList.toggle('active', link.getAttribute('data-path') === path);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initClock();
});
