from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models import CheckinList, DrawnTailNumber, CancellationLog
from datetime import datetime

bp = Blueprint('checkin', __name__)

@bp.route('/')
def self_checkin_page():
    return render_template('checkin/self_checkin.html')

@bp.route('/dashboard')
def dashboard():
    return render_template('checkin/dashboard.html')

@bp.route('/api/status_list')
def api_status_list():
    try:
        # 1. 撈取資料
        checkin_list = CheckinList.query.all()
        total_count = CheckinList.query.count()
        checked_in_count = CheckinList.query.filter_by(status='CheckedIn').count()
        
        # 撈取所有開獎紀錄 (用於比對)
        all_draws = DrawnTailNumber.query.all()
        
        # 分類開獎紀錄 (提升比對效能)
        # 確保資料庫已有 prize_type 欄位，若無則視為舊資料歸類為 tail
        tail_draws = [d for d in all_draws if getattr(d, 'prize_type', 'tail') == 'tail']
        public_draws = [d for d in all_draws if getattr(d, 'prize_type', 'tail') == 'public']

        output_list = []
        
        for person in checkin_list:
            tail_prize_str = ""
            public_prize_str = ""
            
            # (A) 處理尾數獎 (只顯示位數最多的那一個)
            if person.has_won:
                user_num = str(person.lottery_number).zfill(3) if person.lottery_number else "000"
                matched_draws = []
                
                for draw in tail_draws:
                    tail = str(draw.tail_number)
                    if user_num.endswith(tail):
                        matched_draws.append(draw)
                
                if matched_draws:
                    # (*** 核心邏輯：依照尾數長度由大到小排序 ***)
                    # 例如同時中 5 (1碼) 和 15 (2碼)，排序後 15 會在前面
                    matched_draws.sort(key=lambda x: len(str(x.tail_number)), reverse=True)
                    
                    # 只取第一個 (最佳獎項)
                    best_match = matched_draws[0]
                    tail_prize_str = f"{best_match.prize_name} (尾:{best_match.tail_number})"
                else:
                    # 狀態是 has_won 但找不到對應號碼 (可能是手動修改或資料不同步)
                    tail_prize_str = "尾數中獎"

            # (B) 處理公獎 (獨立顯示)
            if person.has_won_public:
                user_num = str(person.lottery_number).zfill(3) if person.lottery_number else "000"
                # 找出這個人中的公獎名稱
                p_names = []
                for draw in public_draws:
                    # 公獎通常是對全碼
                    if str(draw.tail_number).zfill(3) == user_num:
                        p_names.append(draw.prize_name)
                
                if p_names:
                    public_prize_str = " | ".join(p_names)
                else:
                    public_prize_str = "公獎"

            output_list.append({
                "id": person.id,
                "name": person.name,
                "employee_id": person.employee_id,
                "lottery_number": person.lottery_number,
                "site": person.site,
                "dept_code": person.dept_code,
                "status": person.status,
                "check_in_time": person.check_in_time.strftime('%H:%M:%S') if person.status == 'CheckedIn' else '',
                
                # 回傳分開的獎項資訊
                "tail_prize_info": tail_prize_str,
                "public_prize_info": public_prize_str,
                # 為了相容舊篩選邏輯，也可以保留一個合併的欄位 (選用)
                "prize_info": f"{tail_prize_str} {public_prize_str}".strip(),

                "has_won": person.has_won,
                "has_won_public": person.has_won_public,
                "prize_claimed": person.prize_claimed,
                "public_prize_claimed": person.public_prize_claimed
            })
            
        return jsonify({
            "success": True, 
            "checkin_list": output_list,
            "total_count": total_count,
            "checked_in_count": checked_in_count
        })
        
    except Exception as e:
        print(f"API Error: {e}") # 印出錯誤到後台終端機，方便除錯
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route('/api/submit', methods=['POST'])
def api_checkin_by_id():
    data = request.get_json()
    employee_id = data.get('employee_id', '').strip().upper()

    if not employee_id:
        return jsonify({"success": False, "message": "請輸入工號", "status": "warning"}), 400

    person = CheckinList.query.filter_by(employee_id=employee_id).first()

    if not person:
        return jsonify({"success": False, "message": f"工號 [ {employee_id} ] 不在名單中。請洽詢工作人員。", "status": "danger"})

    if person.status == 'CheckedIn':
        # (這裡也可以順便加上編號，方便重複刷的人查詢)
        lottery_msg = f"<br>您的抽獎編號：<b>{person.lottery_number}</b>" if person.lottery_number else ""
        return jsonify({
            "success": False, 
            "message": f"{person.name} ({person.employee_id}) 您已於 {person.check_in_time.strftime('%H:%M:%S')} 報到，無須重複。{lottery_msg}", 
            "status": "warning"
        })
    
    try:
        person.status = 'CheckedIn'
        person.check_in_time = datetime.now()
        db.session.commit()
        
        # (*** 修改這裡：加入抽獎編號 ***)
        # 如果有抽獎編號才顯示，並加粗顯示
        lottery_msg = f"<br>您的抽獎編號：<b>{person.lottery_number}</b>" if person.lottery_number else ""
        
        return jsonify({
            "success": True, 
            "message": f"歡迎！{person.name} ({person.employee_id}) 報到成功！{lottery_msg}", 
            "status": "success"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"伺服器錯誤：{e}。請洽詢工作人員。", "status": "danger"})

