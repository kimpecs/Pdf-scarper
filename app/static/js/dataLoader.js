import { displayError } from './utils.js';
import { displayTechnicalGuides } from './guides.js';

export async function loadInitialData(app) {
  try {
    await Promise.all([
      loadCatalogs(app),
      loadCategories(app),
      loadPartTypes(app),
      loadTechnicalGuides(app)
    ]);
  } catch (error) {
    console.error('Error loading initial data:', error);
    displayError('Failed to connect to backend. Please ensure it’s running.');
  }
}

export async function loadCatalogs(app) {
  const res = await fetch('/catalogs');
  if (!res.ok) throw new Error('Failed to load catalogs');
  const data = await res.json();
  app.catalogData = Object.fromEntries(data.catalogs.map(c => [c.name, c]));
  const select = document.getElementById('catalog_type');
  select.innerHTML = '<option value="">All Catalogs</option>' +
    data.catalogs.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
}

export async function loadCategories(app) {
  const res = await fetch('/categories');
  if (!res.ok) throw new Error('Failed to load categories');
  const data = await res.json();
  app.allCategories = data.categories || [];
  const select = document.getElementById('category');
  select.innerHTML = '<option value="">All Categories</option>' +
    app.allCategories.map(c => `<option value="${c}">${c}</option>`).join('');
}

export async function loadPartTypes(app) {
  const res = await fetch('/part_types');
  if (!res.ok) throw new Error('Failed to load part types');
  const data = await res.json();
  const select = document.getElementById('part_type');
  select.innerHTML = '<option value="">All Part Types</option>' +
    (data.part_types || []).map(t => `<option value="${t}">${t}</option>`).join('');
}

export async function loadTechnicalGuides(app) {
  try {
    const res = await fetch('/technical-guides');
    if (res.ok) {
      const data = await res.json();
      displayTechnicalGuides(app, data.guides || []);
    }
  } catch {
    console.warn('Technical guides unavailable.');
  }
}
