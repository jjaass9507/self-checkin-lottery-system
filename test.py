from app import create_app, db
from app.models import CheckinList
from datetime import datetime

# 1. 初始化 App
app = create_app()

# 2. 進入 App 上下文 (Context)
# 這是必須的，這樣才能連線到資料庫
with app.app_context():
    print("--- 開始執行一鍵全部簽到 (測試用) ---")
    
    # 3. 找出所有「未報到」的人
    pending_users = CheckinList.query.filter(CheckinList.status != 'CheckedIn').all()
    count = len(pending_users)
    
    if count == 0:
        print("目前所有人皆已報到，無需操作。")
    else:
        # 4. 批次更新
        print(f"發現 {count} 位未報到人員，正在更新狀態...")
        current_time = datetime.now()
        
        for person in pending_users:
            person.status = 'CheckedIn'
            person.check_in_time = current_time
            print(f" -> 已簽到: {person.name} ({person.employee_id})")
        
        # 5. 提交變更到資料庫
        db.session.commit()
        print(f"\n成功！已將 {count} 人標記為「已報到」。")

    print("--- 執行結束 ---")