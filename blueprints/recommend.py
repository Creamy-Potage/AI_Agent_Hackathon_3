import datetime
import json
from zoneinfo import ZoneInfo
from flask import Blueprint, render_template, Response, request
import os
import base64
import sqlalchemy
from db_config import db_conn
from vertexai.preview.vision_models import ImageGenerationModel
from google.cloud import storage
import csv
import io

import vertexai 
from vertexai.generative_models import ( 
    GenerationConfig, 
    GenerativeModel, 
    Tool, 
    grounding, 
)

from google.cloud.sql.connector import Connector

import logging
import google.cloud.logging

logger = logging.getLogger()
log_client = google.cloud.logging.Client()
log_client.setup_logging()
logging.basicConfig(level=logging.INFO)

recommend_bp = Blueprint('recommend', __name__, template_folder='templates')

# 設定
# Google Cloud プロジェクト設定
PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION")
REGION=os.environ.get('REGION')

# Cloud SQL データベース設定
BUCKET_WEB = os.environ.get("BUCKET_WEB") # 画像用バケット
BUCKET_RAG = os.environ.get("BUCKET_RAG") # RAGテキスト用バケット

# LLMモデル設定
MODEL_NAME = "gemini-1.5-flash"

def generate_souvenir_rag_suggestion_from_the_souvenir_candidates(user_condition: str):
    print("Cloud SQLからお土産データを取得中...")
    try:
        # GCSクライアントを初期化
        storage_client = storage.Client()
        
        # 環境変数からバケット名を取得
        bucket_name = os.environ.get("BUCKET_WEB") # RAGテキスト用のバケット
        bucket = storage_client.bucket(bucket_name)

        # GCSから取得したデータを格納するリスト
        souvenirs = []
        
        # CSVの各列に対応するキーを定義
        keys = ["id", "name", "image", "category", "purchase_location", "price", "expiration_date", "product_url", "rag_memo", "memo"]

        # バケット内のすべてのファイル（blob）を取得
        blobs = bucket.list_blobs()
        blob_list = list(blobs)

        for blob in blob_list:
            # テキストファイルのみを処理対象にする
            if blob.name.endswith('.txt'):
                # ファイルの内容を文字列としてダウンロード
                content = blob.download_as_string().decode('utf-8')
                
                if not content.strip():
                    print(f"⚠️ 警告: ファイル '{blob.name}' は空のためスキップします。")
                    continue

                string_io = io.StringIO(content)
                reader = csv.reader(string_io)

                for row in reader:
                    # ▼▼▼【修正点2】行が空でないかチェック▼▼▼
                    if not row:
                        continue
                    
                    # ▼▼▼【修正点3】列の数が期待通りかチェック▼▼▼
                    if len(row) == len(keys):
                        souvenir_dict = dict(zip(keys, row))
                        souvenirs.append(souvenir_dict)
                    else:
                        # どのファイルに問題があるかを出力
                        print(f"🚨 エラー: ファイル '{blob.name}' の列の数が一致しません。")


        print(f" {len(souvenirs)}件のお土産データをGCSから取得しました。")

        # データを文字列に変換する部分を辞書アクセス(s['key'])に変更
        souvenir_list_str = "\n".join([
            f"- 品名: {s['name']}, 画像: {s['image']}, カテゴリ: {s['category']}, 購入場所: {s['purchase_location']}, ひとつあたりの価格: {s['price']}円, 日持ち: {s['expiration_date']}, 商品URL: {s['product_url']}, メモ: {s['memo']}, RAGメモ: {s['rag_memo']}"
            for s in souvenirs
        ])

        prompt = f"""
あなたは、プロのお土産選びの専門家です。
お土産リストとユーザーの要望を分析し、最適な商品を推薦してください。
提案は、親しみやすく、魅力的な言葉で行ってください。

以下の情報を考慮して、提案を作成してください。
# ユーザーの要望
{user_condition}
・# 参考情報
・お土産候補リスト (社内DB):
{souvenir_list_str}

上記リストの中から、「ユーザーの要望」に最も合うお土産を2つ厳選し、JSON形式で提案してください。
特に、ユーザーの入力条件と、商品の特徴を結びつけて、「なぜそれがおすすめなのか」という理由が明確に伝わるように提案を作成してください。

参考情報として提供された「品名」と「画像」のURLを、JSONの`product_name`および`image`フィールドに、それぞれ正確にコピーしてください。これらの項目は絶対に`None`や空にしてはいけません。
各商品のキャッチコピーと紹介文は、相手の心に響くような魅力的なものにしてください。 

[
 {{
  "product_name": "品名", 
  "image": "画像", 
  "catch_copy": "キャッチコピー",
  "category": "カテゴリ",
  "description": "紹介文",
  "total_price": "ひとつあたりの価格 (円)", 
  "expiration_date": "日持ち", 
  "purchase_location": "購入場所",
  "product_url": "商品URL",
  "memo": "メモ"
  "rag_memo": "RAGメモ"
 }},
 {{
    ...
 }}
]
"""
        
        print("Vertex AI Geminiモデルで提案を生成中...")
        
        vertexai.init(project=PROJECT_ID, location=REGION)
        model = GenerativeModel(MODEL_NAME)
    
        generation_config = GenerationConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )
    
        response = model.generate_content(prompt, generation_config=generation_config)
        logging.info(f"Geminiからの生の回答: {response.text}")
        print("提案の生成が完了しました！")

        result_json = json.loads(response.text)
        print("生成されたお土産の提案:")
        print("----------------------------------------")
        print(json.dumps(result_json, indent=2, ensure_ascii=False))
        print("----------------------------------------")

        return result_json

    except Exception as e:
        logging.exception(f"RAGの提案生成中に予期せぬエラーが発生しました: {e}")
        print("LLMが有効なJSONを返しませんでした。生の出力を表示します:")
        return {"error": "提案の生成に失敗しました。詳細はサーバーログを確認してください。", "raw_response": str(e)}


