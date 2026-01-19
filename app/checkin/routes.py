from flask import Blueprint, render_template, request, jsonify, url_for
from app import db
from app.models import CheckinList, DrawnTailNumber, CancellationLog
from datetime import datetime

bp = Blueprint('checkin', __name__)

@bp.route('/')
def index():
    return render_template('checkin/self_checkin.html')

@bp.route('/dashboard')
def dashboard():
    return render_template('checkin/dashboard.html')

@bp.route('/api/submit', methods=['POST'])
def api_submit():
    data = request.get_json()
    input_id = data.get('input_id')
    
    if not input_id:
        return jsonify({"success": False, "message": "請輸入工號", "status": "danger"})
    
    person = CheckinList.query.filter_by(employee_id=input_id).first()
    
    if not person:
        return jsonify({"success": False, "message": "找不到此工號，請確認後再試。", "status": "danger"})
    
    if person.status == 'CheckedIn':
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
        
        lottery_msg = f"<br>您的抽獎編號：<b>{person.lottery_number}</b>" if person.lottery_number else ""
        
        return jsonify({
            "success": True, 
            "message": f"歡迎！{person.name} ({person.employee_id}) 報到成功！{lottery_msg}", 
            "status": "success"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"伺服器錯誤：{e}。請洽詢工作人員。", "status": "danger"})

@bp.route('/api/status_list')
def api_status_list():
    try:
        # 1. 撈取資料
        checkin_list = CheckinList.query.all()
        total_count = CheckinList.query.count()
        checked_in_count = CheckinList.query.filter_by(status='CheckedIn').count()
        
        # 撈取所有開獎紀錄
        all_draws = DrawnTailNumber.query.all()
        
        # 分類開獎紀錄 (*** 重要修正：將 None 視為 'tail' 以相容舊資料 ***)
        tail_draws = [d for d in all_draws if (d.prize_type or 'tail') == 'tail']
        public_draws = [d for d in all_draws if (d.prize_type or 'tail') == 'public']

        output_list = []
        
        for person in checkin_list:
            tail_prize_str = ""
            public_prize_str = ""
            
            # (A) 處理尾數獎
            if person.has_won:
                user_num = str(person.lottery_number).zfill(3) if person.lottery_number else "000"
                matched_draws = []
                
                for draw in tail_draws:
                    tail = str(draw.tail_number)
                    if user_num.endswith(tail):
                        matched_draws.append(draw)
                
                if matched_draws:
                    # 排序：取最長的那一個 (例如同時中 5 和 15，取 15)
                    matched_draws.sort(key=lambda x: len(str(x.tail_number)), reverse=True)
                    best_match = matched_draws[0]
                    
                    # (*** 格式化顯示 ***) Ex. A 尾數獎 中2位(15)
                    digit_len = len(str(best_match.tail_number))
                    tail_prize_str = f"{best_match.prize_name} 尾數獎 中{digit_len}位({best_match.tail_number})"
                else:
                    # 如果 has_won=True 但找不到對應號碼，顯示預設訊息
                    tail_prize_str = "尾數中獎(未知)"

            # (B) 處理公獎
            if person.has_won_public:
                user_num = str(person.lottery_number).zfill(3) if person.lottery_number else "000"
                p_names = []
                for draw in public_draws:
                    # 公獎通常是對全碼
                    if str(draw.tail_number).zfill(3) == user_num:
                        # (*** 格式化顯示 ***) Ex. iphone(123)
                        p_names.append(f"{draw.prize_name}({user_num})")
                
                if p_names:
                    public_prize_str = " | ".join(p_names)
                else:
                    public_prize_str = f"公獎({user_num})"

            output_list.append({
                "id": person.id,
                "name": person.name,
                "employee_id": person.employee_id,
                "lottery_number": person.lottery_number,
                "site": person.site,
                "dept_code": person.dept_code,
                "status": person.status,
                "check_in_time": person.check_in_time.strftime('%H:%M:%S') if person.status == 'CheckedIn' else '',
                
                "tail_prize_info": tail_prize_str,
                "public_prize_info": public_prize_str,
                "prize_info": f"{tail_prize_str} {public_prize_str}".strip(), # 搜尋用的合併欄位

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
        print(f"API Error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route('/api/admin_checkin', methods=['POST'])
def api_admin_checkin():
    try:
        data = request.get_json()
        target_id = data.get('id')
        person = CheckinList.query.get(target_id)
        
        if not person:
            return jsonify({"success": False, "message": "找不到人員"}), 404
            
        person.status = 'CheckedIn'
        person.check_in_time = datetime.now()
        db.session.commit()
        
        return jsonify({"success": True, "message": f"{person.name} 簽到成功"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route('/api/admin_cancel_checkin', methods=['POST'])
def api_admin_cancel_checkin():
    try:
        data = request.get_json()
        target_id = data.get('id')
        canceller_id = data.get('canceller_id')
        
        if not canceller_id:
            return jsonify({"success": False, "message": "未輸入操作者工號"}), 400

        person = CheckinList.query.get(target_id)
        if not person:
            return jsonify({"success": False, "message": "找不到人員"}), 404
            
        if person.status != 'CheckedIn':
            return jsonify({"success": False, "message": "該員尚未報到，無法取消"}), 400

        # 記錄 Log
        log = CancellationLog(
            checkin_list_id=person.id,
            cancelled_by=canceller_id,
            timestamp=datetime.now()
        )
        db.session.add(log)

        # 執行取消
        person.status = 'Registered'
        person.check_in_time = None
        db.session.commit()
        
        return jsonify({"success": True, "message": f"已取消 {person.name} 的報到狀態"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route('/api/toggle_claim', methods=['POST'])
def api_toggle_claim():
    try:
        data = request.get_json()
        person_id = data.get('id')
        prize_type = data.get('type') # 'tail' or 'public'
        
        person = CheckinList.query.get(person_id)
        if not person:
            return jsonify({"success": False, "message": "找不到人員"}), 404

        current_status = False
        
        if prize_type == 'tail':
            if not person.has_won:
                return jsonify({"success": False, "message": "該員尚未獲得尾數獎"}), 400
            person.prize_claimed = not person.prize_claimed
            current_status = person.prize_claimed
            
        elif prize_type == 'public':
            if not person.has_won_public:
                return jsonify({"success": False, "message": "該員尚未獲得公獎"}), 400
            person.public_prize_claimed = not person.public_prize_claimed
            current_status = person.public_prize_claimed
        
        else:
            return jsonify({"success": False, "message": "錯誤的類型"}), 400

        db.session.commit()
        
        status_text = "已領取" if current_status else "未領取"
        return jsonify({"success": True, "message": f"更新成功：{status_text}"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500