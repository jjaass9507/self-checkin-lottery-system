# 企業活動報到與抽獎系統

這是一套以 Flask 開發的企業活動報到與抽獎平台，適用於尾牙、春酒、家庭日、研討會等大型活動。系統支援後台名單匯入、前台自助報到、純查詢站、即時報到儀表板、尾數抽獎、公獎抽獎、中獎輪播與操作紀錄。

目前專案已針對 Render 免費方案的 512MB 記憶體限制做過匯入流程最佳化：Excel 匯入不再依賴 pandas / numpy，改用低記憶體 `.xlsx` 串流解析，並以批次寫入資料庫。

---

## 核心功能

### 自助報到與查詢站

- 前台自助報到站可輸入工號完成報到。
- 純查詢站可查詢報到狀態、桌次、抽獎編號、身份與餐點資訊，不會觸發報到。
- 支援員工、眷屬、外部廠商主要窗口、外部廠商等身份。
- 眷屬可綁定員工工號。

### 即時報到儀表板

- 顯示總人數、已報到、未報到等即時統計。
- 支援關鍵字、工號首碼、狀態、中獎狀態、獎項、站點、部門、身份、餐點、分組等篩選。
- 可手動補簽、取消報到、確認領獎。
- 部門顯示以畫面易讀為主，儀表板上最多顯示 4 個字；資料庫仍保留完整部門內容。

### 抽獎系統

- 尾數抽獎：依抽獎編號尾數抽出中獎者。
- 公獎抽獎：依完整抽獎編號比對候選人。
- 支援一般抽出與加碼抽出。
- 中獎狀態與領獎狀態可於後台管理。

### 後台管理

- 後台密碼登入。
- Excel 名單匯入。
- 欄位顯示設定。
- 獎項新增、修改、刪除。
- 清除名單、重置報到、重置抽獎、重置單一獎項。
- 取消報到紀錄會寫入 `cancellation_log` 供稽核使用。

---

## 技術堆疊

- Backend：Python 3、Flask
- Database：SQLite（本機）、PostgreSQL（Render / Neon）
- ORM / Migration：SQLAlchemy、Flask-Migrate、Alembic
- Excel：openpyxl 用於範本產生；匯入使用專案內低記憶體 XLSX stream parser
- Frontend：Bootstrap 5、Vanilla JavaScript、Fetch API
- Server：Gunicorn（Render / Linux）

---

## 專案結構

```text
.
├── app/
│   ├── __init__.py                 # Flask app factory
│   ├── models.py                   # DB models
│   ├── admin/
│   │   ├── routes.py               # 原後台路由
│   │   ├── optimized_routes.py     # Render 低記憶體匯入與清除名單 override
│   │   └── xlsx_stream.py          # 低記憶體 XLSX 串流解析器
│   ├── checkin/                    # 報到、查詢、儀表板 API
│   ├── lottery/                    # 抽獎功能
│   ├── static/
│   └── templates/
├── migrations/                     # Alembic migrations
├── config.py
├── gunicorn.conf.py                # Render 免費方案建議 Gunicorn 設定
├── pandas.py                       # 輕量 pandas 相容層，避免載入 pandas/numpy
├── requirements.txt
└── run.py
```

---

## 本地開發

### 1. 建立虛擬環境

```bash
python -m venv venv
```

Windows：

```bash
.\venv\Scripts\activate
```

macOS / Linux：

```bash
source venv/bin/activate
```

### 2. 安裝套件

```bash
pip install -r requirements.txt
```

### 3. 建立 `.env`

```env
SECRET_KEY=your-secret-key
ADMIN_PASSWORD=your-admin-password
```

本機使用 SQLite 時，不需要設定 `DATABASE_URL`。

### 4. 初始化或升級資料庫

```bash
flask db upgrade
```

### 5. 啟動

開發測試可使用：

```bash
flask run
```

正式活動現場不建議使用 Flask development server。可改用 Gunicorn 或其他正式 WSGI server。

---

## Render + Neon 部署

### Neon

建立 PostgreSQL database，取得連線字串並設定到 Render 的 `DATABASE_URL`。

注意：若 Neon 給的是 `postgres://...`，請改成 `postgresql://...`。

### Render Web Service

Build Command：

```bash
pip install -r requirements.txt
```

Start Command 建議使用：

```bash
flask db upgrade && gunicorn -c gunicorn.conf.py --bind 0.0.0.0:$PORT run:app
```

若 Render 介面沒有正確帶入 `$PORT`，可暫時使用 Render 顯示的固定 port，但建議仍以 `$PORT` 為主。

### Render Environment Variables

```env
DATABASE_URL=postgresql://...
ADMIN_PASSWORD=your-admin-password
SECRET_KEY=your-random-secret
```

### Render 免費方案注意事項

Render 免費方案記憶體只有 512MB，本專案已做以下處理：

- 移除 pandas / numpy 依賴，避免 import 時吃掉大量記憶體。
- 使用 `app/admin/xlsx_stream.py` 直接串流解析 `.xlsx` 內部 XML。
- 匯入時每批寫入資料庫，避免 SQLAlchemy session 累積過多物件。
- `gunicorn.conf.py` 固定 `workers = 1`、`threads = 1`，並將 `timeout` 調高。

若匯入超大 Excel 仍出現 `Worker was sent SIGKILL! Perhaps out of memory?`，請優先確認：

1. Start Command 是否有使用 `-c gunicorn.conf.py`。
2. Excel 是否包含大量格式、圖片、公式或隱藏工作表；建議另存成乾淨的新 `.xlsx`。
3. 可以將名單拆成多份分批匯入。

