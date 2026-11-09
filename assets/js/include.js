/* =======================================================================
   Plant Care — partial loader
   Pulls the shared sidebar / app header / public navbar / footer out of
   nav/*.html and injects them wherever a page has:

     <div data-include="../nav/sidebar.html" data-current="dashboard"></div>

   Supported attributes on the host <div>:
     data-include   path to the partial (required)
     data-current   marks the matching [data-nav="..."] link .active
     data-title     fills [data-field="title"] inside the partial
     data-subtitle  fills [data-field="subtitle"] inside the partial
     data-search    placeholder text for [data-field="search-input"];
                     omit it to hide [data-field="search-box"] entirely

   NOTE: fetch() can't read local files over file://, so open this project
   through a local server while developing, e.g. from the project root:
     npx serve .
     python3 -m http.server
   ======================================================================= */

(function () {
  function applyFields(root, el) {
    var fields = {
      title: el.getAttribute('data-title'),
      subtitle: el.getAttribute('data-subtitle'),
      'search-input': el.getAttribute('data-search')
    };

    Object.keys(fields).forEach(function (key) {
      var value = fields[key];
      var target = root.querySelector('[data-field="' + key + '"]');
      if (!target || value == null) return;
      if (target.tagName === 'INPUT') {
        target.setAttribute('placeholder', value);
      } else {
        target.textContent = value;
      }
    });

    if (!fields['search-input']) {
      var searchBox = root.querySelector('[data-field="search-box"]');
      if (searchBox) searchBox.style.display = 'none';
    }
  }

  function markActive(root, current) {
    if (!current) return;
    root.querySelectorAll('[data-nav]').forEach(function (link) {
      if (link.getAttribute('data-nav') === current) {
        link.classList.add('active');
      }
    });
  }

  function loadOne(el) {
    var src = el.getAttribute('data-include');
    if (!src) return Promise.resolve();

    return fetch(src)
      .then(function (res) {
        if (!res.ok) throw new Error('include.js: failed to fetch ' + src + ' (' + res.status + ')');
        return res.text();
      })
      .then(function (html) {
        var wrapper = document.createElement('div');
        wrapper.innerHTML = html.trim();
        var node = wrapper.firstElementChild;
        if (!node) return;

        applyFields(node, el);
        markActive(node, el.getAttribute('data-current'));
        el.replaceWith(node);
      })
      .catch(function (err) {
        console.error(err);
        el.innerHTML = '<!-- include failed: ' + src + ' -->';
      });
  }

  function loadAll() {
    var nodes = Array.prototype.slice.call(document.querySelectorAll('[data-include]'));
    Promise.all(nodes.map(loadOne)).then(function () {
      document.dispatchEvent(new CustomEvent('partial:loaded'));
    });
  }

  document.addEventListener('DOMContentLoaded', loadAll);
})();