def generate_suggestion_from_web_search(user_condition: str):
    print("🌐 Google検索を利用して提案を生成中...")
    try:
        vertexai.init(project=PROJECT_ID, location=REGION)
        
        tool = Tool.from_google_search_retrieval(grounding.GoogleSearchRetrieval())
        
        model = GenerativeModel(MODEL_NAME)

        prompt = f"""
あなたは、プロのお土産選びの専門家です。
ユーザーの要望を深く理解し、ユーザーが喜ぶ最高のお土産を提案することがあなたの使命です。
提案は、親しみやすく、魅力的な言葉で行ってください。

以下のユーザーの入力条件に最も合うお土産を、Web検索の結果を元に2つ厳選してください。
データベースの情報は考慮せず、一般的な視点から提案してください。
できるだけブランドやお店が重複しないように、多様な選択肢を提示してください。
# ユーザーの入力条件
{user_condition}

提案は、以下のJSON形式の配列で出力してください。
各商品のキャッチコピーと紹介文は、相手の心に響くような魅力的なものにしてください。

[
 {{
  "product_name": "品名",
  "catch_copy": "キャッチコピー",
  "category": "カテゴリ",
  "description": "紹介文",
  "total_price": "ひとつあたりの価格（円）",
  "purchase_location": "購入できる代表的な場所"
  "expiration_date": "日持ち", 
  "product_url": "商品URL",
  "memo": "メモ※商品の特徴、保存方法、個数、個包装か否か、アレルゲン、発売期間、飛行機等での制限など"
 }},
 {{
    ...
 }}
]
"""
        generation_config = GenerationConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )
    
        # ツール（Google検索）を有効にしてコンテンツを生成
        response = model.generate_content(
            prompt,
            tools=[tool],
            generation_config=generation_config
        )
        
        logging.info(f"Gemini (Web検索)からの生の回答: {response.text}")
        print("✅ Web検索による提案の生成が完了しました！")

        result_json = json.loads(response.text)

        return result_json

    except Exception as e:
        logging.exception(f"❌ Web検索による提案生成中にエラーが発生しました: {e}")
        return {"error": "Web検索による提案の生成に失敗しました。", "raw_response": str(e)}


