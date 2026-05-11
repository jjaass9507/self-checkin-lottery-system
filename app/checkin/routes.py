# 修正後的程式碼 (補上 session 和 redirect)
from flask import Blueprint, render_template, request, jsonify, url_for, session, redirect
from app import db
from app.models import CheckinList, DrawnTailNumber, Prize, CancellationLog
from datetime import datetime

bp = Blueprint('checkin', __name__)

@bp.route('/')
def index():
    return render_template('checkin/self_checkin.html')

@bp.route('/dashboard')
def dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('admin.login'))

    from app.models import AppSetting
    dash_field_keys = ['checkin_seq', 'site', 'dept', 'table', 'business_trip',
                       'participant_type', 'meal', 'group', 'lottery_number',
                       'status', 'prize', 'checkin_time']
    dash_fields = {}
    for key in dash_field_keys:
        s = AppSetting.query.get(f'dash_show_{key}')
        dash_fields[key] = (s.value != 'false') if s else True

    return render_template('checkin/dashboard.html', dash_fields=dash_fields)

def _assign_checkin_seq(person):
    """依餐別分配流水號：A餐→A001, B餐→B001, 無餐別→001。已有號碼則不重複分配。"""
    if person.checkin_seq:
        return
    prefix = (person.meal_type or '').upper()
    if prefix not in ('A', 'B'):
        prefix = ''
    # 取同前綴中最大的號碼
    seq_len = len(prefix) + 3
    candidates = CheckinList.query.filter(
        CheckinList.checkin_seq.isnot(None),
        db.func.length(CheckinList.checkin_seq) == seq_len,
        CheckinList.checkin_seq.like(f'{prefix}%')
    ).all()
    max_num = 0
    for c in candidates:
        try:
            max_num = max(max_num, int(c.checkin_seq[len(prefix):]))
        except (ValueError, TypeError):
            pass
    person.checkin_seq = f'{prefix}{max_num + 1:03d}'


@bp.route('/api/checkin_by_id', methods=['POST'])
def api_checkin_by_id():
    data = request.get_json()
    emp_id = data.get('employee_id')

    if not emp_id:
        return jsonify({"success": False, "message": "請輸入工號"}), 400

    # 1. 先去資料庫找人 (這行一定要在最前面！)
    person = CheckinList.query.filter(CheckinList.employee_id.ilike(emp_id)).first()

    if not person:
        return jsonify({"success": False, "message": "找不到此工號，請聯繫工作人員。"}), 404

    # 2. 執行報到 (如果還沒報到)
    if person.status != 'CheckedIn':
        try:
            person.status = 'CheckedIn'
            person.check_in_time = datetime.now()
            _assign_checkin_seq(person)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "message": "報到失敗: 資料庫錯誤"}), 500
        
    # 3. (*** 關鍵順序 ***) 確定 person 存在後，才開始計算顯示資訊
    
    # 取得抽獎號碼字串 (補零)
    lottery_num_str = str(person.lottery_number).zfill(3) if person.lottery_number else "未設定"
    
    # 查詢中獎資訊
    prize_info_list = []
    
    if person.lottery_number:
        # A. 檢查公獎
        if person.has_won_public:
            public_draws = DrawnTailNumber.query.filter_by(prize_type='public').all()
            for d in public_draws:
                if str(d.tail_number) == lottery_num_str:
                    prize_info_list.append(f"【公獎】{d.prize_name}")
        
        # B. 檢查尾數獎
        if person.has_won:
            tail_draws = DrawnTailNumber.query.filter_by(prize_type='tail').all()
            matched_prizes = []
            for d in tail_draws:
                if lottery_num_str.endswith(str(d.tail_number)):
                    matched_prizes.append(d)
            
            if matched_prizes:
                matched_prizes.sort(key=lambda x: len(str(x.tail_number)), reverse=True)
                best_match = matched_prizes[0]
                prize_info_list.append(f"【尾數獎】{best_match.prize_name}")

    # 組合中獎字串
    if prize_info_list:
        prize_display = " & ".join(prize_info_list)
        is_winner = True
    else:
        prize_display = "祝您中大獎！" # 或是 "尚未中獎"
        is_winner = False

    return jsonify({
        "success": True,
        "message": f"歡迎！{person.name} 報到成功！",
        "name": person.name,
        "employee_id": person.employee_id,
        "lottery_number": lottery_num_str,
        "table_number": person.table_number or "未分配",
        "prize_info": prize_display,
        "is_winner": is_winner,
        "checkin_seq": person.checkin_seq,
        # 活動額外欄位
        "participant_type": person.participant_type,
        "linked_employee_id": person.linked_employee_id,
        "meal_type": person.meal_type,
        "group_name": person.group_name,
    })

