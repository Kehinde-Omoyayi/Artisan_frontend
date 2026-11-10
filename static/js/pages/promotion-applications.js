(() => {
  const form = document.querySelector('[data-promotion-form]');
  if (!form) return;

  const product = form.querySelector('[data-promotion-type]');
  const groups = Array.from(form.querySelectorAll('[data-promotion-group]'));
  const country = form.querySelector('[data-promotion-country]');
  const state = form.querySelector('[data-promotion-state]');
  const pickerUrl = form.dataset.pickerUrl || '';
  const pairNode = document.getElementById('promotion-state-pairs');
  let pairs = [];
  try {
    pairs = JSON.parse(pairNode?.textContent || '[]');
  } catch (_) {
    pairs = [];
  }

  const updateStates = () => {
    if (!country || !state) return;
    const selected = state.value;
    const states = Array.from(new Set(
      pairs
        .filter((pair) => pair.country === country.value)
        .map((pair) => pair.state)
    )).sort((a, b) => a.localeCompare(b));
    state.replaceChildren(new Option('Choose a state or region', ''));
    states.forEach((value) => state.add(new Option(value, value)));
    if (states.includes(selected)) state.value = selected;
  };

  /* The institution and area lists stay off the page (they are thousands of
     rows); the browser pulls them once, the first time a target group that
     needs them is shown, and caches the promise for the rest of the visit. */
  let pickerPromise = null;
  const loadPicker = () => {
    if (!pickerUrl) return Promise.resolve(null);
    if (!pickerPromise) {
      pickerPromise = fetch(pickerUrl, { headers: { Accept: 'application/json' } })
        .then((response) => (response.ok ? response.json() : null))
        .catch(() => null);
    }
    return pickerPromise;
  };

  const fillSelect = (select, rows) => {
    if (!select || !Array.isArray(rows)) return;
    const keep = select.value;
    const placeholder = select.options[0]
      ? { text: select.options[0].textContent, value: select.options[0].value }
      : { text: 'Choose', value: '' };
    select.replaceChildren(new Option(placeholder.text, placeholder.value));
    rows.forEach((row) => select.add(new Option(row.label, String(row.id))));
    if (keep) select.value = keep;
  };

  const ensurePicker = () => {
    const selected = product?.value || '';
    if (selected !== 'INSTITUTION' && selected !== 'AREA') return;
    loadPicker().then((data) => {
      if (!data) return;
      if (selected === 'INSTITUTION') {
        fillSelect(form.querySelector('[name="institution_id"]'), data.institutions);
      } else {
        fillSelect(form.querySelector('[name="area_location_id"]'), data.locations);
      }
    });
  };

  const updateGroups = (clearHidden = true) => {
    const selected = product?.value || '';
    groups.forEach((group) => {
      const visible = group.dataset.promotionGroup === selected;
      group.hidden = !visible;
      group.setAttribute('aria-hidden', visible ? 'false' : 'true');
      if (!visible && clearHidden) {
        group.querySelectorAll('select,input,textarea').forEach((control) => {
          if (control.type === 'checkbox' || control.type === 'radio') control.checked = false;
          else control.value = '';
        });
      }
    });
    /* Every country dropdown in the product opens on Nigeria: the State
       target's country select defaults there as soon as the group shows. */
    if (selected === 'STATE' && country && !country.value) {
      const nigeria = [...country.options].find(
        (option) => option.value === 'Nigeria'
      );
      if (nigeria) {
        country.value = 'Nigeria';
        country.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }
    updateStates();
  };

  product?.addEventListener('change', () => {
    updateGroups(true);
    ensurePicker();
  });
  country?.addEventListener('change', updateStates);
  updateGroups(true);
  ensurePicker();
})();
