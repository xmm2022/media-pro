from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["admin-ui"])


ADMIN_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>media-pro admin</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #18202a;
      --muted: #687384;
      --line: #d9dee7;
      --accent: #0f766e;
      --accent-strong: #115e59;
      --danger: #b42318;
      --warn: #a16207;
      --ok: #15803d;
      --shadow: 0 1px 2px rgba(15, 23, 42, .08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      position: sticky;
      top: 0;
      z-index: 5;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 22px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, .96);
      backdrop-filter: blur(8px);
    }
    h1, h2, h3 { margin: 0; letter-spacing: 0; }
    h1 { font-size: 18px; font-weight: 700; }
    h2 { font-size: 15px; font-weight: 700; }
    h3 { font-size: 13px; font-weight: 700; }
    main {
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      gap: 18px;
      max-width: 1440px;
      margin: 0 auto;
      padding: 18px 22px 32px;
    }
    section, aside {
      min-width: 0;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    aside { align-self: start; position: sticky; top: 70px; }
    .section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 13px 14px;
      border-bottom: 1px solid var(--line);
    }
    .body { padding: 14px; }
    .grid { display: grid; gap: 14px; }
    .grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .stack { display: grid; gap: 10px; }
    .row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .spacer { flex: 1; }
    .tabs {
      display: flex;
      gap: 4px;
      padding: 4px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #eef1f5;
    }
    .tab {
      border: 0;
      background: transparent;
      color: var(--muted);
      padding: 7px 10px;
      border-radius: 6px;
      cursor: pointer;
      font: inherit;
      white-space: nowrap;
    }
    .tab.active { background: #fff; color: var(--ink); box-shadow: var(--shadow); }
    button, input, select, textarea {
      font: inherit;
    }
    button {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 6px;
      padding: 7px 10px;
      cursor: pointer;
      min-height: 34px;
    }
    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }
    button.primary:hover { background: var(--accent-strong); }
    button:disabled { cursor: not-allowed; opacity: .55; }
    label {
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
    }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 8px 9px;
      min-height: 36px;
    }
    textarea { min-height: 80px; resize: vertical; }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th, td {
      padding: 9px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      background: #fafbfc;
    }
    tr:last-child td { border-bottom: 0; }
    .metric {
      display: grid;
      gap: 4px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfd;
    }
    .metric strong { font-size: 22px; line-height: 1.1; }
    .metric span, .muted { color: var(--muted); }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      max-width: 100%;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 8px;
      background: #fff;
      font-size: 12px;
      white-space: nowrap;
    }
    .pill.ok { color: var(--ok); border-color: #bbf7d0; background: #f0fdf4; }
    .pill.warn { color: var(--warn); border-color: #fde68a; background: #fffbeb; }
    .pill.danger { color: var(--danger); border-color: #fecaca; background: #fff1f2; }
    .view { display: none; }
    .view.active { display: grid; gap: 18px; }
    .empty {
      color: var(--muted);
      padding: 16px;
      border: 1px dashed var(--line);
      border-radius: 8px;
      background: #fbfcfd;
    }
    pre {
      margin: 0;
      max-height: 280px;
      overflow: auto;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #101828;
      color: #e5e7eb;
      font-size: 12px;
    }
    .statusbar {
      color: var(--muted);
      font-size: 12px;
    }
    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; padding: 14px; }
      aside { position: static; }
      .grid.two, .grid.three { grid-template-columns: 1fr; }
      header { align-items: flex-start; flex-direction: column; }
      .tabs { width: 100%; overflow-x: auto; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>media-pro admin</h1>
      <div class="statusbar" id="status">初始化</div>
    </div>
    <div class="tabs" role="tablist">
      <button class="tab active" data-view="overview">概览</button>
      <button class="tab" data-view="users">用户</button>
      <button class="tab" data-view="drives">Drives</button>
      <button class="tab" data-view="pool">Pool</button>
      <button class="tab" data-view="ops">操作</button>
    </div>
  </header>
  <main>
    <aside>
      <div class="section-head">
        <h2>状态</h2>
        <button id="refresh">刷新</button>
      </div>
      <div class="body stack">
        <div class="grid two">
          <div class="metric"><span>Drive</span><strong id="metric-drives">0</strong></div>
          <div class="metric"><span>缓存</span><strong id="metric-pool">0</strong></div>
          <div class="metric"><span>用户</span><strong id="metric-users">0</strong></div>
          <div class="metric"><span>关注</span><strong id="metric-attention">0</strong></div>
        </div>
        <div class="stack">
          <h3>播放路由</h3>
          <div id="route-pills" class="row"></div>
        </div>
      </div>
    </aside>

    <div class="grid">
      <section class="view active" id="view-overview">
        <div class="section-head"><h2>概览</h2></div>
        <div class="body grid two">
          <div class="stack">
            <h3>需要关注的 drives</h3>
            <div id="attention-drives"></div>
          </div>
          <div class="stack">
            <h3>需要关注的 pool objects</h3>
            <div id="attention-pool"></div>
          </div>
        </div>
      </section>

      <section class="view" id="view-users">
        <div class="section-head"><h2>用户</h2></div>
        <div class="body grid two">
          <form id="user-form" class="stack">
            <label>用户名 <input name="username" autocomplete="off" required></label>
            <label>状态 <input name="status" value="active"></label>
            <div><button class="primary" type="submit">创建用户</button></div>
          </form>
          <div id="users-table"></div>
        </div>
      </section>

      <section class="view" id="view-drives">
        <div class="section-head"><h2>Drives</h2></div>
        <div class="body stack">
          <form id="drive-form" class="grid three">
            <label>用户 ID <input name="user_id" type="number" min="1" required></label>
            <label>类型
              <select name="drive_type">
                <option value="caiyun">caiyun</option>
                <option value="115">115</option>
              </select>
            </label>
            <label>root_dir <input name="root_dir" value="/"></label>
            <label>mount_path <input name="mount_path" placeholder="/yidon"></label>
            <label>adopt_existing
              <select name="adopt_existing">
                <option value="true">true</option>
                <option value="false">false</option>
              </select>
            </label>
            <label>share_pool_enabled
              <select name="share_pool_enabled">
                <option value="false">false</option>
                <option value="true">true</option>
              </select>
            </label>
            <label>115 cookie <textarea name="cookie" placeholder="UID=..."></textarea></label>
            <label>caiyun access_token <textarea name="access_token"></textarea></label>
            <label>caiyun refresh_token <textarea name="refresh_token"></textarea></label>
            <div class="row"><button class="primary" type="submit">保存 drive</button></div>
          </form>
          <div id="drives-table"></div>
        </div>
      </section>

      <section class="view" id="view-pool">
        <div class="section-head"><h2>Pool objects</h2></div>
        <div class="body stack">
          <div class="row">
            <label style="width:180px">状态筛选
              <select id="pool-status">
                <option value="">全部</option>
                <option value="ready">ready</option>
                <option value="suspect">suspect</option>
                <option value="cooldown">cooldown</option>
                <option value="disabled">disabled</option>
                <option value="stale">stale</option>
              </select>
            </label>
            <button id="pool-filter">应用</button>
          </div>
          <div id="pool-table"></div>
        </div>
      </section>

      <section class="view" id="view-ops">
        <div class="section-head"><h2>操作</h2></div>
        <div class="body grid two">
          <form id="catalog-form" class="stack">
            <h3>Catalog sync</h3>
            <label>root_path <input name="root_path" placeholder="/google drive/openlist"></label>
            <div><button class="primary" type="submit">同步</button></div>
          </form>
          <form id="playback-form" class="stack">
            <h3>Playback resolve</h3>
            <label>media_id <input name="media_id" type="number" min="1" required></label>
            <label>user_id <input name="user_id" type="number" min="1" required></label>
            <div><button class="primary" type="submit">解析播放</button></div>
          </form>
          <div class="stack" style="grid-column:1 / -1">
            <h3>输出</h3>
            <pre id="output">{}</pre>
          </div>
        </div>
      </section>
    </div>
  </main>

  <script>
    const state = { overview: null, users: [], drives: [], pool: [] };
    const $ = (selector) => document.querySelector(selector);

    function setStatus(text) {
      $('#status').textContent = text;
    }

    function showOutput(value) {
      $('#output').textContent = JSON.stringify(value, null, 2);
    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { 'content-type': 'application/json', ...(options.headers || {}) },
        ...options,
      });
      const text = await response.text();
      let body = null;
      if (text) {
        try { body = JSON.parse(text); } catch { body = text; }
      }
      if (!response.ok) {
        const error = new Error(`HTTP ${response.status}`);
        error.body = body;
        throw error;
      }
      return body;
    }

    function pill(text, kind = '') {
      return `<span class="pill ${kind}">${escapeHtml(text)}</span>`;
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[ch]));
    }

    function renderTable(container, columns, rows, actions) {
      if (!rows.length) {
        container.innerHTML = '<div class="empty">暂无数据</div>';
        return;
      }
      const actionHead = actions ? '<th style="width:170px">操作</th>' : '';
      container.innerHTML = `
        <table>
          <thead><tr>${columns.map((c) => `<th>${escapeHtml(c.label)}</th>`).join('')}${actionHead}</tr></thead>
          <tbody>
            ${rows.map((row) => `
              <tr>
                ${columns.map((c) => `<td>${c.render ? c.render(row) : escapeHtml(row[c.key])}</td>`).join('')}
                ${actions ? `<td>${actions(row)}</td>` : ''}
              </tr>
            `).join('')}
          </tbody>
        </table>`;
    }

    function renderOverview() {
      const overview = state.overview;
      if (!overview) return;
      $('#metric-drives').textContent = overview.drives.stats.total;
      $('#metric-pool').textContent = overview.pool_objects.stats.total;
      $('#metric-users').textContent = state.users.length;
      $('#metric-attention').textContent = overview.drives.attention_total + overview.pool_objects.attention_total;
      $('#route-pills').innerHTML = Object.entries(overview.routes)
        .map(([key, value]) => pill(`${key}: ${value}`, value ? 'ok' : ''))
        .join('');
      renderTable($('#attention-drives'), [
        { key: 'id', label: 'ID' },
        { key: 'user_id', label: '用户' },
        { key: 'drive_type', label: '类型' },
        { key: 'health_status', label: '健康', render: (r) => pill(r.health_status, r.health_status === 'healthy' ? 'ok' : 'danger') },
        { key: 'openlist_mount_path', label: 'mount' },
      ], overview.drives.items);
      renderTable($('#attention-pool'), [
        { key: 'id', label: 'ID' },
        { key: 'media_id', label: '媒体' },
        { key: 'drive_type', label: '类型' },
        { key: 'status', label: '状态', render: (r) => pill(r.status, r.status === 'ready' ? 'ok' : 'warn') },
        { key: 'target_path', label: '路径' },
      ], overview.pool_objects.items);
    }

    function renderUsers() {
      renderTable($('#users-table'), [
        { key: 'id', label: 'ID' },
        { key: 'username', label: '用户名' },
        { key: 'status', label: '状态' },
      ], state.users);
    }

    function renderDrives() {
      renderTable($('#drives-table'), [
        { key: 'id', label: 'ID' },
        { key: 'user_id', label: '用户' },
        { key: 'drive_type', label: '类型' },
        { key: 'enabled', label: '启用', render: (r) => pill(r.enabled ? 'yes' : 'no', r.enabled ? 'ok' : 'warn') },
        { key: 'health_status', label: '健康', render: (r) => pill(r.health_status, r.health_status === 'healthy' ? 'ok' : 'danger') },
        { key: 'root_dir', label: 'root' },
        { key: 'openlist_mount_path', label: 'mount' },
      ], state.drives, (row) => `
        <button data-action="probe-drive" data-id="${row.id}">probe</button>
        <button data-action="${row.enabled ? 'disable-drive' : 'enable-drive'}" data-id="${row.id}">${row.enabled ? '停用' : '启用'}</button>
      `);
    }

    function renderPool() {
      renderTable($('#pool-table'), [
        { key: 'id', label: 'ID' },
        { key: 'media_id', label: '媒体' },
        { key: 'owner_user_id', label: '用户' },
        { key: 'drive_type', label: '类型' },
        { key: 'status', label: '状态', render: (r) => pill(r.status, r.status === 'ready' ? 'ok' : 'warn') },
        { key: 'target_path', label: '路径' },
      ], state.pool, (row) => `
        <button data-action="recover-pool" data-id="${row.id}">恢复</button>
        <button data-action="disable-pool" data-id="${row.id}">停用</button>
      `);
    }

    async function refresh() {
      setStatus('刷新中');
      const poolStatus = $('#pool-status').value;
      const poolQuery = poolStatus ? `?status=${encodeURIComponent(poolStatus)}` : '';
      const [overview, users, drives, pool] = await Promise.all([
        api('/api/admin/overview'),
        api('/api/admin/users'),
        api('/api/admin/drives'),
        api(`/api/admin/pool-objects${poolQuery}`),
      ]);
      state.overview = overview;
      state.users = users;
      state.drives = drives;
      state.pool = pool;
      renderOverview();
      renderUsers();
      renderDrives();
      renderPool();
      setStatus(`已刷新 ${new Date().toLocaleTimeString()}`);
    }

    function formData(form) {
      return Object.fromEntries(new FormData(form).entries());
    }

    function compact(value) {
      return Object.fromEntries(Object.entries(value).filter(([, v]) => v !== '' && v !== null && v !== undefined));
    }

    async function handleUserSubmit(event) {
      event.preventDefault();
      const payload = compact(formData(event.currentTarget));
      showOutput(await api('/api/admin/users', { method: 'POST', body: JSON.stringify(payload) }));
      event.currentTarget.reset();
      await refresh();
    }

    async function handleDriveSubmit(event) {
      event.preventDefault();
      const data = formData(event.currentTarget);
      const payload = {
        user_id: Number(data.user_id),
        drive_type: data.drive_type,
        root_dir: data.root_dir || '/',
        share_pool_enabled: data.share_pool_enabled === 'true',
      };
      if (data.drive_type === '115') {
        payload.cookie = data.cookie;
      } else {
        payload.mount_path = data.mount_path;
        payload.adopt_existing = data.adopt_existing === 'true';
        if (!payload.adopt_existing) {
          payload.caiyun = {
            access_token: data.access_token,
            refresh_token: data.refresh_token,
            account_type: 'personal_new',
          };
        }
      }
      showOutput(await api('/api/admin/drives', { method: 'POST', body: JSON.stringify(payload) }));
      await refresh();
    }

    async function handleCatalogSubmit(event) {
      event.preventDefault();
      const data = compact(formData(event.currentTarget));
      showOutput(await api('/api/admin/catalog/sync', { method: 'POST', body: JSON.stringify(data) }));
      await refresh();
    }

    async function handlePlaybackSubmit(event) {
      event.preventDefault();
      const data = formData(event.currentTarget);
      showOutput(await api(`/api/playback/${encodeURIComponent(data.media_id)}?user_id=${encodeURIComponent(data.user_id)}`));
      await refresh();
    }

    async function handleAction(event) {
      const button = event.target.closest('button[data-action]');
      if (!button) return;
      const id = Number(button.dataset.id);
      const action = button.dataset.action;
      if (action === 'probe-drive') {
        showOutput(await api(`/api/admin/drives/${id}/probe`, { method: 'POST' }));
      } else if (action === 'disable-drive') {
        showOutput(await api('/api/admin/drives/disable', { method: 'POST', body: JSON.stringify({ ids: [id] }) }));
      } else if (action === 'enable-drive') {
        showOutput(await api('/api/admin/drives/enable', { method: 'POST', body: JSON.stringify({ ids: [id] }) }));
      } else if (action === 'recover-pool') {
        showOutput(await api(`/api/admin/pool-objects/${id}/recover`, { method: 'POST' }));
      } else if (action === 'disable-pool') {
        showOutput(await api('/api/admin/pool-objects/disable', { method: 'POST', body: JSON.stringify({ ids: [id] }) }));
      }
      await refresh();
    }

    document.querySelectorAll('.tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach((item) => item.classList.remove('active'));
        document.querySelectorAll('.view').forEach((item) => item.classList.remove('active'));
        tab.classList.add('active');
        $(`#view-${tab.dataset.view}`).classList.add('active');
      });
    });
    $('#refresh').addEventListener('click', () => refresh().catch((error) => {
      setStatus('刷新失败');
      showOutput(error.body || error.message);
    }));
    $('#pool-filter').addEventListener('click', () => refresh().catch((error) => showOutput(error.body || error.message)));
    $('#user-form').addEventListener('submit', (event) => handleUserSubmit(event).catch((error) => showOutput(error.body || error.message)));
    $('#drive-form').addEventListener('submit', (event) => handleDriveSubmit(event).catch((error) => showOutput(error.body || error.message)));
    $('#catalog-form').addEventListener('submit', (event) => handleCatalogSubmit(event).catch((error) => showOutput(error.body || error.message)));
    $('#playback-form').addEventListener('submit', (event) => handlePlaybackSubmit(event).catch((error) => showOutput(error.body || error.message)));
    document.body.addEventListener('click', (event) => handleAction(event).catch((error) => showOutput(error.body || error.message)));
    refresh().catch((error) => {
      setStatus('初始化失败');
      showOutput(error.body || error.message);
    });
  </script>
</body>
</html>
"""


@router.get("/admin", response_class=HTMLResponse)
def admin_ui() -> HTMLResponse:
    return HTMLResponse(ADMIN_HTML)
