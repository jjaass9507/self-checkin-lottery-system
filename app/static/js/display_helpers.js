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

    const MEAL_STYLE = 'background:#f0f9ff;color:#075985;border:1px solid #bae6fd;';

    const GROUP_STYLES = {
        A: 'background:#fff7ed;color:#c2410c;border:1px solid #fdba74;',
        B: 'background:#fefce8;color:#a16207;border:1px solid #fde68a;',
        C: 'background:#fdf2f8;color:#be185d;border:1px solid #fbcfe8;',
        D: 'background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;',
        E: 'background:#faf5ff;color:#7c3aed;border:1px solid #ddd6fe;',
        F: 'background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0;',
        DEFAULT: 'background:#f8fafc;color:#475569;border:1px solid #cbd5e1;'
    };

    const FILTER_MAP = {
        status: { id: 'filter-status', empty: 'NONE', actual: p => p.status },
        site: { id: 'filter-site', empty: 'NONE', actual: p => p.site },
        dept: { id: 'filter-dept', empty: 'NONE', actual: p => p.dept_code },
        win: { id: 'filter-win', empty: 'NONE', actual: p => (p.has_won || p.has_won_public) ? 'WON' : 'NOT_WON' },
        prize: { id: 'filter-prize', empty: 'NONE', actual: p => p.prize_info || '' },
        participant_type: { id: 'filter-type', empty: 'NONE', actual: p => p.participant_type },
        meal: { id: 'filter-meal', empty: 'NONE', actual: p => p.meal_type },
        group: { id: 'filter-group', empty: 'NONE', actual: p => p.group_name }
    };

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

    function mealLabel(value) {
        if (!value) return '';
        const raw = String(value).trim();
        if (/^[A-Z]$/i.test(raw)) return raw.toUpperCase() + ' 餐';
        return raw;
    }

    function mealBadge(value) {
        const label = mealLabel(value);
        if (!label) return '-';
        return `<span style="${MEAL_STYLE}font-size:0.78rem;padding:3px 9px;border-radius:6px;font-weight:600;display:inline-block;max-width:240px;white-space:normal;line-height:1.35;">${escapeHtml(label)}</span>`;
    }

    function groupKey(value) {
        const raw = String(value || '').trim().toUpperCase();
        const match = raw.match(/^([A-F])\s*(組|$)/);
        return match ? match[1] : '';
    }

    function groupBadge(value) {
        if (!value) return '-';
        const style = GROUP_STYLES[groupKey(value)] || GROUP_STYLES.DEFAULT;
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
        addOptionIfMissing(document.getElementById('filter-type'), 'vendor_contact', '外部廠商主要窗口');
        addOptionIfMissing(document.getElementById('filter-type'), 'vendor', '外部廠商');
        const filterMeal = document.getElementById('filter-meal');
        if (filterMeal) {
            const current = filterMeal.value;
            [...new Set(list.map(p => p.meal_type).filter(Boolean))].sort()
                .forEach(value => addOptionIfMissing(filterMeal, value, mealLabel(value)));
            if (current && Array.from(filterMeal.options).some(option => option.value === current)) filterMeal.value = current;
        }
    }

    function getMultiValues(select) {
        const stored = select && select.dataset.multiValues;
        if (stored) return stored.split('|').filter(Boolean);
        return select ? Array.from(select.selectedOptions).map(option => option.value) : ['ALL'];
    }

    function matchMulti(values, actual, emptyToken, contains) {
        if (!values.length || values.includes('ALL')) return true;
        if (values.includes(emptyToken) && !actual) return true;
        if (contains) return values.some(value => actual && String(actual).includes(value));
        return values.includes(actual || '');
    }

    function applyMultiFilterVisibility() {
        const tableBody = document.getElementById('table-body');
        const displayCount = document.getElementById('display-count');
        if (!tableBody) return;
        const list = getDashboardData();
        const dataByEmployeeId = new Map(list.map(p => [String(p.employee_id), p]));
        let visibleCount = 0;
        Array.from(tableBody.querySelectorAll('tr')).forEach(row => {
            if (!row.children || row.children.length < 2) return;
            const person = dataByEmployeeId.get(row.children[1].textContent.trim());
            if (!person) return;
            let ok = true;
            Object.keys(FILTER_MAP).forEach(key => {
                const meta = FILTER_MAP[key];
                const select = document.getElementById(meta.id);
                if (!select || !select.multiple) return;
                ok = ok && matchMulti(getMultiValues(select), meta.actual(person), meta.empty, key === 'prize');
            });
            row.style.display = ok ? '' : 'none';
            if (ok) visibleCount += 1;
        });
        if (displayCount) displayCount.innerText = visibleCount;
    }

    function enableDashboardFilterModes(modes) {
        Object.keys(FILTER_MAP).forEach(key => {
            const select = document.getElementById(FILTER_MAP[key].id);
            if (!select) return;
            const useMulti = modes && modes[key] !== false;
            select.multiple = useMulti;
            select.size = useMulti ? Math.min(Math.max(select.options.length, 3), 6) : 1;
            if (useMulti) {
                select.dataset.multiValues = 'ALL';
                select.title = '可按 Ctrl / Command 複選';
                select.addEventListener('change', function () {
                    const values = Array.from(select.selectedOptions).map(option => option.value);
                    select.dataset.multiValues = values.length ? values.join('|') : 'ALL';
                    Array.from(select.options).forEach(option => option.selected = option.value === 'ALL');
                    window.setTimeout(() => {
                        const restore = select.dataset.multiValues.split('|').filter(Boolean);
                        Array.from(select.options).forEach(option => option.selected = restore.includes(option.value));
                        applyMultiFilterVisibility();
                    }, 0);
                }, true);
            }
        });
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
        const groupIndex = headers.findIndex(text => text.includes('組別'));
        const ageIndex = headers.findIndex(text => text.includes('大人') || text.includes('小孩'));
        const phoneIndex = headers.findIndex(text => text.includes('電話'));

        Array.from(tableBody.querySelectorAll('tr')).forEach(row => {
            if (!row.children || row.children.length < 2) return;
            const employeeId = row.children[1].textContent.trim();
            const person = dataByEmployeeId.get(employeeId);
            if (!person) return;

            if (deptIndex >= 0 && row.children[deptIndex]) {
                const fullDept = person.dept_code || '';
                row.children[deptIndex].textContent = truncateText(fullDept, 4);
                row.children[deptIndex].title = fullDept;
            }
            if (typeIndex >= 0 && row.children[typeIndex]) row.children[typeIndex].innerHTML = participantBadge(person);
            if (mealIndex >= 0 && row.children[mealIndex]) row.children[mealIndex].innerHTML = mealBadge(person.meal_type);
            if (groupIndex >= 0 && row.children[groupIndex]) row.children[groupIndex].innerHTML = groupBadge(person.group_name);
            if (ageIndex >= 0 && row.children[ageIndex]) row.children[ageIndex].innerHTML = person.age_group ? `<span class="badge bg-light text-dark border">${escapeHtml(person.age_group)}</span>` : '-';
            if (phoneIndex >= 0 && row.children[phoneIndex]) row.children[phoneIndex].innerHTML = person.phone ? `<span style="font-size:0.82rem;">${escapeHtml(person.phone)}</span>` : '-';
        });
        applyMultiFilterVisibility();
    }

    function injectAdminFilterModeCard() {
        if (!location.pathname.includes('/admin')) return;
        if (document.getElementById('filter-mode-settings-card')) return;
        const queryCardTitle = Array.from(document.querySelectorAll('.card-header span')).find(el => el.textContent.trim() === '查詢站顯示欄位');
        if (!queryCardTitle) return;
        fetch('/admin/api/filter_modes').then(r => r.json()).then(data => {
            if (!data.success) return;
            const card = document.createElement('div');
            card.className = 'card mb-4';
            card.id = 'filter-mode-settings-card';
            const rows = Object.entries(data.filter_mode_labels).map(([key, label]) => {
                const isMulti = data.filter_modes[key] !== false;
                return `<div class="col-6 col-md-4"><label class="form-label small fw-bold">${escapeHtml(label)}</label><select class="form-select form-select-sm" name="filter_multi_${escapeHtml(key)}"><option value="true" ${isMulti ? 'selected' : ''}>複選</option><option value="false" ${!isMulti ? 'selected' : ''}>單選</option></select></div>`;
            }).join('');
            card.innerHTML = `<div class="card-header ch-info d-flex align-items-center gap-2"><i class="bi bi-funnel fs-5"></i><span>報到名單篩選模式</span></div><div class="card-body p-4"><p class="small text-muted mb-3">設定 Dashboard 篩選欄位要使用單選或複選。預設皆為複選。</p><form action="/admin/filter_modes" method="POST"><div class="row g-3 mb-3">${rows}</div><div class="d-grid"><button type="submit" class="btn btn-ocean"><i class="bi bi-save me-1"></i>儲存篩選設定</button></div></form></div>`;
            queryCardTitle.closest('.card').before(card);
        }).catch(() => {});
    }

    document.addEventListener('DOMContentLoaded', function () {
        injectAdminFilterModeCard();
        if (document.getElementById('table-body')) {
            fetch('/admin/api/filter_modes').then(r => r.json()).then(data => {
                if (data.success) enableDashboardFilterModes(data.filter_modes);
            }).catch(() => enableDashboardFilterModes({}));
        }
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
