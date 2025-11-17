# app/models.py
from app import db
from datetime import datetime
import uuid

# 1. 報到名單 (CheckinList)
class CheckinList(db.Model):
    __tablename__ = 'checkin_list'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    employee_id = db.Column(db.String(50), nullable=False, index=True) # 工號 (用於報到)
    
    # (*** 1. 這是新增的欄位 ***)
    # 我們允許它為空 (nullable=True)，以防有些人員沒有抽獎編號
    lottery_number = db.Column(db.String(50), nullable=True, index=True) # 抽獎編號 (用於抽獎)
    
    # --- 系統運作欄位 ---
    qr_hash = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    status = db.Column(db.String(20), nullable=False, default='Registered')
    check_in_time = db.Column(db.DateTime, nullable=True)
    
    # (*** 2. has_won 仍是關鍵 ***)
    # 抽中後，此欄位會變為 True
    has_won = db.Column(db.Boolean, default=False, nullable=False, index=True) 

    def __repr__(self):
        return f'<CheckinList {self.name} ({self.employee_id})>'

# (*** 3. Prize 和 Winner 模型已被刪除 ***)

# (*** 4. 這是新增的資料表 ***)
# 用來記錄哪些尾號 (0-9) 已經被抽過了
class DrawnTailNumber(db.Model):
    __tablename__ = 'drawn_tail_number'
    
    id = db.Column(db.Integer, primary_key=True)
    # (我們用 Integer 儲存 0-9)
    tail_number = db.Column(db.Integer, unique=True, nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<DrawnTailNumber {self.tail_number}>'