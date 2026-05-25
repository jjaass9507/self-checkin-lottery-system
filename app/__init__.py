# app/__init__.py
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

# 1. 在 '工廠' 外面先實例化 db 和 migrate
#    但先不綁定 app
db = SQLAlchemy()
migrate = Migrate()

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

    # 5. 注入全域模板變數
    @app.context_processor
    def inject_settings():
        try:
            from app.models import AppSetting
            s = AppSetting.query.get('lottery_enabled')
            lottery_enabled = (s.value == 'true') if s else True
        except Exception:
            lottery_enabled = True
        return {'lottery_enabled': lottery_enabled}

    @app.after_request
    def inject_display_helpers(response):
        # self_checkin.html / self_query.html 是獨立模板，沒有繼承 base.html。
        # 這裡統一把顯示輔助 JS 注入所有 HTML 頁面，確保身份、餐點、部門截字規則一致。
        content_type = response.headers.get('Content-Type', '')
        if response.status_code == 200 and 'text/html' in content_type:
            body = response.get_data(as_text=True)
            helper_tag = '<script src="/static/js/display_helpers.js?v=20260525"></script>'
            if helper_tag not in body and '</body>' in body:
                body = body.replace('</body>', f'{helper_tag}\n</body>')
                response.set_data(body)
                response.headers['Content-Length'] = str(len(response.get_data()))
        return response

    # 6. 建立一個首頁路由 (可選)
    @app.route('/')
    def index():
        return "系統已啟動。請訪問 /admin, /checkin, 或 /lottery"

    return app