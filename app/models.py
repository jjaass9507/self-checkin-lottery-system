from app import db
from datetime import datetime
import uuid

# 1. 報到名單 (CheckinList)
class CheckinList(db.Model):
    __tablename__ = 'checkin_list'
    lottery_number = db.Column(db.String(50), nullable=True, index=True)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    employee_id = db.Column(db.String(50), nullable=False, index=True) 
    lottery_number = db.Column(db.String(50), nullable=True, index=True)
    site = db.Column(db.String(50), nullable=True)      # Site (站點/廠區)
    dept_code = db.Column(db.String(20), nullable=True) # 部門代碼
    
    qr_hash = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    status = db.Column(db.String(20), nullable=False, default='Registered')
    check_in_time = db.Column(db.DateTime, nullable=True)
    has_won = db.Column(db.Boolean, default=False, nullable=False, index=True) 

    def __repr__(self):
        return f'<CheckinList {self.name} ({self.employee_id})>'

# 2. 已抽出尾號紀錄 (DrawnTailNumber)
class DrawnTailNumber(db.Model):
    __tablename__ = 'drawn_tail_number'
    
    id = db.Column(db.Integer, primary_key=True)
    tail_number = db.Column(db.Integer, unique=True, nullable=False, index=True)
    
    # (*** 新增：記錄這是什麼獎項 ***)
    prize_name = db.Column(db.String(100), nullable=False, default="未命名獎項")
    
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<DrawnTailNumber {self.tail_number} - {self.prize_name}>'
    
# 3. (新增) 取消報到紀錄 (CancellationLog)
class CancellationLog(db.Model):
    __tablename__ = 'cancellation_log'
    
    id = db.Column(db.Integer, primary_key=True)
    checkin_list_id = db.Column(db.Integer, db.ForeignKey('checkin_list.id'), nullable=False) # 被取消者的 ID
    cancelled_by = db.Column(db.String(50), nullable=False) # 操作取消的人員工號
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.now) # 操作時間

    def __repr__(self):
        return f'<CancellationLog Target:{self.checkin_list_id} By:{self.cancelled_by}>'