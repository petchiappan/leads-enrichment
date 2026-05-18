/* ═══ Leads Enrichment AI — Vanilla JS ═══ */

// ── Toast Notifications ──
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 3000);
}

// ── JSON Pretty Printer ──
function formatJSON(obj) {
    if (typeof obj === 'string') { try { obj = JSON.parse(obj); } catch { return obj; } }
    return syntaxHighlight(JSON.stringify(obj, null, 2));
}

function syntaxHighlight(json) {
    return json.replace(/("(\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
        function (match) {
            let cls = 'json-number';
            if (/^"/.test(match)) { cls = /:$/.test(match) ? 'json-key' : 'json-string'; }
            else if (/true|false/.test(match)) { cls = 'json-number'; }
            else if (/null/.test(match)) { cls = 'json-null'; }
            return '<span class="' + cls + '">' + match + '</span>';
        });
}

document.querySelectorAll('.json-viewer[data-json]').forEach(el => {
    try { el.innerHTML = formatJSON(el.dataset.json); } catch { /* keep raw */ }
});

// ── Enrichment Form ──
const enrichForm = document.getElementById('enrich-form');
if (enrichForm) {
    enrichForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = enrichForm.querySelector('button[type="submit"]');
        btn.disabled = true; btn.textContent = 'Submitting...';

        const body = { company_name: document.getElementById('company_name').value.trim() };
        const domain = document.getElementById('company_domain')?.value?.trim();
        if (domain) body.company_domain = domain;
        const ctx = document.getElementById('additional_context')?.value?.trim();
        if (ctx) { try { body.additional_context = JSON.parse(ctx); } catch { showToast('Invalid JSON in context', 'error'); btn.disabled = false; btn.textContent = 'Start Enrichment'; return; } }

        try {
            const res = await fetch('/api/enrich', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
            const data = await res.json();
            if (res.ok) {
                showToast(`Enrichment queued: ${data.request_id}`);
                const resultDiv = document.getElementById('enrich-result');
                if (resultDiv) { resultDiv.classList.remove('hidden'); resultDiv.innerHTML = `<div class="card" style="border-left:3px solid var(--blue-500)"><p class="font-semibold text-blue">✓ Job Queued</p><p class="text-sm mt-2">Request ID: <code class="text-mono">${data.request_id}</code></p><p class="mt-2"><a href="/admin/leads/${data.request_id}" class="btn btn-primary btn-sm">View Lead →</a></p></div>`; }
                startPipelineMonitor(data.request_id);
            } else { showToast(data.detail || 'Enrichment failed', 'error'); }
        } catch (err) { showToast('Network error', 'error'); }
        btn.disabled = false; btn.textContent = 'Start Enrichment';
    });
}

// ── WebSocket Pipeline Monitor ──
function startPipelineMonitor(requestId) {
    const container = document.getElementById('pipeline-monitor');
    if (!container) return;
    container.classList.remove('hidden');
    container.innerHTML = '<div class="stepper" id="live-stepper"></div>';
    const stepper = document.getElementById('live-stepper');

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/ws/pipeline/${requestId}`);
    ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        const step = document.createElement('div');
        step.className = 'step';
        const iconClass = data.status === 'success' ? 'success' : data.status === 'failed' ? 'failed' : data.status === 'skipped' ? 'skipped' : 'started';
        const icon = data.status === 'success' ? '✓' : data.status === 'failed' ? '✗' : data.status === 'skipped' ? '—' : '⟳';
        step.innerHTML = `<div class="step-line"></div><div class="step-icon ${iconClass}">${icon}</div><div class="step-content"><div class="step-title">${data.step || data.step_name || ''}</div><div class="step-meta">${data.status} · ${data.timestamp || new Date().toLocaleTimeString()}</div></div>`;
        stepper.appendChild(step);
    };
    ws.onclose = () => { const p = document.createElement('p'); p.className = 'text-sm text-light mt-4'; p.textContent = 'Pipeline monitoring ended.'; container.appendChild(p); };
}

// ── Config CRUD ──
async function addConfig() {
    const key = document.getElementById('new-config-key')?.value?.trim();
    const val = document.getElementById('new-config-value')?.value?.trim();
    if (!key || !val) { showToast('Key and value required', 'error'); return; }
    try {
        const res = await fetch('/api/admin/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ setting_key: key, setting_value: val }) });
        if (res.ok) { showToast('Config added'); location.reload(); } else { const d = await res.json(); showToast(d.detail || 'Error', 'error'); }
    } catch { showToast('Network error', 'error'); }
}

async function deleteConfig(key) {
    if (!confirm(`Delete config "${key}"?`)) return;
    try {
        const res = await fetch(`/api/admin/config/${encodeURIComponent(key)}`, { method: 'DELETE' });
        if (res.ok) { showToast('Config deleted'); location.reload(); } else { showToast('Delete failed', 'error'); }
    } catch { showToast('Network error', 'error'); }
}

async function editConfig(key, currentValue) {
    const newVal = prompt(`Edit value for "${key}":`, currentValue);
    if (newVal === null || newVal === currentValue) return;
    try {
        const res = await fetch(`/api/admin/config/${encodeURIComponent(key)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ setting_key: key, setting_value: newVal }) });
        if (res.ok) { showToast('Config updated'); location.reload(); } else { showToast('Update failed', 'error'); }
    } catch { showToast('Network error', 'error'); }
}

// ── Semantic Search ──
const searchForm = document.getElementById('search-form');
if (searchForm) {
    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = document.getElementById('search-query')?.value?.trim();
        const limit = document.getElementById('search-limit')?.value || 10;
        if (!query) return;
        const resultsDiv = document.getElementById('search-results');
        resultsDiv.innerHTML = '<p class="text-light">Searching...</p>';

        try {
            const res = await fetch('/api/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query, limit: parseInt(limit) }) });
            const data = await res.json();
            if (!data.results?.length) { resultsDiv.innerHTML = '<div class="empty-state"><div class="icon">🔍</div><h3>No results found</h3></div>'; return; }
            resultsDiv.innerHTML = data.results.map(r => `<div class="search-result"><div class="flex justify-between items-center"><a href="/admin/leads/${r.lead_id}" class="link font-semibold">${r.lead_id}</a><span class="badge badge-completed">${(r.similarity * 100).toFixed(1)}%</span></div><p class="text-sm text-light mt-2">${r.content_summary || 'No summary'}</p><div class="similarity-bar"><div class="similarity-fill" style="width:${r.similarity * 100}%"></div></div></div>`).join('');
        } catch { resultsDiv.innerHTML = '<p class="text-sm" style="color:var(--red)">Search failed. Is the API running?</p>'; }
    });
}

// ── Toggle Payload Visibility ──
document.querySelectorAll('[data-toggle-payload]').forEach(btn => {
    btn.addEventListener('click', () => {
        const target = document.getElementById(btn.dataset.togglePayload);
        if (target) target.classList.toggle('hidden');
    });
});
