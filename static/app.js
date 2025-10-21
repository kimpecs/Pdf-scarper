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
    this.catalogData = {};
    this.lastResults = { results: [] };
    this.init();
  }

  init() {
    this.bindEvents();
    this.loadInitialData();
    this.setupViewControls();
  }

  bindEvents() {
    // Buttons
    document.getElementById('searchBtn')?.addEventListener('click', () => this.performSearch());
    document.getElementById('showAll')?.addEventListener('click', () => this.showAll());
    document.getElementById('resetFilters')?.addEventListener('click', () => this.resetFilters());

    // Filter change events
    document.getElementById('catalog_type')?.addEventListener('change', (e) => {
      this.filters.catalog_type = e.target.value;
      this.updateCategoryFilter();
      this.performSearch();
    });

    document.getElementById('category')?.addEventListener('change', (e) => {
      this.filters.category = e.target.value;
      this.performSearch();
    });

    document.getElementById('part_type')?.addEventListener('change', (e) => {
      this.filters.part_type = e.target.value;
      this.performSearch();
    });

    document.getElementById('content_type')?.addEventListener('change', (e) => {
      this.filters.content_type = e.target.value;
      this.performSearch();
    });

    // Search input with debounce
    let searchTimeout;
    document.getElementById('q')?.addEventListener('input', (e) => {
      this.filters.q = e.target.value;
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => this.performSearch(), 300);
    });

    // Modal events
    document.getElementById('pdfModalClose')?.addEventListener('click', () => this.closePdfModal());
    document.getElementById('popupClose')?.addEventListener('click', () => this.closeImagePopup());
    document.getElementById('imagePopup')?.addEventListener('click', (e) => {
      if (e.target === e.currentTarget) this.closeImagePopup();
    });

    // Sidebar toggle for mobile
    document.getElementById('sidebarToggle')?.addEventListener('click', () => {
      document.querySelector('.sidebar')?.classList.toggle('active');
    });
  }

  setupViewControls() {
    document.querySelectorAll('.view-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.currentView = e.currentTarget.dataset.view;
        this.updateView();
      });
    });
  }

  async loadInitialData() {
    try {
      await Promise.all([
        this.loadCatalogs(),
        this.loadCategories(),
        this.loadPartTypes(),
        this.loadTechnicalGuides()
      ]);
      this.performSearch(); // Initial load
    } catch (error) {
      console.error('Error loading initial data:', error);
      this.displayError('Error connecting to server. Please check if the backend is running.');
    }
  }

  async loadCatalogs() {
    try {
      const response = await fetch('/catalogs');
      if (!response.ok) throw new Error('Failed to fetch catalogs');
      
      const data = await response.json();
      this.catalogData = data.catalogs.reduce((acc, catalog) => {
        acc[catalog.name] = catalog;
        return acc;
      }, {});
      
      const select = document.getElementById('catalog_type');
      select.innerHTML = '<option value="">All Catalogs</option>';
      data.catalogs.forEach(catalog => {
        select.innerHTML += `<option value="${catalog.name}">${catalog.name}</option>`;
      });
    } catch (error) {
      console.error('Error loading catalogs:', error);
      // rethrow so loadInitialData can handle
      throw error;
    }
  }

  async loadCategories() {
    try {
      const response = await fetch('/categories');
      if (!response.ok) throw new Error('Failed to fetch categories');
      
      const data = await response.json();
      this.allCategories = data.categories || [];
      this.updateCategoryFilter();
    } catch (error) {
      console.error('Error loading categories:', error);
      throw error;
    }
  }

  async loadPartTypes() {
    try {
      const response = await fetch('/part_types');
      if (!response.ok) throw new Error('Failed to fetch part types');
      
      const data = await response.json();
      const select = document.getElementById('part_type');
      select.innerHTML = '<option value="">All Part Types</option>';
      (data.part_types || []).forEach(type => {
        select.innerHTML += `<option value="${type}">${type}</option>`;
      });
    } catch (error) {
      console.error('Error loading part types:', error);
      throw error;
    }
  }

  async loadTechnicalGuides() {
    try {
      const response = await fetch('/technical-guides');
      if (!response.ok) throw new Error('Failed to fetch technical guides');
      
      const data = await response.json();
      this.displayTechnicalGuides(data.guides || []);
    } catch (error) {
      console.error('Error loading technical guides:', error);
      // don't throw here — guides are optional
    }
  }

  displayTechnicalGuides(guides) {
    const container = document.getElementById('guidesList');
    if (!container) return;
    container.innerHTML = guides.map(guide => `
      <div class="guide-item" data-guide="${guide.guide_name}">
        <div class="guide-name">${guide.display_name}</div>
        <div class="guide-desc">${guide.description}</div>
      </div>
    `).join('');

    // Add click events to guides
    container.querySelectorAll('.guide-item').forEach(item => {
      item.addEventListener('click', () => {
        const guideName = item.dataset.guide;
        this.openTechnicalGuide(guideName);
      });
    });
  }

  updateCategoryFilter() {
    const select = document.getElementById('category');
    if (!select) return;
    select.innerHTML = '<option value="">All Categories</option>';
    (this.allCategories || []).forEach(category => {
      select.innerHTML += `<option value="${category}">${category}</option>`;
    });
  }

  async performSearch() {
    this.setLoadingState(true);
    
    try {
      const params = new URLSearchParams();
      Object.entries(this.filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      params.set('limit', '100');

      const response = await fetch(`/search?${params}`);
      if (!response.ok) throw new Error('Search request failed');
      
      const data = await response.json();
      
      this.lastResults = data;
      this.displayResults(data);
      this.updateBreadcrumb();
    } catch (error) {
      console.error('Search error:', error);
      this.displayError('Error performing search. Please check server connection.');
    } finally {
      this.setLoadingState(false);
    }
  }

  displayResults(data) {
    const container = document.getElementById('results');
    if (!container) return;

    if (!data || !data.results || data.results.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <i class="fas fa-search fa-3x"></i>
          <h3>No results found</h3>
          <p>Try adjusting your search criteria</p>
        </div>
      `;
      return;
    }

    const isGridView = this.currentView === 'grid';
    container.className = isGridView ? 'results-grid' : 'results-list';

    container.innerHTML = data.results.map(part => this.createResultCard(part, isGridView)).join('');

    // Add event listeners
    container.querySelectorAll('.btn-image').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const card = e.target.closest('.part-card');
        this.openImagePopup(card);
      });
    });

    container.querySelectorAll('.part-card').forEach(card => {
      card.addEventListener('click', () => {
        this.showPartDetails(card.dataset.partId);
      });
    });
  }

  createResultCard(part, isGrid) {
    const gridClass = isGrid ? '' : 'list-view';
    const imageDataAttr = part.image_url ? `data-image="${part.image_url}"` : '';
    const pdfLink = part.pdf_url ? `<a href="${part.pdf_url}" class="btn-action btn-pdf" target="_blank"><i class="fas fa-file-pdf"></i> PDF</a>` : '';
    
    return `
      <div class="part-card ${gridClass}" data-part-id="${part.id}">
        <div class="part-header">
          <div class="part-number">${part.part_number}</div>
          <span class="catalog-badge ${part.catalog_type}">${part.catalog_type}</span>
        </div>
        
        <div class="part-meta">
          <div class="meta-item">
            <i class="fas fa-tag"></i>
            <span>${part.part_type || 'N/A'}</span>
          </div>
          <div class="meta-item">
            <i class="fas fa-folder"></i>
            <span>${part.category || 'N/A'}</span>
          </div>
          <div class="meta-item">
            <i class="fas fa-file"></i>
            <span>Page ${part.page}</span>
          </div>
        </div>

        ${part.description ? `
          <div class="part-description">
            ${part.description}
          </div>
        ` : ''}

        <div class="part-actions">
          ${part.image_url ? `
            <button class="btn-action btn-image" ${imageDataAttr}>
              <i class="fas fa-image"></i> Image
            </button>
          ` : ''}

          ${pdfLink}
          
          <button class="btn-action btn-guide">
            <i class="fas fa-book"></i> Guide
          </button>
        </div>
      </div>
    `;
  }

  openImagePopup(card) {
    if (!card) return;
    const imageBtn = card.querySelector('.btn-image');
    const imageUrl = imageBtn?.dataset?.image || '';
    const pdfUrl = card.querySelector('.btn-pdf')?.href || '#';
    
    if (imageUrl) {
      document.getElementById('popupImage').src = imageUrl;
    } else {
      document.getElementById('popupImage').src = '';
    }
    document.getElementById('pdfBtn').href = pdfUrl || '#';
    document.getElementById('imagePopup').style.display = 'flex';
  }

  closeImagePopup() {
    document.getElementById('imagePopup').style.display = 'none';
  }

  async openTechnicalGuide(guideName) {
    try {
      const response = await fetch(`/technical-guides/${guideName}?download=true`);
      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        this.showPdfModal(guideName, url);
      }
    } catch (error) {
      console.error('Error opening guide:', error);
    }
  }

  showPdfModal(title, pdfUrl) {
    document.getElementById('pdfTitle').textContent = title;
    document.getElementById('pdfViewer').src = pdfUrl;
    document.getElementById('pdfModal').style.display = 'flex';
  }

  closePdfModal() {
    document.getElementById('pdfModal').style.display = 'none';
    document.getElementById('pdfViewer').src = '';
  }

  async showPartDetails(partId) {
    // Implement part details view
    console.log('Show details for part:', partId);
  }

  showAll() {
    this.filters.q = '';
    document.getElementById('q').value = '';
    this.performSearch();
  }

  resetFilters() {
    this.filters = {
      q: '',
      category: '',
      part_type: '',
      catalog_type: '',
      content_type: 'all'
    };
    
    document.getElementById('q').value = '';
    document.getElementById('category').value = '';
    document.getElementById('part_type').value = '';
    document.getElementById('catalog_type').value = '';
    document.getElementById('content_type').value = 'all';
    
    this.performSearch();
  }

  updateView() {
    this.displayResults(this.lastResults || { results: [] });
  }

  updateBreadcrumb() {
    const breadcrumb = document.getElementById('breadcrumb');
    if (!breadcrumb) return;
    const activeFilters = Object.entries(this.filters)
      .filter(([key, value]) => value && key !== 'content_type')
      .map(([key, value]) => `${key}: ${value}`);
    
    breadcrumb.textContent = activeFilters.length > 0 
      ? `Search Results (${activeFilters.join(', ')})`
      : 'All Content';
  }

  setLoadingState(loading) {
    const btn = document.getElementById('searchBtn');
    if (!btn) return;
    if (loading) {
      btn.innerHTML = '<div class="spinner"></div>';
      btn.disabled = true;
      document.body.classList.add('loading');
    } else {
      btn.innerHTML = '<i class="fas fa-search"></i> Search';
      btn.disabled = false;
      document.body.classList.remove('loading');
    }
  }

  displayError(message) {
    const container = document.getElementById('results');
    if (!container) return;
    container.innerHTML = `
      <div class="error-state">
        <i class="fas fa-exclamation-triangle fa-2x"></i>
        <h3>${message}</h3>
      </div>
    `;
  }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  new KnowledgeBaseApp();
});
