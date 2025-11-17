from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models import CheckinList, Prize, Winner
from datetime import datetime
import random # <-- (1) 匯入 random
from sqlalchemy.orm import joinedload # (優化查詢用)

bp = Blueprint('lottery', __name__)

# --- (A) 抽獎大螢幕 主頁面 ---
@bp.route('/screen')
def lottery_screen():
    return render_template('lottery/screen.html')

# --- (B) 完整中獎名單 (日誌) 頁面 ---
@bp.route('/winners')
def winners_list():
    # (*** 核心查詢 ***)
    # 1. 取得所有「獎項」
    # 2. 預先載入 (joinedload) 每個獎項的「中獎紀錄 (winners)」
    # 3. 預先載入 (joinedload) 每筆中獎紀錄的「報到者 (checkin_item)」
    # 這樣可以避免 N+1 查詢，效能極高
    prizes_with_winners = Prize.query.options(
        joinedload(Prize.winners).joinedload(Winner.checkin_item)
    ).order_by(Prize.id).all()
    
    return render_template('lottery/winners.html', prizes_with_winners=prizes_with_winners)

# --- (C) 核心 API：(前端) 獲取當前狀態 ---
@bp.route('/api/get_data')
def api_get_data():
    try:
        # 1. 計算抽獎池人數
        available_count = CheckinList.query.filter_by(
            status='CheckedIn',
            has_won=False
        ).count()

        # 2. 獲取所有獎項
        prizes = Prize.query.order_by(Prize.id).all()
        
        # 3. 組合獎項資料 (並檢查是否已抽出)
        prize_data = []
        for p in prizes:
            is_drawn = bool(p.winners) # 檢查 p.winners 列表是否為空
            prize_data.append({
                "id": p.id,
                "name": p.prize_name,
                "quantity": p.quantity,
                "is_drawn": is_drawn # 告訴前端這個獎抽過了沒
            })
            
        return jsonify({
            "available_count": available_count,
            "prizes": prize_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- (D) (*** 最關鍵 API ***)：執行抽獎 ---
@bp.route('/api/draw', methods=['POST'])
def api_draw():
    data = request.get_json()
    prize_id = data.get('prize_id')
    
    if not prize_id:
        return jsonify({"success": False, "message": "未指定獎項ID"}), 400

    # (*** 啟動資料庫交易 ***)
    try:
        # 1. 鎖定獎項 (確保只有一個人能抽)
        # with_for_update() 會鎖定該行，直到 commit
        prize = Prize.query.with_for_update().get(prize_id) 
        
        if not prize:
            return jsonify({"success": False, "message": "找不到該獎項"}), 404
        
        # 2. 檢查是否已抽過 (以防萬一)
        if prize.winners:
            return jsonify({"success": False, "message": "此獎項已被抽過！"}), 400

        quantity_to_draw = prize.quantity
        
        # 3. 找出抽獎池
        pool = CheckinList.query.filter_by(
            status='CheckedIn',
            has_won=False
        ).all()
        
        # 4. 檢查人數是否足夠
        if len(pool) < quantity_to_draw:
            return jsonify({
                "success": False, 
                "message": f"抽獎失敗：抽獎池人數不足！ (僅 {len(pool)} 人，需要 {quantity_to_draw} 人)"
            }), 400
        
        # 5. (*** 核心 ***) 隨機選取中獎者
        winners_list = random.sample(pool, quantity_to_draw)
        
        drawn_winners_info = []
        
        # 6. (*** 核心 ***) 標記中獎並寫入 Log
        for person in winners_list:
            # a. 標記此人已中獎 (從抽獎池移除)
            person.has_won = True 
            
            # b. 建立中獎紀錄
            new_win = Winner(
                checkin_list_id=person.id,
                prize_id=prize.id,
                draw_timestamp=datetime.now() # 記錄抽出時間
            )
            db.session.add(new_win)
            
            # c. 準備回傳給前端
            drawn_winners_info.append({
                "name": person.name,
                "employee_id": person.employee_id
            })

        # 7. (*** 核心 ***) 提交交易
        db.session.commit()
        
        return jsonify({
            "success": True,
            "prize_name": prize.prize_name,
            "winners": drawn_winners_info
        })

    except Exception as e:
        # 8. (*** 核心 ***) 如果發生任何錯誤，回滾所有操作
        db.session.rollback()
        return jsonify({"success": False, "message": f"伺服器發生嚴重錯誤：{e}"}), 500