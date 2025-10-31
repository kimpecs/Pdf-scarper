export function setLoadingState(loading) {
  const btn = document.getElementById('searchBtn');
  if (!btn) return;
  btn.disabled = loading;
  btn.innerHTML = loading ? '<div class="spinner"></div>' : '<i class="fas fa-search"></i> Search';
}

export function displayError(message) {
  const container = document.getElementById('results');
  if (!container) return;
  container.innerHTML = `
    <div class="error-state">
      <i class="fas fa-exclamation-triangle fa-2x"></i>
      <h3>${message}</h3>
    </div>`;
}

export function updateBreadcrumb(app) {
  const breadcrumb = document.getElementById('breadcrumb');
  if (!breadcrumb) return;
  const filters = Object.entries(app.filters)
    .filter(([k, v]) => v && k !== 'content_type')
    .map(([k, v]) => `${k}: ${v}`);
  breadcrumb.textContent = filters.length
    ? `Search Results (${filters.join(', ')})`
    : 'All Content';
}
