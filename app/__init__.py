# app/__init__.py
from flask import Flask, request, jsonify, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

# 1. 在 '工廠' 外面先實例化 db 和 migrate
#    但先不綁定 app
db = SQLAlchemy()
migrate = Migrate()

FILTER_MODE_LABELS = {
    'status': '報到狀態',
    'site': '站點 Site',
    'dept': '部門代碼',
    'win': '中獎狀態',
    'prize': '特定獎項',
    'participant_type': '身分類別',
    'meal': '餐點類型',
    'group': '組別',
}
FILTER_MODE_KEYS = list(FILTER_MODE_LABELS.keys())

def create_app(config_class=Config):
    # 2. 建立 App 實例
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 3. 將 db 和 migrate 綁定到 app
    db.init_app(app)
    migrate.init_app(app, db)

    # 4. 註冊您的 Blueprints (mini-apps)
    
    # 註冊 Admin 藍圖
    from app.admin.routes import bp as admin_bp
    from app.admin import optimized_routes as admin_optimized_routes
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.view_functions['admin.import_page'] = admin_optimized_routes.optimized_import_page
    app.view_functions['admin.reset_list'] = admin_optimized_routes.optimized_reset_list

    # 註冊 Checkin 藍圖
    from app.checkin.routes import bp as checkin_bp
    app.register_blueprint(checkin_bp, url_prefix='/checkin')

    # 註冊 Lottery 藍圖
    from app.lottery.routes import bp as lottery_bp
    app.register_blueprint(lottery_bp, url_prefix='/lottery')

    def get_filter_modes():
        from app.models import AppSetting
        modes = {}
        for key in FILTER_MODE_KEYS:
            setting = AppSetting.query.get(f'filter_multi_{key}')
            modes[key] = (setting.value != 'false') if setting else True
        return modes

    @app.route('/checkin/api/toggle_vendor_gift', methods=['POST'])
    def toggle_vendor_gift():
        from app.models import CheckinList
        try:
            data = request.get_json() or {}
            person_id = data.get('id')
            claimed = data.get('claimed')
            person = CheckinList.query.get(person_id)
            if not person:
                return jsonify({'success': False, 'message': '找不到人員'}), 404
            if person.participant_type != 'vendor_contact':
                return jsonify({'success': False, 'message': '只有外部廠商主要窗口需要確認公司禮品'}), 400
            person.vendor_gift_claimed = bool(claimed)
            db.session.commit()
            status_text = '已領取' if person.vendor_gift_claimed else '未領取'
            return jsonify({
                'success': True,
                'message': f'{person.name} 公司禮品狀態已更新為{status_text}',
                'vendor_gift_claimed': person.vendor_gift_claimed,
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/admin/filter_modes', methods=['POST'])
    def toggle_filter_modes():
        from app.models import AppSetting
        for key in FILTER_MODE_KEYS:
            value = request.form.get(f'filter_multi_{key}', 'true')
            value = 'false' if value == 'false' else 'true'
            setting = AppSetting.query.get(f'filter_multi_{key}')
            if setting:
                setting.value = value
            else:
                db.session.add(AppSetting(key=f'filter_multi_{key}', value=value))
        db.session.commit()
        flash('報到名單篩選模式已更新', 'success')
        return redirect(url_for('admin.import_page'))

    @app.route('/admin/api/filter_modes')
    def filter_modes_api():
        return jsonify({'success': True, 'filter_modes': get_filter_modes(), 'filter_mode_labels': FILTER_MODE_LABELS})

    # 5. 注入全域模板變數
    @app.context_processor
    def inject_settings():
        try:
            from app.models import AppSetting
            s = AppSetting.query.get('lottery_enabled')
            lottery_enabled = (s.value == 'true') if s else True
        except Exception:
            lottery_enabled = True
        try:
            filter_modes = get_filter_modes()
        except Exception:
            filter_modes = {key: True for key in FILTER_MODE_KEYS}
        return {'lottery_enabled': lottery_enabled, 'filter_modes': filter_modes, 'filter_mode_labels': FILTER_MODE_LABELS}

    # 6. 建立一個首頁路由 (可選)
    @app.route('/')
    def index():
        return "系統已啟動。請訪問 /admin, /checkin, 或 /lottery"

    return app
