# 報到與抽獎系統 (Check-in & Lottery System)

這是一套專為企業活動（如尾牙、研討會、家庭日）設計的即時報到與抽獎系統。系統基於 Python Flask 框架開發，並使用 Waitress 伺服器進行部署，可輕鬆在內部網路 (LAN/Wi-Fi) 中運作。

## 🚀 核心功能

本系統分為四大模組，共用一個核心資料庫：

1.  **後台管理 (Admin Module)**
    * **名單匯入:** 支援從 Excel (`.xlsx`) 檔案批次匯入報到名單（姓名、工號）。
    * **獎項設定:** 動態新增、刪除、查看所有抽獎獎項及其名額。
    * **統一導覽:** 整合式後台介面，可快速切換至儀表板與其他系統。

2.  **自助報到 (Check-in Kiosk Module)**
    * **自助服務:** 專為平板電腦或 Kiosk 觸控螢幕設計的自助報到介面。
    * **工號報到:** 報到者僅需輸入工號即可完成報到。
    * **即時反饋:** 立即顯示「報到成功」、「已報到」或「查無此人」等狀態。

3.  **即時儀表板 (Dashboard Module)**
    * **即時統計:** 以圖卡顯示「總人數」、「已報到」、「未報到」等核心數字。
    * **自動刷新:** 儀表板資料每 5 秒自動更新，無需手動重整。
    * **完整名單:** 顯示所有人員的報到狀態、工號、姓名與報到時間。
    * **即時搜尋:** 內建搜尋功能，可快速過濾工號或姓名。

4.  **抽獎大螢幕 (Lottery Module)**
    * **華麗介面:** 專為活動大螢幕投影設計的抽獎介面，具備動態背景與動畫效果。
    * **公平抽獎池:** 抽獎 API **僅**會從「已報到 (CheckedIn)」且「未中獎 (has_won=False)」的人員中抽選。
    * **交易式抽獎:** 抽獎過程具備交易性。一經抽出，系統會**立即**將中獎者標記為 `has_won=True`，並寫入 `Winner` 日誌表，確保同一人不會被重複抽出。
    * **中獎日誌:** 提供獨立的「完整中獎名單」頁面，供活動後稽核與記錄。

## 💻 技術堆疊

* **後端:** Python 3, Flask
* **資料庫:** SQLite (透過 Flask-SQLAlchemy, Flask-Migrate 管理)
* **伺服器:** Waitress (生產級 WSGI 伺服器)
* **前端:** HTML5, CSS3, Bootstrap 5, JavaScript (Fetch API, DOM)
* **核心函式庫:** `pandas`, `openpyxl` (用於 Excel 匯入)

## 📂 專案結構

本專案採用 Flask 的「應用程式工廠 (Application Factory)」模式：

/checkin-system||-- app/                      # 核心應用程式|   |-- init.py         # App 工廠|   |-- models.py           # 資料庫模型 (DB Models)|   ||   |-- admin/              # 後台模組|   |   -- routes.py |   |-- checkin/            # 報到模組 (Kiosk + 儀表板) |   |   -- routes.py|   |-- lottery/            # 抽獎模組|   |   -- routes.py |   | |   -- templates/            # HTML 模板|       |-- admin/|       |-- checkin/|       -- lottery/ | |-- migrations/             # 資料庫遷移腳本 |-- venv/                   # Python 虛擬環境 |-- config.py               # 應用程式設定檔 |-- run.py                  # 應用程式啟動入口 |-- event.db                # SQLite 資料庫檔案 |-- requirements.txt        # Python 套件依賴 -- .flaskenv               # Flask 環境變數 (開發用)
## 🛠️ 安裝與設定

1.  **建立虛擬環境:**
    ```bash
    # (Windows)
    python -m venv venv
    .\venv\Scripts\activate
    ```

2.  **安裝依賴套件:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **建立資料庫:**
    ```bash
    # 第一次初始化 (只需執行一次)
    flask db init

    # (重要!) 修改 migrations/env.py 檔案，使其支援工廠模式
    # (在 env.py 中加入這三行)
    from app import create_app, db
    app = create_app()
    target_metadata = db.metadata

    # 產生遷移腳本
    flask db migrate -m "Initial models"
    
    # 套用遷移，建立 event.db 檔案
    flask db upgrade
    ```

## 🏃‍♂️ 執行應用程式

**請勿使用 `flask run` 於正式活動！** `flask run` 是開發用伺服器，一次只能處理一個請求。

請使用 `Waitress` 生產級伺服器，它能同時處理大量報到請求。

```bash
waitress-serve --host 0.0.0.0 --port 5000 --call "run:create_app"
--host 0.0.0.0: 監聽您電腦的所有 IP (包含內部 Wi-Fi IP)。--port 5000: 指定伺服器運作的埠號。--call "run:create_app": 呼叫 run.py 檔案中的 create_app 工廠函式。🚀 使用流程 (活動日)[您的電腦 IP]: 執行 ipconfig (Windows) 找到您的 IPv4 位址，例如 192.168.1.5。【活動前】步驟一：上傳名單管理員打開 http://[您的電腦IP]:5000/admin/import上傳包含 name 和 employee_id 欄位的 Excel 檔案。【活動前】步驟二：設定獎項管理員打開 http://[您的電腦IP]:5000/admin/prizes新增所有要抽的獎項與名額。【活動日】步驟三：開始報到將 Kiosk 平板電腦連上同一個 Wi-Fi。打開瀏覽器，進入 http://[您的電腦IP]:5000/checkin/員工即可開始使用工號自助報到。【活動日】步驟四：即時監控工作人員打開 http://[您的電腦IP]:5000/checkin/dashboard/隨時監控報到率與報到狀態。【活動日】步驟五：開始抽獎主持人/活動控台電腦打開 http://[您的電腦IP]:5000/lottery/screen/選擇獎項，點擊「DRAW!」開始抽獎。可隨時打開 http://[您的電腦IP]:5000/lottery/winners/ 查核中獎日誌。🔗 快速網址參考頁面網址 (替換[IP])用途自助報到站http://[IP]:5000/checkin/員工自助報到報到儀表板http://[IP]:5000/checkin/dashboard/工作人員監控抽獎大螢幕http://[IP]:5000/lottery/screen/主持人抽獎中獎日誌http://[IP]:5000/lottery/winners/稽核中獎名單名單匯入 (後台)http://[IP]:5000/admin/import/管理員上傳名單獎項設定 (後台)http://[IP]:5000/admin/prizes/管理員設定獎品