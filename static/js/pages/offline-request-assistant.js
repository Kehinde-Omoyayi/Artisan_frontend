(() => {
  'use strict';

  const root = document.querySelector('[data-offline-request-root]');
  const form = document.querySelector('[data-offline-assistant]');
  if (!root || !form) return;

  const apiErrors = window.ArtisanApiErrors;
  const statusNode = document.querySelector('[data-offline-status]');
  const catalogueStatus = document.querySelector('[data-offline-catalog-status]');
  const saveButton = document.querySelector('[data-save-offline]');
  const syncButton = document.querySelector('[data-sync-offline]');
  const returnLink = document.querySelector('[data-offline-return]');
  const categorySelect = form.querySelector('[data-offline-category]');
  const serviceSelect = form.querySelector('[data-offline-service]');
  const countrySelect = form.querySelector('[data-offline-country]');
  const stateSelect = form.querySelector('[data-offline-state]');
  const areaSelect = form.querySelector('[data-offline-area]');
  const locationSelect = form.querySelector('[data-offline-location]');
  const searchInput = form.querySelector('[data-offline-location-search]');
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const formFields = [
    'service_id', 'category_id', 'description', 'location_id', 'country', 'state', 'area',
    'preferred_date', 'preferred_time_start', 'preferred_time_end', 'preferred_time_note',
    'urgency', 'budget', 'budget_unknown', 'additional_details',
  ];
  let conversationId = '';
  let draft = null;
  let catalogue = { categories: [], services: [], locations: [] };
  let dirtyFields = new Set();
  let syncing = false;
  let syncTimer = 0;
  let localStorageAvailable = true;

  function setStatus(message, isError = false) {
    if (!statusNode) return;
    statusNode.textContent = message;
    statusNode.dataset.state = isError ? 'error' : 'ok';
  }

  function getConversationId() {
    const queryId = new URLSearchParams(window.location.search).get('conversation_id');
    const pathMatch = window.location.pathname.match(/\/discover\/conversations\/([0-9a-f-]{36})\/?$/i);
    const value = String(queryId || pathMatch?.[1] || '').toLowerCase();
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value) ? value : '';
  }

  function readStorage(key) {
    try { return JSON.parse(localStorage.getItem(key) || 'null'); }
    catch (_error) { localStorageAvailable = false; return null; }
  }

  function writeStorage(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (_error) {
      localStorageAvailable = false;
      return false;
    }
  }

  function field(name) { return form.elements.namedItem(name); }

  function readValues() {
    const values = {};
    formFields.forEach((name) => {
      const control = field(name);
      if (!control) return;
      values[name] = name === 'budget_unknown' ? control.value === 'true' : String(control.value ?? '');
    });
    return values;
  }

  function applyValues(values = {}) {
    if (values.category_id !== undefined && values.category_id !== null) categorySelect.value = String(values.category_id);
    renderServices(String(values.category_id || ''), String(values.service_id || ''));
    if (values.service_id !== undefined && values.service_id !== null) serviceSelect.value = String(values.service_id);
    renderServices(String(values.category_id || ''), String(values.service_id || ''));
    formFields.forEach((name) => {
      if (['category_id', 'service_id', 'country', 'state', 'area', 'location_id'].includes(name)) return;
      const control = field(name);
      if (!control || values[name] === undefined || values[name] === null) return;
      control.value = name === 'budget_unknown' ? (values[name] ? 'true' : 'false') : String(values[name]);
    });
    refreshLocations({ selectSaved: true, savedValues: values });
  }

  function makeOption(label, value = '') {
    const option = document.createElement('option');
    option.value = String(value);
    option.textContent = String(label);
    return option;
  }

  function populateCatalogue() {
    categorySelect.replaceChildren(makeOption(catalogue.categories.length ? 'Choose a category' : 'No cached categories'));
    catalogue.categories.forEach((category) => categorySelect.appendChild(makeOption(category.name, category.id)));
    renderServices();
    if (!catalogue.services.length) {
      catalogueStatus.textContent = 'No service catalogue is cached for this conversation yet. Open the conversation while online once to load the artisan’s real services and locations.';
    } else {
      catalogueStatus.textContent = 'Using the service and location catalogue previously loaded for this conversation. No new locations can be invented offline.';
    }
  }

  function renderServices(selectedCategory = categorySelect.value, selectedService = serviceSelect.value) {
    const categories = catalogue.categories || [];
    serviceSelect.replaceChildren(makeOption(catalogue.services.length ? 'Choose a service' : 'No cached services'));
    categories.forEach((category) => {
      if (selectedCategory && String(category.id) !== String(selectedCategory)) return;
      (category.services || []).forEach((service) => {
        const option = makeOption(service.name, service.id);
        option.dataset.categoryId = String(category.id);
        serviceSelect.appendChild(option);
      });
    });
    if (selectedService) serviceSelect.value = String(selectedService);
    if (serviceSelect.selectedOptions[0]?.dataset.categoryId && categorySelect.value !== serviceSelect.selectedOptions[0].dataset.categoryId) {
      categorySelect.value = serviceSelect.selectedOptions[0].dataset.categoryId;
    }
  }

  function selectedService() {
    return catalogue.services.find((item) => String(item.id) === String(serviceSelect.value)) || null;
  }

  function locationsForSelection() {
    const service = selectedService();
    if (service) return Array.isArray(service.locations) ? service.locations : [];
    const categoryId = String(categorySelect.value || '');
    if (categoryId) {
      const all = catalogue.categories.find((item) => String(item.id) === categoryId);
      const locations = new Map();
      (all?.services || []).forEach((item) => (item.locations || []).forEach((location) => locations.set(String(location.id), location)));
      return Array.from(locations.values());
    }
    return Array.isArray(catalogue.locations) ? catalogue.locations : [];
  }

  function uniqueValues(records, fieldName) {
    return Array.from(new Set(records.map((item) => String(item[fieldName] || '').trim()).filter(Boolean)))
      .sort((a, b) => a.localeCompare(b));
  }

  function filteredLocations() {
    const records = locationsForSelection();
    const country = String(countrySelect.value || '').trim().toLowerCase();
    const state = String(stateSelect.value || '').trim().toLowerCase();
    const area = String(areaSelect.value || '').trim().toLowerCase();
    const search = String(searchInput.value || '').trim().toLowerCase();
    return records.filter((record) => {
      const countryMatches = !country || String(record.country || '').toLowerCase() === country;
      const stateMatches = !state || String(record.state || '').toLowerCase() === state;
      const areaMatches = !area || String(record.area || '').toLowerCase() === area;
      const searchText = `${record.country || ''} ${record.state || ''} ${record.area || ''}`.toLowerCase();
      return countryMatches && stateMatches && areaMatches && (!search || searchText.includes(search));
    });
  }

  function fillFilter(select, placeholder, values, selectedValue) {
    select.replaceChildren(makeOption(placeholder));
    values.forEach((value) => select.appendChild(makeOption(value, value)));
    if (selectedValue && values.includes(selectedValue)) select.value = selectedValue;
  }

  function refreshLocations({ selectSaved = false, savedValues = null } = {}) {
    const records = locationsForSelection();
    const previousLocationId = String(locationSelect.value || '');
    const wanted = savedValues && typeof savedValues === 'object' ? savedValues : readValues();
    const countryWanted = selectSaved ? String(wanted.country || '') : countrySelect.value;
    const stateWanted = selectSaved ? String(wanted.state || '') : stateSelect.value;
    const areaWanted = selectSaved ? String(wanted.area || '') : areaSelect.value;
    const countries = uniqueValues(records, 'country');
    fillFilter(countrySelect, countries.length ? 'Choose country' : 'No cached countries', countries, countryWanted);
    const statesForCountry = records.filter((item) => !countrySelect.value || item.country === countrySelect.value);
    const states = uniqueValues(statesForCountry, 'state');
    fillFilter(stateSelect, states.length ? 'Choose state or region' : 'No cached states', states, stateWanted);
    const areasForState = statesForCountry.filter((item) => !stateSelect.value || item.state === stateSelect.value);
    const areas = uniqueValues(areasForState, 'area');
    fillFilter(areaSelect, areas.length ? 'Choose area' : 'No cached areas', areas, areaWanted);

    const matching = filteredLocations();
    locationSelect.replaceChildren(makeOption(matching.length ? 'Choose exact catalogue location' : 'No matching cached location'));
    matching.forEach((location) => {
      locationSelect.appendChild(makeOption(location.label || `${location.area}, ${location.state}, ${location.country}`, location.id));
    });
    const savedLocationId = selectSaved ? String(wanted.location_id || '') : previousLocationId;
    if (savedLocationId && matching.some((item) => String(item.id) === savedLocationId)) locationSelect.value = savedLocationId;
  }

  function syncLocationFromId() {
    const selected = locationsForSelection().find((item) => String(item.id) === String(locationSelect.value));
    if (!selected) return;
    countrySelect.value = selected.country;
    refreshLocations();
    stateSelect.value = selected.state;
    refreshLocations();
    areaSelect.value = selected.area;
    refreshLocations();
  }

  function markDirty(name) {
    if (formFields.includes(name)) dirtyFields.add(name);
  }

  function persistLocal({ pending = true } = {}) {
    const values = readValues();
    const existing = draft && typeof draft === 'object' ? draft : {};
    draft = {
      version: 1,
      conversation_id: conversationId,
      values,
      dirty_fields: pending ? (dirtyFields.size ? Array.from(dirtyFields) : formFields.slice()) : [],
      pending,
      sync_status: pending ? 'pending' : 'synced',
      saved_at: new Date().toISOString(),
      server_saved_at: existing.server_saved_at || null,
    };
    const saved = writeStorage(`artisan-request-draft:${conversationId}`, draft);
    setStatus(saved
      ? (pending ? 'Saved on this device only · not submitted to the marketplace.' : 'Draft synced to the conversation · not submitted.')
      : 'This browser could not store the draft. Keep this page open and sync while connected.');
    return saved;
  }

  function syncSchedule() {
    persistLocal({ pending: true });
    window.clearTimeout(syncTimer);
    if (navigator.onLine) syncTimer = window.setTimeout(syncDraft, 900);
  }

  function payloadFormData(values = readValues()) {
    const data = new FormData();
    data.set('action', 'request_draft');
    formFields.forEach((name) => {
      if (values[name] === undefined || values[name] === null) return;
      const value = name === 'budget_unknown' ? (values[name] ? 'true' : 'false') : String(values[name]);
      data.set(name, value);
    });
    return data;
  }

  async function syncDraft() {
    if (syncing || !dirtyFields.size) return false;
    if (!conversationId) {
      setStatus('No conversation is linked to this draft. Return to a conversation to load its request catalogue.', true);
      return false;
    }
    if (!navigator.onLine) {
      persistLocal({ pending: true });
      return false;
    }
    syncing = true;
    const submittedValues = readValues();
    const submittedFields = new Set(dirtyFields);
    if (syncButton) syncButton.disabled = true;
    setStatus('Syncing draft to the existing conversation…');
    try {
      const response = await fetch(`/discover/conversations/${encodeURIComponent(conversationId)}/`, {
        method: 'POST',
        body: payloadFormData(submittedValues),
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf },
      });
      let payload = null;
      if (apiErrors && typeof apiErrors.readResponse === 'function') payload = await apiErrors.readResponse(response);
      else { try { payload = await response.json(); } catch (_error) { payload = null; } }
      if (!response.ok || !payload || payload.ok !== true || !payload.conversation) {
        const message = apiErrors?.format
          ? apiErrors.format(payload, response.status)
          : 'The marketplace did not confirm the draft sync.';
        setStatus(`${message} The local draft is retained.`, true);
        return false;
      }
      const currentValues = readValues();
      submittedFields.forEach((name) => {
        if (String(currentValues[name] ?? '') === String(submittedValues[name] ?? '')) dirtyFields.delete(name);
      });
      const hasNewerEdits = dirtyFields.size > 0;
      const saved = persistLocal({ pending: hasNewerEdits });
      if (saved) {
        draft.server_saved_at = new Date().toISOString();
        draft.server_request_draft = payload.request_draft || null;
        writeStorage(`artisan-request-draft:${conversationId}`, draft);
      }
      if (hasNewerEdits) {
        setStatus('The earlier draft synced. Newer edits remain saved on this device and are waiting to sync.');
        window.clearTimeout(syncTimer);
        syncTimer = window.setTimeout(() => syncDraft(), 100);
      } else {
        setStatus('Draft synced to the real marketplace conversation. It is still editable and has not been submitted.');
      }
      return !hasNewerEdits;
    } catch (_error) {
      persistLocal({ pending: true });
      const message = apiErrors?.format
        ? apiErrors.format(null, null, { networkError: true })
        : 'Could not connect to the marketplace.';
      setStatus(`${message} The local draft is retained.`, true);
      return false;
    } finally {
      syncing = false;
      if (syncButton) syncButton.disabled = false;
    }
  }

  conversationId = getConversationId();
  const returnPath = conversationId ? `/discover/conversations/${encodeURIComponent(conversationId)}/` : '/discover/conversations/';
  if (returnLink) returnLink.href = returnPath;
  if (!conversationId) {
    setStatus('This offline workspace is not linked to a conversation yet. Open the conversation once, then return here to continue its draft.');
  }

  catalogue = readStorage(`artisan-request-catalog:${conversationId}`) || catalogue;
  catalogue = {
    categories: Array.isArray(catalogue.categories) ? catalogue.categories : [],
    services: Array.isArray(catalogue.services) ? catalogue.services : [],
    locations: Array.isArray(catalogue.locations) ? catalogue.locations : [],
  };
  populateCatalogue();
  const loadedDraft = conversationId ? readStorage(`artisan-request-draft:${conversationId}`) : null;
  if (loadedDraft && loadedDraft.values) {
    draft = loadedDraft;
    dirtyFields = new Set(Array.isArray(loadedDraft.dirty_fields) ? loadedDraft.dirty_fields.filter((name) => formFields.includes(name)) : []);
    applyValues(loadedDraft.values);
    setStatus(loadedDraft.pending
      ? 'Recovered your saved draft from this device. It has not been submitted.'
      : 'Recovered the latest local copy. It has not been submitted.');
  } else if (!navigator.onLine) {
    setStatus('Offline · complete the fields you can. Only cached catalogue choices are available.');
  } else if (conversationId) {
    setStatus('No local draft was found for this conversation. Your input will be saved on this device.');
  }

  categorySelect.addEventListener('change', () => {
    renderServices(categorySelect.value, '');
    dirtyFields.add('category_id');
    dirtyFields.add('service_id');
    serviceSelect.value = '';
    locationSelect.value = '';
    ['location_id', 'country', 'state', 'area'].forEach(markDirty);
    refreshLocations();
    syncSchedule();
  });
  serviceSelect.addEventListener('change', () => {
    const service = selectedService();
    if (service?.category_id) categorySelect.value = String(service.category_id);
    renderServices(categorySelect.value, serviceSelect.value);
    ['service_id', 'category_id', 'location_id', 'country', 'state', 'area'].forEach(markDirty);
    locationSelect.value = '';
    refreshLocations();
    syncSchedule();
  });
  [countrySelect, stateSelect, areaSelect, searchInput].forEach((control) => control.addEventListener('change', () => {
    if (control === countrySelect) { stateSelect.value = ''; areaSelect.value = ''; locationSelect.value = ''; }
    if (control === stateSelect) { areaSelect.value = ''; locationSelect.value = ''; }
    if (control === areaSelect) locationSelect.value = '';
    refreshLocations();
    ['country', 'state', 'area', 'location_id'].forEach(markDirty);
    syncSchedule();
  }));
  [countrySelect, stateSelect, areaSelect, searchInput].forEach((control) => control.addEventListener('input', () => {
    refreshLocations();
    if (control === countrySelect) { stateSelect.value = ''; areaSelect.value = ''; locationSelect.value = ''; }
    if (control === stateSelect) { areaSelect.value = ''; locationSelect.value = ''; }
    if (control === areaSelect) locationSelect.value = '';
    ['country', 'state', 'area', 'location_id'].forEach(markDirty);
    syncSchedule();
  }));
  locationSelect.addEventListener('change', () => {
    syncLocationFromId();
    ['location_id', 'country', 'state', 'area'].forEach(markDirty);
    syncSchedule();
  });
  form.addEventListener('input', (event) => {
    if (!event.target?.name || !formFields.includes(event.target.name)) return;
    dirtyFields.add(event.target.name);
    syncSchedule();
  });
  form.addEventListener('change', (event) => {
    if (!event.target?.name || !formFields.includes(event.target.name)) return;
    dirtyFields.add(event.target.name);
    syncSchedule();
  });

  saveButton?.addEventListener('click', () => {
    if (dirtyFields.size === 0) formFields.forEach(markDirty);
    persistLocal({ pending: true });
  });
  syncButton?.addEventListener('click', () => {
    if (dirtyFields.size === 0) formFields.forEach(markDirty);
    persistLocal({ pending: true });
    syncDraft();
  });
  window.addEventListener('online', () => {
    if (dirtyFields.size) syncDraft();
    else setStatus('Online · no unsynced offline edits are waiting.');
  });
  window.addEventListener('offline', () => {
    if (dirtyFields.size) persistLocal({ pending: true });
    setStatus('Offline · changes are stored on this device only until the connection returns.');
  });
})();
