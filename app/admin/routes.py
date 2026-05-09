from flask import (
    Blueprint, render_template, request, flash, redirect, url_for, session, current_app, send_file
)
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill
from io import BytesIO
from app import db
from app.models import CheckinList, DrawnTailNumber, Prize, CancellationLog, AppSetting
from datetime import datetime

bp = Blueprint('admin', __name__)

# --- (新增) 1. 權限卡控攔截器 ---
@bp.before_request
def require_login():
    # 如果請求的是「登入頁面」本身，就放行，避免無窮迴圈
    if request.endpoint == 'admin.login':
        return

    # 檢查 session 中是否有標記 is_admin
    if not session.get('is_admin'):
        return redirect(url_for('admin.login'))

# --- (新增) 2. 登入路由 (只有輸入密碼) ---
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        input_password = request.form.get('password')
        
        # 比對 config 中的密碼
        if input_password == current_app.config['ADMIN_PASSWORD']:
            session['is_admin'] = True  # 寫入 session
            session.permanent = True    # (選用) 記住登入狀態
            flash('登入成功', 'success')
            return redirect(url_for('admin.import_page'))
        else:
            flash('密碼錯誤', 'danger')
            
    return render_template('admin/login.html')

# --- (新增) 3. 登出路由 ---
@bp.route('/logout')
def logout():
    session.pop('is_admin', None) # 移除 session
    flash('已登出', 'info')
    return redirect(url_for('admin.login'))

@bp.route('/')
def index():
    return redirect(url_for('admin.import_page'))

@bp.route('/import', methods=['GET', 'POST'])
def import_page():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('沒有檔案被上傳', 'danger')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('未選擇檔案', 'warning')
            return redirect(request.url)

        if file and file.filename.endswith('.xlsx'):
            try:
                df = pd.read_excel(file)

                if 'name' not in df.columns or 'employee_id' not in df.columns:
                    flash("Excel 檔案中缺少 'name' 或 'employee_id' 欄位", 'danger')
                    return redirect(request.url)

                imported_count = 0
                for _, row in df.iterrows():
                    name = str(row['name'])
                    employee_id = str(row['employee_id']) 
                    lottery_number = str(row.get('lottery_number', ''))
                    
                    # 既有欄位
                    site = str(row.get('site', ''))
                    dept_code = str(row.get('dept_code', ''))

                    # (*** 新增：讀取桌次 ***)
                    table_val = str(row.get('table_number', ''))
                    table_number = table_val if table_val and table_val.lower() != 'nan' else None

                    # 支援輸入: 1, Y, yes, true, 是
                    biz_val = str(row.get('is_business_trip', '')).strip().upper()
                    is_business_trip = biz_val in ['1', 'Y', 'YES', 'TRUE', '是']

                    # ===== 活動額外欄位 (向後相容：欄位不存在時為 None) =====
                    # 身分類別
                    pt_raw = str(row.get('participant_type', '')).strip().lower()
                    if pt_raw in ['dependent', '眷屬', 'dep']:
                        participant_type = 'dependent'
                    elif pt_raw in ['employee', '員工', 'emp']:
                        participant_type = 'employee'
                    else:
                        participant_type = None

                    # 綁定員工工號 (眷屬用)
                    linked_raw = str(row.get('linked_employee_id', '')).strip()
                    linked_employee_id = linked_raw if linked_raw and linked_raw.lower() != 'nan' else None

                    # 餐點類型
                    meal_raw = str(row.get('meal_type', '')).strip().upper()
                    meal_type = meal_raw if meal_raw in ['A', 'B'] else None

                    # 分組
                    group_raw = str(row.get('group_name', '')).strip()
                    group_name = group_raw if group_raw and group_raw.lower() != 'nan' else None

                    if not employee_id:
                        continue

                    exists = CheckinList.query.filter_by(employee_id=employee_id).first()

                    if not exists:
                        initial_status = 'CheckedIn' if is_business_trip else 'Registered'
                        initial_time = datetime.now() if is_business_trip else None

                        new_item = CheckinList(
                            name=name,
                            employee_id=employee_id,
                            lottery_number=lottery_number if lottery_number else None,
                            site=site if site and site.lower() != 'nan' else None,
                            dept_code=dept_code if dept_code and dept_code.lower() != 'nan' else None,
                            table_number=table_number,
                            is_business_trip=is_business_trip,
                            status=initial_status,
                            check_in_time=initial_time,
                            # 活動額外欄位
                            participant_type=participant_type,
                            linked_employee_id=linked_employee_id,
                            meal_type=meal_type,
                            group_name=group_name,
                        )
                        db.session.add(new_item)
                        imported_count += 1
                
                db.session.commit()
                flash(f"成功！總共匯入了 {imported_count} 筆新的報到資料。", 'success')

            except Exception as e:
                db.session.rollback()
                flash(f"匯入時發生嚴重錯誤：{e}", 'danger')
            
            return redirect(url_for('admin.import_page'))

    field_keys = ['employee_id', 'status', 'lottery_number', 'prize_info',
                  'table_number', 'meal_type', 'group_name', 'participant_type']
    query_fields = {}
    for key in field_keys:
        setting = AppSetting.query.get(f'query_show_{key}')
        query_fields[key] = (setting.value != 'false') if setting else True

    return render_template('admin/import.html', query_fields=query_fields)