@bp.route('/api/status_list')
def api_status_list():
    try:
        # 1. 撈取資料
        checkin_list = CheckinList.query.all()
        total_count = CheckinList.query.count()
        checked_in_count = CheckinList.query.filter_by(status='CheckedIn').count()
        
        # 撈取所有開獎紀錄
        all_draws = DrawnTailNumber.query.all()
        
        # 分類開獎紀錄 (*** 將 None 視為 'tail' 以相容舊資料 ***)
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
                "table_number": person.table_number,
                "is_business_trip": person.is_business_trip,
                "checkin_seq": person.checkin_seq,
                "tail_prize_info": tail_prize_str,
                "public_prize_info": public_prize_str,
                "prize_info": f"{tail_prize_str} {public_prize_str}".strip(),
                "has_won": person.has_won,
                "has_won_public": person.has_won_public,
                "prize_claimed": person.prize_claimed,
                "public_prize_claimed": person.public_prize_claimed,
                # 活動額外欄位
                "participant_type": person.participant_type,
                "linked_employee_id": person.linked_employee_id,
                "meal_type": person.meal_type,
                "group_name": person.group_name,
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
    
# --- 新增：純查詢頁面路由 ---
@bp.route('/query')
def query_page():
    return render_template('checkin/self_query.html')

# --- 純查詢 API (不修改報到狀態) ---
@bp.route('/api/search_by_id', methods=['POST'])
def api_search_by_id():
    from app.models import AppSetting

    data = request.get_json()
    emp_id = data.get('employee_id')

    if not emp_id:
        return jsonify({"success": False, "message": "請輸入工號"}), 400

    person = CheckinList.query.filter(CheckinList.employee_id.ilike(emp_id)).first()
    if not person:
        return jsonify({"success": False, "message": "找不到此工號，請聯繫工作人員。"}), 404

    # 讀取已開獎紀錄（共用，避免每人重複查詢）
    tail_draws   = DrawnTailNumber.query.filter_by(prize_type='tail').all()
    public_draws = DrawnTailNumber.query.filter_by(prize_type='public').all()

    def compute_prize(p):
        num = str(p.lottery_number).zfill(3) if p.lottery_number else None
        if not num:
            return "尚未中獎", False
        items = []
        if p.has_won_public:
            for d in public_draws:
                if str(d.tail_number) == num:
                    items.append(f"【公獎】{d.prize_name}")
        if p.has_won:
            matched = [d for d in tail_draws if num.endswith(str(d.tail_number))]
            if matched:
                matched.sort(key=lambda x: len(str(x.tail_number)), reverse=True)
                items.append(f"【尾數獎】{matched[0].prize_name}")
        if items:
            return " & ".join(items), True
        return "尚未中獎", False

    def person_to_dict(p):
        prize_display, is_winner = compute_prize(p)
        return {
            "name": p.name,
            "employee_id": p.employee_id,
            "lottery_number": str(p.lottery_number).zfill(3) if p.lottery_number else "未設定",
            "table_number": p.table_number or "未分配",
            "prize_info": prize_display,
            "is_winner": is_winner,
            "status": p.status,
            "participant_type": p.participant_type,
            "linked_employee_id": p.linked_employee_id,
            "meal_type": p.meal_type,
            "group_name": p.group_name,
        }

    # 讀取後台欄位顯示設定
    field_keys = ['employee_id', 'status', 'lottery_number', 'prize_info',
                  'table_number', 'meal_type', 'group_name', 'participant_type']
    field_settings = {}
    for key in field_keys:
        s = AppSetting.query.get(f'query_show_{key}')
        field_settings[key] = (s.value != 'false') if s else True

    # 若查到的是員工（非眷屬），一併撈出所有眷屬
    dep_records = []
    dependents = []
    if person.participant_type != 'dependent':
        dep_records = CheckinList.query.filter(
            CheckinList.linked_employee_id.ilike(emp_id)
        ).all()
        dependents = [person_to_dict(d) for d in dep_records]

    result = person_to_dict(person)

    # 主員工若缺少「家庭共用」欄位（桌次/餐別/組別），自動從眷屬補上
    if dep_records:
        for fld in ('table_number', 'meal_type', 'group_name'):
            if not getattr(person, fld):
                for d in dep_records:
                    val = getattr(d, fld)
                    if val:
                        result[fld] = val
                        break

    result.update({
        "success": True,
        "message": f"查詢成功：{person.name}",
        "field_settings": field_settings,
        "dependents": dependents,
    })
    return jsonify(result)