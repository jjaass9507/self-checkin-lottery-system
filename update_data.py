import os
import pandas as pd
from app import create_app, db
from app.models import CheckinList

# 設定要讀取的 Excel 檔案名稱
# 請修改成您實際的檔名，例如 '工號與桌次資料整理.xlsx'
EXCEL_FILENAME = 'D:\Dowload\工號與桌次資料整理.xlsx'

app = create_app()

def update_table_data():
    # 檢查檔案是否存在
    if not os.path.exists(EXCEL_FILENAME):
        print(f"錯誤：找不到檔案 '{EXCEL_FILENAME}'。")
        print("請確認檔案名稱是否正確，並已放在專案根目錄下。")
        return

    with app.app_context():
        print(f"--- 開始讀取 {EXCEL_FILENAME} 並更新資料 ---")
        
        updated_count = 0
        not_found_count = 0
        
        try:
            # 使用 pandas 讀取 Excel
            # dtype=str 強制將所有欄位視為字串，避免工號開頭的 0 被吃掉 (例如 00123 變成 123)
            df = pd.read_excel(EXCEL_FILENAME, dtype=str)
            
            # 清理欄位名稱 (移除可能的前後空白)
            df.columns = [c.strip() for c in df.columns]
            
            # 尋找對應欄位
            # 支援常見的命名：'工號', 'employee_id' / '桌次', 'table'
            id_col = next((c for c in df.columns if '工號' in c or 'employee_id' in c), None)
            table_col = next((c for c in df.columns if '桌次' in c or 'table' in c), None)

            if not id_col or not table_col:
                print(f"錯誤：在 Excel 中找不到 '工號' 或 '桌次' 的欄位。")
                print(f"讀到的欄位：{df.columns.tolist()}")
                return

            print(f"對應欄位 -> 工號: [{id_col}], 桌次: [{table_col}]")

            # 逐列處理
            for index, row in df.iterrows():
                # 取得資料並去除空白
                # 處理 NaN (空值)：Pandas 的空值是 float('nan') 或 pd.NA，轉字串會變成 'nan' 或 '<NA>'
                # 所以要先判斷是否為空
                
                raw_id = row[id_col]
                raw_table = row[table_col]

                # 簡單的清理邏輯
                emp_id = str(raw_id).strip() if pd.notna(raw_id) else None
                table_val = str(raw_table).strip() if pd.notna(raw_table) else None

                # 如果工號是 'nan' 字串 (有時轉型會發生)，也視為無效
                if not emp_id or emp_id.lower() == 'nan':
                    continue

                # 搜尋資料庫
                person = CheckinList.query.filter_by(employee_id=emp_id).first()
                
                if person:
                    # 如果桌次是空的或 'nan'，就不更新或設為 None? 這裡假設是要寫入資料
                    if table_val and table_val.lower() != 'nan':
                        person.table_number = table_val
                        updated_count += 1
                        # print(f"更新: {person.name} ({emp_id}) -> 桌次: {table_val}")
                else:
                    not_found_count += 1
                    # 只有當真的有桌次資料時才顯示查無此人，避免顯示一堆空行
                    if table_val and table_val.lower() != 'nan':
                        print(f"查無此人: {emp_id} (Excel 桌次: {table_val})")
            
            # 提交變更
            db.session.commit()
            print("--------------------------------------------------")
            print(f"更新完成！")
            print(f"成功更新: {updated_count} 筆")
            print(f"查無工號: {not_found_count} 筆")

        except Exception as e:
            db.session.rollback()
            print(f"發生錯誤: {e}")

if __name__ == '__main__':
    update_table_data()