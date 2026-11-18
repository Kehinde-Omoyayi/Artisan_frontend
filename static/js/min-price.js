/* Minimum individual price — ₦100.00.
 *
 * The browser-side half of a rule the backend enforces on every API call.
 * Every input carrying [data-min-price] is checked as the artisan types:
 *
 *   data-min-price="required"  -> must be a number >= 100 whenever entered
 *                                 (blank falls through to the form's own
 *                                 required handling / the API's message)
 *   data-min-price="optional"  -> exactly 0 (or blank) is "not charged" and
 *                                 stays valid; anything else must be >= 100
 *
 * Violations show the platform-standard inline message and block submission
 * until fixed. Nothing is ever silently rounded up to ₦100.
 */
(function () {
  'use strict';

  var MIN = 100;
  var MESSAGE = 'The minimum permitted price for an item or service is ₦100.00.';

  function parse(value) {
    var text = String(value == null ? '' : value).trim().replace(/,/g, '');
    if (!text) return null;
    var number = Number(text);
    return Number.isFinite(number) ? number : NaN;
  }

  function fieldError(input) {
    var parsed = parse(input.value);
    var mode = (input.getAttribute('data-min-price') || 'required').toLowerCase();
    if (parsed === null) return null; // blank: defer to required/API handling
    if (Number.isNaN(parsed)) return MESSAGE;
    if (mode === 'optional' && parsed === 0) return null;
    if (parsed < MIN) return MESSAGE;
    return null;
  }

  function ownHost(input) {
    return input.parentNode;
  }

  function showError(input, message) {
    var host = ownHost(input);
    if (!host) return;
    var note = host.querySelector ? host.querySelector('.min-price-error') : null;
    if (!note) {
      note = document.createElement('span');
      note.className = 'field-error min-price-error';
      note.setAttribute('role', 'alert');
      host.appendChild(note);
    }
    note.textContent = message;
    input.setAttribute('aria-invalid', 'true');
    input.classList.add('field-invalid');
  }

  function clearError(input) {
    var host = ownHost(input);
    if (host && host.querySelector) {
      var note = host.querySelector('.min-price-error');
      if (note) note.remove();
    }
    input.removeAttribute('aria-invalid');
    input.classList.remove('field-invalid');
  }

  function validateInput(input) {
    var message = fieldError(input);
    if (message) {
      showError(input, message);
      return false;
    }
    clearError(input);
    return true;
  }

  function validateForm(form) {
    var inputs = form.querySelectorAll('[data-min-price]');
    var ok = true;
    inputs.forEach(function (input) {
      if (!validateInput(input)) ok = false;
    });
    return ok;
  }

  /* Live validation, delegated so dynamically added rows are covered. */
  ['input', 'change', 'blur'].forEach(function (eventName) {
    document.addEventListener(eventName, function (event) {
      var input = event.target && event.target.closest ? event.target.closest('[data-min-price]') : null;
      if (input) validateInput(input);
    }, true);
  });

  /* Submission gate: capture phase, so no other handler can slip a below-
     minimum price past the form. The API still re-checks everything. */
  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!form || !form.querySelectorAll) return;
    if (!form.querySelector('[data-min-price]')) return;
    if (!validateForm(form)) {
      event.preventDefault();
      event.stopImmediatePropagation();
      var firstInvalid = form.querySelector('[data-min-price][aria-invalid="true"]');
      if (firstInvalid) {
        firstInvalid.focus();
        var status = form.querySelector('[data-offer-review-status], #chat-status, .request-submit-status');
        if (status) status.textContent = MESSAGE;
      }
    }
  }, true);

  window.ArtisanMinPrice = {
    MIN: MIN,
    MESSAGE: MESSAGE,
    check: function (value, options) {
      var mode = (options && options.allowZero) ? 'optional' : 'required';
      var parsed = parse(value);
      if (parsed === null) return true; // blank: not a below-minimum charge
      if (Number.isNaN(parsed)) return false;
      if (mode === 'optional' && parsed === 0) return true;
      return parsed >= MIN;
    },
    validateForm: validateForm,
  };
})();