---

## Excel 名單匯入格式

檔案格式必須為 `.xlsx`。第一列為標題列，欄位名稱需與下方一致。

### 必填欄位

| 欄位 | 說明 | 範例 |
|---|---|---|
| `name` | 姓名 | 王小明 |
| `employee_id` | 員工工號 / 身份識別欄 | A001 |

### 選填欄位

| 欄位 | 說明 | 範例 |
|---|---|---|
| `lottery_number` | 抽獎編號 | 001、168 |
| `site` | 站點 / 廠區 | HR、FAC、Taipei |
| `dept_code` | 部門 | RD01、資訊部、總務課 |
| `table_number` | 桌次 | 5、VIP-1 |
| `is_business_trip` | 是否公差，填 `1`、`Y`、`YES`、`TRUE`、`是` 皆視為是 | Y |
| `participant_type` | 身份 | 員工、眷屬、外部廠商主要窗口、外部廠商 |
| `linked_employee_id` | 綁定員工工號；通常由眷屬規則自動產生，不一定要填 | A001 |
| `meal_type` | 餐點，可填代碼或完整描述 | A、B、C餐:滷味+綠豆冰沙 |
| `group_name` | 分組 | 第一組、A組 |

---

## 身份欄位規則

`participant_type` 支援以下值。

| Excel 可填值 | 系統內部值 | 顯示名稱 |
|---|---|---|
| `employee`、`emp`、`員工`、`同仁` | `employee` | 員工 |
| `dependent`、`dep`、`眷屬`、`家屬` | `dependent` | 眷屬 |
| `vendor_contact`、`external_vendor_contact`、`外部廠商主要窗口`、`廠商主要窗口`、`主要窗口` | `vendor_contact` | 外部廠商主要窗口 |
| `vendor`、`external_vendor`、`外部廠商`、`廠商` | `vendor` | 外部廠商 |

### 眷屬 employee_id 規則

如果 `participant_type` 是 `眷屬` / `dependent`：

- Excel 的 `employee_id` 代表「原員工工號」。
- 匯入時會把該值寫入 `linked_employee_id`。
- 系統會自動產生眷屬自己的 `employee_id`。
- 格式為：`原工號_流水號`。

範例：

| Excel name | Excel employee_id | Excel participant_type | 實際 employee_id | linked_employee_id |
|---|---|---|---|---|
| 王小明眷屬1 | A001 | 眷屬 | A001_1 | A001 |
| 王小明眷屬2 | A001 | 眷屬 | A001_2 | A001 |
| 王小明眷屬3 | A001 | 眷屬 | A001_3 | A001 |

---

## 餐點欄位規則

`meal_type` 會保留 Excel 的原始文字，不再限制只能是 A / B。

可填範例：

```text
A
B
C餐:滷味+綠豆冰沙
素食餐
兒童餐
```

資料庫欄位長度已由 migration 放大為 `String(100)`。部署時會透過：

```bash
flask db upgrade
```

自動套用 migration。

---

## 清除與重置資料

後台提供多種重置功能：

- 清除所有名單
- 重置報到狀態
- 重置抽獎狀態
- 重置單一獎項

因 `cancellation_log.checkin_list_id` 有 foreign key 指向 `checkin_list.id`，清除所有名單時必須先刪除 `cancellation_log`，再刪除 `checkin_list`。目前 `optimized_reset_list()` 已處理此順序，避免 PostgreSQL FK violation。

若要保留歷史活動資料，建議不要直接清除正式資料庫，改用 Neon branch 建立新活動資料庫。

---

## 年度活動資料策略

建議每一場大型活動使用獨立 Neon branch：

1. 在 Neon 建立新 branch。
2. 選擇只複製 schema，不複製舊活動資料。
3. 取得新 branch 的 `DATABASE_URL`。
4. 更新 Render 環境變數。
5. 重新部署並匯入新活動名單。

這樣可以保留舊活動資料，又能快速建立乾淨的新活動環境。

---

## 常見問題

### 匯入 Excel 時出現 Internal Server Error / SIGKILL

通常是 Render 免費方案記憶體不足或 Gunicorn timeout。

請確認 Start Command：

```bash
flask db upgrade && gunicorn -c gunicorn.conf.py --bind 0.0.0.0:$PORT run:app
```

並確認 `requirements.txt` 沒有重新加入 pandas / numpy。

### 清除所有名單時出現 ForeignKeyViolation

代表目前執行到舊的清除邏輯，或 Render 尚未部署到最新版本。最新版本會先刪 `cancellation_log` 再刪 `checkin_list`。

請重新部署 main，並確認 `app.__init__` 有覆寫：

```python
app.view_functions['admin.reset_list'] = admin_optimized_routes.optimized_reset_list
```

### 新餐點顯示不完整

請確認 Render 部署時有成功執行：

```bash
flask db upgrade
```

並確認 migration 已將 `checkin_list.meal_type` 放大到 `String(100)`。

---

## 重要實作備註

- `pandas.py` 是專案內的輕量相容層，用來避免實際載入 pandas / numpy。不要移除，除非整個匯入流程已完全不再參考 `import pandas as pd`。
- `app/admin/optimized_routes.py` 會 override 原本的後台匯入與清除名單 route。
- `app/admin/xlsx_stream.py` 是目前 Render 免費方案匯入大型 Excel 的主要最佳化來源。
- `gunicorn.conf.py` 是 Render 免費方案建議配置。
