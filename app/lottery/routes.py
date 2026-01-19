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
    suffix = data.get('suffix', '').strip()
    prize_name = data.get('prize_name', '神秘獎項')
    # (*** 新增：接收 is_addon 參數，預設為 False ***)
    is_addon = data.get('is_addon', False)

    if not suffix:
        return jsonify({"success": False, "message": "請輸入號碼"}), 400
    
    if not suffix.isdigit():
        return jsonify({"success": False, "message": "號碼必須為數字"}), 400

    try:
        # 1. 檢查這個號碼是否重複被抽過 (包含一般或加碼都不能重複)
        #    例如已抽過 "19"，就不能再抽 "19"
        is_drawn = DrawnTailNumber.query.filter_by(tail_number=suffix).first()
        if is_drawn:
            return jsonify({"success": False, "message": f"號碼 {suffix} 已經被抽過了 ({is_drawn.prize_name})！"}), 400

        # 2. 篩選中獎者邏輯
        base_query = CheckinList.query.filter(
            CheckinList.status == 'CheckedIn',
            CheckinList.lottery_number.endswith(suffix)
        )

        if is_addon:
            # 【加碼抽出模式】
            # 針對「已經中獎」的人進行篩選 (has_won=True)
            # 例如：第一階段抽 "9" (已中獎)，第二階段抽 "19" (從中獎者中找 19)
            pool = base_query.filter(CheckinList.has_won == True).all()
            message = f"【加碼】號碼 {suffix} 的幸運得主！"
        else:
            # 【一般抽出模式】
            # 針對「尚未中獎」的人進行篩選 (has_won=False)
            pool = base_query.filter(CheckinList.has_won == False).all()
            message = f"恭喜！號碼 {suffix} 的中獎者！"

        winners_list_info = []
        if not pool:
            message = f"號碼 {suffix} 沒有人符合資格。"
        else:
            for person in pool:
                # 一般模式才需要標記為已中獎
                # 加碼模式下，他們本來就是 True，不需改變，但為了保險起見設為 True 也無妨
                if not is_addon:
                    person.has_won = True
                
                winners_list_info.append({
                    "name": person.name,
                    "employee_id": person.employee_id,
                    "lottery_number": person.lottery_number,
                    "site": person.site  # 用於前端分流
                })
        
        # 3. 寫入紀錄 (不論有沒有人中獎，號碼都要記錄，避免重複抽)
        #    但如果沒人中獎是否要記錄？通常是要記錄「已使用過此號碼」。
        #    若希望沒人中就不記錄，可將下面移到 if pool: 內。這裡維持記錄。
        new_drawn_number = DrawnTailNumber(
            tail_number=suffix,
            prize_name=prize_name,
            timestamp=datetime.now(),
            is_addon=is_addon # 記錄這是否為加碼獎
        )
        db.session.add(new_drawn_number)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": message,
            "prize_name": prize_name,
            "tail_number": suffix,
            "is_addon": is_addon,
            "winners": winners_list_info
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"伺服器錯誤：{e}"}), 500