@bp.route('/api/admin_checkin', methods=['POST'])
def api_admin_checkin():
    try:
        data = request.get_json()
        person_id = data.get('id')
        if not person_id: return jsonify({"success": False, "message": "缺少 ID"}), 400
        person = CheckinList.query.get(person_id)
        if not person: return jsonify({"success": False, "message": "找不到此人員"}), 404
        if person.status == 'CheckedIn': return jsonify({"success": False, "message": "此人已經報到過了"}), 400
        
        person.status = 'CheckedIn'
        person.check_in_time = datetime.now()
        db.session.commit()
        return jsonify({"success": True, "message": f"已成功為 {person.name} 完成報到"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

# --- (修改功能) 取消報到 API ---
@bp.route('/api/admin_cancel_checkin', methods=['POST'])
def api_admin_cancel_checkin():
    try:
        data = request.get_json()
        person_id = data.get('id')
        canceller_id = data.get('canceller_id') # <--- 新增：取得操作者工號

        if not person_id: 
            return jsonify({"success": False, "message": "缺少 ID"}), 400
        
        # 檢查是否有輸入操作者工號
        if not canceller_id:
            return jsonify({"success": False, "message": "請輸入操作人員工號以進行確認"}), 400
        
        person = CheckinList.query.get(person_id)
        if not person: 
            return jsonify({"success": False, "message": "找不到此人員"}), 404
        
        if person.status == 'Registered':
            return jsonify({"success": False, "message": "此人本來就尚未報到"}), 400
            
        # --- 新增紀錄寫入邏輯 ---
        new_log = CancellationLog(
            checkin_list_id=person.id,
            cancelled_by=canceller_id,
            timestamp=datetime.now()
        )
        db.session.add(new_log)
        # ---------------------

        # 執行取消報到
        person.status = 'Registered'
        person.check_in_time = None
        
        db.session.commit()
        return jsonify({"success": True, "message": f"已取消 {person.name} 的報到狀態 (操作者: {canceller_id})"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

# 2. (新增) 切換領獎狀態 API (請加在檔案後方)
@bp.route('/api/toggle_claim', methods=['POST'])
def api_toggle_claim():
    try:
        data = request.get_json()
        person_id = data.get('id')
        prize_type = data.get('type') # 'tail' (尾數) 或 'public' (公獎)
        
        person = CheckinList.query.get(person_id)
        if not person:
            return jsonify({"success": False, "message": "找不到人員"}), 404

        current_status = False
        
        if prize_type == 'tail':
            # 檢查是否真的有中獎，沒中獎不能領
            if not person.has_won:
                return jsonify({"success": False, "message": "該員尚未獲得尾數獎，無法領取"}), 400
            
            person.prize_claimed = not person.prize_claimed # 切換狀態
            current_status = person.prize_claimed
            
        elif prize_type == 'public':
            if not person.has_won_public:
                return jsonify({"success": False, "message": "該員尚未獲得公獎，無法領取"}), 400
            
            person.public_prize_claimed = not person.public_prize_claimed # 切換狀態
            current_status = person.public_prize_claimed
        
        else:
            return jsonify({"success": False, "message": "錯誤的獎項類型"}), 400

        db.session.commit()
        
        status_text = "已領取" if current_status else "未領取"
        return jsonify({"success": True, "message": f"更新成功：狀態為 {status_text}", "new_status": current_status})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500