document.addEventListener('DOMContentLoaded', () => {
  const forms = document.querySelectorAll('[data-service-filter-form]');
  forms.forEach((form) => {
    const categorySelect = form.querySelector('[name="category_name"]');
    const serviceSelect = form.querySelector('[name="service_name"]');
    if (!categorySelect || !serviceSelect) return;

    const serviceGroups = Array.from(serviceSelect.querySelectorAll('optgroup'));
    const placeholder = Array.from(serviceSelect.options).find((option) => option.value === '');

    const filterServices = ({ resetSelection = false } = {}) => {
      const selectedCategory = categorySelect.value;
      let hasServices = false;
      serviceGroups.forEach((group) => {
        const isVisible = Boolean(selectedCategory) && group.label === selectedCategory;
        group.hidden = !isVisible;
        group.disabled = !isVisible;
        if (isVisible) hasServices = true;
      });

      if (placeholder) {
        placeholder.textContent = selectedCategory ? 'Select a service' : 'Choose a category first';
      }
      if (resetSelection) serviceSelect.value = '';

      const selectedOption = serviceSelect.selectedOptions[0];
      const selectedGroup = selectedOption && selectedOption.parentElement;
      const selectedCategoryForService = selectedGroup && selectedGroup.tagName === 'OPTGROUP'
        ? selectedGroup.label
        : '';
      if (serviceSelect.value && selectedCategoryForService !== selectedCategory) {
        serviceSelect.value = '';
      }
      serviceSelect.disabled = !selectedCategory || !hasServices;
    };

    categorySelect.addEventListener('change', () => filterServices({ resetSelection: true }));
    filterServices();
  });

});
