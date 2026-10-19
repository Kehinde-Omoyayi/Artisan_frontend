(() => {
  'use strict';

  const form = document.querySelector('[data-request-assistant]');
  if (!form) return;

  const apiErrors = window.ArtisanApiErrors;
  const conversationId = String(form.dataset.conversationId || '');
  const draftKey = `artisan-request-draft:${conversationId}`;
  const catalogueKey = `artisan-request-catalog:${conversationId}`;
  const statusNode = document.querySelector('[data-request-save-status]');
  const submitStatus = form.querySelector('[data-request-submit-status]');
  const categorySelect = form.querySelector('[data-request-category]');
  const serviceSelect = form.querySelector('[data-request-service]');
  const locationSelect = form.querySelector('[data-location-select]');
  const countryInput = form.querySelector('[data-geography-country]');
  const stateInput = form.querySelector('[data-geography-state]');
  const areaInput = form.querySelector('[data-location-area-filter]');
  const searchInput = form.querySelector('[data-location-search]');
  const dateInput = form.querySelector('[name="preferred_date"]');
  const timeStart = form.querySelector('[name="preferred_time_start"]');
  const timeEnd = form.querySelector('[name="preferred_time_end"]');
  const reviewPanel = form.querySelector('[data-request-review]');
  const reviewButton = form.querySelector('[data-request-review-button]');
  const submitButton = form.querySelector('[data-request-submit]');
  const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value
    || document.querySelector('meta[name="csrf-token"]')?.content || '';
  const optionsNode = document.getElementById('request-assistant-options');
  let requestOptions = { categories: [], services: [], locations: [] };
  let serverAssistantContext = null;
  let applyingAssistantState = false;
  let dirtyFields = new Set();
  let syncTimer = 0;
  let syncing = false;
  let reviewed = false;
  let lastSavedLocal = false;
  let localStorageAvailable = true;
  let requestSubmitted = false;
  let submitInFlight = false;
  let serverDraftExists = form.dataset.serverDraft === 'true';

  let hasServerCatalogue = false;
  try {
    const parsed = JSON.parse(optionsNode?.textContent || '{}');
    if (parsed && typeof parsed === 'object') {
      serverAssistantContext = parsed;
      const catalogue = parsed.request_options || parsed;
      requestOptions = {
        categories: Array.isArray(catalogue.categories) ? catalogue.categories : [],
        services: Array.isArray(catalogue.services) ? catalogue.services : [],
        locations: Array.isArray(catalogue.locations) ? catalogue.locations : [],
      };
      hasServerCatalogue = true;
    }
  } catch (_error) {
    // Try this conversation's local catalogue if server JSON is unavailable.
  }
  if (hasServerCatalogue) {
    try {
      localStorage.setItem(catalogueKey, JSON.stringify(requestOptions));
    } catch (_error) {
      localStorageAvailable = false;
    }
  } else {
    try {
      const cached = JSON.parse(localStorage.getItem(catalogueKey) || '{}');
      requestOptions = {
        categories: Array.isArray(cached.categories) ? cached.categories : [],
        services: Array.isArray(cached.services) ? cached.services : [],
        locations: Array.isArray(cached.locations) ? cached.locations : [],
      };
    } catch (_cacheError) {
      localStorageAvailable = false;
      requestOptions = { categories: [], services: [], locations: [] };
    }
  }

  const fieldNames = [
    'service_id', 'category_id', 'description', 'location_id', 'country', 'state', 'area',
    'preferred_date', 'preferred_time_start', 'preferred_time_end', 'preferred_time_note',
    'urgency', 'budget', 'budget_unknown', 'additional_details',
  ];

  function setStatus(text) {
    if (statusNode) statusNode.textContent = text;
  }

  function setSubmitStatus(text, isError = false) {
    if (!submitStatus) return;
    submitStatus.textContent = text;
    submitStatus.dataset.state = isError ? 'error' : 'ok';
  }

  function apiMessage(payload, status, options = {}) {
    if (apiErrors && typeof apiErrors.format === 'function') {
      return apiErrors.format(payload, status, options);
    }
    return options.networkError
      ? 'Connection unavailable. Your local draft has not been synced.'
      : 'The request could not be completed. Please try again.';
  }

  async function readResponse(response) {
    if (apiErrors && typeof apiErrors.readResponse === 'function') return apiErrors.readResponse(response);
    try { return await response.json(); } catch (_error) { return null; }
  }

  function inputFor(name) {
    return form.elements.namedItem(name);
  }

  function readValues() {
    const values = {};
    fieldNames.forEach((name) => {
      const field = inputFor(name);
      if (!field) return;
      if (name === 'budget_unknown') values[name] = field.value === 'true';
      else values[name] = String(field.value ?? '');
    });
    return values;
  }

  function applyValues(values = {}) {
    const normalized = values && typeof values === 'object' ? values : {};
    const categoryValue = String(normalized.category_id ?? '');
    const serviceValue = String(normalized.service_id ?? '');
    if (categorySelect && Object.prototype.hasOwnProperty.call(normalized, 'category_id')) categorySelect.value = categoryValue;
    filterServices();
    if (serviceSelect && Object.prototype.hasOwnProperty.call(normalized, 'service_id')) serviceSelect.value = serviceValue;
    if (serviceSelect?.selectedOptions[0]?.dataset.categoryId && categorySelect) {
      categorySelect.value = serviceSelect.selectedOptions[0].dataset.categoryId;
    }
    filterServices();
    fieldNames.forEach((name) => {
      if (name === 'category_id' || name === 'service_id') return;
      const field = inputFor(name);
      if (!field || normalized[name] === undefined || normalized[name] === null) return;
      if (name === 'budget_unknown') field.value = normalized[name] ? 'true' : 'false';
      else field.value = String(normalized[name]);
    });
    applyServiceLocations();
    syncLocationLabelsFromSelection(false);
  }

  function serverValues() {
    try {
      const context = JSON.parse(optionsNode?.textContent || '{}');
      const stateValues = context && context.request_state && context.request_state.values;
      if (stateValues && typeof stateValues === 'object') return stateValues;
    } catch (_error) {
      // Initial server-rendered inputs remain the fallback.
    }
    return {};
  }

  function getLocalDraft() {
    try {
      const draft = JSON.parse(localStorage.getItem(draftKey) || 'null');
      return draft && draft.version === 1 && draft.conversation_id === conversationId ? draft : null;
    } catch (_error) {
      localStorageAvailable = false;
      return null;
    }
  }

  function saveLocalDraft({ pending = true } = {}) {
    const draft = {
      version: 1,
      conversation_id: conversationId,
      values: readValues(),
      dirty_fields: Array.from(dirtyFields),
      pending,
      sync_status: pending ? 'pending' : 'synced',
      saved_at: new Date().toISOString(),
    };
    try {
      localStorage.setItem(draftKey, JSON.stringify(draft));
      lastSavedLocal = true;
      return true;
    } catch (_error) {
      localStorageAvailable = false;
      lastSavedLocal = false;
      return false;
    }
  }

  function mergeDraftValues(server, local) {
    const merged = { ...(server || {}) };
    if (!local || !local.values || !Array.isArray(local.dirty_fields)) return merged;
    local.dirty_fields.forEach((name) => {
      if (fieldNames.includes(name) && Object.prototype.hasOwnProperty.call(local.values, name)) {
        merged[name] = local.values[name];
      }
    });
    return merged;
  }

  function valuesEqual(name, left, right) {
    if (name === 'budget_unknown') {
      const asBoolean = (value) => value === true || String(value ?? '').toLowerCase() === 'true';
      return asBoolean(left) === asBoolean(right);
    }
    return String(left ?? '') === String(right ?? '');
  }

  function applyAssistantServerState(event) {
    if (requestSubmitted) return;
    const next = event.detail?.assistant;
    const serverValues = next?.request_state?.values;
    if (!serverValues || typeof serverValues !== 'object') return;
    const previous = event.detail?.previousValues || serverAssistantContext?.request_state?.values || {};
    const current = readValues();
    const updatedFields = fieldNames.filter((name) => (
      Object.prototype.hasOwnProperty.call(serverValues, name)
      && !valuesEqual(name, serverValues[name], previous[name])
    ));
    const nextDirtyFields = new Set(dirtyFields);
    updatedFields.forEach((name) => {
      if (nextDirtyFields.has(name) && valuesEqual(name, current[name], serverValues[name])) {
        nextDirtyFields.delete(name);
      }
    });
    const merged = { ...serverValues };
    nextDirtyFields.forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(current, name)) merged[name] = current[name];
    });

    applyingAssistantState = true;
    try {
      applyValues(merged);
    } finally {
      applyingAssistantState = false;
    }
    dirtyFields = nextDirtyFields;
    serverAssistantContext = next;

    if (updatedFields.length) {
      serverDraftExists = true;
      form.dataset.serverDraft = 'true';
      clearReviewedState();
      const hasPendingEdits = dirtyFields.size > 0;
      const saved = saveLocalDraft({ pending: hasPendingEdits });
      if (saved && !hasPendingEdits) {
        try {
          const local = JSON.parse(localStorage.getItem(draftKey) || '{}');
          local.server_saved_at = new Date().toISOString();
          localStorage.setItem(draftKey, JSON.stringify(local));
        } catch (_error) {
          // The server response is authoritative; local metadata is best-effort.
        }
      }
      setStatus(hasPendingEdits
        ? 'Chat details are saved in the conversation. Other unsynced edits remain on this device and will sync separately.'
        : 'Chat details are saved in the conversation as a draft. The request is not submitted.');
      setSubmitStatus('Your message updated the draft only. Review and submit it when you are ready.');
    }
  }

  window.addEventListener('artisan:assistant-state', applyAssistantServerState);

  function clearFieldErrors() {
    form.querySelectorAll('[data-request-field-error]').forEach((node) => {
      node.textContent = '';
      node.hidden = true;
    });
    form.querySelectorAll('[aria-invalid="true"]').forEach((field) => field.removeAttribute('aria-invalid'));
  }

  function showFieldErrors(payload) {
    const errors = payload && payload.field_errors && typeof payload.field_errors === 'object'
      ? payload.field_errors : {};
    Object.entries(errors).forEach(([name, message]) => {
      const node = Array.from(form.querySelectorAll('[data-request-field-error]'))
        .find((item) => item.dataset.requestFieldError === name);
      if (node) {
        node.textContent = String(message || '').slice(0, 500);
        node.hidden = false;
      }
      const fieldName = name === 'category_id' ? 'category_id'
        : name === 'service' ? 'service_id'
          : name;
      const field = inputFor(fieldName);
      if (field) field.setAttribute('aria-invalid', 'true');
    });
  }

  function buildFormData(action, values = readValues()) {
    const data = new FormData(form);
    data.delete('action');
    data.set('action', action);
    fieldNames.forEach((name) => {
      if (values[name] === undefined || values[name] === null) return;
      data.set(name, name === 'budget_unknown' ? (values[name] ? 'true' : 'false') : String(values[name]));
    });
    return data;
  }

  function filterServices() {
    if (!serviceSelect) return;
    const selectedCategory = String(categorySelect?.value || '');
    Array.from(serviceSelect.options).forEach((option) => {
      if (!option.value) return;
      const categoryId = String(option.dataset.categoryId || '');
      option.hidden = Boolean(selectedCategory && categoryId !== selectedCategory);
      option.disabled = option.hidden;
    });
    Array.from(serviceSelect.querySelectorAll('optgroup')).forEach((group) => {
      const categoryId = String(group.dataset.categoryId || '');
      group.hidden = Boolean(selectedCategory && categoryId !== selectedCategory);
    });
    const selected = serviceSelect.selectedOptions[0];
    if (selected && selected.disabled) serviceSelect.value = '';
  }

  function applyServiceLocations() {
    if (!locationSelect) return;
    locationSelect.dataset.serviceId = String(serviceSelect?.value || '');
    const selectedOption = locationSelect.selectedOptions[0];
    if (selectedOption && selectedOption.value) {
      const allowed = String(selectedOption.dataset.serviceIds || '').split(',').filter(Boolean);
      if (locationSelect.dataset.serviceId && allowed.length && !allowed.includes(locationSelect.dataset.serviceId)) {
        locationSelect.value = '';
      }
    }
    const filterInput = countryInput || stateInput || areaInput;
    filterInput?.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function syncLocationLabelsFromSelection(markChanged = true) {
    if (!locationSelect?.value) return;
    const record = requestOptions.locations.find((item) => String(item.id) === String(locationSelect.value));
    if (!record) return;
    const updates = [[countryInput, 'country', record.country], [stateInput, 'state', record.state], [areaInput, 'area', record.area]];
    updates.forEach(([field, name, value]) => {
      if (!field || field.value === String(value || '')) return;
      field.value = String(value || '');
      field.dispatchEvent(new Event('input', { bubbles: true }));
      if (markChanged) dirtyFields.add(name);
    });
    if (markChanged) dirtyFields.add('location_id');
  }

  function clearReviewedState() {
    reviewed = false;
    if (reviewPanel) reviewPanel.hidden = true;
    if (submitButton) submitButton.textContent = 'Submit request';
  }

  function updateTimeValidity() {
    if (!timeStart || !timeEnd) return true;
    timeEnd.setCustomValidity('');
    if (timeStart.value && timeEnd.value && timeEnd.value <= timeStart.value) {
      timeEnd.setCustomValidity('End time must be later than start time.');
      return false;
    }
    return true;
  }

  function setReviewValue(selector, value, fallback = 'Not provided') {
    const node = form.querySelector(selector);
    if (node) node.textContent = String(value || '').trim() || fallback;
  }

  function buildReview() {
    const selectedService = serviceSelect?.selectedOptions[0];
    const selectedCategory = categorySelect?.selectedOptions[0];
    const selectedLocation = locationSelect?.selectedOptions[0];
    const start = timeStart?.value || '';
    const end = timeEnd?.value || '';
    const timeNote = String(inputFor('preferred_time_note')?.value || '').trim();
    let timeText = start && end ? `${start}–${end}` : start ? `From ${start}` : end ? `Until ${end}` : '';
    if (timeNote) timeText = timeText ? `${timeText} · ${timeNote}` : timeNote;
    const unknownBudget = inputFor('budget_unknown')?.value === 'true';
    const budget = String(inputFor('budget')?.value || '').trim();

    setReviewValue('[data-review-category]', selectedCategory?.textContent, 'Choose a category');
    setReviewValue('[data-review-service]', selectedService?.textContent, 'Choose a service');
    setReviewValue('[data-review-description]', inputFor('description')?.value, 'Describe the work');
    setReviewValue('[data-review-location]', selectedLocation?.textContent, 'Choose a catalogue location');
    setReviewValue('[data-review-date]', dateInput?.value, 'Choose a preferred date');
    setReviewValue('[data-review-time]', timeText, 'No time preference');
    const urgencyField = inputFor('urgency');
    setReviewValue('[data-review-urgency]', urgencyField?.selectedOptions?.[0]?.textContent, 'Normal');
    setReviewValue('[data-review-budget]', unknownBudget ? 'Open to quote / not sure' : budget ? `₦${budget}` : '', 'No budget specified');
    setReviewValue('[data-review-additional]', inputFor('additional_details')?.value, 'None');
  }

  function validateAndReview() {
    clearFieldErrors();
    if (!updateTimeValidity()) {
      timeEnd.reportValidity();
      return false;
    }
    if (!form.reportValidity()) return false;
    buildReview();
    if (reviewPanel) {
      reviewPanel.hidden = false;
      reviewPanel.open = true;
    }
    reviewed = true;
    if (submitButton) submitButton.textContent = 'Confirm and submit request';
    setSubmitStatus('Review the summary above. You can edit any field, then confirm submission.');
    return true;
  }

  async function postRequest(action, values = readValues()) {
    const data = buildFormData(action, values);
    const response = await fetch(window.location.href, {
      method: 'POST',
      body: data,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrf,
      },
    });
    const payload = await readResponse(response);
    return { response, payload };
  }

  async function syncDraft({ manual = false } = {}) {
    if (requestSubmitted || syncing || !conversationId || dirtyFields.size === 0) return false;
    if (!navigator.onLine) {
      saveLocalDraft({ pending: true });
      setStatus(localStorageAvailable && lastSavedLocal
        ? 'Offline · saved on this device only. It will sync when you are back online.'
        : 'Offline · this browser could not save a local copy. Keep this page open until you can sync.');
      return false;
    }
    syncing = true;
    const submittedValues = readValues();
    const submittedFields = new Set(dirtyFields);
    const locallySaved = saveLocalDraft({ pending: true });
    setStatus(locallySaved
      ? 'Saved on this device · syncing the draft to this conversation…'
      : 'Syncing your changes. This browser could not save a local copy; keep this page open.');
    try {
      const { response, payload } = await postRequest('request_draft', submittedValues);
      if (requestSubmitted) return false;
      if (!response.ok || !payload || payload.ok !== true || !payload.conversation) {
        showFieldErrors(payload);
        setStatus(`${apiMessage(payload, response.status)} ${locallySaved ? 'The local draft is still available.' : 'This browser could not persist a local copy; keep this page open.'}`);
        return false;
      }
      const currentValues = readValues();
      submittedFields.forEach((name) => {
        if (String(currentValues[name] ?? '') === String(submittedValues[name] ?? '')) dirtyFields.delete(name);
      });
      serverDraftExists = true;
      form.dataset.serverDraft = 'true';
      const hasNewerEdits = dirtyFields.size > 0;
      const saved = saveLocalDraft({ pending: hasNewerEdits });
      if (saved) {
        try {
          const current = JSON.parse(localStorage.getItem(draftKey) || '{}');
          current.server_saved_at = new Date().toISOString();
          current.server_request_draft = payload?.request_draft || null;
          localStorage.setItem(draftKey, JSON.stringify(current));
        } catch (_error) {
          // The server has confirmed the save; local metadata is best-effort.
        }
      }
      if (hasNewerEdits) {
        setStatus('The earlier draft synced. Newer edits remain saved on this device and are waiting to sync.');
        window.clearTimeout(syncTimer);
        syncTimer = window.setTimeout(() => syncDraft(), 100);
      } else {
        setStatus('Draft saved on this device and synced to the marketplace conversation. It is not submitted yet.');
      }
      if (manual) setSubmitStatus(hasNewerEdits
        ? 'An earlier draft synced. New edits are still syncing; review and submit when you are ready.'
        : 'Draft saved. Review and submit it when you are ready.');
      return !hasNewerEdits;
    } catch (_error) {
      if (!requestSubmitted) setStatus(`${apiMessage(null, null, { networkError: true })} The local draft is still available.`);
      return false;
    } finally {
      syncing = false;
    }
  }

  function scheduleSync() {
    saveLocalDraft({ pending: true });
    if (!navigator.onLine) {
      setStatus(localStorageAvailable && lastSavedLocal
        ? 'Offline · saved on this device only. It will sync when you are back online.'
        : 'Offline · this browser could not save a local copy. Keep this page open until you can sync.');
      return;
    }
    setStatus(localStorageAvailable && lastSavedLocal
      ? 'Saved on this device · waiting to sync with the marketplace…'
      : 'Changes are ready to sync, but this browser could not save a local copy.');
    window.clearTimeout(syncTimer);
    syncTimer = window.setTimeout(() => syncDraft(), 900);
  }

  async function submitRequest() {
    if (requestSubmitted || submitInFlight) return;
    if (!reviewed && !validateAndReview()) return;
    if (!updateTimeValidity()) {
      timeEnd?.reportValidity();
      return;
    }
    const fields = readValues();
    const isComplete = Boolean(fields.service_id && fields.description.trim() && fields.location_id && fields.preferred_date);
    if (!isComplete) {
      validateAndReview();
      return;
    }
    if (dirtyFields.size === 0) fieldNames.forEach((name) => dirtyFields.add(name));
    const submittedValues = readValues();
    const savedLocally = saveLocalDraft({ pending: true });
    setSubmitStatus('Submitting to the marketplace…');
    const controls = Array.from(form.querySelectorAll('input, select, textarea, button'));
    const previousDisabledStates = controls.map((control) => control.disabled);
    submitInFlight = true;
    const submission = postRequest('request_submit', submittedValues);
    controls.forEach((control) => { control.disabled = true; });
    let submissionConfirmed = false;
    try {
      const { response, payload } = await submission;
      if (!response.ok || !payload || payload.ok !== true || !payload.conversation) {
        showFieldErrors(payload);
        setSubmitStatus(`${apiMessage(payload, response.status)} Your request has not been submitted.`, true);
        if (savedLocally) setStatus('The submission was rejected or could not be confirmed. Your draft remains saved on this device.');
        return;
      }
      const request = payload && payload.service_request;
      if (!request || !request.id) {
        setSubmitStatus('The marketplace did not confirm a submitted request. Your draft has not been marked as submitted.', true);
        return;
      }
      submissionConfirmed = true;
      requestSubmitted = true;
      setSubmitStatus('Request submitted and confirmed by the marketplace.');
      setStatus('Submitted · the marketplace has confirmed your service request.');
      try { localStorage.removeItem(draftKey); } catch (_error) { /* Server request is authoritative. */ }
      window.setTimeout(() => window.location.reload(), 350);
    } catch (_error) {
      setSubmitStatus(`${apiMessage(null, null, { networkError: true })} The request is not marked as submitted.`, true);
      setStatus('Submission could not be confirmed. Your local draft is retained; retry when connected.');
    } finally {
      submitInFlight = false;
      if (!submissionConfirmed) {
        controls.forEach((control, index) => { control.disabled = previousDisabledStates[index]; });
      }
    }
  }

  categorySelect?.addEventListener('change', () => {
    const nextCategory = String(categorySelect.value || '');
    const selectedServiceCategory = String(serviceSelect?.selectedOptions[0]?.dataset.categoryId || '');
    if (serviceSelect && selectedServiceCategory && selectedServiceCategory !== nextCategory) {
      serviceSelect.value = '';
      dirtyFields.add('service_id');
      if (locationSelect) locationSelect.value = '';
      dirtyFields.add('location_id');
    }
    filterServices();
    dirtyFields.add('category_id');
    clearReviewedState();
    scheduleSync();
  });

  serviceSelect?.addEventListener('change', () => {
    const selected = serviceSelect.selectedOptions[0];
    if (selected?.dataset.categoryId && categorySelect) categorySelect.value = selected.dataset.categoryId;
    filterServices();
    dirtyFields.add('service_id');
    dirtyFields.add('category_id');
    applyServiceLocations();
    syncLocationLabelsFromSelection(false);
    dirtyFields.add('location_id');
    clearReviewedState();
    scheduleSync();
  });

  locationSelect?.addEventListener('change', () => {
    syncLocationLabelsFromSelection(true);
    clearReviewedState();
    scheduleSync();
  });

  form.addEventListener('input', (event) => {
    if (applyingAssistantState) return;
    const field = event.target;
    if (!field || !field.name || !fieldNames.includes(field.name)) return;
    dirtyFields.add(field.name);
    clearReviewedState();
    if (field.name === 'preferred_time_start' || field.name === 'preferred_time_end') updateTimeValidity();
    clearFieldErrors();
    scheduleSync();
  });

  form.addEventListener('change', (event) => {
    if (applyingAssistantState) return;
    const field = event.target;
    if (!field || !field.name || !fieldNames.includes(field.name)) return;
    dirtyFields.add(field.name);
    clearReviewedState();
    if (field.name === 'preferred_time_start' || field.name === 'preferred_time_end') updateTimeValidity();
    clearFieldErrors();
    scheduleSync();
  });

  reviewButton?.addEventListener('click', () => validateAndReview());

  form.addEventListener('submit', async (event) => {
    const submitter = event.submitter;
    const action = submitter?.value || 'request_submit';
    event.preventDefault();
    window.clearTimeout(syncTimer);
    clearFieldErrors();
    if (action === 'request_draft') {
      if (dirtyFields.size === 0) fieldNames.forEach((name) => dirtyFields.add(name));
      if (navigator.onLine) await syncDraft({ manual: true });
      else {
        const saved = saveLocalDraft({ pending: true });
        setStatus(saved
          ? 'Offline · draft saved on this device only. It will sync when you are back online.'
          : 'Offline · this browser could not save a local copy. Keep this page open until you reconnect.');
        setSubmitStatus('Draft saved locally. Review and submit it after reconnecting.');
      }
      return;
    }
    if (!reviewed) {
      validateAndReview();
      return;
    }
    await submitRequest();
  });

  document.querySelector('[data-focus-attachments]')?.addEventListener('click', () => {
    const attachmentInput = document.getElementById('conversation-attachments');
    attachmentInput?.click();
  });

  window.addEventListener('online', () => {
    if (dirtyFields.size) syncDraft();
    else if (serverDraftExists) setStatus('Online · the draft is synced to the marketplace conversation, but is not submitted.');
    else setStatus('Online · there are no unsynced changes yet.');
  });
  window.addEventListener('offline', () => {
    if (dirtyFields.size) {
      saveLocalDraft({ pending: true });
      setStatus(localStorageAvailable && lastSavedLocal
        ? 'Offline · saved on this device only. It will sync when you are back online.'
        : 'Offline · this browser could not save a local copy. Keep this page open until you can sync.');
    }
  });

  const server = serverValues();
  const local = getLocalDraft();
  const initial = mergeDraftValues(server, local);
  applyValues(initial);
  dirtyFields = new Set(Array.isArray(local?.dirty_fields) ? local.dirty_fields.filter((name) => fieldNames.includes(name)) : []);
  if (!local?.pending && dirtyFields.size === 0) {
    const baselineSaved = saveLocalDraft({ pending: false });
    if (baselineSaved) {
      try {
        const current = JSON.parse(localStorage.getItem(draftKey) || '{}');
        current.server_saved_at = serverDraftExists ? new Date().toISOString() : null;
        localStorage.setItem(draftKey, JSON.stringify(current));
      } catch (_error) {
        // The in-memory server-rendered form remains usable if storage is unavailable.
      }
    }
  }
  if (local?.pending && dirtyFields.size) {
    setStatus(navigator.onLine
      ? 'Recovered an unsynced local draft. Syncing it to the conversation…'
      : 'Recovered your offline draft · saved on this device only. It will sync when you are back online.');
    if (navigator.onLine) syncDraft();
  } else if (!localStorageAvailable) {
    setStatus('Local browser storage is unavailable. Keep this page open and stay online to sync your draft.');
  } else if (!navigator.onLine) {
    setStatus('Offline · your next edits will be saved on this device and synced when you reconnect.');
  } else if (serverDraftExists || (local?.sync_status === 'synced' && local?.server_saved_at)) {
    serverDraftExists = true;
    setStatus('Draft is saved in this conversation. It is not submitted yet.');
  } else {
    setStatus('No draft has been saved yet. Changes will be saved on this device and synced when you are online.');
  }
  filterServices();
  applyServiceLocations();
  syncLocationLabelsFromSelection(false);
})();
