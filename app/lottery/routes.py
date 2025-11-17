from flask import Blueprint, render_template, request, jsonify
from app import db
# (*** 1. 移除了 Prize, Winner ***)
from app.models import CheckinList, DrawnTailNumber
from datetime import datetime
from sqlalchemy import or_ # (我們需要這個來做 .endswith() 查詢)

bp = Blueprint('lottery', __name__)

# --- (A) 抽獎大螢幕 主頁面 ---
@bp.route('/screen')
def lottery_screen():
    return render_template('lottery/screen.html')

# --- (B) 完整中獎名單 (日誌) 頁面 ---
@bp.route('/winners')
def winners_list():
    # (*** 2. 邏輯大改 ***)
    # 查詢所有「已中獎」的人，並依工號排序
    all_winners = CheckinList.query.filter_by(has_won=True).order_by(CheckinList.employee_id).all()
    
    # 查詢所有「已抽出的尾號」
    drawn_numbers = DrawnTailNumber.query.all()
    
    return render_template('lottery/winners.html', 
                           all_winners=all_winners,
                           drawn_numbers=drawn_numbers)

# --- (C) 核心 API：(前端) 獲取當前狀態 ---
@bp.route('/api/get_data')
def api_get_data():
    try:
        # 1. 計算抽獎池人數
        available_count = CheckinList.query.filter_by(
            status='CheckedIn',
            has_won=False
        ).count()

        # 2. 獲取所有「已抽出的尾號」
        drawn_numbers_obj = DrawnTailNumber.query.all()
        # (將 [obj(7), obj(3)] 轉換為 [7, 3])
        drawn_numbers_list = [d.tail_number for d in drawn_numbers_obj]
            
        return jsonify({
            "available_count": available_count,
            "drawn_numbers_list": drawn_numbers_list
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- (D) (*** 最關鍵 API ***)：執行抽獎 ---
@bp.route('/api/draw', methods=['POST'])
def api_draw():
    data = request.get_json()
    
    # (*** 3. 傳入的參數是 tail_number ***)
    tail_number = data.get('tail_number')
    
    if tail_number is None or not (0 <= tail_number <= 9):
        return jsonify({"success": False, "message": "無效的尾號"}), 400

    # (*** 啟動資料庫交易 ***)
    try:
        # 1. 檢查這個尾號是否已被抽過
        is_drawn = DrawnTailNumber.query.filter_by(tail_number=tail_number).first()
        if is_drawn:
            return jsonify({"success": False, "message": f"尾號 {tail_number} 已經被抽過了！"}), 400

        # 2. 找出抽獎池中，所有符合「尾號」的人
        # (注意：我們用字串的 .endswith() 來比對)
        str_tail_number = str(tail_number)
        
        pool = CheckinList.query.filter(
            CheckinList.status == 'CheckedIn',
            CheckinList.has_won == False,
            CheckinList.lottery_number.endswith(str_tail_number)
        ).all()
        
        # 3. 檢查中獎人數
        if not pool:
            # (沒有人中獎，但也算抽過了)
            message = f"尾號 {tail_number} 沒有人中獎。"
            winners_list_info = []
        else:
            # (有人中獎)
            message = f"恭喜尾號 {tail_number} 的中獎者！"
            winners_list_info = []

            # 4. (*** 核心 ***) 標記所有人為「已中獎」
            for person in pool:
                person.has_won = True
                winners_list_info.append({
                    "name": person.name,
                    "employee_id": person.employee_id,
                    "lottery_number": person.lottery_number
                })
        
        # 5. (*** 核心 ***) 記錄這個尾號已被抽出
        new_drawn_number = DrawnTailNumber(
            tail_number=tail_number,
            timestamp=datetime.now()
        )
        db.session.add(new_drawn_number)
        
        # 6. (*** 核心 ***) 提交交易
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": message,
            "tail_number": tail_number,
            "winners": winners_list_info
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"伺服器發生嚴重錯誤：{e}"}), 500