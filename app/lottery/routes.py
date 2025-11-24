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
    # ... (保持原樣) ...
    data = request.get_json()
    tail_number = data.get('tail_number')
    prize_name = data.get('prize_name', '神秘獎項')

    if tail_number is None:
        return jsonify({"success": False, "message": "請輸入尾號"}), 400
        
    try:
        tail_number = int(tail_number)
        if not (0 <= tail_number <= 9):
            raise ValueError
    except ValueError:
        return jsonify({"success": False, "message": "尾號必須是 0-9 的數字"}), 400

    try:
        is_drawn = DrawnTailNumber.query.filter_by(tail_number=tail_number).first()
        if is_drawn:
            return jsonify({"success": False, "message": f"尾號 {tail_number} 已經被抽過了 ({is_drawn.prize_name})！"}), 400

        str_tail_number = str(tail_number)
        pool = CheckinList.query.filter(
            CheckinList.status == 'CheckedIn',
            CheckinList.has_won == False,
            CheckinList.lottery_number.endswith(str_tail_number)
        ).all()
        
        if not pool:
            message = f"尾號 {tail_number} 沒有人中獎。"
            winners_list_info = []
        else:
            message = f"恭喜！尾號 {tail_number} 的中獎者！"
            winners_list_info = []
            for person in pool:
                person.has_won = True
                winners_list_info.append({
                    "name": person.name,
                    "employee_id": person.employee_id,
                    "lottery_number": person.lottery_number
                })
        
        new_drawn_number = DrawnTailNumber(
            tail_number=tail_number,
            prize_name=prize_name,
            timestamp=datetime.now()
        )
        db.session.add(new_drawn_number)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": message,
            "prize_name": prize_name,
            "tail_number": tail_number,
            "winners": winners_list_info
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"伺服器錯誤：{e}"}), 500