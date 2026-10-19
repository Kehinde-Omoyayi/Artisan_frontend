document.addEventListener('DOMContentLoaded', () => {
  /* ------------------------------------------------------------------ */
  /* Profile photos fall back to the initial when the image is missing.  */
  /* ------------------------------------------------------------------ */
  document.querySelectorAll('.artisan-discovery-photo').forEach((photo) => {
    photo.addEventListener('error', () => {
      photo.hidden = true;
      const fallback = photo.parentElement && photo.parentElement.querySelector('.artisan-discovery-avatar-fallback');
      if (fallback) fallback.hidden = false;
    }, { once: true });
  });

  const form = document.querySelector('[data-discovery-form]');
  const filterRoot = document.querySelector('[data-filter-root]');
  const filterToggle = document.querySelector('[data-filter-toggle]');
  const filterPanel = document.querySelector('[data-filter-panel]');
  const filterScrim = document.querySelector('[data-filter-scrim]');
  const filterClose = document.querySelector('[data-filter-close]');
  const filterClear = document.querySelector('[data-filter-clear]');
  const filterBadge = document.querySelector('[data-filter-count]');

  if (!form || !filterRoot || !filterToggle || !filterPanel) return;

  const PLACEHOLDERS = {
    country: 'All countries',
    state: 'All states',
    area: 'All areas',
    institution_id: 'All institutions',
  };
  const GEO_KEYS = Object.keys(PLACEHOLDERS);
  const ALL_KEYS = ['category_name', 'service_name', ...GEO_KEYS];

  const input = (key) => form.querySelector(`[data-filter-input="${key}"]`);
  const row = (key) => filterPanel.querySelector(`[data-filter-row][data-filter-key="${key}"]`);
  const optionsBox = (key) => filterPanel.querySelector(`[data-filter-options="${key}"]`);
  const valueLabel = (key) => {
    const current = row(key);
    return current ? current.querySelector('[data-filter-value]') : null;
  };

  /* ------------------------------------------------------------------ */
  /* Right-hand glass panel: open, close and focus handling.             */
  /* ------------------------------------------------------------------ */
  let closeTimer = null;
  // The click that opens the panel lands the pointer inside it; a short grace
  // period stops that stray hover from expanding a category by accident.
  let hoverGraceUntil = 0;

  /* The panel should never clip a dropdown row. Measure its natural height and
     give it the most room the viewport can offer: below the trigger, above it,
     or floating just under the sticky header on short screens. */
  const placePanel = (naturalHeight) => {
    const isMobile = window.matchMedia('(max-width: 760px)').matches;
    filterPanel.style.removeProperty('top');
    filterPanel.style.removeProperty('right');

    if (isMobile) {
      filterPanel.classList.remove('is-above', 'is-floating');
      filterPanel.style.maxHeight = 'min(86vh, 760px)';
      return;
    }

    const rect = filterToggle.getBoundingClientRect();
    const below = window.innerHeight - rect.bottom - 24;
    const above = rect.top - 24;
    const natural = Math.min(naturalHeight, window.innerHeight - 40);

    if (natural <= below) {
      filterPanel.classList.remove('is-above', 'is-floating');
      filterPanel.style.maxHeight = `${Math.max(natural, 260)}px`;
      return;
    }

    if (natural <= above) {
      filterPanel.classList.remove('is-floating');
      filterPanel.classList.add('is-above');
      filterPanel.style.maxHeight = `${natural}px`;
      return;
    }

    filterPanel.classList.remove('is-above');
    filterPanel.classList.add('is-floating');
    filterPanel.style.top = '84px';
    filterPanel.style.right = `${Math.max(12, Math.round(window.innerWidth - rect.right))}px`;
    filterPanel.style.maxHeight = 'calc(100dvh - 104px)';
  };

  const measurePanel = () => {
    filterPanel.style.visibility = 'hidden';
    filterPanel.style.maxHeight = 'none';
    filterPanel.classList.remove('is-above', 'is-floating');
    filterPanel.hidden = false;
    const naturalHeight = filterPanel.offsetHeight;
    filterPanel.style.visibility = '';
    return naturalHeight;
  };

  const openPanel = () => {
    window.clearTimeout(closeTimer);
    hoverGraceUntil = Date.now() + 350;
    placePanel(measurePanel());
    if (filterScrim) filterScrim.hidden = false;
    filterToggle.setAttribute('aria-expanded', 'true');
    filterRoot.classList.add('is-open');
    window.requestAnimationFrame(() => {
      filterPanel.classList.add('is-visible');
      if (filterScrim) filterScrim.classList.add('is-visible');
    });
  };

  const closePanel = (restoreFocus = false) => {
    filterPanel.classList.remove('is-visible');
    if (filterScrim) filterScrim.classList.remove('is-visible');
    filterToggle.setAttribute('aria-expanded', 'false');
    filterRoot.classList.remove('is-open');
    closeAllRows();
    window.clearTimeout(closeTimer);
    closeTimer = window.setTimeout(() => {
      filterPanel.hidden = true;
      if (filterScrim) filterScrim.hidden = true;
    }, 200);
    if (restoreFocus) filterToggle.focus({ preventScroll: true });
  };

  window.addEventListener('resize', () => {
    if (filterPanel.hidden) return;
    placePanel(measurePanel());
  });

  filterToggle.addEventListener('click', () => {
    if (filterPanel.hidden) openPanel();
    else closePanel(true);
  });
  if (filterClose) filterClose.addEventListener('click', () => closePanel(true));
  window.addEventListener('resize', () => { if (!filterPanel.hidden) fitPanelToViewport(); });
  if (filterScrim) filterScrim.addEventListener('click', () => closePanel(true));

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || filterPanel.hidden) return;
    event.preventDefault();
    closePanel(true);
  });

  // `composedPath()` is captured when the event fires, so clicks on options still
  // count as "inside" even though choosing one rebuilds (detaches) the clicked node.
  document.addEventListener('click', (event) => {
    if (filterPanel.hidden) return;
    if (event.composedPath().includes(filterRoot)) return;
    closePanel();
  });

  /* ------------------------------------------------------------------ */
  /* Collapsible dropdown rows (one chevron each).                       */
  /* ------------------------------------------------------------------ */
  const closeRow = (key) => {
    const current = row(key);
    if (!current) return;
    const head = current.querySelector('[data-filter-row-toggle]');
    const body = current.querySelector('[data-filter-body]');
    current.classList.remove('is-open');
    if (head) head.setAttribute('aria-expanded', 'false');
    if (body) body.hidden = true;
  };

  const closeAllRows = () => {
    GEO_KEYS.forEach(closeRow);
    document.querySelectorAll('[data-trade-item].is-open').forEach((item) => setTradeOpen(item, false, false));
  };

  const openRow = (key, open = true) => {
    const current = row(key);
    if (!current) return;
    const head = current.querySelector('[data-filter-row-toggle]');
    const body = current.querySelector('[data-filter-body]');
    current.classList.toggle('is-open', open);
    if (head) head.setAttribute('aria-expanded', String(open));
    if (body) body.hidden = !open;
  };

  filterPanel.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;

    const rowToggle = target.closest('[data-filter-row-toggle]');
    if (rowToggle) {
      const current = rowToggle.closest('[data-filter-row]');
      if (!current) return;
      const key = current.dataset.filterKey;
      const willOpen = !current.classList.contains('is-open');
      GEO_KEYS.forEach((other) => { if (other !== key) closeRow(other); });
      openRow(key, willOpen);
    }
  });

  /* ------------------------------------------------------------------ */
  /* Geography cascade: country → state → area → institution.            */
  /* ------------------------------------------------------------------ */
  const locationData = document.getElementById('discovery-location-catalogue');
  let locationRows = [];
  try {
    locationRows = JSON.parse((locationData && locationData.textContent) || '[]');
  } catch (_) {
    locationRows = [];
  }

  const allInstitutions = Array.from(
    (optionsBox('institution_id') || document).querySelectorAll('.artisan-filter-option[data-value]')
  )
    .filter((option) => option.dataset.value)
    .map((option) => ({
      value: option.dataset.value,
      label: option.dataset.label || option.textContent.trim(),
      country: option.dataset.country || '',
      state: option.dataset.state || '',
    }));

  const uniqueValues = (records, key) => {
    const seen = new Map();
    records.forEach((record) => {
      const value = String(record[key] || '').trim();
      if (value) seen.set(value.toLocaleLowerCase(), value);
    });
    return Array.from(seen.values()).sort((a, b) => a.localeCompare(b));
  };

  const rebuildOptions = (key, entries, placeholder) => {
    const box = optionsBox(key);
    if (!box) return;
    const selected = input(key) ? input(key).value : '';
    box.replaceChildren();

    const make = (value, label, dataset = {}) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'artisan-filter-option';
      button.setAttribute('role', 'option');
      button.dataset.value = value;
      button.dataset.label = label;
      Object.entries(dataset).forEach(([name, dataValue]) => { button.dataset[name] = dataValue || ''; });
      button.textContent = label;
      const on = value === selected;
      button.classList.toggle('is-selected', on);
      button.setAttribute('aria-selected', String(on));
      box.appendChild(button);
    };

    make('', placeholder);
    entries.forEach((entry) => {
      if (typeof entry === 'string') make(entry, entry);
      else make(entry.value, entry.label, { country: entry.country, state: entry.state });
    });
  };

  const currentValue = (key) => (input(key) ? input(key).value : '');
  const matches = (value, needle) => String(value || '').toLocaleLowerCase() === needle;

  const rowsForCountry = () => {
    const country = currentValue('country');
    if (!country) return locationRows;
    const needle = country.toLocaleLowerCase();
    return locationRows.filter((record) => matches(record.country, needle));
  };

  const rowsForState = () => {
    const state = currentValue('state');
    const base = rowsForCountry();
    if (!state) return base;
    const needle = state.toLocaleLowerCase();
    return base.filter((record) => matches(record.state, needle));
  };

  const keepSelection = (key, allowed) => {
    const value = currentValue(key);
    if (!value) return;
    const stillValid = allowed.some((entry) => {
      const candidate = typeof entry === 'string' ? entry : entry.value;
      return matches(candidate, value.toLocaleLowerCase());
    });
    if (!stillValid) {
      input(key).value = '';
      markSelection(key, '');
    }
  };

  const syncGeography = () => {
    const states = uniqueValues(rowsForCountry(), 'state');
    keepSelection('state', states);
    rebuildOptions('state', states, PLACEHOLDERS.state);

    const areas = uniqueValues(rowsForState(), 'area');
    keepSelection('area', areas);
    rebuildOptions('area', areas, PLACEHOLDERS.area);

    const country = currentValue('country');
    const state = currentValue('state');
    const institutions = allInstitutions.filter((institution) => {
      const countryOk = !country || matches(institution.country, country.toLocaleLowerCase());
      const stateOk = !state || matches(institution.state, state.toLocaleLowerCase());
      return countryOk && stateOk;
    });
    keepSelection('institution_id', institutions);
    rebuildOptions('institution_id', institutions, PLACEHOLDERS.institution_id);

    const empty = filterPanel.querySelector('[data-institution-empty]');
    if (empty) empty.hidden = institutions.length > 0;

    syncDraftState();
  };

  /* ------------------------------------------------------------------ */
  /* Selection helpers.                                                  */
  /* ------------------------------------------------------------------ */
  const markSelection = (key, value) => {
    const box = optionsBox(key);
    if (!box) return;
    box.querySelectorAll('.artisan-filter-option').forEach((option) => {
      const on = (option.dataset.value || '') === (value || '');
      option.classList.toggle('is-selected', on);
      option.setAttribute('aria-selected', String(on));
    });
  };

  const activeCount = () => ALL_KEYS.filter((key) => currentValue(key)).length;

  const syncDraftState = () => {
    GEO_KEYS.forEach((key) => {
      const label = valueLabel(key);
      if (!label) return;
      const value = currentValue(key);
      const box = optionsBox(key);
      const selected = value && box
        ? box.querySelector(`.artisan-filter-option[data-value="${CSS.escape(value)}"]`)
        : null;
      if (key === 'institution_id') {
        label.textContent = selected ? (selected.dataset.label || selected.textContent.trim()) : PLACEHOLDERS[key];
      } else {
        label.textContent = selected ? selected.textContent.trim() : PLACEHOLDERS[key];
      }
      label.classList.toggle('is-placeholder', !value);
    });

    const count = activeCount();
    if (filterBadge) {
      filterBadge.textContent = String(count);
      filterBadge.hidden = count === 0;
    }
    filterToggle.classList.toggle('has-active', count > 0);
  };

  /* ------------------------------------------------------------------ */
  /* Categories & services: hover a trade, see its services beneath it.  */
  /* ------------------------------------------------------------------ */
  const tradeItems = Array.from(filterPanel.querySelectorAll('[data-trade-item]'));
  const tradeSearch = filterPanel.querySelector('[data-trade-search]');
  const tradeEmpty = filterPanel.querySelector('[data-trade-empty]');
  const tradesSummary = filterPanel.querySelector('[data-trades-summary]');
  let tradeCloseTimer = null;

  const setTradeOpen = (item, open, pinned = false) => {
    if (!item) return;
    item.classList.toggle('is-open', open);
    item.dataset.pinned = open && pinned ? 'true' : '';
    const head = item.querySelector('[data-trade-toggle]');
    const body = item.querySelector('[data-trade-services]');
    if (head) head.setAttribute('aria-expanded', String(open));
    if (body) {
      body.inert = !open;
      body.setAttribute('aria-hidden', String(!open));
    }
  };

  const syncTrades = () => {
    const category = currentValue('category_name');
    const service = currentValue('service_name');

    tradeItems.forEach((item) => {
      const itemCategory = item.dataset.tradeCategory || '';
      const isCategory = Boolean(category) && matches(itemCategory, category.toLocaleLowerCase());
      item.classList.toggle('is-selected', isCategory);
      item.querySelectorAll('[data-service-select]').forEach((button) => {
        const buttonService = button.dataset.serviceSelect || '';
        const on = Boolean(service) && isCategory && matches(buttonService, service.toLocaleLowerCase());
        button.classList.toggle('is-selected', on);
      });
      const allButton = item.querySelector('[data-trade-select]');
      if (allButton) allButton.classList.toggle('is-selected', isCategory && !service);
    });

    if (tradesSummary) {
      tradesSummary.textContent = service || category || 'All categories';
      tradesSummary.classList.toggle('is-placeholder', !service && !category);
    }

    syncDraftState();
  };

  const selectCategory = (category) => {
    const categoryInput = input('category_name');
    const serviceInput = input('service_name');
    if (!categoryInput || !serviceInput) return;
    const already = matches(categoryInput.value, category.toLocaleLowerCase()) && !serviceInput.value;
    categoryInput.value = already ? '' : category;
    serviceInput.value = '';
    syncTrades();
  };

  const selectService = (category, service) => {
    const categoryInput = input('category_name');
    const serviceInput = input('service_name');
    if (!categoryInput || !serviceInput) return;
    const already = matches(categoryInput.value, category.toLocaleLowerCase())
      && matches(serviceInput.value, service.toLocaleLowerCase());
    categoryInput.value = already ? '' : category;
    serviceInput.value = already ? '' : service;
    syncTrades();
  };

  if (tradeItems.length) {
    tradeItems.forEach((item) => {
      const head = item.querySelector('[data-trade-toggle]');
      const body = item.querySelector('[data-trade-services]');

      // Start collapsed unless the URL already selected this category.
      setTradeOpen(item, item.classList.contains('is-open'), false);

      if (head) {
        head.addEventListener('click', () => {
          // A hover already opened the list, so the first click pins it open;
          // only a second click on a pinned row collapses it.
          const open = item.classList.contains('is-open');
          const pinned = item.dataset.pinned === 'true';
          if (open && pinned) {
            setTradeOpen(item, false, false);
            return;
          }
          tradeItems.forEach((other) => { if (other !== item) setTradeOpen(other, false, false); });
          setTradeOpen(item, true, true);
        });
      }

      // Hover opens the services beneath the category, like an in-built navbar.
      item.addEventListener('mouseenter', () => {
        if (!window.matchMedia('(hover: hover)').matches) return;
        if (Date.now() < hoverGraceUntil) return;
        window.clearTimeout(tradeCloseTimer);
        tradeItems.forEach((other) => {
          if (other !== item && other.dataset.pinned !== 'true') setTradeOpen(other, false, false);
        });
        setTradeOpen(item, true, item.dataset.pinned === 'true');
      });

      item.addEventListener('mouseleave', () => {
        if (!window.matchMedia('(hover: hover)').matches) return;
        window.clearTimeout(tradeCloseTimer);
        tradeCloseTimer = window.setTimeout(() => {
          if (item.dataset.pinned === 'true') return;
          if (item.contains(document.activeElement)) return;
          setTradeOpen(item, false, false);
        }, 160);
      });

      if (body) {
        body.addEventListener('focusin', () => {
          window.clearTimeout(tradeCloseTimer);
          setTradeOpen(item, true, item.dataset.pinned === 'true');
        });
      }
    });

    filterPanel.addEventListener('click', (event) => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;

      const serviceButton = target.closest('[data-service-select]');
      if (serviceButton) {
        selectService(serviceButton.dataset.serviceCategory || '', serviceButton.dataset.serviceSelect || '');
        return;
      }

      const categoryButton = target.closest('[data-trade-select]');
      if (categoryButton) {
        selectCategory(categoryButton.dataset.tradeSelect || '');
      }
    });

    if (tradeSearch) {
      tradeSearch.addEventListener('input', () => {
        const query = tradeSearch.value.trim().toLocaleLowerCase();
        let visible = 0;
        tradeItems.forEach((item) => {
          const name = (item.dataset.tradeName || '').toLocaleLowerCase();
          const services = Array.from(item.querySelectorAll('[data-service-select]'))
            .map((button) => (button.dataset.serviceSelect || '').toLocaleLowerCase());
          const hit = !query || name.includes(query) || services.some((service) => service.includes(query));
          item.hidden = !hit;
          if (hit) {
            visible += 1;
            if (query) setTradeOpen(item, true, false);
          } else {
            setTradeOpen(item, false, false);
          }
        });
        if (tradeEmpty) tradeEmpty.hidden = visible > 0;
      });
    }
  }

  /* ------------------------------------------------------------------ */
  /* Option clicks on the four dropdown rows.                            */
  /* ------------------------------------------------------------------ */
  filterPanel.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const option = target.closest('.artisan-filter-option');
    if (!option) return;
    const box = option.closest('[data-filter-options]');
    if (!box) return;

    const key = box.dataset.filterOptions;
    const field = input(key);
    if (!field) return;
    field.value = option.dataset.value || '';
    markSelection(key, field.value);

    if (key === 'country' || key === 'state') {
      syncGeography();
    } else {
      syncDraftState();
    }
    closeRow(key);
  });

  if (filterClear) {
    filterClear.addEventListener('click', () => {
      ALL_KEYS.forEach((key) => {
        const field = input(key);
        if (field) field.value = '';
      });
      syncGeography();
      syncTrades();
      closeAllRows();
      if (tradeSearch) {
        tradeSearch.value = '';
        tradeItems.forEach((item) => { item.hidden = false; });
        if (tradeEmpty) tradeEmpty.hidden = true;
      }
    });
  }

  // Reflect the server-rendered selection (shared links, browser history).
  syncGeography();
  syncTrades();
});