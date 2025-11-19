class PartsCatalog {
    constructor() {
        this.currentResults = [];
        this.filters = {
            category: '',
            partType: '',
            catalogType: ''
        };
        this.config = {};
        this.currentPart = null;
        this.viewMode = 'grid';
        this.init();
    }

    getImageUrl(part) {
        // Use the image_url provided by the backend API
        if (part && part.image_url) {
            return part.image_url;
        }
        
        // Fallback: extract filename from image_path
        if (part && part.image_path) {
            const filename = part.image_path.split('\\').pop().split('/').pop();
            if (filename) {
                return `/images/${filename}`;  // Changed from /part_images/ to /images/
            }
        }
        
        return null;
    }

    async init() {
        await this.loadConfig();
        await this.loadFilters();
        this.setupEventListeners();
        this.setupDetailPageListeners();
        this.setupViewMode();
        this.setupEnhancedSearch();
        this.performSearch(''); 
        
        window.addEventListener('popstate', (event) => {
            if (event.state && event.state.page === 'detail') {
                this.showPartDetailPage(event.state.partId);
            } else {
                this.showHomePage();
            }
        });
    }

    setupEnhancedSearch() {
        document.getElementById("searchBtn").addEventListener("click", async () => {
            const query = document.getElementById("searchInput").value.trim();
            if (!query) return;

            document.getElementById("loadingSpinner").classList.remove("hidden");
            document.getElementById("resultsGrid").innerHTML = "";

            try {
                // Use the correct API endpoint
                const params = new URLSearchParams({
                    q: query,
                    category: this.filters.category || '',
                    part_type: this.filters.partType || '',
                    catalog_type: this.filters.catalogType || '',
                    limit: this.config.maxSearchResults || 50
                });

                const response = await fetch(`/api/search?${params}`);
                const data = await response.json();

                document.getElementById("loadingSpinner").classList.add("hidden");
                const resultsGrid = document.getElementById("resultsGrid");
                const resultsCount = document.getElementById("resultsCount");
                const resultsNumber = document.getElementById("resultsNumber");

                if (!data.results || data.results.length === 0) {
                    document.getElementById("noResults").classList.remove("hidden");
                    resultsCount.classList.add("hidden");
                    return;
                }

                resultsNumber.textContent = data.results.length;
                resultsCount.classList.remove("hidden");
                document.getElementById("noResults").classList.add("hidden");

                data.results.forEach(part => {
                    const card = document.createElement("div");
                    card.className = "bg-white rounded-lg shadow-md p-4 cursor-pointer";
                    card.addEventListener('click', () => this.showPartDetailPage(part.id));
                    
                    const imageUrl = this.getImageUrl(part);

                    card.innerHTML = `
                        <h3 class="text-lg font-bold text-gray-800">${part.part_number}</h3>
                        <p class="text-sm text-gray-600 mb-2">${part.description || "No description available"}</p>
                        ${imageUrl ? `<img src="${imageUrl}" class="w-full h-40 object-contain mb-2" alt="${part.part_number}" onerror="this.style.display='none'; this.parentNode.querySelector('.image-placeholder-inline').style.display='flex';">` : ""}
                        <div class="image-placeholder-inline w-full h-40 flex items-center justify-center ${imageUrl ? 'hidden' : ''}">
                            <i class="fas fa-image text-2xl text-gray-400"></i>
                        </div>
                        <p class="text-xs text-gray-500">Catalog: ${part.catalog_name || part.catalog_type || ''}</p>
                        <p class="text-xs text-gray-500 mb-2">Page: ${part.page || ''}</p>
                        ${part.guides && part.guides.length ? `
                            <div class="mt-2">
                                <h4 class="font-semibold text-sm text-gray-700 mb-1">Technical Guides:</h4>
                                <ul class="space-y-1">
                                    ${part.guides.map(g => `
                                        <li>
                                            <a href="/guides/${g.id}" class="text-blue-600 hover:underline text-sm" onclick="event.stopPropagation()">
                                                ${g.display_name}
                                            </a>
                                        </li>
                                    `).join('')}
                                </ul>
                            </div>
                        ` : ""}
                    `;
                    resultsGrid.appendChild(card);
                });
            } catch (err) {
                console.error("Search error:", err);
                document.getElementById("loadingSpinner").classList.add("hidden");
                alert("Error fetching search results.");
            }
        });
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            this.config = await response.json();
        } catch (error) {
            console.error('Failed to load config:', error);
            this.config = {
                maxDescriptionLength: 120,
                maxApplicationsDisplay: 2,
                searchDebounceMs: 300,
                enableTechnicalGuides: true,
                maxSearchResults: 50
            };
        }
    }

    async loadFilters() {
        try {
            const [categories, partTypes, catalogs] = await Promise.all([
                this.fetchCategories(),
                this.fetchPartTypes(),
                this.fetchCatalogs()
            ]);

            this.populateFilter('categoryFilter', categories);
            this.populateFilter('partTypeFilter', partTypes);
            this.populateFilter('catalogFilter', catalogs.map(cat => cat.name));
            
        } catch (error) {
            console.error('Failed to load filters:', error);
        }
    }

    async fetchCategories() {
        const response = await fetch('/api/search/categories');
        const data = await response.json();
        return data.categories || [];
    }

    async fetchPartTypes() {
        const response = await fetch('/api/search/part_types');
        const data = await response.json();
        return data.part_types || [];
    }

    async fetchCatalogs() {
        const response = await fetch('/api/search/catalogs');
        const data = await response.json();
        return data.catalogs || [];
    }

    populateFilter(selectId, options) {
        const select = document.getElementById(selectId);
        // Clear existing options except first
        while (select.children.length > 1) {
            select.removeChild(select.lastChild);
        }
        
        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option;
            optionElement.textContent = option;
            select.appendChild(optionElement);
        });
    }

    setupEventListeners() {
        const searchInput = document.getElementById('searchInput');
        const searchBtn = document.getElementById('searchBtn');
        const categoryFilter = document.getElementById('categoryFilter');
        const partTypeFilter = document.getElementById('partTypeFilter');
        const catalogFilter = document.getElementById('catalogFilter');

        // Search with debounce
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                this.performSearch(e.target.value);
            }, this.config.searchDebounceMs);
        });

        searchBtn.addEventListener('click', () => {
            this.performSearch(searchInput.value);
        });

        // Filter changes
        [categoryFilter, partTypeFilter, catalogFilter].forEach(filter => {
            filter.addEventListener('change', (e) => {
                // Map element id to filters object keys
                const id = e.target.id;
                if (id === 'categoryFilter') this.filters.category = e.target.value;
                if (id === 'partTypeFilter') this.filters.partType = e.target.value;
                if (id === 'catalogFilter') this.filters.catalogType = e.target.value;
                this.performSearch(searchInput.value);
            });
        });

        // Enter key support
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.performSearch(searchInput.value);
            }
        });
    }

    setupDetailPageListeners() {
        // Back button in detail page
        const backButton = document.createElement('button');
        backButton.innerHTML = '<i class="fas fa-arrow-left mr-2"></i>Back to Search';
        backButton.className = 'bg-gray-600 text-white px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors font-medium';
        backButton.addEventListener('click', () => this.showHomePage());
        
        // Add back button to detail page header
        const detailHeader = document.querySelector('#part-detail-page .bg-white');
        if (detailHeader) {
            detailHeader.querySelector('.text-center').insertAdjacentElement('beforebegin', backButton);
        }
    }

    setupViewMode() {
        const gridView = document.getElementById('gridView');
        const listView = document.getElementById('listView');

        if (gridView) {
            gridView.addEventListener('click', () => {
                this.setViewMode('grid');
            });
        }
        if (listView) {
            listView.addEventListener('click', () => {
                this.setViewMode('list');
            });
        }
    }

    setViewMode(mode) {
        this.viewMode = mode;
        const gridView = document.getElementById('gridView');
        const listView = document.getElementById('listView');
        const resultsGrid = document.getElementById('resultsGrid');

        if (mode === 'grid') {
            if (gridView) gridView.classList.add('view-active');
            if (listView) listView.classList.remove('view-active');
            if (resultsGrid) resultsGrid.className = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6';
        } else {
            if (listView) listView.classList.add('view-active');
            if (gridView) gridView.classList.remove('view-active');
            if (resultsGrid) resultsGrid.className = 'grid grid-cols-1 gap-4';
        }

        // Re-render results with new view mode
        this.displayResults();
    }

    async performSearch(query = '') {
        this.showLoading();

        try {
            const params = new URLSearchParams({
                q: query || '',
                category: this.filters.category || '',
                part_type: this.filters.partType || '',
                catalog_type: this.filters.catalogType || '',
                limit: this.config.maxSearchResults || 50
            });

            // Use the correct API endpoint
            const response = await fetch(`/api/search?${params}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            
            this.currentResults = data.results || [];
            this.displayResults();

        } catch (err) {
            console.error("Search failed:", err);
            this.showError('Search failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    displayResults() {
        const grid = document.getElementById('resultsGrid');
        const noResults = document.getElementById('noResults');
        const resultsCount = document.getElementById('resultsCount');
        const resultsNumber = document.getElementById('resultsNumber');

        if (!grid) return;
        grid.innerHTML = '';
        
        if (!this.currentResults || this.currentResults.length === 0) {
            if (noResults) noResults.classList.remove('hidden');
            if (resultsCount) resultsCount.classList.add('hidden');
            return;
        }

        if (noResults) noResults.classList.add('hidden');
        if (resultsCount) resultsCount.classList.remove('hidden');
        if (resultsNumber) resultsNumber.textContent = this.currentResults.length;

        this.currentResults.forEach(part => {
            const card = this.createPartCard(part);
            grid.appendChild(card);
        });
    }

    createPartCard(part) {
        const card = document.createElement('div');
        card.className = this.viewMode === 'grid' 
            ? 'part-card bg-white rounded-lg shadow-md overflow-hidden fade-in cursor-pointer'
            : 'part-card bg-white rounded-lg shadow-md overflow-hidden fade-in cursor-pointer flex';
        
        card.addEventListener('click', () => this.showPartDetailPage(part.id));
        
        const description = part.description 
            ? (part.description.length > this.config.maxDescriptionLength 
                ? part.description.substring(0, this.config.maxDescriptionLength) + '...'
                : part.description)
            : 'No description available';

        // Use helper to get proper image URL
        const imageUrl = this.getImageUrl(part);
        const hasImage = !!imageUrl;

        if (this.viewMode === 'grid') {
            card.innerHTML = `
                <div class="h-48 bg-gray-100 relative">
                    ${hasImage 
                        ? `<img src="${imageUrl}" alt="${part.part_number}" 
                            class="w-full h-full object-contain" 
                            onerror="this.style.display='none'; this.parentNode.querySelector('.image-placeholder').style.display='flex';"
                            onload="this.style.display='block'; this.parentNode.querySelector('.image-placeholder').style.display='none';">`
                        : ''
                    }
                    <div class="image-placeholder w-full h-full ${hasImage ? 'hidden' : 'flex'} items-center justify-center">
                        <i class="fas fa-image text-4xl text-gray-400"></i>
                    </div>
                    <div class="absolute top-2 right-2 bg-blue-600 text-white px-2 py-1 rounded text-sm">
                        ${part.category || 'Uncategorized'}
                    </div>
                </div>
                <div class="p-4">
                    <h3 class="font-bold text-lg text-gray-800 mb-2">${part.part_number}</h3>
                    <p class="text-gray-600 text-sm mb-3">${description}</p>
                    
                    <div class="flex justify-between items-center mt-4">
                        <span class="text-sm text-gray-500">
                            ${part.catalog_type || 'No catalog'}
                        </span>
                        <span class="text-blue-600 text-sm font-medium">
                            View Details →
                        </span>
                    </div>
                </div>
            `;
        } else {
            // List view
            card.innerHTML = `
                <div class="w-32 flex-shrink-0">
                    ${hasImage 
                        ? `<img src="${imageUrl}" alt="${part.part_number}" 
                            class="w-full h-32 object-contain" 
                            onerror="this.style.display='none'; this.parentNode.querySelector('.image-placeholder').style.display='flex';"
                            onload="this.style.display='block'; this.parentNode.querySelector('.image-placeholder').style.display='none';">`
                        : ''
                    }
                    <div class="image-placeholder w-full h-32 ${hasImage ? 'hidden' : 'flex'} items-center justify-center">
                        <i class="fas fa-image text-2xl text-gray-400"></i>
                    </div>
                </div>
                <div class="flex-1 p-4">
                    <div class="flex justify-between items-start">
                        <div>
                            <h3 class="font-bold text-lg text-gray-800 mb-2">${part.part_number}</h3>
                            <p class="text-gray-600 mb-3">${description}</p>
                        </div>
                        <div class="text-right">
                            <span class="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm">
                                ${part.category || 'Uncategorized'}
                            </span>
                            <div class="text-sm text-gray-500 mt-2">
                                ${part.catalog_type || 'No catalog'}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        return card;
    }

    async showPartDetailPage(partId) {
        try {
            const response = await fetch(`/api/parts/${partId}`);
            const part = await response.json();
            this.currentPart = part;
            this.displayPartDetail(part);
            
            // Update URL and history
            history.pushState({ page: 'detail', partId: partId }, '', `/part/${partId}`);
            
        } catch (error) {
            console.error('Failed to load part details:', error);
            this.showError('Failed to load part details');
        }
    }

    displayPartDetail(part) {
        // Switch to detail page
        const homePage = document.getElementById('home-page');
        const detailPage = document.getElementById('part-detail-page');
        if (homePage) homePage.classList.add('hidden');
        if (detailPage) detailPage.classList.remove('hidden');

        // Set header information
        const partNumberHeader = document.getElementById('part-number-header');
        const partDescriptionHeader = document.getElementById('part-description-header');
        if (partNumberHeader) partNumberHeader.textContent = part.part_number;
        if (partDescriptionHeader) partDescriptionHeader.textContent = part.description || '';

        // Set all content sections
        this.setIntroductionContent(part);
        this.setUseContent(part);
        this.setSpecificationsContent(part);
        this.setCrossReferences(part);
        this.setDiagramContent(part);
        this.setVideoContent(part);
        this.setProductImage(part);
        this.setManufacturerInfo(part);
        this.setMaterialInfo(part);
        this.setGeneralInfo(part);
        this.setActionLinks(part);

        // Load related parts
        this.loadRelatedParts(part);
    }

    setIntroductionContent(part) {
        const introContainer = document.getElementById('intro-content');
        
        let introHTML = '';
        
        if (part.description) {
            introHTML += `<p class="text-gray-700 leading-relaxed">${part.description}</p>`;
        }
        
        if (part.features) {
            introHTML += `
                <div class="mt-4">
                    <h4 class="font-semibold text-gray-800 mb-2">Key Features:</h4>
                    <p class="text-gray-700">${part.features}</p>
                </div>
            `;
        }

        if (introContainer) introContainer.innerHTML = introHTML || '<p class="text-gray-500 italic">No introduction content available.</p>';
    }

    setUseContent(part) {
        const useContainer = document.getElementById('use-content');
        
        let useHTML = '';
        
        if (part.applications && part.applications.length > 0) {
            useHTML += `
                <div class="mb-4">
                    <h4 class="font-semibold text-gray-800 mb-2">Primary Applications:</h4>
                    <div class="flex flex-wrap gap-2">
                        ${part.applications.map(app => 
                            `<span class="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm">${app}</span>`
                        ).join('')}
                    </div>
                </div>
            `;
        }

        if (part.machine_info) {
            useHTML += `
                <div>
                    <h4 class="font-semibold text-gray-800 mb-2">Compatible Machinery:</h4>
                    <p class="text-gray-700">${part.machine_info}</p>
                </div>
            `;
        }

        if (useContainer) useContainer.innerHTML = useHTML || '<p class="text-gray-500 italic">No usage information available.</p>';
    }

    setSpecificationsContent(part) {
        const specsContainer = document.getElementById('specifications-content');
        
        let specsHTML = '';
        
        const specData = [
            { label: 'Part Number', value: part.part_number },
            { label: 'Category', value: part.category },
            { label: 'Part Type', value: part.part_type },
            { label: 'Catalog Type', value: part.catalog_type },
            { label: 'Page Reference', value: part.page }
        ];

        specData.forEach(spec => {
            if (spec.value) {
                specsHTML += `
                    <div class="spec-item">
                        <span class="spec-label">${spec.label}:</span>
                        <span class="spec-value">${spec.value}</span>
                    </div>
                `;
            }
        });

        if (specsContainer) specsContainer.innerHTML = specsHTML || '<p class="text-gray-500 italic">No specifications available.</p>';
    }

    setCrossReferences(part) {
        const crossRefContainer = document.getElementById('cross-reference-table');
        
        let crossRefHTML = '';
        
        // Add current part as primary reference
        crossRefHTML = `
            <tr class="cross-ref-table bg-blue-50">
                <td class="px-4 py-2 text-sm font-medium text-gray-900">Primary</td>
                <td class="px-4 py-2 text-sm font-medium text-gray-900">${part.part_number}</td>
                <td class="px-4 py-2 text-sm text-gray-700">Main Part</td>
                <td class="px-4 py-2 text-sm text-gray-700">All compatible applications</td>
            </tr>
        `;

        if (crossRefContainer) crossRefContainer.innerHTML = crossRefHTML || '<tr><td colspan="4" class="px-4 py-4 text-center text-gray-500">No cross references available.</td></tr>';
    }

    setDiagramContent(part) {
        const diagramContainer = document.getElementById('diagram-content');
        
        // Use the part image as diagram if available
        const imageUrl = this.getImageUrl(part);
        if (diagramContainer) {
            if (imageUrl) {
                diagramContainer.innerHTML = `
                    <img src="${imageUrl}" alt="${part.part_number} Diagram" class="max-w-full h-auto mx-auto rounded-lg shadow-md">
                    <p class="text-sm text-gray-600 mt-2">Product diagram for ${part.part_number}</p>
                `;
            } else {
                diagramContainer.innerHTML = `
                    <div class="image-placeholder w-full h-48 rounded-lg flex items-center justify-center">
                        <i class="fas fa-project-diagram text-4xl"></i>
                    </div>
                    <p class="text-sm text-gray-600 mt-2">No diagram available for ${part.part_number}</p>
                `;
            }
        }
    }

    setVideoContent(part) {
        const videoContainer = document.getElementById('video-content');
        if (videoContainer) {
            videoContainer.innerHTML = `
                <div class="image-placeholder w-full h-64 rounded-lg flex items-center justify-center">
                    <i class="fas fa-video text-4xl"></i>
                </div>
                <p class="text-sm text-gray-600 mt-2">Installation video coming soon for ${part.part_number}</p>
            `;
        }
    }

    setProductImage(part) {
        const imagePlaceholder = document.getElementById('product-image-placeholder');
        const productImage = document.getElementById('product-image');
        
        const imageUrl = this.getImageUrl(part);
        if (productImage && imageUrl) {
            productImage.src = imageUrl;
            productImage.alt = part.part_number;
            productImage.classList.remove('hidden');
            if (imagePlaceholder) imagePlaceholder.classList.add('hidden');
        } else {
            if (productImage) productImage.classList.add('hidden');
            if (imagePlaceholder) imagePlaceholder.classList.remove('hidden');
        }
    }

    setManufacturerInfo(part) {
        const manufacturerContainer = document.getElementById('manufacturer-info');
        if (manufacturerContainer) manufacturerContainer.innerHTML = part.catalog_type 
            ? `<p>${part.catalog_type}</p>`
            : '<p class="text-gray-500 italic">Not specified</p>';
    }

    setMaterialInfo(part) {
        const materialContainer = document.getElementById('material-info');
        // Extract material from description or use default
        const material = this.extractMaterial(part.description) || 'Various materials';
        if (materialContainer) materialContainer.innerHTML = `<p>${material}</p>`;
    }

    setGeneralInfo(part) {
        const generalContainer = document.getElementById('general-info');
        
        let infoHTML = '';
        
        if (part.category) {
            infoHTML += `<div><strong>Category:</strong> ${part.category}</div>`;
        }
        
        if (part.part_type) {
            infoHTML += `<div><strong>Type:</strong> ${part.part_type}</div>`;
        }
        
        if (part.page) {
            infoHTML += `<div><strong>Catalog Page:</strong> ${part.page}</div>`;
        }

        if (generalContainer) generalContainer.innerHTML = infoHTML || '<div class="text-gray-500 italic">No general information available</div>';
    }

    setActionLinks(part) {
        const pdfLink = document.getElementById('pdf-link');
        const techGuideLink = document.getElementById('technical-guide-link');
        const pageNumber = document.getElementById('part-page-number');

        if (pdfLink) {
            if (part.pdf_url) {
                pdfLink.href = part.pdf_url;
                pdfLink.classList.remove('hidden');
            } else {
                pdfLink.classList.add('hidden');
            }
        }

        // Set page number
        if (pageNumber) pageNumber.textContent = part.page || 'N/A';

        // Technical guide link
        if (techGuideLink) {
            techGuideLink.href = '#';
            techGuideLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.showTechnicalGuide(part);
            });
        }
    }

    extractMaterial(description) {
        if (!description) return null;
        
        const materialKeywords = ['steel', 'aluminum', 'plastic', 'rubber', 'brass', 'copper', 'nylon', 'composite'];
        const descLower = description.toLowerCase();
        
        for (const material of materialKeywords) {
            if (descLower.includes(material)) {
                return material.charAt(0).toUpperCase() + material.slice(1);
            }
        }
        
        return null;
    }

    async loadRelatedParts(part) {
        try {
            const params = new URLSearchParams({
                category: part.category || '',
                catalog_type: part.catalog_type || '',
                limit: 8
            });

            const response = await fetch(`/api/search?${params}`);
            const data = await response.json();

            const relatedParts = (data.results || [])
                .filter(p => p.id !== part.id)
                .slice(0, 6); // Show max 6 related parts

            this.displayRelatedParts(relatedParts);
        } catch (err) {
            console.error("Failed to load related parts:", err);
        }
    }

    displayRelatedParts(parts) {
        const container = document.getElementById('related-parts-list');
        
        if (!container) return;
        if (!parts || parts.length === 0) {
            container.innerHTML = '<p class="text-gray-500 text-sm italic">No related parts found.</p>';
            return;
        }

        let html = '';
        parts.forEach(part => {
            html += `
                <div class="related-part-card fade-in cursor-pointer p-3 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors" onclick="catalog.showPartDetailPage(${part.id})">
                    <div class="font-medium text-gray-800 text-sm">${part.part_number}</div>
                    <div class="text-gray-600 text-xs mt-1 truncate">${part.description || 'No description'}</div>
                    <div class="flex justify-between items-center mt-2">
                        <span class="text-xs text-gray-500">${part.category || ''}</span>
                        <span class="text-blue-600 text-xs">View →</span>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    async showTechnicalGuide(part) {
        try {
            const response = await fetch(`/api/parts/${part.id}/guides`);
            const data = await response.json();
            
            if (data.guides && data.guides.length > 0) {
                this.displayTechnicalGuides(data.guides, part);
            } else {
                this.showError('No technical guides available for this part');
            }
        } catch (error) {
            console.error('Failed to load technical guides:', error);
            this.showError('Failed to load technical guides');
        }
    }

    showHomePage() {
        const detailPage = document.getElementById('part-detail-page');
        const homePage = document.getElementById('home-page');
        if (detailPage) detailPage.classList.add('hidden');
        if (homePage) homePage.classList.remove('hidden');
        history.pushState({ page: 'home' }, '', '/');
    }

    showLoading() {
        const spinner = document.getElementById('loadingSpinner');
        const resultsGrid = document.getElementById('resultsGrid');
        if (spinner) spinner.classList.remove('hidden');
        if (resultsGrid) resultsGrid.classList.add('opacity-50');
    }

    hideLoading() {
        const spinner = document.getElementById('loadingSpinner');
        const resultsGrid = document.getElementById('resultsGrid');
        if (spinner) spinner.classList.add('hidden');
        if (resultsGrid) resultsGrid.classList.remove('opacity-50');
    }

    showError(message) {
        // Simple error display - you can enhance this with a proper toast/notification
        alert(message);
    }

    displayTechnicalGuides(guides, part) {
        // Create a modal or section to display guides
        const guideHTML = `
            <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                <div class="bg-white rounded-lg p-6 max-w-4xl max-h-[90vh] overflow-y-auto">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="text-xl font-bold">Technical Guides for ${part.part_number}</h3>
                        <button onclick="this.closest('.fixed').remove()" class="text-gray-500 hover:text-gray-700">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="space-y-4">
                        ${guides.map(guide => `
                            <div class="border rounded-lg p-4">
                                <h4 class="font-semibold text-lg">${guide.display_name}</h4>
                                <p class="text-gray-600 mt-2">${guide.description || 'No description available'}</p>
                                
                                ${guide.sections && guide.sections.length > 0 ? `
                                    <div class="mt-3">
                                        <h5 class="font-medium">Sections:</h5>
                                        <ul class="list-disc list-inside mt-1">
                                            ${guide.sections.map(section => `
                                                <li class="text-sm">${section.title}</li>
                                            `).join('')}
                                        </ul>
                                    </div>
                                ` : ''}
                                
                                ${guide.key_specifications && Object.keys(guide.key_specifications).length > 0 ? `
                                    <div class="mt-3">
                                        <h5 class="font-medium">Key Specifications:</h5>
                                        <div class="grid grid-cols-2 gap-2 mt-1">
                                            ${Object.entries(guide.key_specifications).map(([key, value]) => `
                                                <div class="text-sm">
                                                    <span class="font-medium">${key}:</span> ${value}
                                                </div>
                                            `).join('')}
                                        </div>
                                    </div>
                                ` : ''}
                                
                                <div class="mt-3 flex justify-between items-center">
                                    <span class="text-sm text-gray-500">Confidence: ${(guide.confidence_score * 100).toFixed(0)}%</span>
                                    <button class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-sm">
                                        View Full Guide
                                    </button>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', guideHTML);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.catalog = new PartsCatalog();
    
    // Handle direct part page access from URL
    const pathParts = window.location.pathname.split('/');
    if (pathParts[1] === 'part' && pathParts[2]) {
        const partId = parseInt(pathParts[2]);
        if (!isNaN(partId)) {
            window.catalog.showPartDetailPage(partId);
        }
    }
});