# --- (新功能) 0. 查詢站欄位設定 ---
@bp.route('/query_fields', methods=['POST'])
def toggle_query_fields():
    field_keys = ['employee_id', 'status', 'lottery_number', 'prize_info',
                  'table_number', 'meal_type', 'group_name', 'participant_type']
    for key in field_keys:
        new_value = 'true' if request.form.get(f'show_{key}') else 'false'
        setting = AppSetting.query.get(f'query_show_{key}')
        if setting:
            setting.value = new_value
        else:
            db.session.add(AppSetting(key=f'query_show_{key}', value=new_value))
    db.session.commit()
    flash('查詢站欄位設定已更新', 'success')
    return redirect(url_for('admin.import_page'))

# --- (新功能) 1. 清除所有名單 (最徹底) ---
@bp.route('/reset/list', methods=['POST'])
def reset_list():
    try:
        # 清空名單會連帶讓所有狀態消失，所以通常也建議清空抽獎紀錄(選項)
        # 這裡我們只清空 CheckinList，但為了資料一致性，建議使用者先清空抽獎紀錄
        deleted = db.session.query(CheckinList).delete()
        db.session.commit()
        flash(f"已清除所有名單 (共 {deleted} 筆)。", 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f"清除名單失敗：{e}", 'danger')
    return redirect(url_for('admin.import_page'))

# --- (新功能) 2. 清除報到紀錄 (重置為未報到) ---
@bp.route('/reset/checkin', methods=['POST'])
def reset_checkin():
    try:
        # 將所有 status='CheckedIn' 改為 'Registered'，時間歸零
        updated = CheckinList.query.filter_by(status='CheckedIn').update({
            'status': 'Registered',
            'check_in_time': None
        })
        db.session.commit()
        flash(f"已重置所有報到狀態 (共 {updated} 人變回未報到)。", 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f"重置報到失敗：{e}", 'danger')
    return redirect(url_for('admin.import_page'))

# --- (新功能) 3. 清除中獎紀錄 (重置為未中獎) ---
@bp.route('/reset/lottery', methods=['POST'])
def reset_lottery():
    try:
        # 1. 刪除所有開獎號碼紀錄 (DrawnTailNumber)
        # 這會一併刪除尾數獎和公獎的開獎歷史
        deleted_log = db.session.query(DrawnTailNumber).delete()
        
        # 2. 重置所有人員的中獎與領獎狀態
        # 使用 update 一次性更新所有欄位
        updated_rows = db.session.query(CheckinList).update({
            CheckinList.has_won: False,              # 清除尾數中獎
            CheckinList.prize_claimed: False,        # 清除尾數已領
            CheckinList.has_won_public: False,       # (新增) 清除公獎中獎
            CheckinList.public_prize_claimed: False  # (新增) 清除公獎已領
        })
        
        db.session.commit()
        flash(f"已重置所有中獎紀錄 (清除 {deleted_log} 筆開獎，更新 {updated_rows} 人狀態)。", 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f"重置中獎失敗：{e}", 'danger')
    return redirect(url_for('admin.import_page'))

# --- (新功能) 4. 單獨清除特定獎項的中獎紀錄 ---
@bp.route('/reset/prize', methods=['POST'])
def reset_prize():
    prize_name = request.form.get('prize_name')
    prize_type = request.form.get('prize_type')
    
    if not prize_name:
        flash('未指定獎項名稱', 'danger')
        return redirect(url_for('admin.manage_prizes'))

    try:
        # 1. 找出相關的開獎紀錄 (DrawnTailNumber)
        draws = DrawnTailNumber.query.filter_by(
            prize_name=prize_name, 
            prize_type=prize_type
        ).all()
        
        if not draws:
            flash(f"找不到「{prize_name}」的開獎紀錄，可能尚未抽出。", 'info')
            return redirect(url_for('admin.manage_prizes'))

        draw_count = len(draws)
        updated_users = 0
        
        # 2. 針對每一筆開獎，還原中獎者狀態
        for draw in draws:
            suffix = str(draw.tail_number)
            
            if prize_type == 'tail':
                # 尾數獎邏輯
                # 只有 "非加碼 (is_addon=False)" 的紀錄，才代表該次抽獎造成了人員 "從未中獎變成已中獎"。
                # 如果是 "加碼"，代表該人員在抽之前就已經中獎了，所以刪除加碼紀錄不應影響他的 has_won 狀態。
                
                if not draw.is_addon:
                    # 找出符合該尾數 且 has_won=True 的人
                    candidates = CheckinList.query.filter(
                        CheckinList.has_won == True,
                        CheckinList.lottery_number.endswith(suffix)
                    ).all()
                    
                    for p in candidates:
                        p.has_won = False
                        p.prize_claimed = False
                        updated_users += 1
                
                # 若是加碼紀錄，我們只刪除 DrawnTailNumber，不把人改回未中獎，因為他可能還有其他一般獎項

            elif prize_type == 'public':
                # 公獎邏輯 (通常無加碼，直接比對)
                # 公獎號碼比對需要補零至3位數
                target = str(draw.tail_number).zfill(3)
                
                # 找出所有中公獎的人
                candidates = CheckinList.query.filter_by(has_won_public=True).all()
                for p in candidates:
                    p_num = str(p.lottery_number).zfill(3) if p.lottery_number else "000"
                    
                    if p_num == target:
                        p.has_won_public = False
                        p.public_prize_claimed = False
                        updated_users += 1

            # 3. 刪除該筆開獎紀錄
            db.session.delete(draw)
        
        db.session.commit()
        flash(f"已重置「{prize_name}」 (清除 {draw_count} 筆開獎紀錄，還原 {updated_users} 人為未中獎)。", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"重置失敗：{e}", 'danger')

    return redirect(url_for('admin.manage_prizes'))

