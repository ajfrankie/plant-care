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
        btn.textContent = '✓ Watered';
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

  function init() {
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
