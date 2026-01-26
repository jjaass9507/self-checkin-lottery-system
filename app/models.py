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
    # (*** 新增：公獎狀態 ***)
    has_won_public = db.Column(db.Boolean, default=False)

    # (*** 新增：領獎確認狀態 ***)
    prize_claimed = db.Column(db.Boolean, default=False)        # 尾數獎 是否已領獎
    public_prize_claimed = db.Column(db.Boolean, default=False) # 公獎 是否已領獎

    # (*** 新增：桌次 (table_number) ***)
    # (*** 新增：是否為公差 (is_business_trip) ***
    table_number = db.Column(db.String(20), nullable=True)      # 桌次 (建議用字串，以防有 VIP-1 這種格式)
    is_business_trip = db.Column(db.Boolean, default=False)     # 是否為公差

    def __repr__(self):
        return f'<CheckinList {self.name} ({self.employee_id})>'

# 2. 已抽出尾號紀錄 (DrawnTailNumber)
class DrawnTailNumber(db.Model):
    __tablename__ = 'drawn_tail_number'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # (*** 修改 1：移除 unique=True ***)
    tail_number = db.Column(db.String(10), nullable=False, index=True) 
    
    prize_name = db.Column(db.String(100), nullable=False, default="未命名獎項")
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_addon = db.Column(db.Boolean, default=False)
    
    # (*** 修改 2：新增獎項類型欄位，預設為 'tail' (尾數獎) ***)
    # 類型可為: 'tail' (尾數/加碼), 'public' (公獎)
    prize_type = db.Column(db.String(20), default='tail') 

    def __repr__(self):
        return f'<DrawnTailNumber {self.tail_number} ({self.prize_type})>'
    
# 3. (新增) 取消報到紀錄 (CancellationLog)
class CancellationLog(db.Model):
    __tablename__ = 'cancellation_log'
    
    id = db.Column(db.Integer, primary_key=True)
    checkin_list_id = db.Column(db.Integer, db.ForeignKey('checkin_list.id'), nullable=False) # 被取消者的 ID
    cancelled_by = db.Column(db.String(50), nullable=False) # 操作取消的人員工號
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.now) # 操作時間

    def __repr__(self):
        return f'<CancellationLog Target:{self.checkin_list_id} By:{self.cancelled_by}>'

# 4. (新增) 獎項設定 (Prize) 
class Prize(db.Model):
    __tablename__ = 'prizes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)      # 獎項名稱
    prize_type = db.Column(db.String(20), default='tail') # 類型: 'tail'(尾數獎) 或 'public'(公獎)
    quantity = db.Column(db.Integer, default=1)           # 數量 (公獎用，尾數獎通常設為 1 或不限制)
    display_order = db.Column(db.Integer, default=0)      # 顯示排序
    
    def __repr__(self):
        return f'<Prize {self.name}>'