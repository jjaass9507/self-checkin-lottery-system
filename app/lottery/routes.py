from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models import CheckinList, DrawnTailNumber
from datetime import datetime
from sqlalchemy import or_

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
    
# --- 公獎專用 API ---

# --- 修改：公獎搜尋 API (支援 3 位數補零) ---
@bp.route('/api/public/search', methods=['POST'])
def api_public_search():
    """
    逐步搜尋符合資格的人 (邏輯修正：強制視為 3 位數)
    """
    data = request.get_json()
    digits = data.get('digits', '') # 例如 "0" (代表百位數是0)
    
    if not digits:
        return jsonify({"success": False, "message": "無輸入數字"}), 400

    # 1. 先取出所有「已報到」且「未中公獎」的人
    #    (不使用 SQL LIKE，改用 Python 過濾，以處理 "5" -> "005" 的邏輯)
    candidates_db = CheckinList.query.filter(
        CheckinList.status == 'CheckedIn',
        or_(CheckinList.has_won_public == False, CheckinList.has_won_public == None)
    ).all()

    results = []
    
    # 2. Python 端迴圈比對
    for p in candidates_db:
        # 如果欄位是空值，跳過
        if not p.lottery_number:
            continue
            
        # (*** 核心修改 ***)
        # 將資料庫的號碼轉字串後，向左補零至 3 位數
        # 例如: "5" -> "005", "15" -> "015", "123" -> "123"
        normalized_num = str(p.lottery_number).zfill(3)
        
        # 比對開頭 (startswith)
        if normalized_num.startswith(digits):
            results.append({
                "name": p.name,
                "employee_id": p.employee_id,
                "lottery_number": normalized_num, # 回傳補零後的號碼，讓前端顯示 "005"
                "site": p.site
            })

    return jsonify({
        "success": True,
        "count": len(results),
        "candidates": results
    })

@bp.route('/api/public/confirm', methods=['POST'])
def api_public_confirm():
    """
    確認公獎中獎，寫入資料庫
    """
    data = request.get_json()
    employee_id = data.get('employee_id')
    prize_name = data.get('prize_name', '公獎')

    if not employee_id:
        return jsonify({"success": False, "message": "未指定中獎者"}), 400

    try:
        person = CheckinList.query.filter_by(employee_id=employee_id).first()
        if not person:
            return jsonify({"success": False, "message": "找不到此人"}), 404

        if person.has_won_public:
            return jsonify({"success": False, "message": "此人已中過公獎"}), 400

        # 更新狀態
        person.has_won_public = True
        
        # 寫入紀錄 (DrawnTailNumber 也可以用來記公獎，只是 tail_number 存完整號碼)
        new_record = DrawnTailNumber(
            tail_number=person.lottery_number,
            prize_name=prize_name,
            timestamp=datetime.now(),
            is_addon=False # 公獎不算加碼，算獨立獎項
        )
        db.session.add(new_record)
        db.session.commit()

        return jsonify({"success": True, "message": f"恭喜 {person.name} 獲得 {prize_name}！"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

# --- (新增) 查詢可用數字 API ---
# --- 修改：查詢可用數字 API (支援 3 位數補零) ---
@bp.route('/api/public/available_digits', methods=['POST'])
def api_public_available_digits():
    """
    根據目前的 prefix (前綴)，回傳下一位有哪些數字是有效的
    (邏輯修正：強制視為 3 位數)
    """
    data = request.get_json()
    prefix = data.get('prefix', '') # 例如 "0" (已確定百位是0)
    
    # 1. 取出所有候選人
    candidates_db = CheckinList.query.filter(
        CheckinList.status == 'CheckedIn',
        or_(CheckinList.has_won_public == False, CheckinList.has_won_public == None)
    ).all()
    
    target_index = len(prefix)
    available_digits = set()
    
    # 2. Python 端迴圈比對與提取
    for p in candidates_db:
        if not p.lottery_number:
            continue
            
        # (*** 核心修改 ***)
        # 同樣補零至 3 位數
        normalized_num = str(p.lottery_number).zfill(3)
        
        # 檢查是否符合前綴
        if normalized_num.startswith(prefix):
            # 確保還有下一位數 (防止 index out of range)
            if len(normalized_num) > target_index:
                available_digits.add(normalized_num[target_index])
            
    # 轉成排序好的列表
    result_list = sorted(list(available_digits))
    
    return jsonify({
        "success": True,
        "digits": result_list
    })

# 記得註冊頁面路由
@bp.route('/public_lottery')
def public_screen():
    return render_template('lottery/public_screen.html')

