from flask import (
    Blueprint, render_template, request, flash, redirect, url_for
)
import pandas as pd
from app import db
from app.models import CheckinList, DrawnTailNumber, CancellationLog
from datetime import datetime

bp = Blueprint('admin', __name__)

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
                    
                    if not employee_id:
                        continue 

                    exists = CheckinList.query.filter_by(employee_id=employee_id).first()
                    
                    if not exists:
                        new_item = CheckinList(
                            name=name,
                            employee_id=employee_id,
                            lottery_number=lottery_number if lottery_number else None
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
        # 1. 刪除 DrawnTailNumber 紀錄
        deleted_log = db.session.query(DrawnTailNumber).delete()
        
        # 2. 將所有 has_won=True 改為 False
        updated_people = CheckinList.query.filter_by(has_won=True).update({
            'has_won': False
        })
        
        db.session.commit()
        flash(f"已重置中獎紀錄 (清除 {deleted_log} 筆尾號，{updated_people} 人變回未中獎)。", 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f"重置中獎失敗：{e}", 'danger')
    return redirect(url_for('admin.import_page'))

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