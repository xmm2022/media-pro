from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["admin-ui"])


ADMIN_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>media-pro 管理工作台</title>
  <style>
    :root {
      color-scheme: light;
      --page: #f4f6f8;
      --surface: #ffffff;
      --surface-soft: #f8fafc;
      --ink: #17202a;
      --muted: #64748b;
      --line: #d8dee8;
      --line-strong: #c3ccd8;
      --brand: #0f766e;
      --brand-hover: #115e59;
      --amber: #b45309;
      --red: #b42318;
      --green: #15803d;
      --blue: #2563eb;
      --shadow: 0 1px 2px rgba(15, 23, 42, .06);
    }
    * { box-sizing: border-box; }
    html { min-width: 320px; }
    body {
      margin: 0;
      background: var(--page);
      color: var(--ink);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    h1, h2, h3, p { margin: 0; letter-spacing: 0; }
    h1 { font-size: 18px; font-weight: 700; }
    h2 { font-size: 15px; font-weight: 700; }
    h3 { font-size: 13px; font-weight: 700; }
    button, input, select, textarea { font: inherit; }
    button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      min-height: 34px;
      max-width: 100%;
      border: 1px solid var(--line-strong);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 7px 10px;
      cursor: pointer;
      white-space: nowrap;
    }
    button:hover { border-color: #9aa7b8; }
    button:disabled { cursor: not-allowed; opacity: .55; }
    button.primary {
      border-color: var(--brand);
      background: var(--brand);
      color: #fff;
    }
    button.primary:hover { background: var(--brand-hover); }
    input, select, textarea {
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line-strong);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 8px 9px;
    }
    textarea { min-height: 78px; resize: vertical; }
    label {
      display: grid;
      gap: 5px;
      min-width: 0;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th, td {
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    th {
      background: #f8fafc;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    tr:last-child td { border-bottom: 0; }
    pre {
      margin: 0;
      max-height: 320px;
      overflow: auto;
      border: 1px solid #1f2937;
      border-radius: 6px;
      background: #111827;
      color: #e5e7eb;
      padding: 12px;
      font-size: 12px;
    }
    .app-shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 236px minmax(0, 1fr);
    }
    .sidebar {
      position: sticky;
      top: 0;
      height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
      border-right: 1px solid var(--line);
      background: #fbfcfe;
    }
    .brand {
      padding: 18px 18px 14px;
      border-bottom: 1px solid var(--line);
    }
    .brand p {
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
    }
    .nav {
      display: grid;
      align-content: start;
      gap: 4px;
      padding: 12px;
    }
    .nav button {
      justify-content: flex-start;
      width: 100%;
      border-color: transparent;
      background: transparent;
      color: #334155;
      padding: 9px 10px;
    }
    .nav button.active {
      border-color: #b7ded9;
      background: #e8f5f3;
      color: #0f4f4a;
      font-weight: 700;
    }
    .sidebar-foot {
      display: grid;
      gap: 8px;
      padding: 12px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
    }
    .content {
      min-width: 0;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 5;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-width: 0;
      padding: 12px 18px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, .95);
      backdrop-filter: blur(8px);
    }
    .page-title {
      display: grid;
      gap: 2px;
      min-width: 0;
    }
    .page-title span, .statusbar {
      color: var(--muted);
      font-size: 12px;
    }
    .top-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    main {
      min-width: 0;
      max-width: 1440px;
      width: 100%;
      margin: 0 auto;
      padding: 18px;
    }
    .view { display: none; }
    .view.active { display: grid; gap: 14px; }
    .layout-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 330px;
      gap: 14px;
      align-items: start;
    }
    .section {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      box-shadow: var(--shadow);
    }
    .section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-width: 0;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
    }
    .section-head p {
      color: var(--muted);
      font-size: 12px;
    }
    .body { padding: 14px; }
    .stack { display: grid; gap: 10px; min-width: 0; }
    .grid { display: grid; gap: 12px; min-width: 0; }
    .grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .row {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      flex-wrap: wrap;
    }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(140px, 1fr));
      gap: 10px;
    }
    .metric {
      display: grid;
      gap: 5px;
      min-width: 0;
      border: 1px solid var(--line);
      border-left: 3px solid var(--brand);
      border-radius: 7px;
      background: var(--surface-soft);
      padding: 12px;
    }
    .metric:nth-child(2) { border-left-color: var(--blue); }
    .metric:nth-child(3) { border-left-color: var(--green); }
    .metric:nth-child(4) { border-left-color: var(--amber); }
    .metric span, .muted { color: var(--muted); }
    .metric strong { font-size: 24px; line-height: 1.05; }
    .pill {
      display: inline-flex;
      align-items: center;
      max-width: 100%;
      min-height: 22px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      color: #334155;
      padding: 2px 8px;
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .pill.ok { color: var(--green); border-color: #bbf7d0; background: #f0fdf4; }
    .pill.warn { color: var(--amber); border-color: #fde68a; background: #fffbeb; }
    .pill.danger { color: var(--red); border-color: #fecaca; background: #fff1f2; }
    .empty {
      border: 1px dashed var(--line-strong);
      border-radius: 7px;
      background: #fbfcfd;
      color: var(--muted);
      padding: 16px;
    }
    .table-wrap {
      width: 100%;
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 7px;
    }
    .table-wrap table { min-width: 660px; }
    .wide { grid-column: 1 / -1; }
    .form-panel {
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fbfcfd;
      padding: 12px;
    }
    @media (max-width: 1080px) {
      .app-shell { grid-template-columns: 1fr; }
      .sidebar {
        position: static;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
      .brand { padding: 14px; }
      .nav {
        display: flex;
        overflow-x: auto;
        padding: 10px 12px;
      }
      .nav button { width: auto; flex: 0 0 auto; }
      .sidebar-foot { display: none; }
      .layout-grid { grid-template-columns: 1fr; }
      .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 680px) {
      .topbar { align-items: flex-start; flex-direction: column; padding: 12px; }
      .top-actions { width: 100%; justify-content: flex-start; }
      main { padding: 12px; }
      .grid.two, .grid.three, .metric-grid { grid-template-columns: 1fr; }
      .section-head { align-items: flex-start; flex-direction: column; }
      button { white-space: normal; text-align: center; }
    }
  </style>
</head>
<body>
  <div class="app-shell" data-testid="admin-workbench">
    <aside class="sidebar">
      <div class="brand">
        <h1>media-pro 管理工作台</h1>
        <p>媒体网关运维后台</p>
      </div>
      <nav class="nav" aria-label="主导航">
        <button class="active" data-view="overview">概览</button>
        <button data-view="users">用户</button>
        <button data-view="drives">Drive</button>
        <button data-view="pool">Pool</button>
        <button data-view="ops">操作</button>
      </nav>
      <div class="sidebar-foot">
        <span>会话：<span id="session-state">检测中</span></span>
        <span id="status" class="statusbar">初始化</span>
      </div>
    </aside>

    <div class="content">
      <header class="topbar">
        <div class="page-title">
          <h2 id="page-title">系统概览</h2>
          <span id="page-subtitle">查看关键容量、健康状态和播放路由。</span>
        </div>
        <div class="top-actions">
          <span class="pill" id="mobile-status">初始化</span>
          <button id="refresh" type="button">刷新</button>
          <button id="logout" type="button" title="退出登录" hidden>退出</button>
        </div>
      </header>

      <main>
        <section class="view active" id="view-overview" data-title="系统概览" data-subtitle="查看关键容量、健康状态和播放路由。">
          <div class="metric-grid" aria-label="运行状态">
            <div class="metric"><span>Drive 总数</span><strong id="metric-drives">0</strong></div>
            <div class="metric"><span>Pool 对象</span><strong id="metric-pool">0</strong></div>
            <div class="metric"><span>用户</span><strong id="metric-users">0</strong></div>
            <div class="metric"><span>需要关注</span><strong id="metric-attention">0</strong></div>
          </div>
          <div class="layout-grid">
            <div class="grid">
              <section class="section">
                <div class="section-head">
                  <div><h2>需要关注的 drives</h2><p>来自 /api/admin/overview 的健康摘要。</p></div>
                </div>
                <div class="body" id="attention-drives"></div>
              </section>
              <section class="section">
                <div class="section-head">
                  <div><h2>需要关注的 pool objects</h2><p>优先处理 suspect、cooldown、disabled 和 stale 状态。</p></div>
                </div>
                <div class="body" id="attention-pool"></div>
              </section>
            </div>
            <section class="section">
              <div class="section-head"><div><h2>运行状态</h2><p>播放链路与最近刷新结果。</p></div></div>
              <div class="body stack">
                <h3>播放路由</h3>
                <div id="route-pills" class="row"></div>
                <h3>工作台状态</h3>
                <div class="row"><span class="pill" id="desktop-status">初始化</span></div>
              </div>
            </section>
          </div>
        </section>

        <section class="view" id="view-users" data-title="用户管理" data-subtitle="创建用户并查看当前账号状态。">
          <section class="section">
            <div class="section-head"><div><h2>用户</h2><p>用户状态用于后续 drive 归属和播放解析。</p></div></div>
            <div class="body grid two">
              <form id="user-form" class="form-panel stack">
                <h3>创建用户</h3>
                <label>用户名 <input name="username" autocomplete="off" required></label>
                <label>状态 <input name="status" value="active"></label>
                <div><button class="primary" type="submit">创建用户</button></div>
              </form>
              <div id="users-table"></div>
            </div>
          </section>
        </section>

        <section class="view" id="view-drives" data-title="Drive 管理" data-subtitle="登记、探测、启停网盘挂载。">
          <section class="section">
            <div class="section-head"><div><h2>Drive</h2><p>支持 caiyun 和 115，保持原有接口字段。</p></div></div>
            <div class="body stack">
              <form id="drive-form" class="form-panel grid three">
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
                <div class="row wide"><button class="primary" type="submit">保存 drive</button></div>
              </form>
              <div id="drives-table"></div>
            </div>
          </section>
        </section>

        <section class="view" id="view-pool" data-title="Pool 对象" data-subtitle="查看和处理共享池对象状态。">
          <section class="section">
            <div class="section-head">
              <div><h2>Pool objects</h2><p>筛选后仍使用 /api/admin/pool-objects 查询。</p></div>
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
                <button id="pool-filter" type="button">应用</button>
              </div>
            </div>
            <div class="body" id="pool-table"></div>
          </section>
        </section>

        <section class="view" id="view-ops" data-title="操作中心" data-subtitle="执行 catalog 同步和播放测试，输出原始响应。">
          <div class="grid two">
            <section class="section">
              <div class="section-head"><div><h2>Catalog sync</h2><p>触发目录同步任务。</p></div></div>
              <div class="body">
                <form id="catalog-form" class="stack">
                  <label>root_path <input name="root_path" placeholder="/google drive/openlist"></label>
                  <div><button class="primary" type="submit">同步</button></div>
                </form>
              </div>
            </section>
            <section class="section">
              <div class="section-head"><div><h2>播放测试</h2><p>调用 /api/playback/{media_id}?user_id=...</p></div></div>
              <div class="body">
                <form id="playback-form" class="stack">
                  <label>media_id <input name="media_id" type="number" min="1" required></label>
                  <label>user_id <input name="user_id" type="number" min="1" required></label>
                  <div><button class="primary" type="submit">解析播放</button></div>
                </form>
              </div>
            </section>
            <section class="section wide">
              <div class="section-head"><div><h2>输出</h2><p>显示最近一次操作的响应或错误。</p></div></div>
              <div class="body"><pre id="output">{}</pre></div>
            </section>
          </div>
        </section>
      </main>
    </div>
  </div>

  <script>
    const state = { overview: null, users: [], drives: [], pool: [] };
    const $ = (selector) => document.querySelector(selector);

    function setStatus(text) {
      $('#status').textContent = text;
      $('#mobile-status').textContent = text;
      $('#desktop-status').textContent = text;
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

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[ch]));
    }

    function pill(text, kind = '') {
      return `<span class="pill ${kind}">${escapeHtml(text)}</span>`;
    }

    function renderTable(container, columns, rows, actions) {
      if (!rows.length) {
        container.innerHTML = '<div class="empty">暂无数据</div>';
        return;
      }
      const actionHead = actions ? '<th style="width:180px">操作</th>' : '';
      container.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead><tr>${columns.map((c) => `<th>${escapeHtml(c.label)}</th>`).join('')}${actionHead}</tr></thead>
            <tbody>
              ${rows.map((row) => `
                <tr>
                  ${columns.map((c) => `<td>${c.render ? c.render(row) : escapeHtml(row[c.key])}</td>`).join('')}
                  ${actions ? `<td><div class="row">${actions(row)}</div></td>` : ''}
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>`;
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
        <button data-action="probe-drive" data-id="${row.id}" type="button">probe</button>
        <button data-action="${row.enabled ? 'disable-drive' : 'enable-drive'}" data-id="${row.id}" type="button">${row.enabled ? '停用' : '启用'}</button>
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
        <button data-action="recover-pool" data-id="${row.id}" type="button">恢复</button>
        <button data-action="disable-pool" data-id="${row.id}" type="button">停用</button>
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

    function activateView(tab) {
      document.querySelectorAll('.nav button').forEach((item) => item.classList.remove('active'));
      document.querySelectorAll('.view').forEach((item) => item.classList.remove('active'));
      tab.classList.add('active');
      const view = $(`#view-${tab.dataset.view}`);
      view.classList.add('active');
      $('#page-title').textContent = view.dataset.title;
      $('#page-subtitle').textContent = view.dataset.subtitle;
    }

    document.querySelectorAll('.nav button').forEach((tab) => {
      tab.addEventListener('click', () => activateView(tab));
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
    $('#logout').addEventListener('click', async () => {
      await api('/api/admin/logout', { method: 'POST' });
      window.location.href = '/admin/login';
    });
    api('/api/admin/session').then((session) => {
      $('#logout').hidden = !session.auth_enabled;
      $('#session-state').textContent = session.auth_enabled ? '已启用登录保护' : '未启用登录保护';
    }).catch(() => {
      $('#logout').hidden = true;
      $('#session-state').textContent = '检测失败';
    });
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
