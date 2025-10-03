// app.js
document.addEventListener('DOMContentLoaded', function() {
  const searchForm = document.getElementById('searchForm');
  const qInput = document.getElementById('q');
  const categorySelect = document.getElementById('category');
  const partTypeSelect = document.getElementById('part_type');
  const catalogTypeSelect = document.getElementById('catalog_type');
  const searchBtn = document.getElementById('searchBtn');
  const showAllBtn = document.getElementById('showAll');
  const resultsDiv = document.getElementById('results');
  const popup = document.getElementById('popup');
  const popupImage = document.getElementById('popup-image');
  const popupClose = document.getElementById('popup-close');
  const pdfBtn = document.getElementById('pdf-btn');

  // Load filters
  loadFilters();

  // Search form handler
  searchForm.addEventListener('submit', function(e) {
    e.preventDefault();
    performSearch();
  });

  showAllBtn.addEventListener('click', function() {
    qInput.value = '';
    performSearch();
  });

  // Popup handlers
  popupClose.addEventListener('click', function() {
    popup.style.display = 'none';
  });

  popup.addEventListener('click', function(e) {
    if (e.target === popup) {
      popup.style.display = 'none';
    }
  });

  function loadFilters() {
    // Load categories
    fetch('/categories')
      .then(r => r.json())
      .then(data => {
        categorySelect.innerHTML = '<option value="">All Categories</option>';
        data.categories.forEach(cat => {
          categorySelect.innerHTML += `<option value="${cat}">${cat}</option>`;
        });
      });

    // Load part types
    fetch('/part_types')
      .then(r => r.json())
      .then(data => {
        partTypeSelect.innerHTML = '<option value="">All Part Types</option>';
        data.part_types.forEach(type => {
          partTypeSelect.innerHTML += `<option value="${type}">${type}</option>`;
        });
      });

    // Load catalog types
    fetch('/catalogs')
      .then(r => r.json())
      .then(data => {
        catalogTypeSelect.innerHTML = '<option value="">All Catalogs</option>';
        data.catalogs.forEach(catalog => {
          catalogTypeSelect.innerHTML += `<option value="${catalog}">${catalog}</option>`;
        });
      });
  }

  function performSearch() {
    const params = new URLSearchParams();
    if (qInput.value) params.set('q', qInput.value);
    if (categorySelect.value) params.set('category', categorySelect.value);
    if (partTypeSelect.value) params.set('part_type', partTypeSelect.value);
    if (catalogTypeSelect.value) params.set('catalog_type', catalogTypeSelect.value);
    params.set('limit', '200');

    searchBtn.disabled = true;
    searchBtn.textContent = 'Searching...';

    fetch(`/search?${params}`)
      .then(r => r.json())
      .then(data => {
        displayResults(data);
      })
      .catch(error => {
        console.error('Search error:', error);
        resultsDiv.innerHTML = '<p class="error">Error performing search</p>';
      })
      .finally(() => {
        searchBtn.disabled = false;
        searchBtn.textContent = 'Search';
      });
  }

  function displayResults(data) {
    if (data.results.length === 0) {
      resultsDiv.innerHTML = '<p>No parts found.</p>';
      return;
    }

    let html = `
      <div class="results-header">
        <p>Found ${data.count} parts</p>
        <div class="active-filters">
          ${data.query ? `<span>Search: "${data.query}"</span>` : ''}
          ${data.category_filter ? `<span>Category: ${data.category_filter}</span>` : ''}
          ${data.part_type_filter ? `<span>Type: ${data.part_type_filter}</span>` : ''}
          ${data.catalog_filter ? `<span>Catalog: ${data.catalog_filter}</span>` : ''}
        </div>
      </div>
      <div class="results-grid">
    `;

    data.results.forEach(part => {
      html += `
        <div class="part-card" data-part-id="${part.id}">
          <div class="part-header">
            <h3>${part.part_number}</h3>
            <span class="catalog-badge ${part.catalog_type}">${part.catalog_type}</span>
          </div>
          <div class="part-details">
            <p><strong>Type:</strong> ${part.part_type || 'N/A'}</p>
            <p><strong>Category:</strong> ${part.category || 'N/A'}</p>
            <p><strong>Page:</strong> ${part.page}</p>
            ${part.description ? `<p><strong>Description:</strong> ${part.description}</p>` : ''}
          </div>
          <div class="part-actions">
            ${part.image_url ? `<button class="btn-view-image" data-image="${part.image_url}">View Image</button>` : ''}
            ${part.pdf_url ? `<a href="${part.pdf_url}" class="btn-view-pdf" target="_blank">View PDF</a>` : ''}
          </div>
        </div>
      `;
    });

    html += '</div>';
    resultsDiv.innerHTML = html;

    // Add event listeners to image buttons
    document.querySelectorAll('.btn-view-image').forEach(btn => {
      btn.addEventListener('click', function() {
        const imageUrl = this.getAttribute('data-image');
        popupImage.src = imageUrl;
        pdfBtn.href = this.closest('.part-card').querySelector('.btn-view-pdf')?.href || '#';
        popup.style.display = 'flex';
      });
    });
  }

  // Keyboard shortcuts
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      popup.style.display = 'none';
    }
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      performSearch();
    }
  });

  // Initial load - show all parts
  performSearch();
});