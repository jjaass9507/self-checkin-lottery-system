import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # (關鍵修改)
    # 優先讀取環境變數 'DATABASE_URL' (雲端用)
    # 如果讀不到，就用原本的 sqlite (本機用)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'event.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 設定 Secret Key (雲端部署建議要有)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-local-testing'