import os
from datetime import datetime
from tempfile import NamedTemporaryFile

import openpyxl
from flask import flash, redirect, render_template, request, url_for

from app import db
from app.admin.routes import bp
from app.models import AppSetting, CheckinList

IMPORT_BATCH_SIZE = 300


def _clean(value):
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return None
    return text


def _get(row, headers, key):
    idx = headers.get(key)
    if idx is None or idx >= len(row):
        return None
    return _clean(row[idx])


def _parse_business_trip(value):
    value = _clean(value)
    return bool(value and value.upper() in ['1', 'Y', 'YES', 'TRUE', '是'])


def _parse_participant_type(value):
    raw = (_clean(value) or '').lower()
    if raw in ['dependent', '眷屬', 'dep']:
        return 'dependent'
    if raw in ['employee', '員工', 'emp']:
        return 'employee'
    return None


def _parse_meal_type(value):
    raw = (_clean(value) or '').upper()
    return raw if raw in ['A', 'B'] else None


def _build_row_data(row, headers):
    name = _get(row, headers, 'name')
    employee_id = _get(row, headers, 'employee_id')
    if not name or not employee_id:
        return None

    is_business_trip = _parse_business_trip(_get(row, headers, 'is_business_trip'))

    return {
        'name': name,
        'employee_id': employee_id,
        'lottery_number': _get(row, headers, 'lottery_number'),
        'site': _get(row, headers, 'site'),
        'dept_code': _get(row, headers, 'dept_code'),
        'table_number': _get(row, headers, 'table_number'),
        'is_business_trip': is_business_trip,
        'status': 'CheckedIn' if is_business_trip else 'Registered',
        'check_in_time': datetime.now() if is_business_trip else None,
        'participant_type': _parse_participant_type(_get(row, headers, 'participant_type')),
        'linked_employee_id': _get(row, headers, 'linked_employee_id'),
        'meal_type': _parse_meal_type(_get(row, headers, 'meal_type')),
        'group_name': _get(row, headers, 'group_name'),
    }


def _save_batch(rows):
    if not rows:
        return 0, 0

    employee_ids = [row['employee_id'] for row in rows]
    existing_ids = {
        employee_id
        for (employee_id,) in db.session.query(CheckinList.employee_id)
        .filter(CheckinList.employee_id.in_(employee_ids))
        .all()
    }

    new_items = []
    skipped = 0

    for row_data in rows:
        employee_id = row_data['employee_id']
        if employee_id in existing_ids:
            skipped += 1
            continue
        new_items.append(CheckinList(**row_data))
        existing_ids.add(employee_id)

    if new_items:
        db.session.add_all(new_items)
        db.session.commit()
        db.session.expunge_all()

    return len(new_items), skipped


def _render_import_page():
    query_field_keys = [
        'employee_id', 'status', 'lottery_number', 'prize_info',
        'table_number', 'meal_type', 'group_name', 'participant_type'
    ]
    query_fields = {}
    for key in query_field_keys:
        setting = AppSetting.query.get(f'query_show_{key}')
        query_fields[key] = (setting.value != 'false') if setting else True

    dash_field_keys = [
        'checkin_seq', 'site', 'dept', 'table', 'business_trip',
        'participant_type', 'meal', 'group', 'lottery_number',
        'status', 'prize', 'checkin_time'
    ]
    dash_fields = {}
    for key in dash_field_keys:
        setting = AppSetting.query.get(f'dash_show_{key}')
        dash_fields[key] = (setting.value != 'false') if setting else True

    return render_template('admin/import.html', query_fields=query_fields, dash_fields=dash_fields)


def optimized_import_page():
    if request.method != 'POST':
        return _render_import_page()

    if 'file' not in request.files:
        flash('沒有檔案被上傳', 'danger')
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        flash('未選擇檔案', 'warning')
        return redirect(request.url)

    if not file.filename.lower().endswith('.xlsx'):
        flash('請上傳 .xlsx 格式的 Excel 檔案', 'warning')
        return redirect(request.url)

    tmp_path = None
    workbook = None
    imported_count = 0
    skipped_existing_count = 0
    skipped_invalid_count = 0

    try:
        with NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            file.save(tmp)
            tmp_path = tmp.name

        workbook = openpyxl.load_workbook(tmp_path, read_only=True, data_only=True)
        worksheet = workbook.active
        row_iter = worksheet.iter_rows(values_only=True)
        raw_headers = next(row_iter, None)

        if not raw_headers:
            flash('Excel 檔案是空的', 'danger')
            return redirect(request.url)

        headers = {
            str(header).strip(): index
            for index, header in enumerate(raw_headers)
            if header is not None and str(header).strip()
        }

        if 'name' not in headers or 'employee_id' not in headers:
            flash("Excel 檔案中缺少 'name' 或 'employee_id' 欄位", 'danger')
            return redirect(request.url)

        batch = []
        for row in row_iter:
            row_data = _build_row_data(row, headers)
            if not row_data:
                skipped_invalid_count += 1
                continue

            batch.append(row_data)
            if len(batch) >= IMPORT_BATCH_SIZE:
                inserted, skipped = _save_batch(batch)
                imported_count += inserted
                skipped_existing_count += skipped
                batch.clear()

        if batch:
            inserted, skipped = _save_batch(batch)
            imported_count += inserted
            skipped_existing_count += skipped

        message = f"成功！總共匯入了 {imported_count} 筆新的報到資料。"
        if skipped_existing_count:
            message += f" 已跳過 {skipped_existing_count} 筆既有或重複工號。"
        if skipped_invalid_count:
            message += f" 已跳過 {skipped_invalid_count} 筆缺少姓名或工號的資料。"
        flash(message, 'success')

    except Exception as exc:
        db.session.rollback()
        if imported_count:
            flash(f"匯入時發生錯誤：{exc}。已成功寫入 {imported_count} 筆，請檢查資料後再補匯。", 'danger')
        else:
            flash(f"匯入時發生嚴重錯誤：{exc}", 'danger')

    finally:
        if workbook:
            workbook.close()
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    return redirect(url_for('admin.import_page'))


bp.view_functions['import_page'] = optimized_import_page