def generate_db_suggestions_for_partner(user_condition: str):
    print("🔄 DBによる総合提案を生成中...")
    print("Cloud SQLからお土産データを取得中...")
    try:
        # GCSクライアントを初期化
        storage_client = storage.Client()
        
        # 環境変数からバケット名を取得
        bucket_name = os.environ.get("BUCKET_WEB") # RAGテキスト用のバケット
        bucket = storage_client.bucket(bucket_name)

        # GCSから取得したデータを格納するリスト
        souvenirs = []
        
        # CSVの各列に対応するキーを定義
        keys = ["id", "name", "image", "category", "purchase_location", "price", "expiration_date", "product_url", "rag_memo", "memo"]

        # バケット内のすべてのファイル（blob）を取得
        blobs = bucket.list_blobs()
        blob_list = list(blobs)

        for blob in blob_list:
            # テキストファイルのみを処理対象にする
            if blob.name.endswith('.txt'):
                # ファイルの内容を文字列としてダウンロード
                content = blob.download_as_string().decode('utf-8')
                
                if not content.strip():
                    print(f"⚠️ 警告: ファイル '{blob.name}' は空のためスキップします。")
                    continue

                string_io = io.StringIO(content)
                reader = csv.reader(string_io)

                for row in reader:
                    # ▼▼▼【修正点2】行が空でないかチェック▼▼▼
                    if not row:
                        continue
                    
                    # ▼▼▼【修正点3】列の数が期待通りかチェック▼▼▼
                    if len(row) == len(keys):
                        souvenir_dict = dict(zip(keys, row))
                        souvenirs.append(souvenir_dict)
                    else:
                        # どのファイルに問題があるかを出力
                        print(f"🚨 エラー: ファイル '{blob.name}' の列の数が一致しません。")

        print(f" {len(souvenirs)}件のお土産データをGCSから取得しました。")

        # データを文字列に変換する部分を辞書アクセス(s['key'])に変更
        souvenir_list_str = "\n".join([
            f"- 品名: {s['name']}, 画像: {s['image']}, カテゴリ: {s['category']}, 購入場所: {s['purchase_location']}, ひとつあたりの価格: {s['price']}円, 日持ち: {s['expiration_date']}, 商品URL: {s['product_url']}, メモ: {s['memo']}, RAGメモ: {s['rag_memo']}"
            for s in souvenirs
        ])

        prompt = f"""
あなたは、プロのお土産選びの専門家です。
ユーザーの要望+送り相手を理解し、あなたが持つ情報から、ユーザーの要望に含まれる送り相手が喜ぶ最高のお土産を提案することがあなたの使命です。

以下の情報を考慮して、提案を作成してください。

# ユーザーの要望+送り相手
{user_condition}

# 参考情報
・お土産候補リスト (社内DB):
{souvenir_list_str}

上記の「ユーザーの要望+送り相手」をすべて踏まえた上で、送り相手が最も喜びそうなお土産を「お土産候補リスト」の中から、合計2つ厳選してください。
参考情報として提供された「品名」と「画像」のURLを、JSONの`product_name`および`image`フィールドに、それぞれ正確にコピーしてください。これらの項目は絶対に`None`や空にしてはいけません。
各商品のキャッチコピーと紹介文は、相手の心に響くような魅力的なものにしてください。 
提案は、以下のJSON形式の配列で出力してください。

[
 {{
  "product_name": "品名",
  "image": "画像", 
  "catch_copy": "キャッチコピー",
  "category": "カテゴリ",
  "description": "紹介文",
  "total_price": "ひとつあたりの価格（円）",
  "purchase_location": "購入できる代表的な場所"
  "expiration_date": "日持ち", 
  "product_url": "商品URL",
  "memo": "メモ※商品の特徴、保存方法、個数、個包装か否か、アレルゲン、発売期間、飛行機等での制限など"
 }},
 {{
    ...
 }}
]
"""
        vertexai.init(project=PROJECT_ID, location=REGION)
        model = GenerativeModel(MODEL_NAME)

        generation_config = GenerationConfig(
            temperature=0.7,
            response_mime_type="application/json",
        )
    
        response = model.generate_content(prompt, generation_config=generation_config)
        
        logging.info(f"Gemini (総合提案)からの生の回答: {response.text}")
        print("✅ 総合提案の生成が完了しました！")

        result_json = json.loads(response.text)
        return result_json

    except Exception as e:
        logging.exception(f"❌ 総合提案の生成中にエラーが発生しました: {e}")
        return {"error": "総合提案の生成に失敗しました。", "raw_response": str(e)}

