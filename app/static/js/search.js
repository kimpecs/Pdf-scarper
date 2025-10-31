import { setLoadingState, displayError } from './utils.js';
import { createResultCard } from './ui.js';

export async function performSearch(app) {
  setLoadingState(true);
  try {
    const params = new URLSearchParams();
    Object.entries(app.filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    params.set('limit', app.config.maxSearchResults);
    const res = await fetch(`/search?${params}`);
    if (!res.ok) throw new Error('Search failed');
    const data = await res.json();
    app.lastResults = data;
    displayResults(app, data);
  } catch (e) {
    console.error('Search error:', e);
    displayError('Search failed. Check backend connection.');
  } finally {
    setLoadingState(false);
  }
}

export function displayResults(app, data) {
  const container = document.getElementById('results');
  if (!container) return;
  if (!data.results?.length) {
    container.innerHTML = `
      <div class="empty-state">
        <i class="fas fa-search fa-3x"></i>
        <h3>No results found</h3>
        <p>Try adjusting your filters.</p>
      </div>`;
    return;
  }
  const isGridView = app.currentView === 'grid';
  container.className = isGridView ? 'results-grid' : 'results-list';
  container.innerHTML = data.results.map(p => createResultCard(app, p, isGridView)).join('');
}
