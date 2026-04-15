# 企業活動報到與抽獎系統 (Corporate Event Check-in & Lottery System)

這是一套專為企業大型活動（如尾牙、春酒、研討會、家庭日）設計的即時報到與抽獎系統。系統基於 Python Flask 框架開發，具備現代化的 UI 介面，支援本地端離線部署與雲端 (Render + Neon) 部署。

本系統不僅支援傳統的**「尾號抽獎」**，更加入了**「公獎 (全碼) 抽獎」**與**「中獎輪播」**機制，結合即時報到狀態，確保抽獎過程公平、公正且透明。

---

## 🚀 核心功能 (Key Features)

本系統分為五大模組，共用一個核心資料庫，資料即時同步：

### 1. 📱 自助報到與查詢站 (Kiosk & Query Station)
* **極簡操作**：專為平板/觸控螢幕設計，員工僅需輸入「工號」即可完成報到。
* **即時反饋與桌次顯示**：立即顯示報到成功、重複報到或查無此人，並顯示專屬「桌次」與「抽獎編號」。
* **純查詢模式**：提供獨立的 `/query` 路由，僅供查詢個人狀態與桌次，不觸發報到動作。
* **自動重置**：畫面於數秒後自動清空，避免排隊塞車與個資外洩。

### 2. 📊 即時報到儀表板 (Live Dashboard)
* **即時統計**：視覺化顯示總人數、已報到、未報到數據。
* **多重進階篩選**：支援依「關鍵字」、「工號首碼」、「報到狀態」、「中獎狀態」、「所中獎項」、「站點(Site)」、「部門」進行交叉篩選。
* **公差管理**：支援標記「公差 (Business Trip)」人員，系統視同已報到並給予專屬標籤。
* **後台手動操作**：提供管理員一鍵補簽、取消報到，以及「領獎狀態」的核銷功能。

### 3. 🎰 雙軌抽獎系統 (Lottery System)
* **尾數抽獎 (Tail Number)**：依據抽獎編號尾數抽選，支援「一般抽出 (未中獎者)」與「加碼抽出 (已中獎者)」。並依據站點 (HR/FAC) 智慧分流顯示名單。
* **公獎抽獎 (Public Prize)**：針對全碼 (3位數) 進行逐步揭曉抽獎，支援輸入號碼即時比對剩餘符合資格的候選人。
* **智慧防呆**：系統僅鎖定「已報到」且「符合條件」的人員，杜絕重複中獎或未到場中獎。

### 4. 🏆 中獎輪播展示 (Winners Carousel)
* **動態輪播**：依據獎項抽出順序，動態輪播所有已中獎人員名單，適合投影於活動現場大螢幕。
* **自適應排版**：自動根據中獎人數調整卡片與字體大小，確保畫面不跑版。

### 5. 🛠️ 後台管理與安全機制 (Admin & Logs)
* **權限控管**：簡單直覺的密碼登入攔截機制。
* **Excel 批次匯入**：支援匯入包含桌次、站點、部門與公差註記的完整名單。
* **獎項管理**：可自由新增、修改、刪除「尾數獎」與「公獎」的名稱與額度，並可單獨重置特定獎項的中獎紀錄。
* **操作日誌 (Logs)**：完整記錄所有「取消報到」的執行者工號與時間，便於事後稽核。

---

## 💻 技術堆疊 (Tech Stack)

