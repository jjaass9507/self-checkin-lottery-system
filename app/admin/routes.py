from flask import (
    Blueprint, render_template, request, flash, redirect, url_for
)
import pandas as pd
from app import db
# (*** 這裡是修改重點 ***)
# 我們需要 CheckinList (匯入用) 和 Prize, Winner (獎項設定用)
from app.models import CheckinList, Prize, Winner 

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
                    
                    if not employee_id:
                        continue 

                    exists = CheckinList.query.filter_by(employee_id=employee_id).first()
                    
                    if not exists:
                        new_item = CheckinList(
                            name=name,
                            employee_id=employee_id
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

# --- (*** 這裡是新增/修改的程式碼 ***) ---

@bp.route('/prizes', methods=['GET', 'POST'])
def prizes():
    # --- (A) 處理「新增獎項」的 POST 請求 ---
    if request.method == 'POST':
        try:
            # 1. 從表單獲取資料
            prize_name = request.form.get('prize_name')
            description = request.form.get('description')
            quantity = int(request.form.get('quantity', 1)) # 轉成數字

            if not prize_name:
                flash('「獎項名稱」為必填欄位', 'warning')
            elif quantity < 1:
                flash('「名額」必須大於 0', 'warning')
            else:
                # 2. 建立新獎項物件
                new_prize = Prize(
                    prize_name=prize_name,
                    description=description,
                    quantity=quantity
                )
                # 3. 存入資料庫
                db.session.add(new_prize)
                db.session.commit()
                flash(f"獎項 [{prize_name}] 已成功新增！", 'success')
        
        except ValueError:
            flash('「名額」必須是有效的數字', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f"新增獎項時發生錯誤：{e}", 'danger')
        
        return redirect(url_for('admin.prizes')) # 處理完 POST 後，重新導向

    # --- (B) 處理「顯示頁面」的 GET 請求 ---
    all_prizes = Prize.query.order_by(Prize.id).all()
    return render_template('admin/prizes.html', prizes=all_prizes)

@bp.route('/prizes/delete/<int:prize_id>', methods=['POST'])
def delete_prize(prize_id):
    # 1. 找到要刪除的獎項
    prize_to_delete = Prize.query.get_or_404(prize_id)
    
    try:
        # (*** 關鍵檢查 ***)
        # 檢查是否「已經有人」中了這個獎 (雖然現在還沒抽獎，但這是好習慣)
        if prize_to_delete.winners:
            flash(f"獎項 [{prize_to_delete.prize_name}] 已有中獎紀錄，不可刪除。", 'danger')
        else:
            prize_name = prize_to_delete.prize_name
            db.session.delete(prize_to_delete)
            db.session.commit()
            flash(f"獎項 [{prize_name}] 已成功刪除。", 'success')
            
    except Exception as e:
        db.session.rollback()
        flash(f"刪除時發生錯誤：{e}", 'danger')

    return redirect(url_for('admin.prizes'))