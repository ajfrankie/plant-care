/* =======================================================================
   Plant Care — shared page behaviors
   (original assets/script.js wasn't included in the upload, so this is a
   reconstruction covering the data-attribute hooks used across the pages:
   password show/hide toggles and the "Mark as Watered" demo action.)
   ======================================================================= */

(function () {
  function initPasswordToggles() {
    document.querySelectorAll('[data-toggle-password]').forEach(function (btn) {
      if (btn.__wired) return;
      btn.__wired = true;
      btn.addEventListener('click', function () {
        var targetId = btn.getAttribute('data-target');
        var input = targetId && document.getElementById(targetId);
        if (!input) return;
        var showingText = input.type === 'text';
        input.type = showingText ? 'password' : 'text';
        btn.setAttribute('aria-pressed', String(!showingText));
        var showIcon = btn.querySelector('.icon-show');
        var hideIcon = btn.querySelector('.icon-hide');
        if (showIcon) showIcon.style.display = showingText ? '' : 'none';
        if (hideIcon) hideIcon.style.display = showingText ? 'none' : '';
      });
    });
  }

  function initMarkWatered() {
    document.querySelectorAll('[data-mark-watered]').forEach(function (btn) {
      if (btn.__wired) return;
      btn.__wired = true;
      btn.addEventListener('click', function () {
        var scope = document;
        var status = scope.querySelector('[data-water-status]');
        var lastWatered = scope.querySelector('[data-last-watered]');
        var nextWatering = scope.querySelector('[data-next-watering]');
        if (lastWatered) lastWatered.textContent = 'Just now';
        if (nextWatering) nextWatering.textContent = 'In 7 days';
        if (status) {
          status.innerHTML = '<span class="badge-dot"></span>Healthy';
        }
        btn.textContent = 'Watered';
        btn.disabled = true;
      });
    });
  }

  function initFaqAccordions() {
    document.querySelectorAll('[data-faq-trigger]').forEach(function (btn) {
      if (btn.__wired) return;
      btn.__wired = true;
      btn.addEventListener('click', function () {
        var item = btn.closest('[data-faq-item]');
        var answer = item && item.querySelector('.faq-answer');
        if (!answer) return;
        var isOpen = item.getAttribute('data-open') === 'true';
        item.setAttribute('data-open', String(!isOpen));
        answer.style.display = isOpen ? 'none' : 'block';
        btn.setAttribute('aria-expanded', String(!isOpen));
        var marker = btn.querySelector('span');
        if (marker) marker.textContent = isOpen ? '+' : '−';
      });
    });
  }

  function initNotificationDropdown() {
    var notificationBtn = document.getElementById('notificationBtn');
    var notificationDropdown = document.getElementById('notificationDropdown');
    
    if (!notificationBtn || !notificationDropdown) return;
    if (notificationBtn.__wired) return;
    notificationBtn.__wired = true;

    // Add hover effect to button
    notificationBtn.addEventListener('mouseenter', function() {
      this.style.background = '#F8F8F2';
    });
    notificationBtn.addEventListener('mouseleave', function() {
      this.style.background = '#fff';
    });
    
    // Toggle dropdown on click
    notificationBtn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      
      var isVisible = notificationDropdown.style.visibility === 'visible';
      
      if (isVisible) {
        notificationDropdown.style.visibility = 'hidden';
        notificationDropdown.style.opacity = '0';
      } else {
        notificationDropdown.style.visibility = 'visible';
        notificationDropdown.style.opacity = '1';
      }
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
      if (!notificationDropdown.contains(e.target) && !notificationBtn.contains(e.target)) {
        notificationDropdown.style.visibility = 'hidden';
        notificationDropdown.style.opacity = '0';
      }
    });
  }

  // Public site header: menu button on small screens.
  function initSiteMenu() {
    document.querySelectorAll('[data-site-menu]').forEach(function (btn) {
      if (btn.__wired) return;
      btn.__wired = true;
      var menu = document.getElementById(btn.getAttribute('aria-controls'));
      if (!menu) return;
      btn.addEventListener('click', function () {
        var open = menu.classList.toggle('open');
        btn.setAttribute('aria-expanded', String(open));
        btn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
      });
    });
  }

  // ---------- Public pages: motion ----------
  // Elements fade and slide up as they scroll into view. Grid items are
  // staggered. Skipped entirely when the visitor prefers reduced motion.
  var REVEAL_SELECTOR = [
    '[data-reveal]', '.hero-row > *', '.page-hero .container > *',
    '.section > .eyebrow', '.section > h2', '.section > div > .eyebrow', '.section > div > h2',
    '.species-card', '.card', '.stat-band > div', '.problem-card', '.empty-state',
    '.grid-3 > *', '.grid-4 > *', '.two-col > *', '.care-fact', '[data-faq-item]'
  ].join(',');

  function initScrollReveal() {
    if (!document.querySelector('.site-header') || !('IntersectionObserver' in window)) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    var targets = [];
    document.querySelectorAll(REVEAL_SELECTOR).forEach(function (el) {
      if (el.__revealed || el.closest('.site-header, .site-footer, .chip-bar, .tab-content')) return;
      // Animate the outer element only, not cards nested inside it.
      for (var i = 0; i < targets.length; i++) if (targets[i].contains(el)) return;
      targets.push(el);
    });

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        observer.unobserve(el);
        el.classList.add('in');
        countUp(el);
        // Hand hover effects back to the element once it has arrived.
        var delay = parseInt(el.style.getPropertyValue('--reveal-delay'), 10) || 0;
        setTimeout(function () {
          el.classList.remove('reveal', 'in');
          el.style.removeProperty('--reveal-delay');
        }, 900 + delay);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });

    targets.forEach(function (el) {
      el.__revealed = true;
      // Stagger siblings that animate together (cards in a grid).
      var index = 0, sib = el.previousElementSibling;
      while (sib && index < 6) {
        if (targets.indexOf(sib) !== -1) index++;
        sib = sib.previousElementSibling;
      }
      el.style.setProperty('--reveal-delay', (index * 80) + 'ms');
      el.classList.add('reveal');
      observer.observe(el);
    });
  }

  // Numbers in a stat band count up from zero when they appear.
  function countUp(scope) {
    if (!scope.matches('.stat-band > div')) return;
    scope.querySelectorAll('.num').forEach(function (num) {
      var target = parseInt(num.textContent.replace(/[^0-9]/g, ''), 10);
      if (!target) return;
      var start = null, duration = 1200;
      function step(ts) {
        if (start === null) start = ts;
        var t = Math.min((ts - start) / duration, 1);
        num.textContent = Math.round(target * (1 - Math.pow(1 - t, 3))).toLocaleString();
        if (t < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  }

  // The public header gets a shadow once the page has scrolled.
  function initHeaderShadow() {
    var header = document.querySelector('.site-header');
    if (!header || header.__wired) return;
    header.__wired = true;
    var update = function () { header.classList.toggle('scrolled', window.scrollY > 8); };
    window.addEventListener('scroll', update, { passive: true });
    update();
  }

  function init() {
    initScrollReveal();
    initHeaderShadow();
    initSiteMenu();
    initPasswordToggles();
    initMarkWatered();
    initFaqAccordions();
    initNotificationDropdown();
  }

  // Run once for anything already in the DOM at load time...
  document.addEventListener('DOMContentLoaded', init);
  // ...and again whenever a nav/*.html partial finishes injecting, since
  // partials can add new elements with these data-attributes after load.
  document.addEventListener('partial:loaded', init);
})();
