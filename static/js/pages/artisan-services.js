/**
 * Artisan "My services" form pickers.
 *
 * Category, Service, Country, State, Area and Institution all behave like the
 * public discovery filters: one panel open at a time, a single rotating chevron,
 * options rendered from the marketplace catalogue.
 *
 * Location rules
 *  - "Anywhere" on  -> location_id = __anywhere__ (the API's general offering)
 *  - "Anywhere" off -> Country > State > Area pick any place in the worldwide
 *    geographic catalogue (the same data as the public discovery filters) and
 *    location_id becomes the __geo__ sentinel; the server resolves the names.
 *
 * Every picker writes into the existing hidden Django form fields, so the
 * server-side validation in ArtisanServiceForm is untouched.
 */
(() => {
  const form = document.querySelector('[data-service-picker-form]');
  if (!form) return;

  const readJSON = (id, fallback) => {
    const node = document.getElementById(id);
    if (!node) return fallback;
    try {
      const value = JSON.parse(node.textContent);
      return Array.isArray(value) ? value : fallback;
    } catch (error) {
      return fallback;
    }
  };

  const readJSONObject = (id, fallback) => {
    const node = document.getElementById(id);
    if (!node) return fallback;
    try {
      const value = JSON.parse(node.textContent);
      return value && !Array.isArray(value) && typeof value === 'object' ? value : fallback;
    } catch (error) {
      return fallback;
    }
  };

  /* The world list lives in a 2.4 MB static file and is fetched the first time
     a location picker is opened; until then the pickers use what the page
     already has. */
  let geography = readJSONObject('service-geography-records', {});
  const geographyUrl = form.dataset.geographyUrl || '';
  /* The institution register is ~5 MB. It is searched and paged on the
     server: fifty rows at a time, filtered by the location pickers. */
  const institutionsUrl = form.dataset.institutionsUrl || '';
  let institutionRows = [];
  let institutionTotal = 0;
  let institutionSeq = 0;
  let institutionTimer = 0;
  let institutionLoaded = false;
  let selectedInstitution = null;
  const catalogue = readJSON('service-catalogue-records', []);

  const anywhereValue = form.dataset.anywhereValue || '__anywhere__';
  const geographicValue = form.dataset.geographicValue || '__geo__';
  const maxServices = Number.parseInt(form.dataset.maxServices || '3', 10) || 3;
  const serviceCount = Number.parseInt(form.dataset.serviceCount || '0', 10) || 0;

  const inputs = {
    category: form.querySelector('[name="category_name"]'),
    service: form.querySelector('[name="service_name"]'),
    country: form.querySelector('[name="location_country_filter"]'),
    state: form.querySelector('[name="location_state_filter"]'),
    area: form.querySelector('[name="location_area_filter"]'),
    institution: form.querySelector('[name="institution"]'),
    location: form.querySelector('[name="location_id"]'),
  };
  if (!inputs.location || !inputs.category || !inputs.service) return;

  const rows = {};
  form.querySelectorAll('[data-service-row]').forEach((row) => {
    rows[row.dataset.pickerKey] = row;
  });

  const state = {
    category: inputs.category.value || '',
    service: inputs.service.value || '',
    country: inputs.country.value || '',
    state: inputs.state.value || '',
    area: inputs.area.value || '',
    institution: inputs.institution.value || '',
    anywhere: (() => {
      const field = form.querySelector('[name="available_anywhere"]');
      if (field) {
        return ['true', '1', 'on', 'yes'].includes(String(field.value).trim().toLowerCase());
      }
      return !inputs.location.value || inputs.location.value === anywhereValue;
    })(),
  };

  /* --------------------------------------------------------------- helpers */

  const uniqueSorted = (values) =>
    [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));

  const catalogueServices = catalogue
    .filter((item) => item && item.name)
    .map((item) => ({ name: String(item.name), category: String(item.category_name || item.category || '') }));

  const servicesFor = (categoryName) =>
    catalogueServices
      .filter((item) => !categoryName || item.category === categoryName)
      .map((item) => item.name)
      .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));

  const categories = uniqueSorted(catalogueServices.map((item) => item.category));
  const countryList = () => uniqueSorted(Object.keys(geography));

  const statesFor = (countryName) =>
    countryName ? uniqueSorted(Object.keys(geography[countryName] || {})) : [];

  const areasFor = (countryName, stateName) =>
    countryName && stateName
      ? uniqueSorted((geography[countryName] || {})[stateName] || [])
      : [];

  // A complete geographic pick resolves to the __geo__ sentinel; the server
  // validates the names against the same catalogue and registers them.
  const locationFor = (countryName, stateName, areaName) =>
    countryName && stateName && areaName
      ? { id: geographicValue, country: countryName, state: stateName, area: areaName }
      : null;

  const closeRows = (except) => {
    Object.values(rows).forEach((row) => {
      if (!row || row === except) return;
      row.classList.remove('is-open');
      const head = row.querySelector('[data-picker-toggle]');
      const body = row.querySelector('[data-picker-body]');
      if (head) head.setAttribute('aria-expanded', 'false');
      if (body) body.hidden = true;
    });
  };

  const setValue = (key, label, placeholder) => {
    const row = rows[key];
    if (!row) return;
    const target = row.querySelector('[data-picker-value]');
    if (!target) return;
    const text = label || placeholder || '';
    target.textContent = text;
    target.classList.toggle('is-placeholder', !label);
  };

  const renderOptions = (key, items, onPick, selected) => {
    const row = rows[key];
    if (!row) return;
    const list = row.querySelector('[data-picker-options]');
    const empty = row.querySelector('[data-picker-empty]');
    if (!list) return;
    list.textContent = '';

    items.forEach((item) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'artisan-pick-option';
      button.setAttribute('role', 'option');
      button.dataset.value = item.value;
      button.setAttribute('aria-selected', String(item.value === selected));
      if (item.value === selected) button.classList.add('is-selected');
      button.textContent = item.label;
      button.addEventListener('click', () => {
        onPick(item);
        closeRows();
      });
      list.appendChild(button);
    });

    if (empty) empty.hidden = items.length > 0;
  };

  /* ---------------------------------------------------------------- render */

  const renderCategory = () => {
    renderOptions(
      'category',
      categories.map((name) => ({ value: name, label: name })),
      (item) => {
        state.category = item.value;
        state.service = '';
        inputs.category.value = item.value;
        inputs.service.value = '';
        setValue('category', item.value, 'Choose a category');
        setValue('service', '', 'Choose a service');
        renderService();
      },
      state.category,
    );
  };

  const renderService = () => {
    const names = servicesFor(state.category);
    const row = rows.service;
    if (row && !state.service) {
      const target = row.querySelector('[data-picker-value]');
      if (target) {
        target.textContent = state.category ? 'Choose a service' : 'Choose a category first';
        target.classList.add('is-placeholder');
      }
    }
    renderOptions(
      'service',
      names.map((name) => ({ value: name, label: name })),
      (item) => {
        state.service = item.value;
        inputs.service.value = item.value;
        setValue('service', item.value, 'Choose a service');
      },
      state.service,
    );
  };

  /* -------------------------------------------------------------- coverage */

  const syncLocation = () => {
    // The server reads "available_anywhere" plus the three names, so this hidden
    // field is only a convenience: a complete area wins, anywhere fills the gap.
    const record = locationFor(state.country, state.state, state.area);
    if (record) {
      inputs.location.value = record.id;
      return;
    }
    inputs.location.value = state.anywhere ? anywhereValue : '';
  };

  const renderCountries = () => {
    renderOptions(
      'country',
      countryList().map((name) => ({ value: name, label: name })),
      (item) => {
        state.country = item.value;
        state.state = '';
        state.area = '';
        inputs.country.value = state.country;
        inputs.state.value = '';
        inputs.area.value = '';
        setValue('country', state.country, 'All countries');
        setValue('state', '', 'All states');
        setValue('area', '', 'All areas');
        renderStates();
        renderAreas();
        syncLocation();
        renderInstitutions();
      },
      state.country,
    );
    setValue('country', state.country, 'All countries');
  };

  const renderStates = () => {
    const names = statesFor(state.country);
    renderOptions(
      'state',
      names.map((name) => ({ value: name, label: name })),
      (item) => {
        state.state = item.value;
        state.area = '';
        inputs.state.value = state.state;
        inputs.area.value = '';
        setValue('state', state.state, 'All states');
        setValue('area', '', 'All areas');
        renderAreas();
        syncLocation();
        renderInstitutions();
      },
      state.state,
    );
    setValue('state', state.state, 'All states');
  };

  const areaEmptyNote = () => {
    const row = rows.area;
    return row ? row.querySelector('[data-picker-empty="area"]') : null;
  };

  const areaLoads = new Set();
  const ensureCountryAreas = () => {
    const countryName = state.country;
    if (!countryName || !geographyUrl || !window.GeographySource) return;
    if (areasFor(countryName, state.state).length) return;
    if (areaLoads.has(countryName)) return;
    areaLoads.add(countryName);
    // GeographySource fills the shared tree in place, which is the same object
    // this page reads through `geography`.
    window.GeographySource.areas(geographyUrl, countryName)
      .then(() => {
        renderAreas();
        // A state can genuinely list no localities; say so rather than keep
        // showing "Loading…" after the answer has arrived.
        if (areasFor(countryName, state.state).length) return;
        const note = areaEmptyNote();
        if (note) {
          note.textContent = 'No areas are listed for this state yet. Choose another state, or use the closest institution below.';
          note.hidden = false;
        }
      })
      .catch(() => {
        // Say what actually happened instead of spinning forever.
        if (areasFor(countryName, state.state).length) return;
        const note = areaEmptyNote();
        if (note) {
          note.textContent = 'Could not load the areas for this state. Check your connection, then open this list again.';
          note.hidden = false;
        }
      })
      .finally(() => areaLoads.delete(countryName));
  };

  const renderAreas = () => {
    const names = areasFor(state.country, state.state);
    const row = rows.area;
    if (row && !state.area) {
      const target = row.querySelector('[data-picker-value]');
      if (target) {
        target.textContent = state.state ? 'All areas' : 'Choose a state first';
        target.classList.add('is-placeholder');
      }
    }
    const emptyNote = areaEmptyNote();
    if (emptyNote) {
      // The note is only for the open panel with nothing in it: the picker was
      // never given a state, the areas are still coming, or the fetch failed.
      if (!state.state) emptyNote.textContent = 'Choose a state first.';
      else if (!names.length) emptyNote.textContent = 'Loading areas for this state…';
      emptyNote.hidden = names.length > 0;
    }
    if (state.state && !names.length) ensureCountryAreas();
    renderOptions(
      'area',
      names.map((name) => ({ value: name, label: name })),
      (item) => {
        state.area = item.value;
        inputs.area.value = state.area;
        setValue('area', state.area, 'All areas');
        if (state.area) showCoverageNote('');
        syncLocation();
        renderInstitutions();
      },
      state.area,
    );
  };

  const institutionLabel = (item) => {
    const abbr = item.abbreviation ? ` (${item.abbreviation})` : '';
    const place = [item.area, item.state].filter(Boolean).join(', ');
    return `${item.name}${abbr}${place ? ' · ' + place : ''}`;
  };

  const institutionCountry = (item) => String(item.country || '');

  const institutionQuery = () => {
    const input = form.querySelector('[data-picker-search="institution"]');
    return input ? input.value.trim() : '';
  };

  const institutionParams = (offset) => {
    const params = new URLSearchParams();
    const query = institutionQuery();
    if (query) params.set('q', query);
    if (state.country) params.set('country', state.country);
    if (state.state) params.set('state', state.state);
    if (state.area) params.set('area', state.area);
    params.set('offset', String(offset));
    return params;
  };

  const institutionItems = () =>
    institutionRows.map((item) => ({ value: String(item.id), label: institutionLabel(item) }));

  const paintInstitutionMore = () => {
    const more = form.querySelector('[data-picker-more="institution"]');
    if (!more) return;
    const left = institutionTotal - institutionRows.length;
    more.hidden = left <= 0;
    more.textContent = left > 0 ? `Show more (${left.toLocaleString()} left)` : '';
  };

  const loadInstitutions = (reset = true) => {
    if (!institutionsUrl) return;
    const offset = reset ? 0 : institutionRows.length;
    const seq = ++institutionSeq;
    fetch(`${institutionsUrl}?${institutionParams(offset).toString()}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (seq !== institutionSeq || !payload) return;
        const rows = Array.isArray(payload.results) ? payload.results : [];
        institutionRows = reset ? rows : institutionRows.concat(rows);
        institutionTotal = Number.parseInt(payload.count || 0, 10) || institutionRows.length;
        institutionLoaded = true;
        renderInstitutions(false);
        const chosen = state.institution
          ? institutionRows.find((item) => String(item.id) === String(state.institution))
          : null;
        if (chosen && !selectedInstitution) selectedInstitution = chosen;
      })
      .catch(() => {});
  };

  const loadInstitutionById = (id) => {
    if (!institutionsUrl || !id) return;
    const url = `${institutionsUrl}?id=${encodeURIComponent(id)}`;
    fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        const row = payload && Array.isArray(payload.results) ? payload.results[0] : null;
        if (!row) return;
        selectedInstitution = row;
        inputs.institution.value = String(row.id);
        setValue('institution', institutionLabel(row), 'Optional');
      })
      .catch(() => {});
  };

  const pickInstitution = (item) => {
    const record =
      institutionRows.find((entry) => String(entry.id) === item.value) || selectedInstitution;
    if (!record) return;
    selectedInstitution = record;
    state.institution = String(record.id);
    inputs.institution.value = institutionLabel(record);
    setValue('institution', institutionLabel(record), 'Optional');

    // Picking an institution fills the geographic pickers from its record.
    if (record.country) state.country = record.country;
    if (record.state) state.state = record.state;
    if (record.area) state.area = record.area;
    inputs.country.value = state.country;
    inputs.state.value = state.state;
    inputs.area.value = state.area;
    setValue('country', state.country, 'All countries');
    renderStates();
    renderAreas();
    syncLocation();
  };

  const institutionPanelOpen = () => {
    const row = rows.institution;
    return Boolean(row && row.classList.contains('is-open'));
  };

  const renderInstitutions = (reload = true) => {
    renderOptions('institution', institutionItems(), pickInstitution, state.institution);
    paintInstitutionMore();
    // Only an open panel needs rows: a closed picker fetches when it is opened.
    if (reload && institutionPanelOpen()) loadInstitutions(true);
  };

  const institutionSearch = form.querySelector('[data-picker-search="institution"]');
  if (institutionSearch) {
    institutionSearch.addEventListener('input', () => {
      clearTimeout(institutionTimer);
      institutionTimer = setTimeout(() => loadInstitutions(true), 220);
    });
  }

  const institutionMore = form.querySelector('[data-picker-more="institution"]');
  if (institutionMore) {
    institutionMore.addEventListener('click', () => loadInstitutions(false));
  }

  const coverage = form.querySelector('[data-anywhere-toggle]');
  const locationRows = form.querySelector('[data-location-rows]');
  const caption = form.querySelector('[data-anywhere-caption]');

  /* "Available anywhere" and a named area are two promises, not two modes: both
     may be on at once, so this switch never hides the area pickers. */
  const anywhereInput = form.querySelector('[name="available_anywhere"]');
  const coverageNote = form.querySelector('[data-coverage-note]');
  const showCoverageNote = (text) => {
    if (!coverageNote) return;
    coverageNote.textContent = text || '';
    coverageNote.hidden = !text;
  };

  const setAnywhere = (value) => {
    state.anywhere = Boolean(value);
    if (anywhereInput) anywhereInput.value = state.anywhere ? 'True' : 'False';
    if (coverage) coverage.setAttribute('aria-pressed', String(state.anywhere));
    if (caption) {
      caption.textContent = state.anywhere
        ? 'Available across all locations'
        : 'Only the area you choose below';
    }
    if (state.anywhere) showCoverageNote('');
    syncLocation();
  };

  const renderCoverage = () => {
    if (coverage) coverage.setAttribute('aria-pressed', String(state.anywhere));
    if (locationRows) locationRows.hidden = false;
    if (caption) {
      caption.textContent = state.anywhere
        ? 'Available across all locations'
        : 'Only the area you choose below';
    }
    syncLocation();
  };

  if (coverage) {
    coverage.addEventListener('click', () => setAnywhere(!state.anywhere));
  }

  /* ----------------------------------------------------------- interactions */

  form.querySelectorAll('[data-picker-toggle]').forEach((head) => {
    head.addEventListener('click', () => {
      const row = head.closest('[data-service-row]');
      if (!row) return;
      const body = row.querySelector('[data-picker-body]');
      const open = !row.classList.contains('is-open');
      const key = row.dataset.pickerKey;
      if (open && key === 'institution') loadInstitutions(true);
      if (open && ['country', 'state', 'area'].includes(key) && !Object.keys(geography).length && geographyUrl && window.GeographySource) {
        window.GeographySource.load(geographyUrl)
          .then((source) => {
            geography = (source && source.tree) || {};
            renderCountries();
            renderStates();
            renderAreas();
            return key === 'area' ? window.GeographySource.areas(geographyUrl, state.country) : null;
          })
          .then(() => renderAreas())
          .catch(() => {});
      } else if (open && key === 'area' && geographyUrl && window.GeographySource) {
        window.GeographySource.areas(geographyUrl, state.country).then(() => renderAreas()).catch(() => {});
      }
      closeRows(row);
      row.classList.toggle('is-open', open);
      head.setAttribute('aria-expanded', String(open));
      if (body) body.hidden = !open;
    });
  });

  document.addEventListener('click', (event) => {
    if (!(event.target instanceof Element)) return;
    // Keep the panel that was just toggled (or an option inside it) open.
    if (event.target.closest('[data-picker-toggle]') || event.target.closest('[data-picker-body]')) return;
    closeRows();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeRows();
  });

  /* ----------------------------------------------------------------- limit */

  const atLimit = serviceCount >= maxServices;
  form.addEventListener('submit', (event) => {
    const editing = form.querySelector('[name="offering_id"]');
    if (atLimit && !editing) {
      event.preventDefault();
      return;
    }
    if (!state.anywhere && !inputs.location.value) {
      event.preventDefault();
      showCoverageNote('Choose where this service is offered: available anywhere, one specific area, or both.');
      renderCoverage();
      const countryRow = rows.country;
      if (countryRow) {
        closeRows(countryRow);
        countryRow.classList.add('is-open');
        const head = countryRow.querySelector('[data-picker-toggle]');
        const body = countryRow.querySelector('[data-picker-body]');
        if (head) head.setAttribute('aria-expanded', 'true');
        if (body) body.hidden = false;
      }
    }
  });

  /* ---------------------------------------------------------------- paint */

  renderCategory();
  renderService();
  renderCountries();
  renderStates();
  renderAreas();
  renderInstitutions();
  renderCoverage();
  if (state.institution && !institutionLoaded) loadInstitutionById(state.institution);

  setValue('category', state.category, 'Choose a category');
  setValue('service', state.service, 'Choose a service');
  setValue('country', state.country, 'All countries');
  setValue('state', state.state, 'All states');
  setValue('area', state.area, 'All areas');
})();