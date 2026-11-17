// Comparison thumbnails show no native controls at rest; they appear on hover or keyboard focus. Touch screens keep
// the controls, since they have no hover.
(() => {
  if (!window.matchMedia('(hover: hover)').matches) return;
  document.querySelectorAll('.comparison-item video').forEach((video) => {
    video.removeAttribute('controls');
    video.tabIndex = 0;
    const show = () => video.setAttribute('controls', '');
    const hide = () => { if (document.activeElement !== video) video.removeAttribute('controls'); };
    video.addEventListener('mouseenter', show);
    video.addEventListener('mouseleave', hide);
    video.addEventListener('focus', show);
    video.addEventListener('blur', hide);
  });
})();

// Comparison posters load when their video comes within about 1200 px of the viewport, not all 88 at once.
(() => {
  const videos = [...document.querySelectorAll('video[data-poster]')];
  // The poster is also the element's background: WebKit drops the poster as soon as a source is set, until the first
  // frame arrives, which would leave a blank tile.
  const show = (video) => {
    video.poster = video.dataset.poster;
    video.style.background = `center / cover no-repeat url("${video.dataset.poster}"), var(--rule)`;
    video.removeAttribute('data-poster');
  };
  if (!('IntersectionObserver' in window)) { videos.forEach(show); return; }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => { if (entry.isIntersecting) { show(entry.target); observer.unobserve(entry.target); } });
  }, { rootMargin: '1200px 0px' });
  videos.forEach((video) => observer.observe(video));
})();

// Result videos while loading: each comparison video gets a small spinner and "Loading" until it can show its first
// frame, and is dimmed meanwhile. (Not the demo: it is click-to-play, and its poster is a title card whose centred
// text the label would sit on.) Each video is wrapped in a .video-frame that holds the overlay, so nothing moves; the
// overlay takes no pointer events. States on the frame: queued (comparison.js plays it once in view), loading
// (playing, before the first frame), loaded (final), idle (paused and not queued, e.g. reduced motion, paused by the
// reader or autoplay blocked: the poster shows), error.
(() => {
  const STATES = ['video-queued', 'video-loading', 'video-loaded', 'video-idle', 'video-error'];
  document.querySelectorAll('.comparison-grid video').forEach((video) => {
    const frame = document.createElement('div');
    frame.className = 'video-frame';
    video.before(frame);
    frame.append(video);
    const overlay = document.createElement('div');
    overlay.className = 'video-loading-overlay';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML = '<span class="loading-spinner"></span><span class="loading-label">Loading</span>';
    frame.append(overlay);

    let loaded = false;
    const update = () => {
      if (loaded) return;
      let state = 'idle';
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) { loaded = true; state = 'loaded'; }
      else if (video.error) state = 'error';
      else if (!video.paused) state = 'loading';
      else if (video.hasAttribute('data-autoplay')) state = 'queued';
      frame.classList.remove(...STATES);
      frame.classList.add(`video-${state}`);
    };
    'loadstart emptied play pause waiting error loadeddata canplay playing'.split(' ').forEach((type) => video.addEventListener(type, update));
    new MutationObserver(update).observe(video, { attributes: true, attributeFilter: ['data-autoplay'] });
    update();
  });
})();

// A comparison row is a keyboard stop only while it scrolls sideways (its grid is wider than the column, e.g. under
// text-only zoom), so that the arrow keys can scroll it.
(() => {
  const rows = [...document.querySelectorAll('.comparison-scroll')];
  const check = () => rows.forEach((row) => {
    if (row.scrollWidth > row.clientWidth) row.tabIndex = 0;
    else row.removeAttribute('tabindex');
  });
  check();
  window.addEventListener('load', check);
  if ('ResizeObserver' in window) {
    const observer = new ResizeObserver(check);
    rows.forEach((row) => { observer.observe(row); observer.observe(row.firstElementChild); });
  } else {
    window.addEventListener('resize', check);
  }
})();

// Chrome ignores a click on a preload="none" video that has no data yet (the demo, and comparison videos that are not
// autoplaying); start it from the click. Deferred, so that a browser that starts it itself (WebKit) is not toggled twice.
document.querySelectorAll('.comparison-item video, .interactive-video').forEach((video) => {
  video.addEventListener('click', () => setTimeout(() => {
    if (video.paused && video.readyState === HTMLMediaElement.HAVE_NOTHING) video.play().catch(() => {});
  }, 0));
});
