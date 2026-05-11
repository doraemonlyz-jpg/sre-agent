// SRE Command Center — frontend (Linear/Vercel restyle)
(() => {
  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const STATE = {
    incidents: [],
    selectedId: null,
    fullIncident: null,
    scenarios: [],
    activeTab: 'logs',
  };

  // ─────────────────────────── boot ───────────────────────────
  document.addEventListener('DOMContentLoaded', async () => {
    bindUi();
    await loadScenarios();
    await refresh();
    setInterval(refresh, 1000);
  });

  function bindUi() {
    $('#btn-fire').addEventListener('click', openFireModal);
    $('#btn-modal-close').addEventListener('click', closeFireModal);
    $('#fire-modal').addEventListener('click', (e) => {
      if (e.target.id === 'fire-modal') closeFireModal();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeFireModal();
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        openFireModal();
      }
    });
  }

  async function loadScenarios() {
    const r = await fetch('/api/scenarios');
    const j = await r.json();
    STATE.scenarios = j.scenarios;
    const ul = $('#scenario-list');
    ul.innerHTML = STATE.scenarios.map(s => `
      <li class="scenario-item" data-id="${s.id}">
        <div class="scenario-label">${escapeHtml(s.label)}</div>
        <div class="scenario-svc">${s.service} · ${s.severity}</div>
      </li>
    `).join('');
    $$('.scenario-item', ul).forEach(el => {
      el.addEventListener('click', () => fireScenario(el.dataset.id));
    });
  }

  function openFireModal()  { $('#fire-modal').classList.remove('hidden'); }
  function closeFireModal() { $('#fire-modal').classList.add('hidden'); }

  async function fireScenario(scenarioId) {
    closeFireModal();
    const r = await fetch('/api/incidents/fire', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId }),
    });
    const j = await r.json();
    STATE.selectedId = j.id;
    await refresh();
  }

  // ─────────────────────────── refresh ───────────────────────────

  async function refresh() {
    const [listRes, detailRes] = await Promise.all([
      fetch('/api/incidents').then(r => r.json()).catch(() => ({ incidents: [] })),
      STATE.selectedId
        ? fetch(`/api/incidents/${STATE.selectedId}`).then(r => r.json()).catch(() => null)
        : Promise.resolve(null),
    ]);

    STATE.incidents = listRes.incidents || [];
    STATE.fullIncident = detailRes && !detailRes.error ? detailRes : null;

    renderStats();
    renderIncidentList();
    renderDetail();
    renderActivity();
  }

  // ─────────────────────────── stats ───────────────────────────

  function renderStats() {
    const active = STATE.incidents.filter(i => i.phase === 'investigating').length;
    const diag   = STATE.incidents.filter(i => i.phase === 'diagnosed').length;
    const mttis  = STATE.incidents.filter(i => i.diagnosis_ms).map(i => i.diagnosis_ms);
    $('#stat-active').textContent = active;
    $('#stat-diag').textContent   = diag;
    if (mttis.length) {
      const avg = mttis.reduce((a, b) => a + b, 0) / mttis.length;
      $('#stat-mtti').textContent = `${(avg / 1000).toFixed(1)}s`;
    } else {
      $('#stat-mtti').textContent = '—';
    }
  }

  // ─────────────────────────── incident list ───────────────────────────

  function renderIncidentList() {
    const ul = $('#incident-list');
    if (!STATE.incidents.length) {
      ul.innerHTML = '<li class="empty">No incidents yet.<br/>Click <b>Fire alert</b> to start a demo.</li>';
      return;
    }

    ul.innerHTML = STATE.incidents.map(inc => {
      const sevN = (inc.alert.severity || '').match(/\d+/)?.[0] || '3';
      const isActive = inc.id === STATE.selectedId ? 'active' : '';
      const phaseLabel = inc.phase.replace('_', ' ');
      const phaseCls = `phase-${inc.phase}`;
      const elapsed = inc.diagnosis_ms
        ? `${(inc.diagnosis_ms / 1000).toFixed(1)}s`
        : relTime(inc.started_at);
      return `
        <li class="incident-item ${isActive}" data-id="${inc.id}">
          <div class="incident-svc">${escapeHtml(inc.alert.service)}</div>
          <div class="incident-meta">
            <span class="sev-pill sev-${sevN}">SEV-${sevN}</span>
            <span class="phase-pill ${phaseCls}">${phaseLabel}</span>
            <span>${elapsed}</span>
          </div>
        </li>
      `;
    }).join('');

    $$('.incident-item', ul).forEach(el => {
      el.addEventListener('click', () => {
        STATE.selectedId = el.dataset.id;
        refresh();
      });
    });
  }

  function relTime(ts) {
    const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
    if (s < 60)   return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s/60)}m ago`;
    return `${Math.floor(s/3600)}h ago`;
  }

  // ─────────────────────────── detail ───────────────────────────

  function renderDetail() {
    const body = $('#detail-body');
    const head = $('#detail-header');
    const inc  = STATE.fullIncident;

    if (!inc) {
      head.innerHTML = '<span>Select an incident</span>';
      body.innerHTML = `
        <div class="empty-detail">
          <div class="empty-graphic">◇</div>
          <p>Pick an incident from the left, or fire a new demo alert to start a multi-agent investigation.</p>
        </div>
      `;
      return;
    }

    const sevN = (inc.alert.severity || '').match(/\d+/)?.[0] || '3';
    head.innerHTML = `
      <span>${inc.alert.service}</span>
      <span style="display:flex;gap:8px;align-items:center;">
        <span class="sev-pill sev-${sevN}">SEV-${sevN}</span>
        <span class="phase-pill phase-${inc.phase}">${inc.phase.replace('_',' ')}</span>
      </span>
    `;

    const sections = [];

    sections.push(`
      <div class="detail-section">
        <div class="section-title">Alert</div>
        <div class="kv-grid">
          <div class="k">service</div>      <div class="v">${escapeHtml(inc.alert.service)}</div>
          <div class="k">severity</div>     <div class="v">${inc.alert.severity}</div>
          <div class="k">description</div>  <div class="v">${escapeHtml(inc.alert.description)}</div>
          <div class="k">tags</div>         <div class="v">${(inc.alert.tags || []).join(', ') || '<span style="color:var(--fg-4)">—</span>'}</div>
          <div class="k">started</div>      <div class="v">${new Date(inc.started_at).toLocaleString()}</div>
        </div>
      </div>
    `);

    if (inc.hypothesis) {
      const h = inc.hypothesis;
      const supporting = (h.supporting_evidence || []).map(s => `<code>${s}</code>`).join(' ');
      sections.push(`
        <div class="detail-section">
          <div class="section-title mag">Top hypothesis</div>
          <div class="hypothesis-card">
            <div class="conf">${(h.confidence * 100).toFixed(0)}% confidence</div>
            <div class="text">${escapeHtml(h.top)}</div>
            ${supporting ? `<div style="margin-top:10px;font-family:var(--font-mono);font-size:var(--t-2xs);color:var(--fg-4);letter-spacing:0;">backed by: ${supporting}</div>` : ''}
            ${h.why_not_alternative ? `<div style="margin-top:8px;font-size:var(--t-sm);color:var(--fg-4);line-height:1.55;"><span style="color:var(--fg-5);font-family:var(--font-mono);font-size:var(--t-2xs);text-transform:uppercase;letter-spacing:0.04em;">why not alternative · </span>${escapeHtml(h.why_not_alternative)}</div>` : ''}
          </div>
        </div>
      `);
    }

    if (inc.remediation && inc.remediation.length) {
      const reMd = inc.remediation.map(r => `
        <div class="remediation-item">
          <div class="remediation-head">
            <span class="remediation-title">${escapeHtml(r.title || '')}</span>
            <span class="risk-pill risk-${r.risk}">${r.risk}</span>
          </div>
          ${r.command ? `<div class="remediation-cmd">${escapeHtml(r.command)}</div>` : ''}
          ${r.why ? `<div class="remediation-why">${escapeHtml(r.why)}</div>` : ''}
          ${r.expected_effect ? `<div class="remediation-why" style="color:var(--fg-3);"><span style="color:var(--fg-5);font-family:var(--font-mono);font-size:var(--t-2xs);text-transform:uppercase;letter-spacing:0.04em;">expected · </span>${escapeHtml(r.expected_effect)}</div>` : ''}
          ${r.reversal ? `<div class="remediation-reversal"><span class="label">reversal</span><code style="font-family:var(--font-mono);color:var(--fg-2);font-size:var(--t-sm);">${escapeHtml(r.reversal)}</code></div>` : ''}
        </div>
      `).join('');
      sections.push(`
        <div class="detail-section">
          <div class="section-title green">Remediation · human-in-the-loop</div>
          ${reMd}
          <div class="detail-actions">
            <button class="btn-primary" id="btn-slack">Post to Slack</button>
            <button class="btn-secondary">Mark false positive</button>
          </div>
        </div>
      `);
    }

    if (inc.findings && Object.keys(inc.findings).length) {
      sections.push(renderEvidenceTabs(inc.findings));
    }

    body.innerHTML = sections.join('');

    $$('.tab', body).forEach(t => {
      t.addEventListener('click', () => {
        if (t.classList.contains('disabled')) return;
        STATE.activeTab = t.dataset.tab;
        $$('.tab', body).forEach(x => x.classList.toggle('active', x.dataset.tab === STATE.activeTab));
        $$('.tab-pane', body).forEach(x => x.classList.toggle('active', x.dataset.pane === STATE.activeTab));
      });
    });

    const slackBtn = $('#btn-slack', body);
    if (slackBtn) slackBtn.addEventListener('click', () => postToSlack(inc.id));
  }

  async function postToSlack(incidentId) {
    const r = await fetch(`/api/incidents/${incidentId}/post-slack`, { method: 'POST' });
    const j = await r.json();
    alert(j.preview || JSON.stringify(j));
  }

  function renderEvidenceTabs(findings) {
    const tabs = [
      { key: 'logs',    label: 'logs',    has: !!findings.logs },
      { key: 'metrics', label: 'metrics', has: !!findings.metrics },
      { key: 'traces',  label: 'traces',  has: !!findings.traces },
      { key: 'deploys', label: 'deploys', has: !!findings.deploys },
    ];
    const activeKey = tabs.find(t => t.has && t.key === STATE.activeTab)?.key
                    || tabs.find(t => t.has)?.key
                    || 'logs';
    STATE.activeTab = activeKey;

    return `
      <div class="detail-section">
        <div class="section-title amber">Evidence</div>
        <div class="tabs">
          ${tabs.map(t => `
            <button class="tab ${t.key === activeKey ? 'active' : ''} ${t.has ? '' : 'disabled'}"
                    data-tab="${t.key}" ${t.has ? '' : 'disabled'}>${t.label}</button>
          `).join('')}
        </div>
        <div class="tab-pane ${activeKey === 'logs' ? 'active' : ''}" data-pane="logs">${renderLogs(findings.logs)}</div>
        <div class="tab-pane ${activeKey === 'metrics' ? 'active' : ''}" data-pane="metrics">${renderMetrics(findings.metrics)}</div>
        <div class="tab-pane ${activeKey === 'traces' ? 'active' : ''}" data-pane="traces">${renderTraces(findings.traces)}</div>
        <div class="tab-pane ${activeKey === 'deploys' ? 'active' : ''}" data-pane="deploys">${renderDeploys(findings.deploys)}</div>
      </div>
    `;
  }

  function renderLogs(logs) {
    if (!logs) return '<div style="color:var(--fg-4);font-size:var(--t-sm);">no logs evidence yet…</div>';
    const top = (logs.top_messages || []).map(m =>
      `<div class="log-msg"><span class="count">${m.count}</span><span>${escapeHtml(m.message)}</span></div>`
    ).join('');
    return `
      <div class="kv-grid">
        <div class="k">total hits</div> <div class="v">${logs.hits}</div>
        <div class="k">first at</div>   <div class="v">${formatTs(logs.first_at) || '—'}</div>
        <div class="k">peak at</div>    <div class="v">${formatTs(logs.peak_at) || '—'}</div>
      </div>
      ${top ? `<div style="margin-top:14px;">${top}</div>` : ''}
      ${logs.interpretation ? `<div style="margin-top:12px;font-size:var(--t-sm);color:var(--fg-3);line-height:1.6;font-style:italic;">${escapeHtml(logs.interpretation)}</div>` : ''}
    `;
  }

  function renderMetrics(metrics) {
    if (!metrics) return '<div style="color:var(--fg-4);font-size:var(--t-sm);">no metrics yet…</div>';
    return Object.entries(metrics).map(([name, m]) => {
      const cls = (m.verdict || '').startsWith('SPIKE') ? 'spike'
                : (m.verdict || '').startsWith('NORMAL') ? 'normal' : '';
      return `
        <div class="evidence-line">
          <span class="k">${name}</span>
          <span class="v ${cls}">${m.baseline} → ${m.peak} ${m.peak_at ? `@ ${m.peak_at.slice(11,16)}` : ''} · <b>${m.verdict}</b></span>
        </div>
      `;
    }).join('');
  }

  function renderTraces(traces) {
    if (!traces) return '<div style="color:var(--fg-4);font-size:var(--t-sm);">no traces yet…</div>';
    let html = `
      <div class="kv-grid">
        <div class="k">inspected</div>  <div class="v">${traces.traces_inspected}</div>
        <div class="k">error rate</div> <div class="v">${traces.error_rate}</div>
      </div>
    `;
    if (traces.hot_span) {
      html += `
        <div style="margin-top:14px;font-family:var(--font-mono);font-size:var(--t-2xs);color:var(--fg-4);letter-spacing:0.06em;text-transform:uppercase;margin-bottom:6px;">hot span</div>
        <div class="evidence-line">
          <span class="k">${escapeHtml(traces.hot_span.name)}</span>
          <span class="v spike">${traces.hot_span.baseline_ms}ms → ${traces.hot_span.median_ms}ms (${traces.hot_span.ratio})</span>
        </div>
        ${traces.downstream_suspect ? `<div style="margin-top:10px;font-size:var(--t-sm);color:var(--fg-3);line-height:1.55;">${escapeHtml(traces.downstream_suspect)}</div>` : ''}
      `;
    }
    return html;
  }

  function renderDeploys(deploys) {
    if (!deploys) return '<div style="color:var(--fg-4);font-size:var(--t-sm);">no deploy info yet…</div>';
    if (!deploys.deploys || !deploys.deploys.length) {
      return '<div style="color:var(--fg-3);font-style:italic;font-size:var(--t-sm);">No deploys in the 2h window — likely not a code regression.</div>';
    }
    return deploys.deploys.map(d => `
      <div class="evidence-line">
        <span class="k suspect-${d.suspect}">${d.suspect}</span>
        <span class="v">
          <b>${escapeHtml(d.service)}</b> · <code>${(d.sha || '').slice(0, 7)}</code> · ${d.minutes_before}m before<br/>
          ${escapeHtml(d.pr_title)} by @${escapeHtml(d.author)}<br/>
          <a href="${d.pr_url}" target="_blank" rel="noopener">${d.pr_url}</a>
        </span>
      </div>
    `).join('');
  }

  // ─────────────────────────── activity log ───────────────────────────

  function renderActivity() {
    const ul = $('#activity-log');
    const inc = STATE.fullIncident;
    if (!inc || !inc.events?.length) {
      ul.innerHTML = '<li class="empty">— idle —</li>';
      return;
    }

    const atBottom = ul.scrollHeight - ul.scrollTop - ul.clientHeight < 12;

    ul.innerHTML = inc.events.map(e => {
      const t = new Date(e.ts);
      const time = `${pad(t.getHours())}:${pad(t.getMinutes())}:${pad(t.getSeconds())}`;
      return `
        <li class="activity-line">
          <span class="time">${time}</span>
          <span class="agent agent-${e.agent}">${e.agent}</span>
          <span class="detail">${escapeHtml(e.detail || '')}</span>
        </li>
      `;
    }).join('');

    if (atBottom) ul.scrollTop = ul.scrollHeight;
  }

  // ─────────────────────────── util ───────────────────────────

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  function formatTs(ts) {
    if (!ts) return null;
    try { return new Date(ts).toLocaleString(); }
    catch { return ts; }
  }

  function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
})();
