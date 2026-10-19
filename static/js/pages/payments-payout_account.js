document.addEventListener('DOMContentLoaded', () => {
  const select = document.querySelector('[data-payout-bank-select]');
  if (!select) return;

  const allOptions = Array.from(select.options).map((option) => ({
    value: option.value,
    label: option.textContent,
    disabled: option.disabled,
  }));
  const search = document.createElement('input');
  search.type = 'search';
  search.className = select.className;
  search.placeholder = 'Search supported banks';
  search.autocomplete = 'off';
  search.setAttribute('aria-label', 'Search supported banks');
  search.setAttribute('data-payout-bank-search', '');
  select.parentNode.insertBefore(search, select);

  const filterOptions = () => {
    const term = search.value.trim().toLocaleLowerCase();
    const selected = select.value;
    select.replaceChildren();
    allOptions.forEach((item, index) => {
      if (index !== 0 && term && !item.label.toLocaleLowerCase().includes(term) && item.value !== selected) return;
      const option = document.createElement('option');
      option.value = item.value;
      option.textContent = item.label;
      option.disabled = item.disabled;
      select.appendChild(option);
    });
    if (Array.from(select.options).some((option) => option.value === selected)) {
      select.value = selected;
    }
  };

  search.addEventListener('input', filterOptions);
});
