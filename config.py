import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv()  # 讀取 .env 檔案

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    
    # (*** 修改這行 ***)
    # 優先讀取 DATABASE_URL，如果沒有才使用本地 event.db
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'event.db')
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # (新增) 設定一組簡單的後台密碼
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')