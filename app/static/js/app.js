console.log('Knowledge Base App loading...');

class KnowledgeBaseApp {
  constructor() {
    this.currentView = 'grid';
    this.filters = {
      q: '',
      category: '',
      part_type: '',
      catalog_type: '',
      content_type: 'all'
    };
    this.config = {
      maxDescriptionLength: 120,
      maxApplicationsDisplay: 2,
      searchDebounceMs: 300,
      enableTechnicalGuides: true,
      maxSearchResults: 50
    };
    
    console.log('App initialized, loading data...');
    this.init();
  }

  async init() {
    await this.loadConfig();
    await this.loadInitialData();
    this.setupEventListeners();
    await this.performSearch();
  }

  async loadConfig() {
    try {
      const response = await fetch('/api/config');
      if (response.ok) {
        const config = await response.json();
        this.config = { ...this.config, ...config };
        console.log('Config loaded:', this.config);
      }
    } catch (error) {
      console.error('Error loading config:', error);
    }
  }

  async loadInitialData() {
    console.log('Loading initial data...');
    
    try {
      // Load catalogs
      const catalogsResponse = await fetch('/catalogs');
      if (catalogsResponse.ok) {
        const catalogsData = await catalogsResponse.json();
        this.populateSelect('catalog_type', catalogsData.catalogs, 'name');
        console.log('Catalogs loaded:', catalogsData.catalogs.length);
      }

      // Load categories
      const categoriesResponse = await fetch('/categories');
      if (categoriesResponse.ok) {
        const categoriesData = await categoriesResponse.json();
        this.populateSelect('category', categoriesData.categories);
        console.log('Categories loaded:', categoriesData.categories.length);
      }

      // Load part types
      const partTypesResponse = await fetch('/part_types');
      if (partTypesResponse.ok) {
        const partTypesData = await partTypesResponse.json();
        this.populateSelect('part_type', partTypesData.part_types);
        console.log('Part types loaded:', partTypesData.part_types.length);
      }

    } catch (error) {
      console.error('Error loading initial data:', error);
    }
  }

  populateSelect(selectId, data, nameKey = null) {
    const select = document.getElementById(selectId);
    if (!select) {
      console.error('Select element not found:', selectId);
      return;
    }

    // Keep the first option (All)
    const firstOption = select.options[0];
    select.innerHTML = '';
    select.appendChild(firstOption);

    // Add new options
    data.forEach(item => {
      const value = nameKey ? item[nameKey] : item;
      const text = nameKey ? item[nameKey] : item;
      const option = new Option(text, value);
      select.appendChild(option);
    });

    console.log(`Populated ${selectId} with ${data.length} items`);
  }

  setupEventListeners() {
    // Search button
    const searchBtn = document.getElementById('searchBtn');
    if (searchBtn) {
      searchBtn.addEventListener('click', () => this.performSearch());
    }

    // Show all button
    const showAllBtn = document.getElementById('showAll');
    if (showAllBtn) {
      showAllBtn.addEventListener('click', () => {
        this.filters = { q: '', category: '', part_type: '', catalog_type: '', content_type: 'all' };
        this.performSearch();
      });
    }

    // Reset filters button
    const resetBtn = document.getElementById('resetFilters');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        this.filters = { q: '', category: '', part_type: '', catalog_type: '', content_type: 'all' };
        document.getElementById('catalog_type').value = '';
        document.getElementById('category').value = '';
        document.getElementById('part_type').value = '';
        document.getElementById('content_type').value = 'all';
        document.getElementById('q').value = '';
        this.performSearch();
      });
    }

    // Filter changes
    ['catalog_type', 'category', 'part_type', 'content_type'].forEach(id => {
      const element = document.getElementById(id);
      if (element) {
        element.addEventListener('change', (e) => {
          this.filters[id] = e.target.value;
          this.performSearch();
        });
      }
    });

    // Search input with debounce
    const searchInput = document.getElementById('q');
    if (searchInput) {
      let timeout;
      searchInput.addEventListener('input', (e) => {
        this.filters.q = e.target.value;
        clearTimeout(timeout);
        timeout = setTimeout(() => this.performSearch(), this.config.searchDebounceMs);
      });
    }

    console.log('Event listeners setup complete');
  }

  async performSearch() {
    console.log('Performing search with filters:', this.filters);
    
    try {
      const params = new URLSearchParams();
      Object.entries(this.filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      params.set('limit', this.config.maxSearchResults);

      const response = await fetch(`/search?${params}`);
      if (!response.ok) throw new Error('Search failed');
      
      const data = await response.json();
      console.log('Search results:', data.results.length, 'items');
      this.displayResults(data);
      
    } catch (error) {
      console.error('Search error:', error);
      this.displayError('Search failed: ' + error.message);
    }
  }

  displayResults(data) {
    const container = document.getElementById('results');
    if (!container) return;

    if (!data.results || data.results.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <i class="fas fa-search fa-3x"></i>
          <h3>No results found</h3>
          <p>Try adjusting your search or filters.</p>
        </div>`;
      return;
    }

    // Simple grid display
    container.className = 'results-grid';
    container.innerHTML = data.results.map(part => `
      <div class="part-card">
        <div class="part-header">
          <div class="part-number">${part.part_number}</div>
          <span class="catalog-badge ${part.catalog_type}">${part.catalog_type}</span>
        </div>
        <div class="part-meta">
          <div><i class="fas fa-tag"></i> ${part.part_type || 'N/A'}</div>
          <div><i class="fas fa-folder"></i> ${part.category || 'N/A'}</div>
        </div>
        <div class="part-description">${part.description || 'No description'}</div>
        ${part.applications && part.applications.length ? `
          <div class="part-applications">
            <strong>Applications:</strong> ${part.applications.slice(0, 2).join(', ')}
          </div>
        ` : ''}
      </div>
    `).join('');

    console.log('Results displayed:', data.results.length, 'items');
  }

  displayError(message) {
    const container = document.getElementById('results');
    if (!container) return;
    container.innerHTML = `
      <div class="error-state">
        <i class="fas fa-exclamation-triangle fa-2x"></i>
        <h3>${message}</h3>
      </div>`;
  }
}

// Initialize app
console.log('Starting app initialization...');
document.addEventListener('DOMContentLoaded', () => {
  console.log('DOM loaded, creating app instance...');
  window.app = new KnowledgeBaseApp();
});