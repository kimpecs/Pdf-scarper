import { displayError } from './utils.js';

export class KnowledgeBaseGuides {
  constructor(app) { this.app = app; }

  async searchTechnicalGuides(category) {
    try {
      const res = await fetch(`/api/guides/search?category=${category}`);
      if (res.ok) {
        const data = await res.json();
        if (data.guides?.length) {
          window.open(`/guides/${data.guides[0].guide_name}`, '_blank');
        } else {
          displayError('No technical guides found for this category');
        }
      }
    } catch (e) {
      console.error('Guide search error:', e);
    }
  }
}

export function displayTechnicalGuides(app, guides) {
  const container = document.getElementById('guidesList');
  if (!container) return;
  container.innerHTML = guides.map(g => `
    <div class="guide-item" data-guide="${g.guide_name}">
      <div class="guide-name">${g.display_name}</div>
      <div class="guide-desc">${g.description}</div>
    </div>`).join('');

  container.querySelectorAll('.guide-item').forEach(item => {
    item.addEventListener('click', () => {
      const guideName = item.dataset.guide;
      window.open(`/guides/${guideName}`, '_blank');
    });
  });
}