# --- 測試用一鍵簽到 ---
@bp.route('/test_checkin_all', methods=['POST'])
def test_checkin_all():
    try:
        pending_users = CheckinList.query.filter(CheckinList.status != 'CheckedIn').all()
        count = len(pending_users)
        if count == 0:
            flash("目前所有人皆已報到。", 'info')
            return redirect(url_for('admin.import_page'))

        current_time = datetime.now()
        for person in pending_users:
            person.status = 'CheckedIn'
            person.check_in_time = current_time
        db.session.commit()
        flash(f"【測試】已將剩餘 {count} 人標記為已報到。", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"失敗：{e}", 'danger')
    return redirect(url_for('admin.import_page'))

# --- 下載範本 ---
@bp.route('/download_template')
def download_template():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '報到名單範本'

    headers = [
        'name', 'employee_id', 'lottery_number',
        'site', 'dept_code', 'table_number', 'is_business_trip',
        'participant_type', 'linked_employee_id', 'meal_type', 'group_name'
    ]
    ws.append(headers)

    # 範例資料列
    ws.append(['王小明', 'A001', '101', 'Taipei', 'IT', '5', '', 'employee', '', 'A', '第一組'])
    ws.append(['李小花', 'B002', '202', '', '', '', '', 'dependent', 'A001', 'B', '第一組'])
    ws.append(['陳大雄', 'C003', '303', 'Hsinchu', 'RD', '8', 'Y', '', '', '', ''])

    # 標題列樣式
    header_fill = PatternFill(start_color='0369a1', end_color='0369a1', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font

    # 自動欄寬
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max(max_len + 4, 14)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='checkin_template.xlsx'
    )


# --- 切換抽獎功能 ---
@bp.route('/toggle_lottery', methods=['POST'])
def toggle_lottery():
    new_value = request.form.get('lottery_enabled', 'true')
    setting = AppSetting.query.get('lottery_enabled')
    if setting:
        setting.value = new_value
    else:
        db.session.add(AppSetting(key='lottery_enabled', value=new_value))
    db.session.commit()
    state = '啟用' if new_value == 'true' else '停用'
    flash(f'抽獎功能已{state}', 'success')
    return redirect(url_for('admin.import_page'))


# --- (新增) 檢視取消紀錄頁面 ---
@bp.route('/logs')
def logs_page():
    # 撈取所有紀錄，並依照時間倒序 (最新的在最上面)
    # 使用 join 讓我們可以直接查到「被取消的人」的名字
    logs = db.session.query(CancellationLog, CheckinList)\
        .join(CheckinList, CancellationLog.checkin_list_id == CheckinList.id)\
        .order_by(CancellationLog.timestamp.desc())\
        .all()

    return render_template('admin/logs.html', logs=logs)

# --- (新增) 獎項管理頁面 ---
@bp.route('/prizes', methods=['GET', 'POST'])
# @login_required
def manage_prizes():
    """管理獎項清單"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            name = request.form.get('name')
            prize_type = request.form.get('prize_type')
            quantity = int(request.form.get('quantity', 1))
            display_order = int(request.form.get('display_order', 0))
            
            if name:
                new_prize = Prize(
                    name=name, 
                    prize_type=prize_type, 
                    quantity=quantity,
                    display_order=display_order
                )
                db.session.add(new_prize)
                flash('獎項已新增', 'success')

        elif action == 'edit':
            prize_id = request.form.get('prize_id')
            prize = Prize.query.get(prize_id)
            if prize:
                prize.name = request.form.get('name')
                prize.prize_type = request.form.get('prize_type')
                prize.quantity = int(request.form.get('quantity', 1))
                prize.display_order = int(request.form.get('display_order', 0))
                flash('獎項已更新', 'success')
                
        elif action == 'delete':
            prize_id = request.form.get('prize_id')
            prize = Prize.query.get(prize_id)
            if prize:
                db.session.delete(prize)
                flash('獎項已刪除', 'warning')

        db.session.commit()
        return redirect(url_for('admin.manage_prizes'))

    # 讀取所有獎項並排序
    prizes = Prize.query.order_by(Prize.prize_type, Prize.display_order).all()
    return render_template('admin/prizes.html', prizes=prizes)