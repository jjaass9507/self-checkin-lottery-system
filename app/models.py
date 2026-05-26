from app import db
from datetime import datetime
import uuid

# 1. 報到名單 (CheckinList)
class CheckinList(db.Model):
    __tablename__ = 'checkin_list'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    employee_id = db.Column(db.String(50), nullable=False, index=True)
    lottery_number = db.Column(db.String(50), nullable=True, index=True)

    # 地點 / 部門
    site = db.Column(db.String(50), nullable=True)      # 站點/廠區
    dept_code = db.Column(db.String(20), nullable=True) # 部門代碼

    # QR / UUID
    qr_hash = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

    # 報到狀態
    status = db.Column(db.String(20), nullable=False, default='Registered')
    check_in_time = db.Column(db.DateTime, nullable=True)

    # 抽獎狀態
    has_won = db.Column(db.Boolean, default=False, nullable=False, index=True)
    has_won_public = db.Column(db.Boolean, default=False)

    # 領獎確認
    prize_claimed = db.Column(db.Boolean, default=False)        # 尾數獎
    public_prize_claimed = db.Column(db.Boolean, default=False) # 公獎
    vendor_gift_claimed = db.Column(db.Boolean, default=False, nullable=False) # 外部廠商主要窗口公司禮品

    # 桌次 / 公差
    table_number = db.Column(db.String(20), nullable=True)
    is_business_trip = db.Column(db.Boolean, default=False)

    # 報到流水號（依餐別分配，例如 A001 / B003 / C002 / 001）
    checkin_seq = db.Column(db.String(10), nullable=True)

    # ===== 活動額外欄位 (外部活動/眷屬支援) =====
    participant_type   = db.Column(db.String(20), nullable=True, default=None)
    # 值: 'employee' (員工) | 'dependent' (眷屬) | 'vendor_contact' (外部廠商主要窗口) | 'vendor' (外部廠商) | None

    linked_employee_id = db.Column(db.String(50), nullable=True, default=None)
    # 眷屬所綁定的員工工號，participant_type='dependent' 時才有意義

    meal_type = db.Column(db.String(100), nullable=True, default=None)
    # 餐點類型/描述，例如: 'A', 'B', 'C餐:滷味+綠豆冰沙'

    group_name = db.Column(db.String(50), nullable=True, default=None)
    # 活動分組名稱，例如: 'A組', '第1組', 'Red Team'

    age_group = db.Column(db.String(20), nullable=True, default=None)
    # 大人/小孩，例如: '大人', '小孩', '成人', '兒童'

    phone = db.Column(db.String(30), nullable=True, default=None)
    # 聯絡電話

    def __repr__(self):
        return f'<CheckinList {self.name} ({self.employee_id})>'


# 2. 已抽出號碼紀錄 (DrawnTailNumber)
class DrawnTailNumber(db.Model):
    __tablename__ = 'drawn_tail_number'

    id = db.Column(db.Integer, primary_key=True)
    tail_number = db.Column(db.String(10), nullable=False, index=True)
    prize_name = db.Column(db.String(100), nullable=False, default="未命名獎項")
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_addon = db.Column(db.Boolean, default=False)
    prize_type = db.Column(db.String(20), default='tail')
    # 類型: 'tail' (尾數獎) | 'public' (公獎)

    def __repr__(self):
        return f'<DrawnTailNumber {self.tail_number} ({self.prize_type})>'


# 3. 取消報到紀錄 (CancellationLog)
class CancellationLog(db.Model):
    __tablename__ = 'cancellation_log'

    id = db.Column(db.Integer, primary_key=True)
    checkin_list_id = db.Column(db.Integer, db.ForeignKey('checkin_list.id'), nullable=False)
    cancelled_by = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.now)

    def __repr__(self):
        return f'<CancellationLog Target:{self.checkin_list_id} By:{self.cancelled_by}>'


# 4. 獎項設定 (Prize)
class Prize(db.Model):
    __tablename__ = 'prizes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    prize_type = db.Column(db.String(20), default='tail')
    quantity = db.Column(db.Integer, default=1)
    display_order = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<Prize {self.name}>'


# 5. 系統設定 (AppSetting)
class AppSetting(db.Model):
    __tablename__ = 'app_settings'

    key   = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<AppSetting {self.key}={self.value}>'
