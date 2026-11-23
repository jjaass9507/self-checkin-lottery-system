"""歷史版次：封存當屆活動資料、查看與匯出歷史版次。

做法是「封存後開新一屆」：
- 封存時把名單、開獎、獎項、取消紀錄整包存成 JSON 快照 (EventEdition.data)，
  然後在同一個交易內清空這些資料表與報到流水號計數器。
- 系統設定 (AppSetting：站點開關、抽獎開關、顯示欄位、篩選方式、管理員權限) 不動，沿用到下一屆。
- 歷史版次只讀，可匯出 Excel；只有超級管理員可以封存或刪除。
"""
import json
from datetime import date, datetime
from io import BytesIO

import openpyxl
from flask import abort, flash, redirect, render_template, request, send_file, url_for
from openpyxl.styles import Font, PatternFill

from app import db
from app.admin.routes import bp, _admin_role
from app.models import AppSetting, CancellationLog, CheckinList, DrawnTailNumber, EventEdition, Prize

SNAPSHOT_VERSION = 1
TYPE_LABELS = {'employee': '員工', 'dependent': '眷屬', 'vendor_contact': '外部廠商主要窗口', 'vendor': '外部廠商'}


def _plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=' ', timespec='seconds') if isinstance(value, datetime) else value.isoformat()
    return value


def _row_dict(obj):
    return {c.name: _plain(getattr(obj, c.name)) for c in obj.__table__.columns}


def _prize_labels(person, public_draws, tail_draws):
    """與查詢站相同的中獎判定：公獎全碼相符、尾數獎取最長相符尾號。"""
    if not person.lottery_number:
        return []
    num = str(person.lottery_number).zfill(3)
    labels = []
    if person.has_won_public:
        labels += [f"【公獎】{d.prize_name}" for d in public_draws if str(d.tail_number).zfill(3) == num]
    if person.has_won:
        matched = sorted((d for d in tail_draws if num.endswith(str(d.tail_number))), key=lambda d: len(str(d.tail_number)), reverse=True)
        if matched:
            labels.append(f"【尾數獎】{matched[0].prize_name}")
    return labels


def build_snapshot():
    people = CheckinList.query.order_by(CheckinList.id).all()
    draws = DrawnTailNumber.query.order_by(DrawnTailNumber.timestamp).all()
    public_draws = [d for d in draws if d.prize_type == 'public']
    tail_draws = [d for d in draws if d.prize_type != 'public']
    by_id = {p.id: p for p in people}

    participants = []
    for p in people:
        row = _row_dict(p)
        row['prize_info'] = ' & '.join(_prize_labels(p, public_draws, tail_draws))
        participants.append(row)

    cancellations = []
    for log in CancellationLog.query.order_by(CancellationLog.timestamp).all():
        person = by_id.get(log.checkin_list_id)
        cancellations.append({
            'timestamp': _plain(log.timestamp),
            'cancelled_by': log.cancelled_by,
            'name': person.name if person else '',
            'employee_id': person.employee_id if person else '',
        })

    return {
        'version': SNAPSHOT_VERSION,
        'participants': participants,
        'draws': [_row_dict(d) for d in draws],
        'prizes': [_row_dict(p) for p in Prize.query.order_by(Prize.prize_type, Prize.display_order, Prize.id).all()],
        'cancellations': cancellations,
    }


def _load(edition):
    try:
        data = json.loads(edition.data)
    except (TypeError, ValueError):
        data = {}
    for key in ('participants', 'draws', 'prizes', 'cancellations'):
        data.setdefault(key, [])
    return data


def _super_only():
    if _admin_role() != 'super':
        flash('只有超級管理員可以執行此操作', 'danger')
        return redirect(url_for('admin.editions_page'))
    return None


@bp.route('/editions')
def editions_page():
    current = {
        'total': CheckinList.query.count(),
        'checked_in': CheckinList.query.filter_by(status='CheckedIn').count(),
        'winners': CheckinList.query.filter((CheckinList.has_won == True) | (CheckinList.has_won_public == True)).count(),  # noqa: E712
        'draws': DrawnTailNumber.query.count(),
        'prizes': Prize.query.count(),
    }
    editions = EventEdition.query.order_by(EventEdition.archived_at.desc()).all()
    return render_template('admin/editions.html', current=current, editions=editions,
                           is_super=_admin_role() == 'super', default_name=f"{datetime.now().year} 活動")


