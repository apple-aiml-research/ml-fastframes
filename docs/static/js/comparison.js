(() => {
  'use strict';

  // Each comparison video has its src from the start with preload="none": nothing is fetched before it plays, and
  // Chrome names it by its aria-label (it names a video without a source "Unable to play media.").
  const videos = document.querySelectorAll('.comparison-item video');
  const visibleVideos = new Set();
  const unloadTimers = new WeakMap();
  const observed = 'IntersectionObserver' in window;
  // Reduced motion: no video starts by itself. One that has played pauses out of view and resumes in view.
  const autoplay = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  // A video the reader paused stays paused, also on scrolling back or returning to the tab, until it is played again
  // or its row's Replay is pressed. `pausing` holds this script's own pause() calls until their 'pause' event.
  const pausedByReader = new WeakSet();
  const pausing = new WeakSet();
  const played = new WeakSet();
  // A released video gets its src back at once in Chromium, which fetches nothing for a preload="none" source.
  // WebKit would download the whole file again, so there the src returns when the video plays.
  const restoreSource = 'userAgentData' in navigator;

  const wanted = (video) => !pausedByReader.has(video) && (autoplay || played.has(video));
  // data-autoplay marks the videos that will play once in view (release.js shows them as loading).
  const mark = (video) => video.toggleAttribute('data-autoplay', wanted(video));

  function release(video) {
    video.removeAttribute('src');
    video.load();
    if (restoreSource) video.src = video.dataset.src;
  }

  async function play(video) {
    clearTimeout(unloadTimers.get(video));
    if (!video.hasAttribute('src')) video.src = video.dataset.src;
    try {
      await video.play();
    } catch (error) {
      // Autoplay can be blocked by browser settings, in which case native controls remain available.
      if (error.name === 'NotAllowedError') video.removeAttribute('data-autoplay');
    }
  }

  function pause(video) {
    if (!video.paused) {
      pausing.add(video);
      video.pause();
    }
    clearTimeout(unloadTimers.get(video));
    if (video.readyState === HTMLMediaElement.HAVE_NOTHING && video.networkState !== HTMLMediaElement.NETWORK_LOADING) return;
    unloadTimers.set(video, setTimeout(() => {
      if (visibleVideos.has(video)) return;
      release(video);
    }, 1500));
  }

  videos.forEach((video) => {
    mark(video);
    video.addEventListener('play', () => {
      pausedByReader.delete(video);
      played.add(video);
      mark(video);
      if (observed && (!visibleVideos.has(video) || document.hidden)) pause(video);
    });
    video.addEventListener('pause', () => {
      if (pausing.has(video)) {
        pausing.delete(video);
      } else {
        pausedByReader.add(video);
        mark(video);
      }
    });
  });

  if (observed) {
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        const video = entry.target;
        if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
          visibleVideos.add(video);
          if (wanted(video) && !document.hidden) play(video);
        } else {
          visibleVideos.delete(video);
          pause(video);
        }
      }
    }, { threshold: [0, 0.5, 1] });
    videos.forEach((video) => observer.observe(video));
  }

  document.addEventListener('visibilitychange', () => {
    for (const video of visibleVideos) {
      if (document.hidden) pause(video);
      else if (wanted(video)) play(video);
    }
  });

  document.querySelectorAll('.replay-button').forEach((button) => {
    button.addEventListener('click', () => {
      button.closest('.comparison-group').querySelectorAll('video').forEach((video) => {
        pausedByReader.delete(video);
        played.add(video);
        mark(video);
        if (video.readyState > 0) video.currentTime = 0;
        if (visibleVideos.has(video)) play(video);
      });
    });
  });
})();
