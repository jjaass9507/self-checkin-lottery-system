from flask import flash, redirect, url_for

from app import db
from app.admin.routes import _guard
from app.models import AppSetting, CheckinList


def reset_checkin():
    """Reset all check-in records and restart meal-based check-in sequences.

    Cancellation keeps the issued sequence moving forward during normal operation.
    However, the admin reset-checkin action is meant to start the event check-in
    records over, so it must clear both assigned checkin_seq values and the
    persisted AppSetting counters used by the next assignment.
    """
    denied = _guard('reset_checkin')
    if denied:
        return denied
    try:
        checked_in_count = CheckinList.query.filter_by(status='CheckedIn').count()
        updated_people = db.session.query(CheckinList).update(
            {
                CheckinList.status: 'Registered',
                CheckinList.check_in_time: None,
                CheckinList.checkin_seq: None,
            },
            synchronize_session=False,
        )
        deleted_seq_counters = AppSetting.query.filter(
            AppSetting.key.like('checkin_seq_counter_%')
        ).delete(synchronize_session=False)

        db.session.commit()
        flash(
            f"已重置所有報到紀錄，共 {checked_in_count} 人變回未報到；"
            f"已清除 {updated_people} 人的報到流水號，並重置 {deleted_seq_counters} 組流水號計數器。",
            'warning',
        )
    except Exception as exc:
        db.session.rollback()
        flash(f"重置報到失敗：{exc}", 'danger')
    return redirect(url_for('admin.import_page'))
