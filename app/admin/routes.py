from flask import (
    Blueprint, render_template, request, flash, redirect, url_for, session, current_app
)
import pandas as pd
from app import db
from app.models import CheckinList, DrawnTailNumber, Prize, CancellationLog
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

                    # (*** 新增：讀取是否為公差 ***)
                    # 支援輸入: 1, Y, yes, true, 是
                    biz_val = str(row.get('is_business_trip', '')).strip().upper()
                    is_business_trip = False
                    if biz_val in ['1', 'Y', 'YES', 'TRUE', '是']:
                        is_business_trip = True

                    if not employee_id:
                        continue 

                    exists = CheckinList.query.filter_by(employee_id=employee_id).first()
                    
                    if not exists:
                        # (*** 修改：如果是公差，預設狀態直接設為 CheckedIn ***)
                        initial_status = 'CheckedIn' if is_business_trip else 'Registered'
                        initial_time = datetime.now() if is_business_trip else None

                        new_item = CheckinList(
                            name=name,
                            employee_id=employee_id,
                            lottery_number=lottery_number if lottery_number else None,
                            site=site if site and site.lower() != 'nan' else None,
                            dept_code=dept_code if dept_code and dept_code.lower() != 'nan' else None,
                            
                            # (*** 寫入新欄位 ***)
                            table_number=table_number,
                            is_business_trip=is_business_trip,
                            
                            # (*** 設定初始狀態 ***)
                            status=initial_status,
                            check_in_time=initial_time
                        )
                        db.session.add(new_item)
                        imported_count += 1
                
                db.session.commit()
                flash(f"成功！總共匯入了 {imported_count} 筆新的報到資料。", 'success')

            except Exception as e:
                db.session.rollback()
                flash(f"匯入時發生嚴重錯誤：{e}", 'danger')
            
            return redirect(url_for('admin.import_page'))

    return render_template('admin/import.html')

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