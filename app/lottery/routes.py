from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models import CheckinList, DrawnTailNumber, Prize
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
            "prize_name": prize_name,
            "is_business_trip": w.is_business_trip  # (*** 新增此行 ***)
        })

    return render_template('lottery/winners.html', 
                        drawn_numbers=drawn_numbers, 
                        winners_data=winners_data)

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
        # (*** 修改檢查邏輯 ***)
        # 只檢查「同為尾數獎 (prize_type='tail')」是否重複
        is_drawn = DrawnTailNumber.query.filter_by(
            tail_number=suffix, 
            prize_type='tail'
        ).first()
        
        if is_drawn:
            return jsonify({"success": False, "message": f"號碼 {suffix} 已經被抽過了 ({is_drawn.prize_name})！"}), 400

        # 2. 篩選中獎者邏輯 (*** 修改：改用 Python 邏輯補零篩選，以支援 1 匹配 01 的情況 ***)
        
        # A. 根據模式先撈出候選人池
        if is_addon:
            # 【加碼抽出模式】針對「已經中獎」的人進行篩選
            candidates = CheckinList.query.filter(
                CheckinList.status == 'CheckedIn',
                CheckinList.has_won == True
            ).all()
            message = f"【加碼】號碼 {suffix} 的幸運得主！"
        else:
            # 【一般抽出模式】針對「尚未中獎」的人進行篩選
            candidates = CheckinList.query.filter(
                CheckinList.status == 'CheckedIn',
                CheckinList.has_won == False
            ).all()
            message = f"恭喜！號碼 {suffix} 的中獎者！"

        # B. 進行補零比對 (Ex. suffix='01', user='1' -> '001' -> Match)
        pool = []
        for person in candidates:
            if person.lottery_number:
                # 強制轉為 3 位數字串 (e.g. "1" -> "001")
                normalized_num = str(person.lottery_number).zfill(3)
                if normalized_num.endswith(suffix):
                    pool.append(person)

        winners_list_info = []
        if not pool:
            message = f"號碼 {suffix} 沒有人符合資格。"
        else:
            for person in pool:
                # 一般模式才需要標記為已中獎
                # 加碼模式下，他們本來就是 True，不需改變
                if not is_addon:
                    person.has_won = True
                
                winners_list_info.append({
                    "name": person.name,
                    "employee_id": person.employee_id,
                    "lottery_number": person.lottery_number,
                    "site": person.site,  # 用於前端分流
                    "is_business_trip": person.is_business_trip  # (*** 新增此行 ***)
                })
        
        # 3. 寫入紀錄
        # (*** 修改寫入邏輯 ***)
        new_drawn_number = DrawnTailNumber(
            tail_number=suffix,
            prize_name=prize_name,
            timestamp=datetime.now(),
            is_addon=is_addon,
            prize_type='tail' # 明確標記為尾數獎
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
                "site": p.site,
                "is_business_trip": p.is_business_trip  # (*** 新增此行 ***)
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
        # 1. 先從資料庫找出這個人
        person = CheckinList.query.filter_by(employee_id=employee_id).first()
        if not person:
            return jsonify({"success": False, "message": "找不到此人"}), 404

        # 2. 檢查是否已經中過
        if person.has_won_public:
            return jsonify({"success": False, "message": "此人已中過公獎"}), 400

        # 3. 更新狀態 (必須在找到 person 之後)
        person.has_won_public = True
        
        # 4. 寫入紀錄，標記為 'public'
        # 注意：這裡使用 person.lottery_number，確保它是 3 位數字串
        lottery_num = str(person.lottery_number).zfill(3) if person.lottery_number else "000"

        new_record = DrawnTailNumber(
            tail_number=lottery_num, 
            prize_name=prize_name,
            timestamp=datetime.now(),
            is_addon=False,
            prize_type='public' # 明確標記為公獎
        )
        db.session.add(new_record)
        db.session.commit()

        return jsonify({"success": True, "message": f"恭喜 {person.name} 獲得 {prize_name}！"})

    except Exception as e:
        db.session.rollback()
        print(f"Error in api_public_confirm: {e}") 
        return jsonify({"success": False, "message": f"系統錯誤: {str(e)}"}), 500

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

# --- (新增) 輪播中獎名單 API ---
@bp.route('/api/winners_all', methods=['GET'])
def api_winners_all():
    """
    撈取所有已開出的獎項與對應的中獎人，用於輪播展示
    """
    try:
        # 1. 撈出所有開獎紀錄 (最新的在前面)
        draws = DrawnTailNumber.query.order_by(DrawnTailNumber.timestamp.desc()).all()
        
        results = []
        
        for draw in draws:
            # 2. 針對每一個開獎紀錄，找出符合的人
            # 注意：這裡要區分一下邏輯
            # 如果是公獎 (通常 tail_number 是完整 3 碼)，邏輯是全符合
            # 如果是尾數獎，邏輯是 endswith
            
            # 統一邏輯：
            # 先撈出所有已報到的人
            # 再用 Python 過濾 (為了處理 '5' vs '005' 的補零問題)
            
            suffix = str(draw.tail_number) # 開出的號碼
            prize_name = draw.prize_name
            
            # 撈取候選人 (只撈 has_won 或 has_won_public 為 True 的人，提升效能)
            # 也可以直接撈全部 status='CheckedIn' 的人來比對
            candidates = CheckinList.query.filter_by(status='CheckedIn').all()
            
            for p in candidates:
                if not p.lottery_number:
                    continue
                
                user_num = str(p.lottery_number).zfill(3) # 補零
                
                # 比對邏輯
                is_match = False
                
                # 如果開出號碼長度 >= 3 (或是公獎)，通常是精確比對
                # 但為了相容尾數邏輯，我們統一用 endswith
                # 唯一的例外是：如果 suffix 是 '05'，user_num 是 '005' -> endswith 成立
                
                if user_num.endswith(suffix):
                    # 還有一個條件：這個人必須真的有被標記中獎
                    # 避免 "尾數獎" 開了 5，結果 "公獎" 得主 (號碼也是 5) 被誤列
                    # 但通常公獎得主 has_won_public=True, 尾數 has_won=True
                    
                    # 這裡為了展示方便，只要號碼符合且該獎項存在，我們就列出來
                    # 為了更精準，我們可以檢查：
                    # 如果 draw.is_addon (加碼/尾數) -> 檢查 p.has_won
                    # 如果 draw.prize_name == '公獎' -> 檢查 p.has_won_public
                    
                    # (簡化版邏輯：只要號碼對上就顯示，適合輪播)
                    results.append({
                        "prize_name": prize_name,
                        "tail_number": suffix,
                        "name": p.name,
                        "employee_id": p.employee_id,
                        "lottery_number": user_num,
                        "site": p.site,
                        "timestamp": draw.timestamp.strftime('%H:%M'),
                        "is_business_trip": p.is_business_trip # (*** 新增此行 ***)
                    })

        return jsonify({"success": True, "data": results})
        
    except Exception as e:
        print(e)
        return jsonify({"success": False, "data": []}), 500

# --- (新增) 輪播頁面路由 ---
@bp.route('/winners_carousel')
def winners_carousel():
    return render_template('lottery/winners_carousel.html')


# (*** 修改：取得獎項清單 API ***)
# 加入 prize_type 的過濾，避免 "公獎" 和 "尾數獎" 若剛好同名會算錯數量
# (*** 修改：取得獎項清單 API (支援過濾類型) ***)
@bp.route('/api/prizes', methods=['GET'])
def api_get_prizes():
    """取得獎項清單 API"""
    p_type = request.args.get('type', 'tail') # 預設 tail, 公獎前端會傳 public
    
    # 1. 取出該類型的獎項設定
    prizes_config = Prize.query.filter_by(prize_type=p_type)\
                        .order_by(Prize.display_order)\
                        .all()
    
    available_prizes = []
    
    for p in prizes_config:
        # 2. 計算已抽出的次數 (加入 prize_type 確保精確)
        drawn_count = DrawnTailNumber.query.filter_by(
            prize_name=p.name, 
            prize_type=p_type 
        ).count()
        
        remaining = p.quantity - drawn_count
        
        available_prizes.append({
            "id": p.id,
            "name": p.name,
            "quantity": p.quantity,
            "remaining": remaining
        })
    
    return jsonify({"success": True, "prizes": available_prizes})

# (*** 新增：查詢特定獎項的中獎資訊 API ***)
@bp.route('/api/query_prize', methods=['POST'])
def api_query_prize():
    data = request.get_json()
    prize_name = data.get('prize_name')

    if not prize_name:
        return jsonify({"success": False, "message": "Missing prize name"}), 400

    # 1. 搜尋該獎項的所有開獎紀錄 (依時間倒序，最新的在前面)
    draws = DrawnTailNumber.query.filter_by(prize_name=prize_name).order_by(DrawnTailNumber.timestamp.desc()).all()

    if not draws:
        # 該獎項還沒抽過
        return jsonify({"success": True, "drawn": False})

    # 2. 收集該獎項開出的號碼 (用於回填前端輸入框)
    tail_numbers = [str(d.tail_number) for d in draws]
    
    # 3. 找出符合這些號碼且已中獎的人
    # 邏輯：找出「已報到」且「已中獎 (has_won=True)」的人
    candidates = CheckinList.query.filter(
        CheckinList.status == 'CheckedIn',
        CheckinList.has_won == True
    ).all()

    winners_data = []
    
    for p in candidates:
        if not p.lottery_number:
            continue
            
        user_num = str(p.lottery_number).zfill(3) # 補零以利比對
        
        # 4. 判斷此人是否屬於這個獎項
        matched_draws = []
        for d in draws:
            # 比對尾號 (例如 draw='5', user='005' -> match)
            if user_num.endswith(str(d.tail_number)):
                matched_draws.append(d)
        
        if matched_draws:
            # 如果一個人同時符合多個 (極少見)，取「號碼最長」或「最新」的那個來決定屬性
            # 這裡我們取「號碼最長」的 (例如同時中 5 和 15，視為中 15)
            matched_draws.sort(key=lambda x: len(str(x.tail_number)), reverse=True)
            best_match = matched_draws[0]
            
            winners_data.append({
                "name": p.name,
                "employee_id": p.employee_id,
                "lottery_number": p.lottery_number,
                "site": p.site,
                "is_addon": best_match.is_addon,  # (關鍵) 將加碼狀態回傳給前端
                "is_business_trip": p.is_business_trip  # (*** 新增此行 ***)   
            })

    return jsonify({
        "success": True, 
        "drawn": True,
        "tail_numbers": tail_numbers, 
        "winners": winners_data
    })