* **Backend**: Python 3, Flask
* **Database**: 
  * Local: SQLite (`event.db`)
  * Cloud: PostgreSQL (via [Neon.tech](https://neon.tech/))
* **ORM & Migrations**: SQLAlchemy, Flask-Migrate
* **Frontend**: HTML5, Bootstrap 5, JavaScript (Vanilla JS + Fetch API), CSS3 Animations
* **Server**: Waitress (Windows Local), Gunicorn (Cloud/Linux)

---

## 📂 專案結構

```text
/checkin-system
|-- app/                      # 核心應用程式 (App Factory)
|   |-- models.py             # 資料庫模型 (報到名單、開獎紀錄、獎項設定、取消日誌)
|   |-- admin/                # 後台模組 (匯入、重置、獎項管理、Log)
|   |-- checkin/              # 報到模組 (Kiosk, Query, Dashboard, API)
|   |-- lottery/              # 抽獎模組 (尾數抽獎, 公獎, 輪播, 日誌, API)
|   `-- templates/            # HTML 模板
|-- migrations/               # 資料庫遷移紀錄 (Alembic)
|-- .env                      # 環境變數設定檔 (需自行建立)
|-- config.py                 # 系統設定檔
|-- run.py                    # 啟動入口
|-- test.py                   # 測試腳本 (一鍵全員報到)
|-- update_data.py            # 資料更新腳本 (從 Excel 更新現有桌次等資料)
`-- requirements.txt          # 套件依賴清單
🛠️ 本地開發與執行 (Local Setup)適用於活動現場無對外網路，或開發測試環境。建立並啟用虛擬環境:Bashpython -m venv venv

# Windows 啟用:
.\venv\Scripts\activate
# Mac/Linux 啟用:
source venv/bin/activate
安裝依賴套件:Bashpip install -r requirements.txt
設定環境變數 (.env):在專案根目錄建立 .env 檔案，輸入以下內容：程式碼片段SECRET_KEY="your-secret-key"
ADMIN_PASSWORD="your-admin-password" # 後台登入密碼
# 若要使用本地 SQLite，請不要設定 DATABASE_URL
初始化資料庫:Bashflask db upgrade
啟動伺服器:請勿在正式場合使用 flask run。請使用 Waitress 以處理併發請求：Bashwaitress-serve --host 0.0.0.0 --port 5000 --call "run:create_app"
本機連線: http://localhost:5000區網連線: http://[您的電腦IP]:5000 (需允許防火牆通過)☁️ 雲端部署 (Cloud Deployment via Render + Neon)本專案已優化，可直接部署於 Render 免費版並串接 Neon Serverless Postgres。準備資料庫 (Neon):註冊 Neon.tech 取得連線字串 (DATABASE_URL)。準備平台 (Render):新增 Web Service，連結您的 GitHub Repo。Render 設定:Build Command: pip install -r requirements.txtStart Command: flask db upgrade && gunicorn --bind 0.0.0.0:10000 run:create_app()Environment Variables:DATABASE_URL: postgresql://... (注意：若是 postgres:// 請改為 postgresql://)ADMIN_PASSWORD: 您自訂的後台密碼SECRET_KEY: 隨機亂碼字串🔄 資料庫管理：年度活動重置與備份策略 (重要！)當一次活動結束，準備迎來下一場活動（例如從 2026 尾牙切換到 2027 尾牙）時，強烈建議不要使用後台的「危險區重置」功能，以避免歷史資料遺失。請採用以下最佳實務：使用 Neon 分支 (Branching) 建立全新平台Neon 提供了類似 Git 的資料庫分支功能，讓您可以一秒建立乾淨的新環境，並保留舊資料隨時可查。登入 Neon 控制台，進入專案。點擊 Branches -> New Branch。命名新分支（例：2027-event），並在資料選項中選擇 Schema only (只複製結構，不複製資料)。請確保不要勾選 "Automatically delete branch"。獲取這個新分支的 DATABASE_URL。前往 Render (或您的 .env 檔案)，將 DATABASE_URL 替換為新分支的網址。重新啟動伺服器。此時您將擁有一個架構完整、但資料全空的全新系統！注意：因切換至全新 Schema，您需要重新登入後台匯入名單，並重新建立「獎項設定」。若日後需要查詢舊活動資料，只需將 DATABASE_URL 改回舊分支的網址即可瞬間切換。📝 Excel 名單匯入格式規範由後台匯入的 Excel (.xlsx) 檔案，標題列必須包含以下欄位名稱 (大小寫需一致)：欄位名稱 (必填/選填)說明範例name (必填)員工姓名王小明employee_id (必填)員工工號 (做為登入與唯一識別)K12345lottery_number (選填)抽獎編號 (通常為 3 碼數字)005, 123site (選填)站點或廠區 (用於抽獎名單分流顯示)HR, FACdept_code (選填)部門代碼 (用於儀表板篩選)RD-01table_number (選填)桌次編號VIP-1, 15is_business_trip (選填)是否為公差 (系統視同報到)。填 1, Y, yes, 是 皆可Y
