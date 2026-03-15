/* ════════════════════════════════════════════════════════
   LARRY — LIG Parts Intelligence Frontend
   Talks to FastAPI backend at /api/*
   ════════════════════════════════════════════════════════ */

'use strict';

/* ── Toast helper ──────────────────────────────────────── */
function toast(msg, type = 'info', duration = 3200) {
  const stack = document.getElementById('toastStack');
  if (!stack) return;
  const el = document.createElement('div');
  el.className = `toast toast--${type}`;
  const icons = { success: 'fa-circle-check', error: 'fa-triangle-exclamation', warn: 'fa-exclamation', info: 'fa-circle-info' };
  el.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i><span>${msg}</span>`;
  stack.appendChild(el);
  setTimeout(() => {
    el.classList.add('removing');
    setTimeout(() => el.remove(), 250);
  }, duration);
}

/* ── DOM refs ───────────────────────────────────────────── */
const $ = id => document.getElementById(id);

/* ════════════════════════════════════════════════════════
   MAIN APP CLASS
   ════════════════════════════════════════════════════════ */
class LarryApp {
  constructor() {
    this.filters = { q: '', catalog_type: '', category: '', part_type: '' };
    this.viewMode = 'grid';   // 'grid' | 'list'
    this.debounceTimer = null;
    this.currentPartId = null;
    this.config = { searchDebounceMs: 300, maxSearchResults: 50 };
    this.abortController = null;

    this._bindUI();
    this._init();
  }

  /* ── Bootstrap ──────────────────────────────────────── */
  async _init() {
    await Promise.all([
      this._loadConfig(),
      this._loadDropdowns(),
      this._checkHealth(),
    ]);
    this._search();
  }

  async _loadConfig() {
    try {
      const r = await fetch('/api/config');
      if (r.ok) Object.assign(this.config, await r.json());
    } catch (_) { /* silently continue with defaults */ }
  }

  async _checkHealth() {
    const dot = document.querySelector('.dot');
    const label = $('health-dot')?.querySelector('.health-label');
    try {
      const r = await fetch('/health');
      const healthy = r.ok;
      if (dot) dot.className = `dot dot--${healthy ? 'healthy' : 'error'}`;
      if (label) label.textContent = healthy ? 'Online' : 'Offline';
    } catch (_) {
      if (dot) dot.className = 'dot dot--error';
      if (label) label.textContent = 'Offline';
    }
  }

  async _loadDropdowns() {
    const [catalogs, categories, partTypes] = await Promise.allSettled([
      fetch('/api/analytics/catalogs').then(r => r.json()),
      fetch('/api/analytics/categories').then(r => r.json()),
      fetch('/api/parts/types').then(r => r.json()),
    ]);

    if (catalogs.status === 'fulfilled') {
      this._populateSelect('catalog_type', catalogs.value, item => ({
        value: item.catalog_name,
        label: `${item.catalog_name} (${item.part_count})`,
      }));
    }
    if (categories.status === 'fulfilled') {
      this._populateSelect('category', categories.value, item => ({
        value: item.category,
        label: `${item.category} (${item.part_count})`,
      }));
    }
    if (partTypes.status === 'fulfilled') {
      const types = partTypes.value.part_types || [];
      this._populateSelect('part_type', types, item => ({ value: item, label: item }));
    }
  }

  _populateSelect(id, data, mapper) {
    const sel = $(id);
    if (!sel || !Array.isArray(data)) return;
    const first = sel.options[0];
    sel.innerHTML = '';
    sel.appendChild(first);
    data.forEach(item => {
      const { value, label } = mapper(item);
      if (!value) return;
      sel.appendChild(new Option(label, value));
    });
  }

  /* ── Event bindings ─────────────────────────────────── */
  _bindUI() {
    // Search input (debounced)
    $('q')?.addEventListener('input', e => {
      this.filters.q = e.target.value.trim();
      const clear = $('clearSearch');
      if (clear) clear.classList.toggle('visible', this.filters.q.length > 0);
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => this._search(), this.config.searchDebounceMs);
    });

    $('clearSearch')?.addEventListener('click', () => {
      $('q').value = '';
      this.filters.q = '';
      $('clearSearch').classList.remove('visible');
      this._search();
    });

    // Filter selects
    ['catalog_type', 'category', 'part_type'].forEach(id => {
      $(id)?.addEventListener('change', e => {
        this.filters[id] = e.target.value;
        this._search();
      });
    });

    // Reset
    $('resetFilters')?.addEventListener('click', () => {
      this.filters = { q: '', catalog_type: '', category: '', part_type: '' };
      $('q').value = '';
      $('catalog_type').value = '';
      $('category').value = '';
      $('part_type').value = '';
      $('clearSearch')?.classList.remove('visible');
      this._search();
    });

    // Show all
    $('showAll')?.addEventListener('click', () => {
      this.filters = { q: '', catalog_type: '', category: '', part_type: '' };
      $('q').value = '';
      $('catalog_type').value = '';
      $('category').value = '';
      $('part_type').value = '';
      this._search();
    });

    // View toggle
    $('viewGrid')?.addEventListener('click', () => this._setView('grid'));
    $('viewList')?.addEventListener('click', () => this._setView('list'));

    // Retry button
    $('retryBtn')?.addEventListener('click', () => this._search());

    // Detail close
    $('detailBack')?.addEventListener('click', () => this._closeDetail());
    $('detailOverlay')?.addEventListener('click', e => {
      if (e.target === $('detailOverlay')) this._closeDetail();
    });

    // Keyboard: Escape closes detail
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !$('detailOverlay')?.classList.contains('hidden')) {
        this._closeDetail();
      }
    });
  }

  _setView(mode) {
    this.viewMode = mode;
    $('viewGrid')?.classList.toggle('active', mode === 'grid');
    $('viewList')?.classList.toggle('active', mode === 'list');
    const results = $('results');
    if (results) {
      results.className = mode === 'grid' ? 'results-grid' : 'results-list';
    }
  }

  /* ── Search ─────────────────────────────────────────── */
  async _search() {
    // Cancel in-flight request
    if (this.abortController) this.abortController.abort();
    this.abortController = new AbortController();

    this._showState('loading');

    const params = new URLSearchParams();
    Object.entries(this.filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    params.set('limit', this.config.maxSearchResults);

    try {
      const r = await fetch(`/api/search?${params}`, { signal: this.abortController.signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      this._renderResults(data);
    } catch (err) {
      if (err.name === 'AbortError') return;
      console.error('Search error:', err);
      this._showState('error');
      $('errorMsg').textContent = `Search failed: ${err.message}`;
    }
  }

  /* ── Render results ─────────────────────────────────── */
  _renderResults(data) {
    const results = data.results || [];
    const count = data.count ?? results.length;

    // Update stat counters
    const countText = $('countText');
    if (countText) {
      countText.innerHTML = results.length
        ? `<strong>${count}</strong> result${count !== 1 ? 's' : ''}${this.filters.q ? ` for "<em>${this._esc(this.filters.q)}</em>"` : ''}`
        : 'No results';
    }

    // Update sidebar stat
    const stat = $('stat-parts');
    if (stat) stat.textContent = `${count} part${count !== 1 ? 's' : ''} found`;

    if (!results.length) {
      this._showState('empty');
      return;
    }

    this._showState('results');
    const container = $('results');
    container.className = this.viewMode === 'grid' ? 'results-grid' : 'results-list';
    container.innerHTML = results.map(p => this._cardHTML(p)).join('');

    // Attach click handlers
    container.querySelectorAll('.part-card').forEach(card => {
      card.addEventListener('click', () => this._openDetail(parseInt(card.dataset.id, 10)));
    });
  }

  _cardHTML(p) {
    const apps = this._parseList(p.applications);
    const appText = apps.length ? apps.slice(0, 2).join(' · ') : '';
    return `
      <div class="part-card" data-id="${p.id}" role="button" tabindex="0">
        <div class="card-header">
          <div class="card-part-number">${this._esc(p.part_number)}</div>
          ${p.catalog_name ? `<span class="catalog-badge">${this._esc(p.catalog_name)}</span>` : ''}
        </div>
        <div class="card-description">${this._esc(p.description || 'No description available')}</div>
        <div class="card-meta">
          ${p.part_type  ? `<span class="meta-pill meta-pill--type">${this._esc(p.part_type)}</span>` : ''}
          ${p.category   ? `<span class="meta-pill">${this._esc(p.category)}</span>` : ''}
          ${p.catalog_type ? `<span class="meta-pill meta-pill--catalog">${this._esc(p.catalog_type)}</span>` : ''}
        </div>
        ${appText ? `<div class="card-applications"><i class="fas fa-truck" style="color:var(--blue-ocean);margin-right:.3rem;font-size:.7rem"></i>${this._esc(appText)}</div>` : ''}
      </div>`;
  }

  /* ── Detail panel ───────────────────────────────────── */
  async _openDetail(partId) {
    this.currentPartId = partId;
    const overlay = $('detailOverlay');
    overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // Reset panel
    $('dTitlePartNumber').textContent = '…';
    $('dDescription').textContent = '';
    $('imagePlaceholder').classList.remove('hidden');
    $('detailImage').classList.add('hidden');
    ['sectionApplications','sectionSpecs','sectionOE','sectionFeatures','sectionGuides']
      .forEach(id => $(id)?.classList.add('hidden'));

    try {
      const [partResp, guidesResp] = await Promise.all([
        fetch(`/api/parts/${partId}`),
        fetch(`/api/parts/${partId}/guides`),
      ]);

      if (!partResp.ok) throw new Error('Part not found');
      const part = await partResp.json();
      const guides = guidesResp.ok ? await guidesResp.json() : [];

      this._fillDetail(part, guides);

      // Try to load image
      const img = $('detailImage');
      img.src = `/api/images/${partId}`;
      img.onload = () => {
        $('imagePlaceholder').classList.add('hidden');
        img.classList.remove('hidden');
      };
      img.onerror = () => { /* keep placeholder */ };

    } catch (err) {
      toast(`Could not load part: ${err.message}`, 'error');
      this._closeDetail();
    }
  }

  _fillDetail(p, guides) {
    // Header
    $('dTitlePartNumber').textContent = p.part_number || '—';
    $('dTitleCatalog').textContent = p.catalog_name || '';
    $('dDescription').textContent = p.description || 'No description available.';
    $('detailBreadcrumb').textContent = [p.catalog_name, p.category, p.part_type].filter(Boolean).join(' › ');

    // Sidebar meta
    $('dPartNumber').textContent = p.part_number || '—';
    $('dCatalog').textContent    = p.catalog_name || '—';
    $('dCategory').textContent   = p.category || '—';
    $('dPartType').textContent   = p.part_type || '—';
    $('dPage').textContent       = p.page ?? '—';

    // Applications
    const apps = this._parseList(p.applications);
    if (apps.length) {
      $('dApplications').innerHTML = apps.map(a => `<span class="app-tag">${this._esc(a)}</span>`).join('');
      $('sectionApplications').classList.remove('hidden');
    }

    // Specifications
    const specs = this._parseSpecs(p.specifications);
    if (specs.length) {
      $('dSpecsBody').innerHTML = specs.map(([k, v]) =>
        `<tr><td>${this._esc(k)}</td><td>${this._esc(v)}</td></tr>`
      ).join('');
      $('sectionSpecs').classList.remove('hidden');
    }

    // OE Numbers
    const oes = this._parseList(p.oe_numbers);
    if (oes.length) {
      $('dOENumbers').innerHTML = oes.map(n => `<span class="oe-tag">${this._esc(n)}</span>`).join('');
      $('sectionOE').classList.remove('hidden');
    }

    // Features
    const feats = this._parseList(p.features);
    if (feats.length) {
      $('dFeatures').innerHTML = feats.map(f => `<div class="feature-item">${this._esc(f)}</div>`).join('');
      $('sectionFeatures').classList.remove('hidden');
    }

    // Technical guides
    if (guides.length) {
      $('dGuides').innerHTML = guides.map(g => `
        <div class="guide-card">
          <i class="fas fa-book-open"></i>
          <div>
            <div class="guide-name">${this._esc(g.display_name || g.guide_name)}</div>
            ${g.description ? `<div class="guide-desc">${this._esc(g.description)}</div>` : ''}
          </div>
        </div>`).join('');
      $('sectionGuides').classList.remove('hidden');
    }
  }

  _closeDetail() {
    $('detailOverlay').classList.add('hidden');
    document.body.style.overflow = '';
    this.currentPartId = null;
  }

  /* ── State management ───────────────────────────────── */
  _showState(state) {
    $('stateLoading').classList.toggle('hidden', state !== 'loading');
    $('stateEmpty').classList.toggle('hidden', state !== 'empty');
    $('stateError').classList.toggle('hidden', state !== 'error');
    $('results').classList.toggle('hidden', state !== 'results');
    $('resultsToolbar').classList.toggle('hidden', state === 'loading');
  }

  /* ── Parsers ────────────────────────────────────────── */
  _parseList(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw.filter(Boolean);
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed.filter(Boolean);
    } catch (_) {}
    return raw.split(/[,;\n]+/).map(s => s.trim()).filter(Boolean);
  }

  _parseSpecs(raw) {
    if (!raw) return [];
    try {
      const obj = JSON.parse(raw);
      if (typeof obj === 'object' && !Array.isArray(obj)) {
        return Object.entries(obj);
      }
    } catch (_) {}
    // Try "Key: Value" lines
    return raw.split('\n').map(line => {
      const idx = line.indexOf(':');
      if (idx > 0) return [line.slice(0, idx).trim(), line.slice(idx + 1).trim()];
      return null;
    }).filter(Boolean);
  }

  /* ── Security ───────────────────────────────────────── */
  _esc(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
}

/* ── Boot ──────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  window.larry = new LarryApp();
});