def generate_web_suggestions_for_partner(user_condition: str):
    print("🔄 Web検索による総合提案を生成中...")
    try:
        
        # --- AIへの指示 (プロンプト) ---
        vertexai.init(project=PROJECT_ID, location=REGION)
        tool = Tool.from_google_search_retrieval(grounding.GoogleSearchRetrieval())
        model = GenerativeModel(MODEL_NAME)

        prompt = f"""
あなたは、プロのお土産選びの専門家です。
ユーザーの要望+送り相手を理解し、Webでの検索から、ユーザーの要望に含まれる送り相手が喜ぶ最高のお土産を提案することがあなたの使命です。

以下の情報を考慮して、提案を作成してください。
# ユーザーの要望+送り相手
{user_condition}

上記の「ユーザーの要望+送り相手」を踏まえ、Web検索を元に、送り相手が最も喜びそうなお土産を2つ厳選してください。
提案は、以下のJSON形式の配列で出力してください。

[
 {{
  "product_name": "品名",
  "catch_copy": "キャッチコピー",
  "category": "カテゴリ",
  "description": "紹介文",
  "total_price": "ひとつあたりの価格（円）",
  "purchase_location": "購入できる代表的な場所"
  "expiration_date": "日持ち", 
  "product_url": "商品URL",
  "memo": "メモ※商品の特徴、保存方法、個数、個包装か否か、アレルゲン、発売期間、飛行機等での制限など"
 }},
 {{
    ...
 }}
]
"""
        generation_config = GenerationConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )
    
        response = model.generate_content(
            prompt,
            tools=[tool],
            generation_config=generation_config
        )
        
        logging.info(f"Gemini (総合提案)からの生の回答: {response.text}")
        print("✅ 総合提案の生成が完了しました！")

        result_json = json.loads(response.text)
        return result_json

    except Exception as e:
        logging.exception(f"❌ 総合提案の生成中にエラーが発生しました: {e}")
        return {"error": "総合提案の生成に失敗しました。", "raw_response": str(e)}


@recommend_bp.route('/recommend/input')
def recommend_input():
    query = """
        SELECT
            giftee_uid,
            name,
            relationship,
            area,
            gender,
            number_of_people,
            favorite,
            dislikes,
            caution,
            memo,
            DATE_FORMAT(created_at, '%Y/%m/%d %H:%i:%s') AS created_at,
            DATE_FORMAT(updated_at, '%Y/%m/%d %H:%i:%s') AS updated_at
        FROM
            giftee;
    """
    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            giftees = conn.execute(stmt).fetchall()
    except Exception as e:
        logger.error(e)
        return Response(
             status=500,
             response="transaction error!",
        )
    return render_template('recommend/input.html', giftees=giftees)

