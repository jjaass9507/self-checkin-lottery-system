# app/models.py
from app import db
from datetime import datetime
import uuid

# 1. 報到名單 (CheckinList) - 原 Attendee
class CheckinList(db.Model):
    __tablename__ = 'checkin_list'  # 資料表名稱
    
    id = db.Column(db.Integer, primary_key=True)
    
    # --- 您要求的欄位 ---
    name = db.Column(db.String(100), nullable=False)
    employee_id = db.Column(db.String(50), nullable=False, index=True) # 工號
    # -----------------------
    
    # --- 系統運作欄位 ---
    qr_hash = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    status = db.Column(db.String(20), nullable=False, default='Registered') # Status: Registered, CheckedIn
    check_in_time = db.Column(db.DateTime, nullable=True)
    has_won = db.Column(db.Boolean, default=False, nullable=False, index=True) # 是否已中獎
    # -----------------------

    # 建立與 Winner 的關聯
    winnings = db.relationship('Winner', back_populates='checkin_item', lazy=True)

    def __repr__(self):
        return f'<CheckinList {self.name} ({self.employee_id})>'

# 2. 獎項表 (Prizes)
class Prize(db.Model):
    __tablename__ = 'prize'
    
    id = db.Column(db.Integer, primary_key=True)
    prize_name = db.Column(db.String(100), nullable=False) # e.g., "特獎"
    description = db.Column(db.String(200), nullable=True) # e.g., "iPhone 16 Pro"
    quantity = db.Column(db.Integer, nullable=False, default=1) # 總名額
    
    # target_category 已移除
    
    winners = db.relationship('Winner', back_populates='prize', lazy=True)

    def __repr__(self):
        return f'<Prize {self.prize_name}>'

# 3. 中獎紀錄表 (Winners)
class Winner(db.Model):
    __tablename__ = 'winner'
    
    id = db.Column(db.Integer, primary_key=True)
    draw_timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # 關聯已更新 (attendee_id -> checkin_list_id)
    checkin_list_id = db.Column(db.Integer, db.ForeignKey('checkin_list.id'), nullable=False)
    prize_id = db.Column(db.Integer, db.ForeignKey('prize.id'), nullable=False)
    
    # 關聯已更新 (attendee -> checkin_item)
    checkin_item = db.relationship('CheckinList', back_populates='winnings')
    prize = db.relationship('Prize', back_populates='winners')

    def __repr__(self):
        return f'<Winner {self.checkin_item.name} won {self.prize.prize_name}>'