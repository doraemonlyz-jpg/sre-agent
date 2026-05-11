// SRE Command Center — frontend (Linear/Vercel restyle + i18n)
(() => {
  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // ─────────────────────────── i18n ───────────────────────────
  // Single source of truth for every visible string. Keys are dot-paths.
  // Use t('foo.bar') for plain text; t('foo.bar', { count: 3 }) for placeholders.

  const I18N = {
    en: {
      'brand.title':         'SRE Command Center',
      'brand.live':          'Live',
      'stats.active':        'ACTIVE',
      'stats.diagnosed':     'DIAGNOSED',
      'stats.mtti':          'MTTI',
      'action.fire':         'Fire alert',
      'action.cancel':       'Cancel',
      'action.slack':        'Post to Slack',
      'action.falsepos':     'Mark false positive',
      'col.incidents':       'Incidents',
      'col.activity':        'Activity',
      'col.select':          'Select an incident',
      'empty.incidents':     'No incidents yet.<br/>Click <b>{action}</b> to start a demo.',
      'empty.detail':        'Pick an incident from the left, or fire a new demo alert to start a multi-agent investigation.',
      'empty.activity':      '— idle —',
      'modal.title':         'Fire a demo alert',
      'modal.sub':           'Choose a scenario. The dashboard spawns a real multi-agent investigation — 7 agents fan out across logs, metrics, traces, and deploys, then synthesize a ranked hypothesis and a remediation plan.',
      'section.alert':       'Alert',
      'section.hypothesis':  'Top hypothesis',
      'section.remediation': 'Remediation · human-in-the-loop',
      'section.evidence':    'Evidence',
      'field.service':       'service',
      'field.severity':      'severity',
      'field.description':   'description',
      'field.tags':          'tags',
      'field.started':       'started',
      'field.confidence':    'confidence',
      'field.backed_by':     'backed by:',
      'field.why_not':       'why not alternative ·',
      'field.expected':      'expected ·',
      'field.reversal':      'reversal',
      'field.total_hits':    'total hits',
      'field.first_at':      'first at',
      'field.peak_at':       'peak at',
      'field.hot_span':      'hot span',
      'field.inspected':     'inspected',
      'field.error_rate':    'error rate',
      'tab.logs':            'logs',
      'tab.metrics':         'metrics',
      'tab.traces':          'traces',
      'tab.deploys':         'deploys',
      'phase.investigating': 'investigating',
      'phase.diagnosed':     'diagnosed',
      'phase.no_signal':     'no signal',
      'phase.failed':        'failed',
      'no.logs':             'no logs evidence yet…',
      'no.metrics':          'no metrics yet…',
      'no.traces':           'no traces yet…',
      'no.deploys':          'no deploy info yet…',
      'no.deploys_window':   'No deploys in the 2h window — likely not a code regression.',
      'time.sec':            '{n}s ago',
      'time.min':            '{n}m ago',
      'time.hour':           '{n}h ago',
      'time.before':         '{n}m before',
    },
    zh: {
      'brand.title':         'SRE 指挥中心',
      'brand.live':          '在线',
      'stats.active':        '调查中',
      'stats.diagnosed':     '已诊断',
      'stats.mtti':          '平均诊断',
      'action.fire':         '触发告警',
      'action.cancel':       '取消',
      'action.slack':        '推送 Slack',
      'action.falsepos':     '标记误报',
      'col.incidents':       '故障列表',
      'col.activity':        '实时活动',
      'col.select':          '请选择一个故障',
      'empty.incidents':     '暂无故障。<br/>点击 <b>{action}</b> 启动一个演示。',
      'empty.detail':        '从左侧选择一个故障，或触发一个新的演示告警，启动多智能体协同诊断。',
      'empty.activity':      '— 空闲 —',
      'modal.title':         '触发一个演示告警',
      'modal.sub':           '选择一个场景。仪表盘会启动一次真实的多智能体协同调查 —— 7 个 agent 并行扫描日志、指标、链路、发布历史，然后综合排序根因假设并给出修复方案。',
      'section.alert':       '告警',
      'section.hypothesis':  '根因假设',
      'section.remediation': '修复建议 · 人工最终决策',
      'section.evidence':    '证据',
      'field.service':       '服务',
      'field.severity':      '严重等级',
      'field.description':   '描述',
      'field.tags':          '标签',
      'field.started':       '触发时间',
      'field.confidence':    '置信度',
      'field.backed_by':     '证据来源：',
      'field.why_not':       '为何不是次选 ·',
      'field.expected':      '预期效果 ·',
      'field.reversal':      '回滚命令',
      'field.total_hits':    '错误总数',
      'field.first_at':      '首次出现',
      'field.peak_at':       '峰值时间',
      'field.hot_span':      '热点 span',
      'field.inspected':     '已检查',
      'field.error_rate':    '错误率',
      'tab.logs':            '日志',
      'tab.metrics':         '指标',
      'tab.traces':          '链路',
      'tab.deploys':         '发布',
      'phase.investigating': '调查中',
      'phase.diagnosed':     '已诊断',
      'phase.no_signal':     '无信号',
      'phase.failed':        '失败',
      'no.logs':             '暂无日志证据…',
      'no.metrics':          '暂无指标数据…',
      'no.traces':           '暂无链路数据…',
      'no.deploys':          '暂无发布信息…',
      'no.deploys_window':   '过去 2 小时无发布 —— 大概率不是代码回归引起。',
      'time.sec':            '{n} 秒前',
      'time.min':            '{n} 分钟前',
      'time.hour':           '{n} 小时前',
      'time.before':         '触发前 {n} 分钟',
    },
  };

  const STATE = {
    incidents: [],
    selectedId: null,
    fullIncident: null,
    scenarios: [],
    activeTab: 'logs',
    // i18n
    lang: (localStorage.getItem('sre.lang') === 'zh' ? 'zh' : 'en'),
    // For incremental activity-log rendering — never re-paint old lines
    activityRenderedFor: null,
    activityRenderedCount: 0,
  };

  function t(key, params) {
    const raw = (I18N[STATE.lang] || I18N.en)[key] ?? I18N.en[key] ?? key;
    if (!params) return raw;
    return raw.replace(/\{(\w+)\}/g, (_, k) => (params[k] ?? `{${k}}`));
  }

  function applyStaticI18n() {
    $$('[data-i18n]').forEach(el => {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    $$('[data-i18n-html]').forEach(el => {
      const key = el.getAttribute('data-i18n-html');
      // Allow {action} placeholder to be filled with the localized button label.
      el.innerHTML = t(key, { action: t('action.fire') });
    });
    document.documentElement.lang = STATE.lang === 'zh' ? 'zh-CN' : 'en';
    $$('.lang-toggle button').forEach(b => {
      b.classList.toggle('active', b.dataset.lang === STATE.lang);
    });
  }

  function setLang(lang) {
    if (lang !== 'en' && lang !== 'zh') return;
    if (STATE.lang === lang) return;
    STATE.lang = lang;
    localStorage.setItem('sre.lang', lang);
    applyStaticI18n();
    // Force a full re-render of the dynamic panels — we keep dicts in code,
    // not in DOM, so we have to repaint to pick up the new strings.
    STATE.activityRenderedFor = null;   // force activity log redraw
    $('#incident-list').dataset.state = '';  // bust incident-list cache
    refresh();
    // Re-render the scenario list (loaded once on boot).
    renderScenarioList();
  }

  // ─────────────────────────── boot ───────────────────────────
  document.addEventListener('DOMContentLoaded', async () => {
    applyStaticI18n();
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
    $$('.lang-toggle button').forEach(b => {
      b.addEventListener('click', () => setLang(b.dataset.lang));
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
    renderScenarioList();
  }

  // Scenario labels come from the backend in English. We provide a localized
  // override keyed by scenario id so the modal feels native in Chinese mode.
  const SCENARIO_LABELS_ZH = {
    'redis-pool-exhaustion': '部署后 Redis 连接池耗尽',
    'false-positive':         '告警触发但实际无故障（误报）',
    'downstream-cascade':     '下游服务级联故障',
  };

  function renderScenarioList() {
    const ul = $('#scenario-list');
    ul.innerHTML = STATE.scenarios.map(s => {
      const label = STATE.lang === 'zh' && SCENARIO_LABELS_ZH[s.id]
        ? SCENARIO_LABELS_ZH[s.id]
        : s.label;
      return `
        <li class="scenario-item" data-id="${s.id}">
          <div class="scenario-label">${escapeHtml(label)}</div>
          <div class="scenario-svc">${s.service} · ${s.severity}</div>
        </li>
      `;
    }).join('');
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

  // Render the incident list. We reuse existing <li> nodes when possible so
  // continuously-animating elements (e.g. the pulsing 'investigating' dot)
  // don't restart their animation every 1s poll.
  function renderIncidentList() {
    const ul = $('#incident-list');

    if (!STATE.incidents.length) {
      const sig = `empty|${STATE.lang}`;
      if (ul.dataset.state !== sig) {
        ul.innerHTML = `<li class="empty">${t('empty.incidents', { action: t('action.fire') })}</li>`;
        ul.dataset.state = sig;
      }
      return;
    }
    if (ul.dataset.state !== 'list') {
      ul.innerHTML = '';
      ul.dataset.state = 'list';
    }

    const existing = new Map(
      $$('.incident-item', ul).map(el => [el.dataset.id, el])
    );
    const seen = new Set();

    STATE.incidents.forEach((inc, idx) => {
      seen.add(inc.id);
      let el = existing.get(inc.id);
      if (!el) {
        el = document.createElement('li');
        el.className = 'incident-item';
        el.dataset.id = inc.id;
        el.addEventListener('click', () => {
          STATE.selectedId = el.dataset.id;
          refresh();
        });
      }

      const sevN = (inc.alert.severity || '').match(/\d+/)?.[0] || '3';
      const isActive = inc.id === STATE.selectedId;
      el.classList.toggle('active', isActive);

      const phaseLabel = t(`phase.${inc.phase}`);
      const phaseCls = `phase-${inc.phase}`;
      const elapsed = inc.diagnosis_ms
        ? `${(inc.diagnosis_ms / 1000).toFixed(1)}s`
        : relTime(inc.started_at);

      // Only touch the inner HTML if something changed — avoids restarting
      // the pulse animation on the investigating phase pill.
      const signature = `${STATE.lang}|${inc.alert.service}|${sevN}|${inc.phase}|${elapsed}`;
      if (el.dataset.signature !== signature) {
        el.dataset.signature = signature;
        el.innerHTML = `
          <div class="incident-svc">${escapeHtml(inc.alert.service)}</div>
          <div class="incident-meta">
            <span class="sev-pill sev-${sevN}">SEV-${sevN}</span>
            <span class="phase-pill ${phaseCls}">${phaseLabel}</span>
            <span>${elapsed}</span>
          </div>
        `;
      }

      // Ensure ordering matches the desired index (most-recent first).
      if (ul.children[idx] !== el) ul.insertBefore(el, ul.children[idx] || null);
    });

    // Remove items that no longer exist.
    existing.forEach((el, id) => { if (!seen.has(id)) el.remove(); });
  }

  function relTime(ts) {
    const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
    if (s < 60)   return t('time.sec',  { n: s });
    if (s < 3600) return t('time.min',  { n: Math.floor(s/60) });
    return                 t('time.hour', { n: Math.floor(s/3600) });
  }

  // ─────────────────────────── detail ───────────────────────────

  function renderDetail() {
    const body = $('#detail-body');
    const head = $('#detail-header');
    const inc  = STATE.fullIncident;

    if (!inc) {
      head.innerHTML = `<span>${t('col.select')}</span>`;
      body.innerHTML = `
        <div class="empty-detail">
          <div class="empty-graphic">◇</div>
          <p>${t('empty.detail')}</p>
        </div>
      `;
      return;
    }

    const sevN = (inc.alert.severity || '').match(/\d+/)?.[0] || '3';
    head.innerHTML = `
      <span>${inc.alert.service}</span>
      <span style="display:flex;gap:8px;align-items:center;">
        <span class="sev-pill sev-${sevN}">SEV-${sevN}</span>
        <span class="phase-pill phase-${inc.phase}">${t(`phase.${inc.phase}`)}</span>
      </span>
    `;

    const sections = [];

    sections.push(`
      <div class="detail-section">
        <div class="section-title">${t('section.alert')}</div>
        <div class="kv-grid">
          <div class="k">${t('field.service')}</div>     <div class="v">${escapeHtml(inc.alert.service)}</div>
          <div class="k">${t('field.severity')}</div>    <div class="v">${inc.alert.severity}</div>
          <div class="k">${t('field.description')}</div> <div class="v">${escapeHtml(inc.alert.description)}</div>
          <div class="k">${t('field.tags')}</div>        <div class="v">${(inc.alert.tags || []).join(', ') || '<span style="color:var(--fg-4)">—</span>'}</div>
          <div class="k">${t('field.started')}</div>     <div class="v">${new Date(inc.started_at).toLocaleString()}</div>
        </div>
      </div>
    `);

    if (inc.hypothesis) {
      const h = inc.hypothesis;
      const supporting = (h.supporting_evidence || []).map(s => `<code>${s}</code>`).join(' ');
      sections.push(`
        <div class="detail-section">
          <div class="section-title mag">${t('section.hypothesis')}</div>
          <div class="hypothesis-card">
            <div class="conf">${(h.confidence * 100).toFixed(0)}% ${t('field.confidence')}</div>
            <div class="text">${escapeHtml(h.top)}</div>
            ${supporting ? `<div style="margin-top:10px;font-family:var(--font-mono);font-size:var(--t-2xs);color:var(--fg-4);letter-spacing:0;">${t('field.backed_by')} ${supporting}</div>` : ''}
            ${h.why_not_alternative ? `<div style="margin-top:8px;font-size:var(--t-sm);color:var(--fg-4);line-height:1.55;"><span style="color:var(--fg-5);font-family:var(--font-mono);font-size:var(--t-2xs);text-transform:uppercase;letter-spacing:0.04em;">${t('field.why_not')} </span>${escapeHtml(h.why_not_alternative)}</div>` : ''}
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
          ${r.expected_effect ? `<div class="remediation-why" style="color:var(--fg-3);"><span style="color:var(--fg-5);font-family:var(--font-mono);font-size:var(--t-2xs);text-transform:uppercase;letter-spacing:0.04em;">${t('field.expected')} </span>${escapeHtml(r.expected_effect)}</div>` : ''}
          ${r.reversal ? `<div class="remediation-reversal"><span class="label">${t('field.reversal')}</span><code style="font-family:var(--font-mono);color:var(--fg-2);font-size:var(--t-sm);">${escapeHtml(r.reversal)}</code></div>` : ''}
        </div>
      `).join('');
      sections.push(`
        <div class="detail-section">
          <div class="section-title green">${t('section.remediation')}</div>
          ${reMd}
          <div class="detail-actions">
            <button class="btn-primary" id="btn-slack">${t('action.slack')}</button>
            <button class="btn-secondary">${t('action.falsepos')}</button>
          </div>
        </div>
      `);
    }

    if (inc.findings && Object.keys(inc.findings).length) {
      sections.push(renderEvidenceTabs(inc.findings));
    }

    body.innerHTML = sections.join('');

    $$('.tab', body).forEach(tabEl => {
      tabEl.addEventListener('click', () => {
        if (tabEl.classList.contains('disabled')) return;
        STATE.activeTab = tabEl.dataset.tab;
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
      { key: 'logs',    has: !!findings.logs },
      { key: 'metrics', has: !!findings.metrics },
      { key: 'traces',  has: !!findings.traces },
      { key: 'deploys', has: !!findings.deploys },
    ];
    const activeKey = tabs.find(x => x.has && x.key === STATE.activeTab)?.key
                    || tabs.find(x => x.has)?.key
                    || 'logs';
    STATE.activeTab = activeKey;

    return `
      <div class="detail-section">
        <div class="section-title amber">${t('section.evidence')}</div>
        <div class="tabs">
          ${tabs.map(x => `
            <button class="tab ${x.key === activeKey ? 'active' : ''} ${x.has ? '' : 'disabled'}"
                    data-tab="${x.key}" ${x.has ? '' : 'disabled'}>${t('tab.' + x.key)}</button>
          `).join('')}
        </div>
        <div class="tab-pane ${activeKey === 'logs' ? 'active' : ''}" data-pane="logs">${renderLogs(findings.logs)}</div>
        <div class="tab-pane ${activeKey === 'metrics' ? 'active' : ''}" data-pane="metrics">${renderMetrics(findings.metrics)}</div>
        <div class="tab-pane ${activeKey === 'traces' ? 'active' : ''}" data-pane="traces">${renderTraces(findings.traces)}</div>
        <div class="tab-pane ${activeKey === 'deploys' ? 'active' : ''}" data-pane="deploys">${renderDeploys(findings.deploys)}</div>
      </div>
    `;
  }

  const NULL_LINE = (key) => `<div style="color:var(--fg-4);font-size:var(--t-sm);">${t(key)}</div>`;

  function renderLogs(logs) {
    if (!logs) return NULL_LINE('no.logs');
    const top = (logs.top_messages || []).map(m =>
      `<div class="log-msg"><span class="count">${m.count}</span><span>${escapeHtml(m.message)}</span></div>`
    ).join('');
    return `
      <div class="kv-grid">
        <div class="k">${t('field.total_hits')}</div> <div class="v">${logs.hits}</div>
        <div class="k">${t('field.first_at')}</div>   <div class="v">${formatTs(logs.first_at) || '—'}</div>
        <div class="k">${t('field.peak_at')}</div>    <div class="v">${formatTs(logs.peak_at) || '—'}</div>
      </div>
      ${top ? `<div style="margin-top:14px;">${top}</div>` : ''}
      ${logs.interpretation ? `<div style="margin-top:12px;font-size:var(--t-sm);color:var(--fg-3);line-height:1.6;font-style:italic;">${escapeHtml(logs.interpretation)}</div>` : ''}
    `;
  }

  function renderMetrics(metrics) {
    if (!metrics) return NULL_LINE('no.metrics');
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
    if (!traces) return NULL_LINE('no.traces');
    let html = `
      <div class="kv-grid">
        <div class="k">${t('field.inspected')}</div>  <div class="v">${traces.traces_inspected}</div>
        <div class="k">${t('field.error_rate')}</div> <div class="v">${traces.error_rate}</div>
      </div>
    `;
    if (traces.hot_span) {
      html += `
        <div style="margin-top:14px;font-family:var(--font-mono);font-size:var(--t-2xs);color:var(--fg-4);letter-spacing:0.06em;text-transform:uppercase;margin-bottom:6px;">${t('field.hot_span')}</div>
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
    if (!deploys) return NULL_LINE('no.deploys');
    if (!deploys.deploys || !deploys.deploys.length) {
      return `<div style="color:var(--fg-3);font-style:italic;font-size:var(--t-sm);">${t('no.deploys_window')}</div>`;
    }
    return deploys.deploys.map(d => `
      <div class="evidence-line">
        <span class="k suspect-${d.suspect}">${d.suspect}</span>
        <span class="v">
          <b>${escapeHtml(d.service)}</b> · <code>${(d.sha || '').slice(0, 7)}</code> · ${t('time.before', { n: d.minutes_before })}<br/>
          ${escapeHtml(d.pr_title)} by @${escapeHtml(d.author)}<br/>
          <a href="${d.pr_url}" target="_blank" rel="noopener">${d.pr_url}</a>
        </span>
      </div>
    `).join('');
  }

  // ─────────────────────────── activity log ───────────────────────────
  //
  // Incremental rendering. We NEVER re-paint old lines — that's what made
  // the panel flash on every 1s poll. We only append new lines as they
  // arrive. Switching incidents wipes and starts fresh.

  function renderActivity() {
    const ul = $('#activity-log');
    const inc = STATE.fullIncident;

    if (!inc || !inc.events?.length) {
      if (STATE.activityRenderedFor !== null || ul.dataset.lang !== STATE.lang) {
        ul.innerHTML = `<li class="empty">${t('empty.activity')}</li>`;
        ul.dataset.lang = STATE.lang;
        STATE.activityRenderedFor = null;
        STATE.activityRenderedCount = 0;
      }
      return;
    }

    // Switched incident? Wipe and restart.
    if (STATE.activityRenderedFor !== inc.id) {
      ul.innerHTML = '';
      STATE.activityRenderedFor = inc.id;
      STATE.activityRenderedCount = 0;
    }

    const newEvents = inc.events.slice(STATE.activityRenderedCount);
    if (!newEvents.length) return;

    const atBottom = ul.scrollHeight - ul.scrollTop - ul.clientHeight < 16;
    const frag = document.createDocumentFragment();

    for (const e of newEvents) {
      const li = document.createElement('li');
      li.className = 'activity-line';
      const dt = new Date(e.ts);
      const time = `${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`;
      li.innerHTML = `
        <span class="time">${time}</span>
        <span class="agent agent-${e.agent}">${escapeHtml(e.agent)}</span>
        <span class="detail">${escapeHtml(e.detail || '')}</span>
      `;
      frag.appendChild(li);
    }

    ul.appendChild(frag);
    STATE.activityRenderedCount = inc.events.length;

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
