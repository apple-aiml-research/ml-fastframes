(() => {
  'use strict';

  const nav = document.querySelector('.page-toc');
  if (!nav) return;
  const links = Array.from(nav.querySelectorAll('.page-toc-item'));
  const sections = links.map((link) => document.getElementById(link.hash.slice(1)));
  let active = null;
  let pending = false;

  function activate(index) {
    if (index === active) return;
    active = index;
    links.forEach((link, i) => {
      link.classList.toggle('is-active', i === index);
      if (i === index) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
    const link = links[index];
    // Rail: move the highlight to the active dot. Bar: keep the active label in view.
    nav.style.setProperty('--toc-active-top', `${link.offsetTop + link.offsetHeight / 2}px`);
    if (nav.scrollWidth > nav.clientWidth) {
      const left = link.offsetLeft - (nav.clientWidth - link.offsetWidth) / 2;
      nav.scrollTo({ left: Math.max(0, left), behavior: 'auto' });
    }
  }

  function update() {
    pending = false;
    const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
    let index = 0;
    if (atBottom) {
      index = sections.length - 1;
    } else {
      const line = window.innerHeight * 0.35;
      sections.forEach((section, i) => {
        if (section && section.getBoundingClientRect().top <= line) index = i;
      });
    }
    activate(index);
  }

  function schedule() {
    if (!pending) {
      pending = true;
      requestAnimationFrame(update);
    }
  }

  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', () => {
    active = null;
    schedule();
  });
  update();
})();
