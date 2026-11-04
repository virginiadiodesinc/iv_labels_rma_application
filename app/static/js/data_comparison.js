function getFiltersJson() {
    // parsed once, then cached
    if (!getFiltersJson.cache) {
        const form = document.getElementById('data-comparison-form');
        getFiltersJson.cache = JSON.parse(form.dataset.filters);
    }
    return getFiltersJson.cache;
}


function updateFilterOperationsSelect(filterSelect) {
    const filtersJson = getFiltersJson();
    const row = filterSelect.closest('.filter-container');
    const opsSelect = row.querySelector('select[name^="filter-op-"]');
    opsSelect.innerHTML = '';
    (filtersJson[filterSelect.value] || []).forEach(item => {
        const option = document.createElement("option");
        option.value = item;
        option.textContent = item;
        opsSelect.appendChild(option);
    });
    htmx.trigger(opsSelect, 'change');
}