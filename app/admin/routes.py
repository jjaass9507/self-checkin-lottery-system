from flask import (
    Blueprint, render_template, request, flash, redirect, url_for
)
import pandas as pd
from app import db
# (*** 1. 移除了 Prize, Winner ***)
from app.models import CheckinList 

bp = Blueprint('admin', __name__)

@bp.route('/')
def index():
    # (*** 2. 獎項頁面沒了，所以首頁永遠是匯入頁 ***)
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

                # (*** 3. 檢查欄位更新 ***)
                if 'name' not in df.columns or 'employee_id' not in df.columns:
                    flash("Excel 檔案中缺少 'name' 或 'employee_id' 欄位", 'danger')
                    return redirect(request.url)

                imported_count = 0
                for _, row in df.iterrows():
                    name = str(row['name'])
                    employee_id = str(row['employee_id']) 
                    
                    # (*** 4. 讀取新的 lottery_number ***)
                    # (使用 .get()，如果 Excel 沒這欄，就存為 None)
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

# (*** 5. 獎項相關的 /prizes 和 /prizes/delete 路由已全部刪除 ***)