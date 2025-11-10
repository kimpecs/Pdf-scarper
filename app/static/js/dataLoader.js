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
    displayError('Failed to connect to backend. Please ensure it\'s running.');
  }
}

export async function loadCatalogs(app) {
  try {
    const res = await fetch('/catalogs');
    if (!res.ok) throw new Error('Failed to load catalogs');
    const data = await res.json();
    
    // Debug log
    console.log('Catalogs API response:', data);
    
    const select = document.getElementById('catalog_type');
    if (select) {
      select.innerHTML = '<option value="">All Catalogs</option>' +
        data.catalogs.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
      console.log('Catalogs dropdown populated');
    }
  } catch (error) {
    console.error('Error loading catalogs:', error);
  }
}

export async function loadCategories(app) {
  try {
    const res = await fetch('/categories');
    if (!res.ok) throw new Error('Failed to load categories');
    const data = await res.json();
    
    // Debug log
    console.log('Categories API response:', data);
    
    const select = document.getElementById('category');
    if (select) {
      select.innerHTML = '<option value="">All Categories</option>' +
        data.categories.map(c => `<option value="${c}">${c}</option>`).join('');
      console.log('Categories dropdown populated');
    }
  } catch (error) {
    console.error('Error loading categories:', error);
  }
}

export async function loadPartTypes(app) {
  try {
    const res = await fetch('/part_types');
    if (!res.ok) throw new Error('Failed to load part types');
    const data = await res.json();
    
    // Debug log
    console.log('Part Types API response:', data);
    
    const select = document.getElementById('part_type');
    if (select) {
      select.innerHTML = '<option value="">All Part Types</option>' +
        data.part_types.map(t => `<option value="${t}">${t}</option>`).join('');
      console.log('Part Types dropdown populated');
    }
  } catch (error) {
    console.error('Error loading part types:', error);
  }
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