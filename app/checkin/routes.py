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
                       'participant_type', 'age_group', 'phone', 'meal', 'group', 'lottery_number',
                       'status', 'prize', 'checkin_time']
    dash_fields = {}
    for key in dash_field_keys:
        s = AppSetting.query.get(f'dash_show_{key}')
        dash_fields[key] = (s.value != 'false') if s else True

    return render_template('checkin/dashboard.html', dash_fields=dash_fields)

def _meal_seq_prefix(meal_type):
    raw = (meal_type or '').strip().upper()
    if not raw:
        return ''
    first = raw[0]
    return first if 'A' <= first <= 'Z' else ''

def _assign_checkin_seq(person):
    """依餐別分配流水號：A餐→A001, C餐:...→C001, 無餐別→001。已有號碼則不重複分配。"""
    if person.checkin_seq:
        return
    prefix = _meal_seq_prefix(person.meal_type)
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


def _participant_label(value):
    return {
        'employee': '員工',
        'dependent': '眷屬',
        'vendor_contact': '外部廠商主要窗口',
        'vendor': '外部廠商',
    }.get(value, value)


@bp.route('/api/checkin_by_id', methods=['POST'])
def api_checkin_by_id():
    data = request.get_json()
    emp_id = data.get('employee_id')

    if not emp_id:
        return jsonify({"success": False, "message": "請輸入工號"}), 400

    person = CheckinList.query.filter(CheckinList.employee_id.ilike(emp_id)).first()

    if not person:
        return jsonify({"success": False, "message": "找不到此工號，請聯繫工作人員。"}), 404

    if person.status != 'CheckedIn':
        try:
            person.status = 'CheckedIn'
            person.check_in_time = datetime.now()
            _assign_checkin_seq(person)
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({"success": False, "message": "報到失敗: 資料庫錯誤"}), 500

    lottery_num_str = str(person.lottery_number).zfill(3) if person.lottery_number else "未設定"
    prize_info_list = []

    if person.lottery_number:
        if person.has_won_public:
            public_draws = DrawnTailNumber.query.filter_by(prize_type='public').all()
            for d in public_draws:
                if str(d.tail_number) == lottery_num_str:
                    prize_info_list.append(f"【公獎】{d.prize_name}")
        if person.has_won:
            tail_draws = DrawnTailNumber.query.filter_by(prize_type='tail').all()
            matched_prizes = [d for d in tail_draws if lottery_num_str.endswith(str(d.tail_number))]
            if matched_prizes:
                matched_prizes.sort(key=lambda x: len(str(x.tail_number)), reverse=True)
                prize_info_list.append(f"【尾數獎】{matched_prizes[0].prize_name}")

    if prize_info_list:
        prize_display = " & ".join(prize_info_list)
        is_winner = True
    else:
        prize_display = "祝您中大獎！"
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
        "participant_type": person.participant_type,
        "participant_type_label": _participant_label(person.participant_type),
        "linked_employee_id": person.linked_employee_id,
        "meal_type": person.meal_type,
        "group_name": person.group_name,
        "age_group": person.age_group,
        "phone": person.phone,
    })

@bp.route('/api/status_list')
def api_status_list():
    try:
        checkin_list = CheckinList.query.all()
        total_count = CheckinList.query.count()
        checked_in_count = CheckinList.query.filter_by(status='CheckedIn').count()
        all_draws = DrawnTailNumber.query.all()
        tail_draws = [d for d in all_draws if (d.prize_type or 'tail') == 'tail']
        public_draws = [d for d in all_draws if (d.prize_type or 'tail') == 'public']

        output_list = []
        for person in checkin_list:
            tail_prize_str = ""
            public_prize_str = ""
            if person.has_won:
                user_num = str(person.lottery_number).zfill(3) if person.lottery_number else "000"
                matched_draws = [draw for draw in tail_draws if user_num.endswith(str(draw.tail_number))]
                if matched_draws:
                    matched_draws.sort(key=lambda x: len(str(x.tail_number)), reverse=True)
                    best_match = matched_draws[0]
                    digit_len = len(str(best_match.tail_number))
                    tail_prize_str = f"{best_match.prize_name} 尾數獎 中{digit_len}位({best_match.tail_number})"
                else:
                    tail_prize_str = "尾數中獎(未知)"

            if person.has_won_public:
                user_num = str(person.lottery_number).zfill(3) if person.lottery_number else "000"
                p_names = [f"{draw.prize_name}({user_num})" for draw in public_draws if str(draw.tail_number).zfill(3) == user_num]
                public_prize_str = " | ".join(p_names) if p_names else f"公獎({user_num})"

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
                "participant_type": person.participant_type,
                "participant_type_label": _participant_label(person.participant_type),
                "linked_employee_id": person.linked_employee_id,
                "meal_type": person.meal_type,
                "group_name": person.group_name,
                "age_group": person.age_group,
                "phone": person.phone,
            })
        return jsonify({"success": True, "checkin_list": output_list, "total_count": total_count, "checked_in_count": checked_in_count})
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
        _assign_checkin_seq(person)
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
        db.session.add(CancellationLog(checkin_list_id=person.id, cancelled_by=canceller_id, timestamp=datetime.now()))
        person.status = 'Registered'
        person.check_in_time = None
        person.checkin_seq = None
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
        prize_type = data.get('type')
        person = CheckinList.query.get(person_id)
        if not person:
            return jsonify({"success": False, "message": "找不到人員"}), 404
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

@bp.route('/query')
def query_page():
    return render_template('checkin/self_query.html')

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

    tail_draws = DrawnTailNumber.query.filter_by(prize_type='tail').all()
    public_draws = DrawnTailNumber.query.filter_by(prize_type='public').all()

    def compute_prize(p):
        num = str(p.lottery_number).zfill(3) if p.lottery_number else None
        if not num:
            return "尚未中獎", False
        items = []
        if p.has_won_public:
            items.extend(f"【公獎】{d.prize_name}" for d in public_draws if str(d.tail_number) == num)
        if p.has_won:
            matched = [d for d in tail_draws if num.endswith(str(d.tail_number))]
            if matched:
                matched.sort(key=lambda x: len(str(x.tail_number)), reverse=True)
                items.append(f"【尾數獎】{matched[0].prize_name}")
        return (" & ".join(items), True) if items else ("尚未中獎", False)

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
            "participant_type_label": _participant_label(p.participant_type),
            "linked_employee_id": p.linked_employee_id,
            "meal_type": p.meal_type,
            "group_name": p.group_name,
            "age_group": p.age_group,
            "phone": p.phone,
        }

    field_keys = ['employee_id', 'status', 'lottery_number', 'prize_info',
                  'table_number', 'meal_type', 'group_name', 'participant_type',
                  'age_group', 'phone']
    field_settings = {}
    for key in field_keys:
        s = AppSetting.query.get(f'query_show_{key}')
        field_settings[key] = (s.value != 'false') if s else True

    dep_records = []
    dependents = []
    if person.participant_type != 'dependent':
        dep_records = CheckinList.query.filter(CheckinList.linked_employee_id.ilike(emp_id)).all()
        dependents = [person_to_dict(d) for d in dep_records]

    result = person_to_dict(person)
    if dep_records:
        for fld in ('table_number', 'meal_type', 'group_name', 'age_group', 'phone'):
            if not getattr(person, fld):
                for d in dep_records:
                    val = getattr(d, fld)
                    if val:
                        result[fld] = val
                        break

    result.update({"success": True, "message": f"查詢成功：{person.name}", "field_settings": field_settings, "dependents": dependents})
    return jsonify(result)