@recommend_bp.route('/recommend/propose', methods=['POST'])
def propose():
    print("--- ★★★ PROPOSE関数が呼び出されました！ ★★★ ---")
    selected_giftee_uids = request.form.getlist('giftee_checkbox')
    condition_text = request.form.get('condition_text')

    db_suggestions = None
    web_suggestions = None
    db_suggestions_for_partner = None
    web_suggestions_for_partner = None

    giftee_info_text_for_partner = ""
    giftee_info_text_for_not_partner = ""

    all_giftee_uids = []
    try:
        with db_conn.connect() as conn:
            query = sqlalchemy.text("SELECT giftee_uid FROM giftee")
            results = conn.execute(query).fetchall()
            all_giftee_uids = [str(row[0]) for row in results] # 比較のため文字列に変換
    except Exception as e:
        logging.exception(f"全相手情報のUID取得中にエラー: {e}")

    selected_giftee_uids_str = [str(uid) for uid in selected_giftee_uids]
    unselected_giftee_uids = list(set(all_giftee_uids) - set(selected_giftee_uids_str))

    checked_giftee_text = ""
    # チェックされた相手がいる場合
    if selected_giftee_uids:
        try:
            # UIDのリストを元に、人の名前をDBから取得
            with db_conn.connect() as conn:
                # SQLインジェクションを防ぐため、IN句を安全に構築
                placeholders = ','.join([f':uid{i}' for i, _ in enumerate(selected_giftee_uids)])
                params = {f'uid{i}': uid for i, uid in enumerate(selected_giftee_uids)}
                query = sqlalchemy.text(f"SELECT * FROM giftee WHERE giftee_uid IN ({placeholders})")
                results = conn.execute(query, params).fetchall()
                for person in results:
                    giftee_info_text_for_partner += f"・渡したい相手: {person.name} ({person.relationship}), 好きなもの: {person.favorite}, 嫌いなもの: {person.dislikes}\n"

        except Exception as e:
            logging.exception(f"チェックされたお土産の取得中にエラー: {e}")
            # エラーが発生しても処理は続行
    
    # テキストエリアの内容と、チェックされたお土産の情報を結合

        full_user_condition = f"{giftee_info_text_for_partner}・ユーザーからの追加要望: {condition_text}"
        
        # 新しい「総合提案」関数を呼び出す
        db_suggestions_for_partner = generate_db_suggestions_for_partner(user_condition=full_user_condition)
        web_suggestions_for_partner = generate_web_suggestions_for_partner(user_condition=full_user_condition)
        
        try:
            with db_conn.connect() as conn:
                # SQLインジェクションを防ぐため、IN句を安全に構築
                placeholders = ','.join([f':uid{i}' for i, _ in enumerate(unselected_giftee_uids)])
                params = {f'uid{i}': uid for i, uid in enumerate(unselected_giftee_uids)}
                query = sqlalchemy.text(f"SELECT * FROM giftee WHERE giftee_uid IN ({placeholders})")
                results = conn.execute(query, params).fetchall()
                for person in results:
                    giftee_info_text_for_not_partner += f"・候補者（送りたい相手として特定されていない）: {person.name} ({person.relationship}), 好きなもの: {person.favorite}, 嫌いなもの: {person.dislikes}\n"
        except Exception as e:
            logging.exception(f"対象の相手情報の取得中にエラー: {e}")

        # 「送りたい人以外」という文脈をAIに与える
        user_condition_for_ai = f"{giftee_info_text_for_not_partner}・ユーザーからの追加要望: {condition_text}"

        # AI関数を呼び出し
        db_suggestions_for_not_partner = generate_db_suggestions_for_partner(user_condition=user_condition_for_ai)
        web_suggestions_for_not_partner = generate_web_suggestions_for_partner(user_condition=user_condition_for_ai)

        # テンプレートには、suggestions変数だけを渡す
        return render_template('recommend/result.html', 
                               condition=condition_text, 
                               db_suggestions_for_partner=db_suggestions_for_partner,
                               web_suggestions_for_partner=web_suggestions_for_partner,
                               db_suggestions_for_not_partner=db_suggestions_for_not_partner,
                               web_suggestions_for_not_partner=web_suggestions_for_not_partner,
                               selected_uids=selected_giftee_uids)

    else:
        db_suggestions = generate_souvenir_rag_suggestion_from_the_souvenir_candidates(user_condition=condition_text)

        web_suggestions = generate_suggestion_from_web_search(user_condition=condition_text)

        return render_template('recommend/result.html', condition=condition_text, db_suggestions=db_suggestions, web_suggestions=web_suggestions, selected_uids=selected_giftee_uids)