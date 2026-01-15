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
        all_people = CheckinList.query.order_by(CheckinList.name).all()
        drawn_records = DrawnTailNumber.query.all()
        prize_map = {str(d.tail_number): d.prize_name for d in drawn_records}
        
        checked_in_count = 0
        output_list = []
        
        for person in all_people:
            if person.status == 'CheckedIn':
                checked_in_count += 1
            
            prize_info = ""
            if person.has_won and person.lottery_number:
                tail = person.lottery_number.strip()[-1]
                prize_info = prize_map.get(tail, "已中獎")

            output_list.append({
                "id": person.id,
                "name": person.name,
                "employee_id": person.employee_id,
                "lottery_number": person.lottery_number,
                "site": person.site,
                "dept_code": person.dept_code,
                "status": person.status,
                "check_in_time": person.check_in_time.strftime('%H:%M:%S') if person.status == 'CheckedIn' else '',
                "prize_info": prize_info
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
