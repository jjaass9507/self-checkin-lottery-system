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
        C: 'background:linear-gradient(90deg,#7c2d12,#ea580c);color:#fff;border:1px solid #fdba74;',
        D: 'background:linear-gradient(90deg,#581c87,#9333ea);color:#fff;border:1px solid #d8b4fe;',
        E: 'background:linear-gradient(90deg,#831843,#db2777);color:#fff;border:1px solid #f9a8d4;',
        VEGETARIAN: 'background:linear-gradient(90deg,#166534,#65a30d);color:#fff;border:1px solid #bef264;',
        DEFAULT: 'background:#f0f9ff;color:#075985;border:1px solid #bae6fd;'
    };

    const GROUP_STYLES = [
        'background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0;',
        'background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;',
        'background:#fff7ed;color:#c2410c;border:1px solid #fed7aa;',
        'background:#faf5ff;color:#7c3aed;border:1px solid #ddd6fe;',
        'background:#fefce8;color:#a16207;border:1px solid #fde68a;',
        'background:#fdf2f8;color:#be185d;border:1px solid #fbcfe8;',
        'background:#ecfeff;color:#0e7490;border:1px solid #a5f3fc;',
        'background:#f8fafc;color:#475569;border:1px solid #cbd5e1;'
    ];

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function truncateText(value, maxChars) {
        if (!value) return '-';
        const chars = Array.from(String(value));
        return chars.length > maxChars ? chars.slice(0, maxChars).join('') : String(value);
    }

    function stableHash(value) {
        const text = String(value || '');
        let hash = 0;
        for (let i = 0; i < text.length; i++) {
            hash = ((hash << 5) - hash) + text.charCodeAt(i);
            hash |= 0;
        }
        return Math.abs(hash);
    }

    function mealKey(value) {
        const raw = String(value || '').trim();
        const upper = raw.toUpperCase();
        if (!upper) return '';
        if (upper.includes('素')) return 'VEGETARIAN';
        const match = upper.match(/^([A-Z])\s*(餐|[:：]|$)/);
        if (match) return match[1];
        return upper;
    }

    function mealLabel(value) {
        if (!value) return '';
        const raw = String(value).trim();
        if (raw.toUpperCase() === 'A') return 'A 餐';
        if (raw.toUpperCase() === 'B') return 'B 餐';
        return raw;
    }

    function mealBadge(value) {
        const label = mealLabel(value);
        if (!label) return '-';
        const style = MEAL_STYLES[mealKey(value)] || MEAL_STYLES.DEFAULT;
        return `<span style="${style}font-size:0.78rem;padding:3px 9px;border-radius:6px;font-weight:600;display:inline-block;max-width:240px;white-space:normal;line-height:1.35;">${escapeHtml(label)}</span>`;
    }

    function groupBadge(value) {
        if (!value) return '-';
        const style = GROUP_STYLES[stableHash(value) % GROUP_STYLES.length];
        return `<span style="${style}font-size:0.75rem;padding:2px 7px;border-radius:5px;font-weight:600;display:inline-block;max-width:180px;white-space:normal;line-height:1.35;">${escapeHtml(value)}</span>`;
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
            if (current && Array.from(filterMeal.options).some(option => option.value === current)) filterMeal.value = current;
        }
    }

    function ensureExtraColumns(head, bodyRows) {
        const headerRow = head.querySelector('tr');
        if (!headerRow || headerRow.dataset.extraContactColumns === '1') return;
        const actionHeader = Array.from(headerRow.children).find(th => th.textContent.trim() === '操作');
        ['大人/小孩', '連絡電話'].forEach(label => {
            const th = document.createElement('th');
            th.textContent = label;
            headerRow.insertBefore(th, actionHeader || null);
        });
        headerRow.dataset.extraContactColumns = '1';
        bodyRows.forEach(row => { row.dataset.extraContactColumns = ''; });
    }

    function patchDashboardRows() {
        const tableBody = document.getElementById('table-body');
        const head = document.getElementById('table-head');
        if (!tableBody || !head) return;

        const list = getDashboardData();
        if (!list.length) return;
        patchDashboardFilters(list);

        const rows = Array.from(tableBody.querySelectorAll('tr')).filter(row => row.children && row.children.length >= 2);
        ensureExtraColumns(head, rows);

        const dataByEmployeeId = new Map(list.map(p => [String(p.employee_id), p]));
        const headers = Array.from(head.querySelectorAll('th')).map(th => th.textContent.trim());
        const deptIndex = headers.findIndex(text => text.includes('部門'));
        const typeIndex = headers.findIndex(text => text.includes('身分'));
        const mealIndex = headers.findIndex(text => text.includes('餐點'));
        const groupIndex = headers.findIndex(text => text.includes('組別'));
        const actionIndex = headers.findIndex(text => text === '操作');

        rows.forEach(row => {
            const cells = row.children;
            const employeeId = cells[1].textContent.trim();
            const person = dataByEmployeeId.get(employeeId);
            if (!person) return;

            if (row.dataset.extraContactColumns !== '1' && actionIndex >= 0) {
                const ageCell = document.createElement('td');
                const phoneCell = document.createElement('td');
                ageCell.innerHTML = person.age_group ? `<span class="badge bg-light text-dark border">${escapeHtml(person.age_group)}</span>` : '-';
                phoneCell.innerHTML = person.phone ? `<span style="font-size:0.82rem;">${escapeHtml(person.phone)}</span>` : '-';
                const actionCell = row.children[actionIndex] || row.lastElementChild;
                row.insertBefore(ageCell, actionCell);
                row.insertBefore(phoneCell, actionCell);
                row.dataset.extraContactColumns = '1';
            }

            if (deptIndex >= 0 && row.children[deptIndex]) {
                const fullDept = person.dept_code || '';
                row.children[deptIndex].textContent = truncateText(fullDept, 4);
                row.children[deptIndex].title = fullDept;
            }
            if (typeIndex >= 0 && row.children[typeIndex]) row.children[typeIndex].innerHTML = participantBadge(person);
            if (mealIndex >= 0 && row.children[mealIndex]) row.children[mealIndex].innerHTML = mealBadge(person.meal_type);
            if (groupIndex >= 0 && row.children[groupIndex]) row.children[groupIndex].innerHTML = groupBadge(person.group_name);
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
        new MutationObserver(runPatch).observe(tableBody, { childList: true });
        window.setInterval(patchDashboardRows, 1500);
    });
})();
