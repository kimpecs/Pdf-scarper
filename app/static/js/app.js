import { loadConfig } from './config.js';
import { loadInitialData } from './dataLoader.js';
import { bindUIEvents, setupViewControls } from './ui.js';
import { performSearch } from './search.js';
import { updateBreadcrumb } from './utils.js';
import { KnowledgeBaseGuides } from './guides.js';

export class KnowledgeBaseApp {
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
    this.config = {
      maxDescriptionLength: 120,
      maxApplicationsDisplay: 2,
      searchDebounceMs: 300,
      enableTechnicalGuides: true,
      maxSearchResults: 50
    };

    this.guides = new KnowledgeBaseGuides(this);
    this.init();
  }

  async init() {
    bindUIEvents(this);
    await loadConfig(this);
    setupViewControls(this);
    await loadInitialData(this);
    performSearch(this);
  }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => new KnowledgeBaseApp());
