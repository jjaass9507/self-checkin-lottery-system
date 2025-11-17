# config.py
import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # 新增這一行！
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-hard-to-guess-string' # 建議未來用環境變數

    # 資料庫設定
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'event.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False