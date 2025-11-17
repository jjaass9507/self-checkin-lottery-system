from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models import CheckinList
from datetime import datetime

bp = Blueprint('checkin', __name__)

# --- (1) 自助報到機 (Kiosk) 的主頁面 ---
@bp.route('/')
def self_checkin_page():
    # 這個路由只負責顯示 self_checkin.html 頁面
    # 未來: 您的報到站平板/電腦的瀏覽器將永遠停在這個頁面
    return render_template('checkin/self_checkin.html')

# --- (2) 核心 API：處理工號報到 ---
@bp.route('/api/submit', methods=['POST'])
def api_checkin_by_id():
    data = request.get_json()
    
    # 1. 獲取工號 (並做清理，例如去除前後空格、轉大寫)
    employee_id = data.get('employee_id', '').strip().upper()

    if not employee_id:
        return jsonify({
            "success": False, 
            "message": "請輸入工號", 
            "status": "warning"
        }), 400

    # 2. 用工號 (employee_id) 找到報到者
    person = CheckinList.query.filter_by(employee_id=employee_id).first()

    # 3. 查無此人
    if not person:
        return jsonify({
            "success": False, 
            "message": f"工號 [ {employee_id} ] 不在名單中。請洽詢工作人員。", 
            "status": "danger"
        })

    # 4. 此人已報到
    if person.status == 'CheckedIn':
        return jsonify({
            "success": False, 
            "message": f"{person.name} ({person.employee_id}) 您已於 {person.check_in_time.strftime('%H:%M:%S')} 報到，無須重複。", 
            "status": "warning"
        })
    
    # 5. 成功報到
    try:
        person.status = 'CheckedIn'
        person.check_in_time = datetime.now()
        db.session.commit()
        return jsonify({
            "success": True, 
            "message": f"歡迎！{person.name} ({person.employee_id}) 報到成功！", 
            "status": "success"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False, 
            "message": f"伺服器錯誤：{e}。請洽詢工作人員。", 
            "status": "danger"
        })

# (在 app/checkin/routes.py 的最下方貼上)

# --- (1) 新增：儀表板的主網頁 ---
@bp.route('/dashboard')
def dashboard():
    # 這個路由只負責顯示 dashboard.html
    # 所有的資料將由頁面上的 JavaScript 動態載入
    return render_template('checkin/dashboard.html')

# --- (2) 新增：提供全名單狀態的 API ---
@bp.route('/api/status_list')
def api_status_list():
    try:
        # 1. 查詢所有名單
        all_people = CheckinList.query.order_by(CheckinList.name).all()
        
        checked_in_count = 0
        output_list = []
        
        # 2. 組合 JSON 資料
        for person in all_people:
            if person.status == 'CheckedIn':
                checked_in_count += 1
                
            output_list.append({
                "id": person.id,
                "name": person.name,
                "employee_id": person.employee_id,
                "status": person.status,
                # (如果狀態是 CheckedIn，才顯示時間，否則為空)
                "check_in_time": person.check_in_time.strftime('%H:%M:%S') if person.status == 'CheckedIn' else ''
            })

        return jsonify({
            "success": True,
            "checked_in_count": checked_in_count,
            "total_count": len(all_people),
            "checkin_list": output_list
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    
# --- (3) 新增：儀表板專用的手動簽到 API ---
@bp.route('/api/admin_checkin', methods=['POST'])
def api_admin_checkin():
    try:
        data = request.get_json()
        person_id = data.get('id')
        
        if not person_id:
            return jsonify({"success": False, "message": "缺少 ID"}), 400
            
        # 透過 ID 找到該人員
        person = CheckinList.query.get(person_id)
        
        if not person:
            return jsonify({"success": False, "message": "找不到此人員"}), 404
            
        if person.status == 'CheckedIn':
            return jsonify({"success": False, "message": "此人已經報到過了"}), 400
            
        # 執行簽到
        person.status = 'CheckedIn'
        person.check_in_time = datetime.now()
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"已成功為 {person.name} 完成報到"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500