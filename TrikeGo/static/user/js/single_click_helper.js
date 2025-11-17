(function () {
  function getCsrfToken() {
    // Try common injection points
    if (window.RIDER_DASH_CONFIG && window.RIDER_DASH_CONFIG.csrfToken) return window.RIDER_DASH_CONFIG.csrfToken;
    const el = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (el) return el.value;
    // fallback cookie
    const match = document.cookie.match('(^|;)\\s*' + 'csrftoken' + '\\s*=\\s*([^;]+)');
    return match ? match.pop() : '';
  }

  function createSpinner() {
    const spinner = document.createElement('span');
    spinner.className = 'btn-loading-spinner';
    spinner.setAttribute('aria-hidden', 'true');
    return spinner;
  }

  function setLoadingState(button) {
    if (!button) return;
    button.dataset._origHtml = button.innerHTML;
    // Replace button content with spinner and visually-hidden label
    const label = document.createElement('span');
    label.className = 'btn-loading-label';
    label.textContent = button.dataset.loadingText || 'Loading...';
    label.style.display = 'inline-block';

    const spinner = createSpinner();

    button.innerHTML = '';
    button.appendChild(spinner);
    button.appendChild(label);
    button.classList.add('is-loading');
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
  }

  function clearLoadingState(button) {
    if (!button) return;
    button.classList.remove('is-loading');
    button.disabled = false;
    button.removeAttribute('aria-busy');
    if (button.dataset._origHtml) {
      button.innerHTML = button.dataset._origHtml;
      delete button.dataset._origHtml;
    }
  }

  async function handleFetchClick(e, button) {
    e.preventDefault();
    if (button.dataset.processing === 'true') return;
    button.dataset.processing = 'true';
    setLoadingState(button);

    const url = button.dataset.url;
    const method = (button.dataset.method || 'POST').toUpperCase();
    const bodyType = button.dataset.bodyType || 'form'; // 'json' or 'form'

    const headers = new Headers({ 'X-Requested-With': 'XMLHttpRequest' });
    const csrf = getCsrfToken();
    if (csrf) headers.set('X-CSRFToken', csrf);

    const opts = { method, headers, credentials: 'same-origin' };
    if (method !== 'GET') {
      if (bodyType === 'json' && button.dataset.body) {
        headers.set('Content-Type', 'application/json');
        opts.body = button.dataset.body;
      } else if (button.dataset.formSelector) {
        const form = document.querySelector(button.dataset.formSelector);
        if (form) opts.body = new FormData(form);
      } else if (button.dataset.form) {
        // allow passing form html id
        const f = document.getElementById(button.dataset.form);
        if (f) opts.body = new FormData(f);
      } else if (button.dataset.body) {
        // treat as urlencoded
        headers.set('Content-Type', 'application/x-www-form-urlencoded');
        opts.body = button.dataset.body;
      }
    }

    try {
      const res = await fetch(url, opts);
      let payload = null;
      const ct = res.headers.get('content-type') || '';
      if (ct.indexOf('application/json') !== -1) payload = await res.json();
      else payload = await res.text();

      if (!res.ok) {
        button.dispatchEvent(new CustomEvent('single-click-error', { detail: { status: res.status, payload } }));
      } else {
        button.dispatchEvent(new CustomEvent('single-click-success', { detail: payload }));
      }
      return payload;
    } catch (err) {
      button.dispatchEvent(new CustomEvent('single-click-error', { detail: err }));
      throw err;
    } finally {
      button.dataset.processing = 'false';
      clearLoadingState(button);
    }
  }

  document.addEventListener('click', function (ev) {
    const button = ev.target.closest('[data-single-click]');
    if (!button) return;

    // If a data-url is present, we will intercept and fetch
    if (button.dataset.url) {
      handleFetchClick(ev, button);
      return;
    }

    // For form-submit buttons, prevent double-submits by disabling until navigation
    const form = button.closest('form');
    if (form) {
      if (button.dataset.processing === 'true') {
        ev.preventDefault();
        return;
      }
      // allow native submit but set processing state and loading UI
      button.dataset.processing = 'true';
      setLoadingState(button);
      // Do NOT clear loading immediately. Expect calling code to dispatch 'single-click-success'/'single-click-error' or call clearLoading.
      // Fallback to clear after 30s to avoid stuck UI in case of navigation issues.
      setTimeout(function () {
        if (button.dataset.processing === 'true') {
          button.dataset.processing = 'false';
          clearLoadingState(button);
        }
      }, 30000);
      return; // let form submit normally
    }

    // If not a form and not an URL, we still guard against double click and show loading briefly
    if (button.dataset.processing === 'true') {
      ev.preventDefault();
      return;
    }

    button.dataset.processing = 'true';
    setLoadingState(button);
    // Do NOT auto-clear quickly; expect caller to dispatch events or call clearLoading. Use longer fallback.
    setTimeout(() => {
      if (button.dataset.processing === 'true') {
        button.dataset.processing = 'false';
        clearLoadingState(button);
      }
    }, 30000);
  }, true);

  // Listen for explicit success/error events dispatched by page code to clear loading
  document.addEventListener('single-click-success', function (ev) {
    const target = ev.target;
    if (target && target.matches && target.matches('[data-single-click]')) {
      clearLoadingState(target);
      target.dataset.processing = 'false';
    }
  }, true);

  document.addEventListener('single-click-error', function (ev) {
    const target = ev.target;
    if (target && target.matches && target.matches('[data-single-click]')) {
      clearLoadingState(target);
      target.dataset.processing = 'false';
    }
  }, true);

  // Expose helper to window for programmatic control
  window.singleClickHelper = {
    setLoading: setLoadingState,
    clearLoading: clearLoadingState
  };
})();
