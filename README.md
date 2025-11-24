企業活動報到與抽獎系統 (Check-in & Lottery System)

這是一套專為企業活動（如尾牙、研討會、家庭日）設計的即時報到與抽獎系統。系統基於 Python Flask 框架開發，支援本地部署與雲端部署 (Render + Neon)。

本系統特色在於**「尾號抽獎」**機制，結合即時報到狀態，確保抽獎過程公平、公正且透明。

🚀 核心功能 (Key Features)

本系統分為四大模組，共用一個核心資料庫，資料即時同步：

1. 📱 自助報到站 (Self-Service Kiosk)

極簡操作: 專為平板/觸控螢幕設計，員工僅需輸入「工號」即可完成報到。

即時反饋: 立即顯示報到成功、重複報到或查無此人。

自動重置: 畫面於 2 秒後自動清空，避免排隊塞車。

2. 📊 即時儀表板 (Live Dashboard)

即時統計: 視覺化顯示總人數、已報到、未報到數據。

多重篩選 (Advanced Filters): 支援依「關鍵字」、「工號首碼」、「報到狀態」、「中獎狀態」及「所中獎項」進行交叉篩選，快速鎖定特定人員。

手動補簽: 針對無法自助報到的人員，後台提供一鍵補簽功能。

自動刷新: 頁面每 5 秒自動更新，無需手動重整。

3. 🎰 尾號抽獎系統 (Tail Number Lottery)

尾號機制: 依據名單中 抽獎編號 的 尾數 (0-9) 進行抽選。

指定獎項: 抽獎時可輸入「獎項名稱」與「指定尾號」，系統自動抽出該尾號所有符合資格者。

智慧抽獎池 (Smart Pool): 系統僅鎖定 「已報到」 且 「未中獎」 的人員，杜絕重複中獎。

交易安全: 抽出當下立即寫入資料庫，確保資料一致性。

4. 🛠️ 後台管理 (Admin & Logs)

名單匯入: 支援 Excel (.xlsx) 批次匯入 (需包含 name, employee_id, lottery_number)。

資料重置: 提供一鍵清空所有資料功能 (Danger Zone)，方便測試後重置。

中獎日誌: 完整記錄所有已抽出獎項、尾號及得獎者名單，支援搜尋與篩選核對。

💻 技術堆疊 (Tech Stack)

Backend: Python 3, Flask

Database: * Local: SQLite

Cloud: PostgreSQL (via Neon / Render)

ORM: SQLAlchemy, Flask-Migrate

Frontend: HTML5, Bootstrap 5, JavaScript (Vanilla JS + Fetch API)

Server: Waitress (Windows Local), Gunicorn (Cloud/Linux)

📂 專案結構

/checkin-system
|
|-- app/                      # 核心應用程式
|   |-- __init__.py         # App Factory
|   |-- models.py           # 資料庫模型 (CheckinList, DrawnTailNumber)
|   |
|   |-- admin/              # 後台模組 (匯入、重置)
|   |-- checkin/            # 報到模組 (Kiosk, Dashboard, API)
|   |-- lottery/            # 抽獎模組 (Screen, Winners Log, API)
|   |
|   `-- templates/            # HTML 模板
|
|-- migrations/             # 資料庫遷移紀錄
|-- test_checkin_all.py     # 測試腳本 (一鍵全到)
|-- config.py               # 設定檔 (自動切換 SQLite/PostgreSQL)
|-- run.py                  # 啟動入口
|-- requirements.txt        # 套件依賴清單
`-- README.md               # 本文件


🛠️ 本地開發與執行 (Local Setup)

適用於活動現場無外網，或是開發測試環境。

建立虛擬環境:

python -m venv venv
# Windows 啟用:
.\venv\Scripts\activate
# Mac/Linux 啟用:
source venv/bin/activate


安裝依賴:

pip install -r requirements.txt


初始化資料庫:

flask db init
flask db migrate -m "Initial setup"
flask db upgrade


啟動伺服器 (使用 Waitress):
請勿在正式場合使用 flask run，建議使用 Waitress 以處理併發請求。

waitress-serve --host 0.0.0.0 --port 5000 --call "run:create_app"


連線:

本機: http://localhost:5000

區網: http://[您的電腦IP]:5000 (需允許防火牆通過)

☁️ 雲端部署 (Render + Neon)

本專案已優化，可直接部署於 Render 免費版。

前置準備

PostgreSQL 資料庫: 註冊 Neon.tech 取得免費資料庫連線字串 (DATABASE_URL)。

注意: 連線字串開頭若為 postgres:// 請改為 postgresql://。

Render 設定

New Web Service: 連結 GitHub Repo。

Build Command: pip install -r requirements.txt

Start Command: ```bash
flask db upgrade && gunicorn --bind 0.0.0.0:10000 run:app
