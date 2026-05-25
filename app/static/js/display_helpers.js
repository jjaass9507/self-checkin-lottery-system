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

    function mealBadge(value) {
        const label = mealLabel(value);
        if (!label) return '-';
        const upper = String(value || '').trim().toUpperCase();
        const style = upper === 'A'
            ? 'background:linear-gradient(90deg,#065f46,#059669);color:#fff;border:1px solid #6ee7b7;'
            : upper === 'B'
                ? 'background:linear-gradient(90deg,#0369a1,#0ea5e9);color:#fff;border:1px solid #93c5fd;'
                : 'background:#f0f9ff;color:#075985;border:1px solid #bae6fd;';
        return `<span style="${style}font-size:0.78rem;padding:3px 9px;border-radius:6px;font-weight:600;display:inline-block;max-width:220px;white-space:normal;line-height:1.35;">${escapeHtml(label)}</span>`;
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
        if (!Array.from(select.options).some(option => option.value === value)) {
            select.appendChild(new Option(label, value));
        }
    }

    function getDashboardData() {
        try {
            // dashboard.html 內使用 let fullDataCache；這裡只讀取，不改寫。
            if (Array.isArray(fullDataCache)) return fullDataCache;
        } catch (e) {}
        return [];
    }

    function patchDashboardFilters(list) {
        const filterType = document.getElementById('filter-type');
        addOptionIfMissing(filterType, 'vendor_contact', '外部廠商主要窗口');
        addOptionIfMissing(filterType, 'vendor', '外部廠商');

        const filterMeal = document.getElementById('filter-meal');
        if (filterMeal) {
            const current = filterMeal.value;
            [...new Set(list.map(p => p.meal_type).filter(Boolean))].sort()
                .forEach(value => addOptionIfMissing(filterMeal, value, mealLabel(value)));
            if (current && Array.from(filterMeal.options).some(option => option.value === current)) {
                filterMeal.value = current;
            }
        }
    }

    function patchDashboardRows() {
        const tableBody = document.getElementById('table-body');
        const head = document.getElementById('table-head');
        if (!tableBody || !head) return;

        const list = getDashboardData();
        if (!list.length) return;
        patchDashboardFilters(list);

        const dataByEmployeeId = new Map(list.map(p => [String(p.employee_id), p]));
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

    document.addEventListener('DOMContentLoaded', function () {
        const tableBody = document.getElementById('table-body');
        if (!tableBody) return;

        let ticking = false;
        const runPatch = function () {
            if (ticking) return;
            ticking = true;
            window.setTimeout(function () {
                patchDashboardRows();
                ticking = false;
            }, 0);
        };

        const observer = new MutationObserver(runPatch);
        observer.observe(tableBody, { childList: true });
        window.setInterval(patchDashboardRows, 1500);
    });
})();
