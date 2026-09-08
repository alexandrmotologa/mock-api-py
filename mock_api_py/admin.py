"""Embedded Web Admin Dashboard (Dark Mode & Glassmorphism) for mock-api-py."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from mock_api_py.store import DataStore


def get_admin_html() -> str:
    """Returns the single-page HTML/CSS/JS application for the admin dashboard."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>mock-api Studio & Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-primary: #0a0d14;
      --bg-surface: rgba(18, 24, 38, 0.75);
      --bg-surface-hover: rgba(28, 36, 56, 0.85);
      --border-color: rgba(255, 255, 255, 0.08);
      --border-glow: rgba(56, 189, 248, 0.25);
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --accent-cyan: #38bdf8;
      --accent-blue: #3b82f6;
      --accent-purple: #a855f7;
      --accent-green: #10b981;
      --accent-red: #ef4444;
      --radius: 12px;
      --transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg-primary);
      color: var(--text-main);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
      background-image: 
        radial-gradient(circle at 15% 15%, rgba(56, 189, 248, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 85% 85%, rgba(168, 85, 247, 0.08) 0%, transparent 40%);
    }

    header {
      backdrop-filter: blur(16px);
      background: rgba(10, 13, 20, 0.8);
      border-bottom: 1px solid var(--border-color);
      padding: 1rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 50;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-weight: 700;
      font-size: 1.25rem;
      letter-spacing: -0.02em;
    }

    .brand-icon {
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
      width: 32px;
      height: 32px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1rem;
      box-shadow: 0 0 16px var(--border-glow);
    }

    .nav-links {
      display: flex;
      align-items: center;
      gap: 1rem;
    }

    .btn {
      padding: 0.5rem 1rem;
      border-radius: 8px;
      font-size: 0.875rem;
      font-weight: 500;
      cursor: pointer;
      transition: var(--transition);
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      text-decoration: none;
      border: 1px solid var(--border-color);
      background: var(--bg-surface);
      color: var(--text-main);
    }

    .btn:hover {
      background: var(--bg-surface-hover);
      border-color: var(--accent-cyan);
      transform: translateY(-1px);
    }

    .btn-primary {
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
      border: none;
      color: #000;
      font-weight: 600;
    }

    .btn-primary:hover {
      opacity: 0.9;
      box-shadow: 0 0 16px var(--border-glow);
    }

    .layout {
      display: flex;
      flex: 1;
      height: calc(100vh - 65px);
    }

    aside {
      width: 280px;
      background: var(--bg-surface);
      backdrop-filter: blur(12px);
      border-right: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      padding: 1.5rem 1rem;
      overflow-y: auto;
    }

    .section-title {
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 0.75rem;
      padding-left: 0.5rem;
    }

    .resource-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
      margin-bottom: 2rem;
    }

    .resource-item {
      padding: 0.65rem 0.85rem;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      transition: var(--transition);
      font-size: 0.9rem;
      color: var(--text-muted);
    }

    .resource-item:hover, .resource-item.active {
      background: var(--bg-surface-hover);
      color: var(--text-main);
      border-left: 3px solid var(--accent-cyan);
    }

    .badge {
      background: rgba(255, 255, 255, 0.06);
      padding: 0.15rem 0.5rem;
      border-radius: 12px;
      font-size: 0.75rem;
      font-family: 'JetBrains Mono', monospace;
    }

    main {
      flex: 1;
      padding: 2rem;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }

    .toolbar {
      background: var(--bg-surface);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 1rem 1.25rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
    }

    .search-box {
      flex: 1;
      min-width: 260px;
      position: relative;
    }

    .search-box input {
      width: 100%;
      padding: 0.6rem 1rem 0.6rem 2.5rem;
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      color: var(--text-main);
      font-size: 0.875rem;
      outline: none;
      transition: var(--transition);
    }

    .search-box input:focus {
      border-color: var(--accent-cyan);
      box-shadow: 0 0 12px rgba(56, 189, 248, 0.2);
    }

    .search-icon {
      position: absolute;
      left: 0.85rem;
      top: 50%;
      transform: translateY(-50%);
      color: var(--text-muted);
      font-size: 0.875rem;
    }

    .query-builder {
      display: flex;
      gap: 0.75rem;
      align-items: center;
      flex-wrap: wrap;
    }

    .query-builder input, .query-builder select {
      padding: 0.5rem 0.75rem;
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid var(--border-color);
      border-radius: 6px;
      color: var(--text-main);
      font-size: 0.8rem;
      outline: none;
    }

    .card {
      background: var(--bg-surface);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 1.5rem;
      overflow: hidden;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.875rem;
    }

    th {
      padding: 0.85rem 1rem;
      border-bottom: 1px solid var(--border-color);
      color: var(--text-muted);
      font-weight: 600;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    td {
      padding: 0.85rem 1rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.03);
      vertical-align: middle;
      font-family: 'JetBrains Mono', monospace;
    }

    tr:hover td {
      background: rgba(255, 255, 255, 0.02);
    }

    pre {
      background: rgba(0, 0, 0, 0.35);
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      color: #38bdf8;
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
    }

    .pill-green { background: rgba(16, 185, 129, 0.15); color: #34d399; }
    .pill-blue { background: rgba(56, 189, 248, 0.15); color: #38bdf8; }

    #loading {
      text-align: center;
      padding: 3rem;
      color: var(--text-muted);
      font-size: 0.9rem;
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="brand-icon">⚡</div>
      <span>mock-api Studio</span>
      <span class="status-pill pill-green">Online</span>
    </div>
    <div class="nav-links">
      <a href="/docs" target="_blank" class="btn">📖 Swagger Docs</a>
      <a href="/" target="_blank" class="btn">📡 Root JSON</a>
    </div>
  </header>

  <div class="layout">
    <aside>
      <div class="section-title">Collections</div>
      <ul id="collections-list" class="resource-list"></ul>

      <div class="section-title">Singletons</div>
      <ul id="singletons-list" class="resource-list"></ul>
    </aside>

    <main>
      <div class="toolbar">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input type="text" id="global-search" placeholder="Full-text search (q=)..." />
        </div>
        <div class="query-builder">
          <input type="text" id="sort-field" placeholder="Sort by field..." style="width: 120px;" />
          <select id="sort-order">
            <option value="asc">ASC</option>
            <option value="desc">DESC</option>
          </select>
          <button class="btn btn-primary" onclick="applyQuery()">Run Query</button>
          <button class="btn" onclick="toggleView()" id="view-toggle-btn">Toggle JSON</button>
        </div>
      </div>

      <div class="card" id="data-container">
        <div id="loading">Select a resource from the sidebar to inspect data...</div>
      </div>
    </main>
  </div>

  <script>
    let currentResource = null;
    let isSingleton = false;
    let currentData = null;
    let showRawJson = false;

    async function loadResources() {
      try {
        const res = await fetch('/');
        const data = await res.json();
        
        const colList = document.getElementById('collections-list');
        colList.innerHTML = '';
        const cols = data.resources.collections || {};
        const colKeys = Object.keys(cols);

        colKeys.forEach((key, idx) => {
          const li = document.createElement('li');
          li.className = 'resource-item' + (idx === 0 ? ' active' : '');
          li.innerHTML = `<span>/${key}</span><span class="badge">${cols[key]}</span>`;
          li.onclick = () => selectResource(key, false, li);
          colList.appendChild(li);
        });

        const sinList = document.getElementById('singletons-list');
        sinList.innerHTML = '';
        const sins = data.resources.singletons || [];
        sins.forEach(key => {
          const li = document.createElement('li');
          li.className = 'resource-item';
          li.innerHTML = `<span>/${key}</span><span class="badge">object</span>`;
          li.onclick = () => selectResource(key, true, li);
          sinList.appendChild(li);
        });

        if (colKeys.length > 0) {
          selectResource(colKeys[0], false, colList.children[0]);
        }
      } catch (err) {
        document.getElementById('data-container').innerHTML = `<div style="color: var(--accent-red)">Failed to load resources: ${err.message}</div>`;
      }
    }

    async function selectResource(name, isSingle, elem) {
      currentResource = name;
      isSingleton = isSingle;

      document.querySelectorAll('.resource-item').forEach(el => el.classList.remove('active'));
      if (elem) elem.classList.add('active');

      applyQuery();
    }

    async function applyQuery() {
      if (!currentResource) return;

      const container = document.getElementById('data-container');
      container.innerHTML = '<div id="loading">Fetching data...</div>';

      const q = document.getElementById('global-search').value.trim();
      const sort = document.getElementById('sort-field').value.trim();
      const order = document.getElementById('sort-order').value;

      let url = `/${currentResource}`;
      const params = new URLSearchParams();
      if (!isSingleton) {
        if (q) params.append('q', q);
        if (sort) {
          params.append('_sort', sort);
          params.append('_order', order);
        }
      }

      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      try {
        const res = await fetch(url);
        const data = await res.json();
        currentData = data;
        renderData();
      } catch (err) {
        container.innerHTML = `<div style="color: var(--accent-red)">Error loading ${url}: ${err.message}</div>`;
      }
    }

    function toggleView() {
      showRawJson = !showRawJson;
      document.getElementById('view-toggle-btn').innerText = showRawJson ? 'Show Table' : 'Show JSON';
      renderData();
    }

    function renderData() {
      const container = document.getElementById('data-container');
      if (!currentData) return;

      if (showRawJson || isSingleton || !Array.isArray(currentData) || currentData.length === 0) {
        container.innerHTML = `<pre>${JSON.stringify(currentData, null, 2)}</pre>`;
        return;
      }

      // Render Table
      const headers = Object.keys(currentData[0]);
      let html = `<table><thead><tr>`;
      headers.forEach(h => html += `<th>${h}</th>`);
      html += `</tr></thead><tbody>`;

      currentData.forEach(row => {
        html += `<tr>`;
        headers.forEach(h => {
          let val = row[h];
          if (typeof val === 'object' && val !== null) val = JSON.stringify(val);
          html += `<td>${val !== undefined ? val : ''}</td>`;
        });
        html += `</tr>`;
      });
      html += `</tbody></table>`;
      container.innerHTML = html;
    }

    document.getElementById('global-search').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') applyQuery();
    });

    loadResources();
  </script>
</body>
</html>
"""


def create_admin_router() -> APIRouter:
    """Creates the FastAPI router mounting the /_admin dashboard."""
    router = APIRouter(include_in_schema=False)

    @router.get("/_admin", response_class=HTMLResponse)
    async def admin_dashboard():
        return HTMLResponse(content=get_admin_html())

    return router
