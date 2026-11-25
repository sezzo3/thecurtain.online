/* Article engagement uses the existing Google tag and its consent settings. */
(() => {
  'use strict';
  const article = document.querySelector('article');
  const match = location.pathname.match(/^\/(?:(tr|de|es)\/)?story\/([^/]+)\/?$/);
  if (!article || !match || window.__curtainArticleMetrics) return;
  window.__curtainArticleMetrics = true;

  const parameters = {
    send_to: 'G-XN1LZMCFTY',
    article_id: match[2],
    article_language: match[1] || 'en',
    content_group: 'Articles'
  };
  function emit(name, extra = {}) {
    if (typeof window.gtag === 'function') {
      window.gtag('event', name, { ...parameters, ...extra });
    }
  }
  emit('article_open');

  let visibleSeconds = 0;
  let furthestProgress = 0;
  let previous = performance.now();
  let completed = false;
  function sample() {
    const now = performance.now();
    const elapsed = Math.min((now - previous) / 1000, 2);
    previous = now;
    const bounds = article.getBoundingClientRect();
    const visible = !document.hidden && bounds.bottom > 0 && bounds.top < innerHeight;
    if (visible) {
      visibleSeconds += elapsed;
      furthestProgress = Math.max(furthestProgress,
        Math.min(1, Math.max(0, (innerHeight - bounds.top) / bounds.height)));
    }
    if (!completed && visibleSeconds >= 30 && furthestProgress >= 0.5) {
      completed = true;
      emit('article_read', { reading_seconds: Math.floor(visibleSeconds),
        article_progress: Math.round(furthestProgress * 100),
        minimum_reading_seconds: 30, minimum_article_progress: 50 });
      clearInterval(timer);
    }
  }
  const timer = setInterval(sample, 1000);
  document.addEventListener('visibilitychange', () => { previous = performance.now(); });
  window.addEventListener('pagehide', () => clearInterval(timer), { once: true });
})();
