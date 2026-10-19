document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.artisan-discovery-photo').forEach((photo) => {
    photo.addEventListener('error', () => {
      photo.hidden = true;
      const fallback = photo.parentElement && photo.parentElement.querySelector('.artisan-discovery-avatar-fallback');
      if (fallback) fallback.hidden = false;
    }, { once: true });
  });

  const categorySearch = document.querySelector('[data-discovery-category-search]');
  const categoryItems = Array.from(document.querySelectorAll('[data-discovery-category]'));
  const noCategoryMatches = document.querySelector('[data-discovery-category-empty]');
  if (categorySearch && categoryItems.length) {
    categorySearch.addEventListener('input', () => {
      const query = categorySearch.value.trim().toLocaleLowerCase();
      let visibleCount = 0;
      categoryItems.forEach((item) => {
        const name = (item.dataset.categoryName || '').toLocaleLowerCase();
        item.hidden = Boolean(query && !name.includes(query));
        if (!item.hidden) visibleCount += 1;
      });
      if (noCategoryMatches) noCategoryMatches.hidden = visibleCount > 0;
    });
  }

  const drawer = document.querySelector('[data-discovery-category-drawer]');
  const categoryToggle = document.querySelector('[data-discovery-sidebar-toggle]');
  const categoryPanel = document.querySelector('[data-discovery-category-panel]');
  const categoryClose = document.querySelector('[data-discovery-category-close]');
  if (drawer && categoryToggle && categoryPanel) {
    const setCategoryPanelOpen = (open, restoreFocus = false) => {
      categoryPanel.hidden = !open;
      categoryToggle.setAttribute('aria-expanded', String(open));
      if (open) {
        const search = categoryPanel.querySelector('[data-discovery-category-search]');
        if (search) window.requestAnimationFrame(() => search.focus({ preventScroll: true }));
      } else if (restoreFocus) {
        categoryToggle.focus({ preventScroll: true });
      }
    };

    categoryToggle.addEventListener('click', () => {
      setCategoryPanelOpen(categoryPanel.hidden);
    });
    if (categoryClose) categoryClose.addEventListener('click', () => setCategoryPanelOpen(false, true));
    categoryPanel.addEventListener('click', (event) => {
      if (event.target instanceof Element && event.target.closest('a[data-discovery-category-filter], a[data-discovery-service-filter]')) {
        setCategoryPanelOpen(false);
      }
    });
    document.addEventListener('click', (event) => {
      if (categoryPanel.hidden || !(event.target instanceof Element)) return;
      if (drawer.contains(event.target)) return;
      setCategoryPanelOpen(false);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !categoryPanel.hidden) {
        event.preventDefault();
        setCategoryPanelOpen(false, true);
      }
    });
  }

  const locationData = document.getElementById('discovery-location-catalogue');
  const countrySelect = document.querySelector('[data-discovery-country]');
  const stateSelect = document.querySelector('[data-discovery-state]');
  const areaSelect = document.querySelector('[data-discovery-area]');
  const institutionSelect = document.querySelector('[data-discovery-institution]');
  if (locationData && countrySelect && stateSelect && areaSelect) {
    let rows = [];
    try {
      rows = JSON.parse(locationData.textContent || '[]');
    } catch (_) {
      rows = [];
    }

    const uniqueValues = (records, key) => {
      const values = new Map();
      records.forEach((row) => {
        const value = String(row[key] || '').trim();
        if (value && !values.has(value.toLocaleLowerCase())) values.set(value.toLocaleLowerCase(), value);
      });
      return Array.from(values.values()).sort((a, b) => a.localeCompare(b));
    };
    const setOptions = (select, values, placeholder, selected = '') => {
      select.replaceChildren();
      const empty = document.createElement('option');
      empty.value = '';
      empty.textContent = placeholder;
      select.appendChild(empty);
      values.forEach((value) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        if (value.toLocaleLowerCase() === String(selected || '').toLocaleLowerCase()) option.selected = true;
        select.appendChild(option);
      });
    };
    const countryRows = () => {
      const country = countrySelect.value.toLocaleLowerCase();
      return rows.filter((row) => !country || String(row.country || '').toLocaleLowerCase() === country);
    };
    const updateStates = (selected = '') => {
      setOptions(stateSelect, uniqueValues(countryRows(), 'state'), 'Any state or region', selected);
      updateAreas('');
    };
    const updateAreas = (selected = '') => {
      const state = stateSelect.value.toLocaleLowerCase();
      const candidates = countryRows().filter((row) => !state || String(row.state || '').toLocaleLowerCase() === state);
      setOptions(areaSelect, uniqueValues(candidates, 'area'), 'Any area', selected);
    };
    const updateInstitutions = () => {
      if (!institutionSelect) return;
      const country = countrySelect.value.toLocaleLowerCase();
      const state = stateSelect.value.toLocaleLowerCase();
      Array.from(institutionSelect.options).forEach((option) => {
        if (!option.value) return;
        const matchesCountry = !country || String(option.dataset.country || '').toLocaleLowerCase() === country;
        const matchesState = !state || String(option.dataset.state || '').toLocaleLowerCase() === state;
        option.hidden = !(matchesCountry && matchesState);
        if (option.selected && option.hidden) institutionSelect.value = '';
      });
    };
    countrySelect.addEventListener('change', () => {
      updateStates('');
      updateInstitutions();
    });
    stateSelect.addEventListener('change', () => {
      updateAreas('');
      updateInstitutions();
    });
    updateInstitutions();
  }
});
