from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models import CheckinList, DrawnTailNumber
from datetime import datetime

bp = Blueprint('lottery', __name__)

@bp.route('/screen')
def lottery_screen():
    return render_template('lottery/screen.html')

@bp.route('/winners')
def winners_list():
    # 1. 取得所有中獎人
    all_winners = CheckinList.query.filter_by(has_won=True).order_by(CheckinList.employee_id).all()
    
    # 2. 取得已抽尾號紀錄
    drawn_numbers = DrawnTailNumber.query.order_by(DrawnTailNumber.timestamp.desc()).all()
    prize_map = {str(d.tail_number): d.prize_name for d in drawn_numbers}
    
    # 3. 準備 JSON 資料給前端
    winners_data = []
    for w in all_winners:
        tail = w.lottery_number.strip()[-1] if w.lottery_number else ""
        prize_name = prize_map.get(tail, "未知獎項")
        
        winners_data.append({
            "name": w.name,
            "employee_id": w.employee_id,
            "lottery_number": w.lottery_number,
            "prize_name": prize_name
        })

    return render_template('lottery/winners.html', 
                           drawn_numbers=drawn_numbers, 
                           winners_data=winners_data) # 這裡必須傳遞 winners_data

# (API 部分保持不變)
@bp.route('/api/get_data')
def api_get_data():
    # ... (保持原樣) ...
    try:
        available_count = CheckinList.query.filter_by(status='CheckedIn', has_won=False).count()
        drawn_numbers_obj = DrawnTailNumber.query.all()
        drawn_numbers_list = [d.tail_number for d in drawn_numbers_obj]
        return jsonify({"available_count": available_count, "drawn_numbers_list": drawn_numbers_list})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/api/draw', methods=['POST'])
def api_draw():
    data = request.get_json()
    # (*** 修改：接收 suffix (字串) 而不是 tail_number (整數) ***)
    suffix = data.get('suffix', '').strip() 
    prize_name = data.get('prize_name', '神秘獎項')

    if not suffix:
        return jsonify({"success": False, "message": "請輸入號碼"}), 400
    
    # 檢查是否為數字 (雖然是字串處理，但內容要是數字)
    if not suffix.isdigit():
        return jsonify({"success": False, "message": "號碼必須為數字"}), 400

    try:
        # 檢查是否抽過 (直接比對字串)
        is_drawn = DrawnTailNumber.query.filter_by(tail_number=suffix).first()
        if is_drawn:
            return jsonify({"success": False, "message": f"號碼 {suffix} 已經被抽過了 ({is_drawn.prize_name})！"}), 400

        # (*** 核心邏輯：比對字串結尾 ***)
        # 不管是 1 碼 (5), 2 碼 (35), 3 碼 (135) 都可以通用 endswith
        pool = CheckinList.query.filter(
            CheckinList.status == 'CheckedIn',
            CheckinList.has_won == False,
            CheckinList.lottery_number.endswith(suffix)
        ).all()
        
        # 判斷是否為加碼 (長度 > 1 視為加碼)
        is_addon = len(suffix) > 1

        if not pool:
            message = f"號碼 {suffix} 沒有人中獎。"
            winners_list_info = []
        else:
            message = f"恭喜！號碼 {suffix} 的中獎者！"
            winners_list_info = []
            for person in pool:
                person.has_won = True
                winners_list_info.append({
                    "name": person.name,
                    "employee_id": person.employee_id,
                    "lottery_number": person.lottery_number,
                    # (*** 新增：回傳 site 讓前端分流 ***)
                    "site": person.site
                })
        
        new_drawn_number = DrawnTailNumber(
            tail_number=suffix,
            prize_name=prize_name,
            timestamp=datetime.now(),
            is_addon=is_addon # 寫入資料庫
        )
        db.session.add(new_drawn_number)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": message,
            "prize_name": prize_name,
            "tail_number": suffix, # 回傳字串
            "is_addon": is_addon,  # 回傳是否加碼
            "winners": winners_list_info
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"伺服器錯誤：{e}"}), 500