from flask import Blueprint, render_template, request, jsonify
from app import db
# (*** 新增匯入 DrawnTailNumber 以查詢獎項名稱 ***)
from app.models import CheckinList, DrawnTailNumber
from datetime import datetime

bp = Blueprint('checkin', __name__)

@bp.route('/')
def self_checkin_page():
    return render_template('checkin/self_checkin.html')

@bp.route('/dashboard')
def dashboard():
    return render_template('checkin/dashboard.html')

# --- (核心修改) 提供全名單狀態的 API ---
@bp.route('/api/status_list')
def api_status_list():
    try:
        # 1. 查詢所有名單
        all_people = CheckinList.query.order_by(CheckinList.name).all()
        
        # 2. (*** 新增 ***) 預先抓取所有已抽出的尾號與獎項名稱，做成對照表
        # 格式: { '7': '特獎', '3': '二獎' }
        drawn_records = DrawnTailNumber.query.all()
        prize_map = {str(d.tail_number): d.prize_name for d in drawn_records}
        
        checked_in_count = 0
        output_list = []
        
        for person in all_people:
            if person.status == 'CheckedIn':
                checked_in_count += 1
            
            # (*** 新增 ***) 判斷獎項資訊
            prize_info = ""
            if person.has_won and person.lottery_number:
                # 取抽獎編號的最後一碼
                tail = person.lottery_number.strip()[-1]
                # 從對照表找獎項名稱
                prize_info = prize_map.get(tail, "已中獎")

            output_list.append({
                "id": person.id,
                "name": person.name,
                "employee_id": person.employee_id,
                "status": person.status,
                "check_in_time": person.check_in_time.strftime('%H:%M:%S') if person.status == 'CheckedIn' else '',
                "prize_info": prize_info # (*** 新增欄位 ***)
            })

        return jsonify({
            "success": True,
            "checked_in_count": checked_in_count,
            "total_count": len(all_people),
            "checkin_list": output_list
        })
        
    except Exception as e:
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
        return jsonify({"success": False, "message": f"{person.name} ({person.employee_id}) 您已於 {person.check_in_time.strftime('%H:%M:%S')} 報到，無須重複。", "status": "warning"})
    
    try:
        person.status = 'CheckedIn'
        person.check_in_time = datetime.now()
        db.session.commit()
        return jsonify({"success": True, "message": f"歡迎！{person.name} ({person.employee_id}) 報到成功！", "status": "success"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"伺服器錯誤：{e}。請洽詢工作人員。", "status": "danger"})

@bp.route('/api/admin_checkin', methods=['POST'])
def api_admin_checkin():
    try:
        data = request.get_json()
        person_id = data.get('id')
        
        if not person_id:
            return jsonify({"success": False, "message": "缺少 ID"}), 400
            
        person = CheckinList.query.get(person_id)
        
        if not person:
            return jsonify({"success": False, "message": "找不到此人員"}), 404
            
        if person.status == 'CheckedIn':
            return jsonify({"success": False, "message": "此人已經報到過了"}), 400
            
        person.status = 'CheckedIn'
        person.check_in_time = datetime.now()
        db.session.commit()
        
        return jsonify({"success": True, "message": f"已成功為 {person.name} 完成報到"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500