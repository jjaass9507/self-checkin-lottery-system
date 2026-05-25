(function () {
    'use strict';

    const PARTICIPANT_LABELS = { employee: '員工', dependent: '眷屬', vendor_contact: '外部廠商主要窗口', vendor: '外部廠商' };
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
    let MULTI_MODES = {};
    let renderWrapped = false;

    function escapeHtml(value) {
        return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\"/g, '&quot;').replace(/'/g, '&#39;');
    }
    function truncateText(value, maxChars) {
        if (!value) return '-';
        const chars = Array.from(String(value));
        return chars.length > maxChars ? chars.slice(0, maxChars).join('') : String(value);
    }
    function mealLabel(value) {
        if (!value) return '';
        const raw = String(value).trim();
        return /^[A-Z]$/i.test(raw) ? raw.toUpperCase() + ' 餐' : raw;
    }
    function mealBadge(value) {
        const label = mealLabel(value);
        if (!label) return '-';
        return `<span style="${MEAL_STYLE}font-size:0.78rem;padding:3px 9px;border-radius:6px;font-weight:600;display:inline-block;max-width:240px;white-space:normal;line-height:1.35;">${escapeHtml(label)}</span>`;
    }
    function groupBadge(value) {
        if (!value) return '-';
        const match = String(value || '').trim().toUpperCase().match(/^([A-F])\s*(組|$)/);
        const style = GROUP_STYLES[match ? match[1] : ''] || GROUP_STYLES.DEFAULT;
        return `<span style="${style}font-size:0.75rem;padding:2px 7px;border-radius:5px;font-weight:600;display:inline-block;max-width:180px;white-space:normal;line-height:1.35;">${escapeHtml(value)}</span>`;
    }
    function participantBadge(person) {
        const type = person && person.participant_type;
        const label = PARTICIPANT_LABELS[type];
        if (!label) return '-';
        let html = `<span style="${TYPE_STYLES[type] || TYPE_STYLES.employee}font-size:0.75rem;padding:2px 7px;border-radius:5px;font-weight:600;display:inline-block;">${escapeHtml(label)}</span>`;
        if (type === 'dependent' && person.linked_employee_id) html += `<br><small class="text-muted" style="font-size:0.7rem;">→ ${escapeHtml(person.linked_employee_id)}</small>`;
        return html;
    }
    function addOptionIfMissing(select, value, label) {
        if (!select || !value) return;
        if (!Array.from(select.options).some(option => option.value === value)) select.appendChild(new Option(label, value));
    }
    function getDashboardData() {
        try { if (Array.isArray(fullDataCache)) return fullDataCache; } catch (e) {}
        return [];
    }

    function patchDashboardFilters(list) {
        addOptionIfMissing(document.getElementById('filter-type'), 'vendor_contact', '外部廠商主要窗口');
        addOptionIfMissing(document.getElementById('filter-type'), 'vendor', '外部廠商');
        const filterMeal = document.getElementById('filter-meal');
        if (filterMeal) [...new Set(list.map(p => p.meal_type).filter(Boolean))].sort().forEach(value => addOptionIfMissing(filterMeal, value, mealLabel(value)));
        rebuildAllMultiWidgets();
    }

    function widgetFor(key) { return document.getElementById(`multi-filter-${key}`); }
    function selectedValuesFor(key) {
        const widget = widgetFor(key);
        if (widget) return (widget.dataset.values || 'ALL').split('|').filter(Boolean);
        const select = document.getElementById(FILTER_MAP[key].id);
        return select ? [select.value || 'ALL'] : ['ALL'];
    }
    function setWidgetValues(key, values) {
        const widget = widgetFor(key);
        if (!widget) return;
        const normalized = (!values.length || values.includes('ALL')) ? ['ALL'] : values;
        widget.dataset.values = normalized.join('|');
        widget.querySelectorAll('input[type="checkbox"]').forEach(input => { input.checked = normalized.includes(input.value); });
        const select = document.getElementById(FILTER_MAP[key].id);
        const labels = Array.from(select.options).filter(o => normalized.includes(o.value) && o.value !== 'ALL').map(o => o.textContent.trim());
        const btn = widget.querySelector('button');
        btn.textContent = labels.length ? (labels.length <= 2 ? labels.join('、') : `已選 ${labels.length} 項`) : (select.options[0] ? select.options[0].textContent.trim() : '全部');
    }
    function rebuildMultiWidget(key) {
        const meta = FILTER_MAP[key];
        const select = document.getElementById(meta.id);
        if (!select) return;
        if (MULTI_MODES[key] === false) {
            select.classList.remove('d-none');
            const old = widgetFor(key);
            if (old) old.remove();
            return;
        }
        select.value = 'ALL';
        select.classList.add('d-none');
        let widget = widgetFor(key);
        const values = widget ? selectedValuesFor(key) : ['ALL'];
        const signature = Array.from(select.options).map(o => `${o.value}:${o.textContent}`).join('|');
        if (widget && widget.dataset.signature === signature) return;
        if (!widget) {
            widget = document.createElement('div');
            widget.id = `multi-filter-${key}`;
            widget.className = 'dropdown dashboard-multi-filter';
            select.after(widget);
        }
        widget.dataset.signature = signature;
        const items = Array.from(select.options).map(option => `
            <label class="dropdown-item small d-flex align-items-center gap-2" style="cursor:pointer;">
                <input class="form-check-input m-0" type="checkbox" value="${escapeHtml(option.value)}">
                <span>${escapeHtml(option.textContent.trim())}</span>
            </label>`).join('');
        widget.innerHTML = `<button class="btn btn-sm btn-light border dropdown-toggle w-100 text-start" type="button" data-bs-toggle="dropdown" data-bs-auto-close="outside">全部</button><div class="dropdown-menu p-2 shadow" style="max-height:260px;overflow:auto;min-width:100%;">${items}</div>`;
        widget.querySelectorAll('input[type="checkbox"]').forEach(input => {
            input.addEventListener('change', () => {
                let checked = Array.from(widget.querySelectorAll('input:checked')).map(i => i.value);
                if (input.value === 'ALL' && input.checked) checked = ['ALL'];
                else checked = checked.filter(v => v !== 'ALL');
                if (!checked.length) checked = ['ALL'];
                setWidgetValues(key, checked);
                if (typeof window.renderTable === 'function') window.renderTable();
            });
        });
        setWidgetValues(key, values.filter(value => Array.from(select.options).some(o => o.value === value)));
    }
    function rebuildAllMultiWidgets() { Object.keys(FILTER_MAP).forEach(rebuildMultiWidget); }

    function matchFilter(key, person) {
        const values = selectedValuesFor(key);
        if (!values.length || values.includes('ALL')) return true;
        const meta = FILTER_MAP[key];
        const actual = meta.actual(person);
        if (values.includes(meta.empty) && !actual) return true;
        if (key === 'prize') return values.some(value => actual && String(actual).includes(value));
        return values.includes(actual || '');
    }
    function applyMultiFilterVisibility() {
        const tableBody = document.getElementById('table-body');
        const displayCount = document.getElementById('display-count');
        if (!tableBody) return;
        const dataByEmployeeId = new Map(getDashboardData().map(p => [String(p.employee_id), p]));
        let visibleCount = 0;
        Array.from(tableBody.querySelectorAll('tr')).forEach(row => {
            if (!row.children || row.children.length < 2) return;
            const person = dataByEmployeeId.get(row.children[1].textContent.trim());
            if (!person) return;
            const ok = Object.keys(FILTER_MAP).every(key => MULTI_MODES[key] === false || matchFilter(key, person));
            row.style.display = ok ? '' : 'none';
            if (ok) visibleCount += 1;
        });
        if (displayCount) displayCount.innerText = visibleCount;
    }

    function enableDashboardFilterModes(modes) {
        MULTI_MODES = modes || {};
        rebuildAllMultiWidgets();
        wrapRenderTable();
    }
    function wrapRenderTable() {
        if (renderWrapped || typeof window.renderTable !== 'function') return;
        const originalRenderTable = window.renderTable;
        window.renderTable = function () {
            Object.keys(FILTER_MAP).forEach(key => {
                if (MULTI_MODES[key] !== false) {
                    const select = document.getElementById(FILTER_MAP[key].id);
                    if (select) select.value = 'ALL';
                }
            });
            originalRenderTable.apply(this, arguments);
            rebuildAllMultiWidgets();
            applyMultiFilterVisibility();
        };
        renderWrapped = true;
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
            const person = dataByEmployeeId.get(row.children[1].textContent.trim());
            if (!person) return;
            if (deptIndex >= 0 && row.children[deptIndex]) { row.children[deptIndex].textContent = truncateText(person.dept_code || '', 4); row.children[deptIndex].title = person.dept_code || ''; }
            if (typeIndex >= 0 && row.children[typeIndex]) row.children[typeIndex].innerHTML = participantBadge(person);
            if (mealIndex >= 0 && row.children[mealIndex]) row.children[mealIndex].innerHTML = mealBadge(person.meal_type);
            if (groupIndex >= 0 && row.children[groupIndex]) row.children[groupIndex].innerHTML = groupBadge(person.group_name);
            if (ageIndex >= 0 && row.children[ageIndex]) row.children[ageIndex].innerHTML = person.age_group ? `<span class="badge bg-light text-dark border">${escapeHtml(person.age_group)}</span>` : '-';
            if (phoneIndex >= 0 && row.children[phoneIndex]) row.children[phoneIndex].innerHTML = person.phone ? `<span style="font-size:0.82rem;">${escapeHtml(person.phone)}</span>` : '-';
        });
        applyMultiFilterVisibility();
    }

    function injectAdminFilterModeCard() {
        if (!location.pathname.includes('/admin') || document.getElementById('filter-mode-settings-card')) return;
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
        if (document.getElementById('table-body')) fetch('/admin/api/filter_modes').then(r => r.json()).then(data => enableDashboardFilterModes(data.success ? data.filter_modes : {})).catch(() => enableDashboardFilterModes({}));
        const tableBody = document.getElementById('table-body');
        if (!tableBody) return;
        let ticking = false;
        const runPatch = function () {
            if (ticking) return;
            ticking = true;
            window.setTimeout(function () { patchDashboardRows(); ticking = false; }, 0);
        };
        new MutationObserver(runPatch).observe(tableBody, { childList: true });
        window.setInterval(patchDashboardRows, 1500);
    });
})();
