import { performSearch } from './search.js';
import { searchTechnicalGuides } from './guides.js';

export function bindUIEvents(app) {
  const q = document.getElementById('q');
  const filters = ['catalog_type', 'category', 'part_type', 'content_type'];

  document.getElementById('searchBtn')?.addEventListener('click', () => performSearch(app));
  document.getElementById('showAll')?.addEventListener('click', () => performSearch(app));
  document.getElementById('resetFilters')?.addEventListener('click', () => resetFilters(app));

  filters.forEach(id => {
    document.getElementById(id)?.addEventListener('change', (e) => {
      app.filters[id] = e.target.value;
      performSearch(app);
    });
  });

  // Debounced search input
  let t;
  q?.addEventListener('input', (e) => {
    app.filters.q = e.target.value;
    clearTimeout(t);
    t = setTimeout(() => performSearch(app), app.config.searchDebounceMs);
  });
}

export function setupViewControls(app) {
  document.querySelectorAll('.view-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
      e.currentTarget.classList.add('active');
      app.currentView = e.currentTarget.dataset.view;
      performSearch(app);
    });
  });
}

export function resetFilters(app) {
  app.filters = { q: '', category: '', part_type: '', catalog_type: '', content_type: 'all' };
  ['q', 'category', 'part_type', 'catalog_type', 'content_type'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = id === 'content_type' ? 'all' : '';
  });
  performSearch(app);
}

export function createResultCard(app, part, isGrid) {
  const gridClass = isGrid ? '' : 'list-view';
  const image = part.image_url ? `data-image="${part.image_url}"` : '';
  const pdf = part.pdf_url ? `<a href="${part.pdf_url}" class="btn-action btn-pdf" target="_blank"><i class="fas fa-file-pdf"></i> PDF</a>` : '';

  const desc = part.description
    ? (part.description.length > app.config.maxDescriptionLength
      ? part.description.slice(0, app.config.maxDescriptionLength) + '...'
      : part.description)
    : 'No description available';

  const guide = app.config.enableTechnicalGuides
    ? `<button class="btn-action btn-guide" data-category="${part.category}"><i class="fas fa-book"></i> Guide</button>`
    : '';

  const apps = part.applications?.length
    ? `<div class="part-applications"><strong>Applications:</strong> ${part.applications.slice(0, app.config.maxApplicationsDisplay).join(', ')}</div>`
    : '';

  return `
    <div class="part-card ${gridClass}" data-part-id="${part.id}">
      <div class="part-header">
        <div class="part-number">${part.part_number}</div>
        <div class="badge-container">
          <span class="catalog-badge ${part.catalog_type}">${part.catalog_type}</span>
        </div>
      </div>
      <div class="part-meta">
        <div><i class="fas fa-tag"></i> ${part.part_type || 'N/A'}</div>
        <div><i class="fas fa-folder"></i> ${part.category || 'N/A'}</div>
        <div><i class="fas fa-file"></i> Page ${part.page}</div>
      </div>
      <div class="part-description">${desc}</div>
      ${apps}
      <div class="part-actions">
        ${part.image_url ? `<button class="btn-action btn-image" ${image}><i class="fas fa-image"></i> Image</button>` : ''}
        ${pdf}
        ${guide}
      </div>
    </div>`;
}