@bp.route('/editions/archive', methods=['POST'])
def archive_edition():
    denied = _super_only()
    if denied:
        return denied
    name = (request.form.get('name') or '').strip()[:100]
    if not name:
        flash('請輸入版次名稱', 'danger')
        return redirect(url_for('admin.editions_page'))
    if not request.form.get('acknowledge'):
        flash('請勾選確認後再封存', 'danger')
        return redirect(url_for('admin.editions_page'))

    try:
        snapshot = build_snapshot()
        people = snapshot['participants']
        if not people and not snapshot['draws']:
            flash('目前沒有任何名單或開獎資料，無需封存', 'info')
            return redirect(url_for('admin.editions_page'))

        edition = EventEdition(
            name=name,
            archived_at=datetime.now(),
            total_count=len(people),
            checked_in_count=sum(1 for p in people if p.get('status') == 'CheckedIn'),
            winner_count=sum(1 for p in people if p.get('has_won') or p.get('has_won_public')),
            draw_count=len(snapshot['draws']),
            data=json.dumps(snapshot, ensure_ascii=False),
        )
        db.session.add(edition)

        # 清空當屆資料（順序：先刪有外鍵參照的取消紀錄）
        db.session.query(CancellationLog).delete(synchronize_session=False)
        db.session.query(DrawnTailNumber).delete(synchronize_session=False)
        db.session.query(CheckinList).delete(synchronize_session=False)
        db.session.query(Prize).delete(synchronize_session=False)
        AppSetting.query.filter(AppSetting.key.like('checkin_seq_counter_%')).delete(synchronize_session=False)

        db.session.commit()
        flash(f"已封存「{name}」（{edition.total_count} 人、{edition.draw_count} 筆開獎），可以開始匯入下一屆名單。", 'success')
    except Exception as exc:
        db.session.rollback()
        flash(f"封存失敗，資料未變動：{exc}", 'danger')
    return redirect(url_for('admin.editions_page'))


@bp.route('/editions/<int:edition_id>')
def edition_detail(edition_id):
    edition = db.session.get(EventEdition, edition_id) or abort(404)
    data = _load(edition)
    people = data['participants']
    winners = [p for p in people if p.get('has_won') or p.get('has_won_public')]
    winners.sort(key=lambda p: str(p.get('lottery_number') or ''))
    return render_template('admin/edition_detail.html', edition=edition, data=data, people=people,
                           winners=winners, type_labels=TYPE_LABELS, is_super=_admin_role() == 'super')


@bp.route('/editions/<int:edition_id>/export')
def edition_export(edition_id):
    edition = db.session.get(EventEdition, edition_id) or abort(404)
    data = _load(edition)

    wb = openpyxl.Workbook()
    header_fill = PatternFill(start_color='0369a1', end_color='0369a1', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)

    def sheet(ws, headers, rows):
        ws.append([h for h, _ in headers])
        for row in rows:
            ws.append([fn(row) for _, fn in headers])
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
        for col in ws.columns:
            width = max(len(str(c.value or '')) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(width + 4, 10), 50)
        ws.freeze_panes = 'A2'

    yes = lambda v: '是' if v else ''  # noqa: E731
    g = lambda k: (lambda r: r.get(k) or '')  # noqa: E731
    sheet(wb.active, [
        ('姓名', g('name')), ('工號', g('employee_id')), ('身分', lambda r: TYPE_LABELS.get(r.get('participant_type'), r.get('participant_type') or '')),
        ('綁定員工', g('linked_employee_id')), ('抽獎號碼', g('lottery_number')), ('站點', g('site')), ('部門', g('dept_code')),
        ('桌次', g('table_number')), ('餐點', g('meal_type')), ('組別', g('group_name')), ('大人/小孩', g('age_group')),
        ('電話', g('phone')), ('公差', lambda r: yes(r.get('is_business_trip'))),
        ('報到狀態', lambda r: '已報到' if r.get('status') == 'CheckedIn' else '未報到'),
        ('報到時間', g('check_in_time')), ('報到序號', g('checkin_seq')), ('中獎資訊', g('prize_info')),
        ('尾數獎已領', lambda r: yes(r.get('prize_claimed'))), ('公獎已領', lambda r: yes(r.get('public_prize_claimed'))),
        ('廠商禮品已領', lambda r: yes(r.get('vendor_gift_claimed'))),
    ], data['participants'])
    wb.active.title = '名單'
    sheet(wb.create_sheet('開獎紀錄'), [
        ('時間', g('timestamp')), ('號碼', g('tail_number')), ('獎項', g('prize_name')),
        ('類型', lambda r: '公獎' if r.get('prize_type') == 'public' else '尾數獎'), ('加碼', lambda r: yes(r.get('is_addon'))),
    ], data['draws'])
    sheet(wb.create_sheet('獎項'), [
        ('類型', lambda r: '公獎' if r.get('prize_type') == 'public' else '尾數獎'), ('名稱', g('name')),
        ('數量', g('quantity')), ('排序', g('display_order')),
    ], data['prizes'])
    sheet(wb.create_sheet('取消報到紀錄'), [
        ('時間', g('timestamp')), ('姓名', g('name')), ('工號', g('employee_id')), ('執行者工號', g('cancelled_by')),
    ], data['cancellations'])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    safe = ''.join(ch for ch in edition.name if ch not in '\\/:*?"<>|').strip() or f'edition_{edition.id}'
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=f"{safe}_{edition.archived_at:%Y%m%d}.xlsx")


@bp.route('/editions/<int:edition_id>/delete', methods=['POST'])
def edition_delete(edition_id):
    denied = _super_only()
    if denied:
        return denied
    edition = db.session.get(EventEdition, edition_id) or abort(404)
    name = edition.name
    db.session.delete(edition)
    db.session.commit()
    flash(f"已刪除歷史版次「{name}」", 'warning')
    return redirect(url_for('admin.editions_page'))
