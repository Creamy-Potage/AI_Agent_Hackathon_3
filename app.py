import os
from flask import Flask, render_template, Response
from zoneinfo import ZoneInfo
from blueprints.giftee import giftee_bp
from blueprints.souvenir import souvenir_bp
from blueprints.recommend import recommend_bp
import sqlalchemy
import vertexai 
from vertexai.generative_models import ( 
    GenerationConfig, 
    GenerativeModel, 
    Tool, 
    grounding, 
)
from db_config import db_conn

# Flaskアプリのインスタンスを作成
app = Flask(__name__)

app.register_blueprint(giftee_bp)
app.register_blueprint(souvenir_bp)
app.register_blueprint(recommend_bp)

@app.route('/')
def index():
    # templatesフォルダにあるindex.htmlをレンダリングして返す
    return render_template('index.html')

# このファイルが直接実行された場合に開発サーバーを起動
#if __name__ == '__main__':
    # 環境変数PORTからポート番号を取得。なければ8081を使う
#    port = int(os.environ.get("PORT", 8081))
    # host="0.0.0.0" と取得したportを指定して起動
#    app.run(host="0.0.0.0", port=port)
