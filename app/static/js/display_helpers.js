(function () {
    'use strict';

    const PARTICIPANT_LABELS = {
        employee: '員工',
        dependent: '眷屬',
        vendor_contact: '外部廠商主要窗口',
        vendor: '外部廠商'
    };

    const TYPE_STYLES = {
        employee: 'background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;',
        dependent: 'background:#faf5ff;color:#7c3aed;border:1px solid #ddd6fe;',
        vendor_contact: 'background:#fff7ed;color:#c2410c;border:1px solid #fed7aa;',
        vendor: 'background:#fefce8;color:#a16207;border:1px solid #fde68a;'
    };

    const MEAL_STYLES = {
        A: 'background:linear-gradient(90deg,#065f46,#059669);color:#fff;border:1px solid #6ee7b7;',
        B: 'background:linear-gradient(90deg,#0369a1,#0ea5e9);color:#fff;border:1px solid #93c5fd;',
        DEFAULT: 'background:#f0f9ff;color:#075985;border:1px solid #bae6fd;'
    };

    let latestStatusList = [];
    let latestLookupData = null;

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function truncateText(value, maxChars) {
        if (!value) return '-';
        const chars = Array.from(String(value));
        return chars.length > maxChars ? chars.slice(0, maxChars).join('') : String(value);
    }

    function mealLabel(value) {
        if (!value) return '';
        const raw = String(value).trim();
        const upper = raw.toUpperCase();
        if (upper === 'A') return 'A 餐';
        if (upper === 'B') return 'B 餐';
        return raw;
    }

    function mealStyle(value) {
        const upper = String(value || '').trim().toUpperCase();
        return MEAL_STYLES[upper] || MEAL_STYLES.DEFAULT;
    }

    function mealBadge(value) {
        const label = mealLabel(value);
        if (!label) return '-';
        return `<span style="${mealStyle(value)}font-size:0.78rem;padding:3px 9px;border-radius:6px;font-weight:600;display:inline-block;max-width:220px;white-space:normal;line-height:1.35;">${escapeHtml(label)}</span>`;
    }

    function participantBadge(person) {
        const type = person && person.participant_type;
        const label = PARTICIPANT_LABELS[type];
        if (!label) return '-';
        let html = `<span style="${TYPE_STYLES[type] || TYPE_STYLES.employee}font-size:0.75rem;padding:2px 7px;border-radius:5px;font-weight:600;display:inline-block;">${escapeHtml(label)}</span>`;
        if (type === 'dependent' && person.linked_employee_id) {
            html += `<br><small class="text-muted" style="font-size:0.7rem;">→ ${escapeHtml(person.linked_employee_id)}</small>`;
        }
        return html;
    }

    function addOptionIfMissing(select, value, label) {
        if (!select || !value) return;
        const exists = Array.from(select.options).some(option => option.value === value);
        if (!exists) select.appendChild(new Option(label, value));
    }

    function updateDashboardFilters(list) {
        const filterType = document.getElementById('filter-type');
        addOptionIfMissing(filterType, 'vendor_contact', '外部廠商主要窗口');
        addOptionIfMissing(filterType, 'vendor', '外部廠商');

        const filterMeal = document.getElementById('filter-meal');
        if (filterMeal) {
            const mealValues = [...new Set(list.map(p => p.meal_type).filter(Boolean))].sort();
            mealValues.forEach(value => addOptionIfMissing(filterMeal, value, mealLabel(value)));
        }
    }

    function patchDashboardRows() {
        const tableBody = document.getElementById('table-body');
        const head = document.getElementById('table-head');
        if (!tableBody || !head || !latestStatusList.length) return;

        const dataByEmployeeId = new Map(latestStatusList.map(p => [String(p.employee_id), p]));
        const headers = Array.from(head.querySelectorAll('th')).map(th => th.textContent.trim());
        const deptIndex = headers.findIndex(text => text.includes('部門'));
        const typeIndex = headers.findIndex(text => text.includes('身分'));
        const mealIndex = headers.findIndex(text => text.includes('餐點'));

        Array.from(tableBody.querySelectorAll('tr')).forEach(row => {
            const cells = row.children;
            if (!cells || cells.length < 2) return;

            const employeeId = cells[1].textContent.trim();
            const person = dataByEmployeeId.get(employeeId);
            if (!person) return;

            if (deptIndex >= 0 && cells[deptIndex]) {
                const fullDept = person.dept_code || '';
                cells[deptIndex].textContent = truncateText(fullDept, 4);
                cells[deptIndex].title = fullDept;
            }
            if (typeIndex >= 0 && cells[typeIndex]) {
                cells[typeIndex].innerHTML = participantBadge(person);
            }
            if (mealIndex >= 0 && cells[mealIndex]) {
                cells[mealIndex].innerHTML = mealBadge(person.meal_type);
            }
        });
    }

    function patchLookupResult() {
        if (!latestLookupData) return;

        const typeBadge = document.getElementById('res-type-badge');
        if (typeBadge) typeBadge.innerHTML = participantBadge(latestLookupData) === '-' ? '' : participantBadge(latestLookupData);

        const linked = document.getElementById('res-linked');
        if (linked) {
            linked.textContent = latestLookupData.participant_type === 'dependent' && latestLookupData.linked_employee_id
                ? `綁定員工：${latestLookupData.linked_employee_id}`
                : '';
        }

        const mealBox = document.getElementById('res-meal-box');
        const mealText = document.getElementById('res-meal-text');
        if (mealBox && mealText) {
            const label = mealLabel(latestLookupData.meal_type);
            if (label) {
                mealText.textContent = label;
                mealBox.style.display = 'block';
                mealBox.style.background = '#f0f9ff';
                mealBox.style.border = '1px solid #bae6fd';
                mealBox.style.color = '#075985';
            } else {
                mealBox.style.display = 'none';
            }
        }

        if (Array.isArray(latestLookupData.dependents)) {
            const depCards = Array.from(document.querySelectorAll('#dep-grid .dep-card'));
            depCards.forEach((card, index) => {
                const dep = latestLookupData.dependents[index];
                if (!dep) return;

                const meal = card.querySelector('.dep-meal-box');
                if (meal && dep.meal_type) {
                    meal.innerHTML = `<i class="bi bi-egg-fried me-1"></i>${escapeHtml(mealLabel(dep.meal_type))}`;
                    meal.style.display = 'block';
                    meal.style.background = '#f0f9ff';
                    meal.style.border = '1px solid #bae6fd';
                    meal.style.color = '#075985';
                }
            });
        }
    }

    function patchFromData(data, url) {
        if (!data || !data.success) return;

        if (url.includes('/api/status_list') && Array.isArray(data.checkin_list)) {
            latestStatusList = data.checkin_list;
            updateDashboardFilters(latestStatusList);
            setTimeout(patchDashboardRows, 0);
        }

        if (url.includes('/api/checkin_by_id') || url.includes('/api/search_by_id')) {
            latestLookupData = data;
            setTimeout(patchLookupResult, 0);
        }
    }

    if (!window.__displayHelpersFetchPatched) {
        window.__displayHelpersFetchPatched = true;
        const originalFetch = window.fetch;
        window.fetch = function () {
            const url = String(arguments[0] || '');
            return originalFetch.apply(this, arguments).then(response => {
                if (url.includes('/api/status_list') || url.includes('/api/checkin_by_id') || url.includes('/api/search_by_id')) {
                    response.clone().json().then(data => patchFromData(data, url)).catch(() => {});
                }
                return response;
            });
        };
    }

    document.addEventListener('DOMContentLoaded', () => {
        const tableBody = document.getElementById('table-body');
        if (tableBody) {
            const observer = new MutationObserver(() => patchDashboardRows());
            observer.observe(tableBody, { childList: true, subtree: true });
        }

        const bodyObserver = new MutationObserver(() => patchLookupResult());
        bodyObserver.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style'] });
    });
})();
