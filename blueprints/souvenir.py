import datetime

from flask import Blueprint, render_template, Response, request, jsonify, redirect, url_for

import sqlalchemy
from db_config import db_conn
from zoneinfo import ZoneInfo
import logging
from google.cloud import storage
import os, uuid
import google.cloud.logging

logger = logging.getLogger()
log_client = google.cloud.logging.Client()
log_client.setup_logging()

import vertexai
from vertexai.generative_models import (
    GenerationConfig,
    GenerativeModel,
    Tool,
    grounding,
    Part
)

vertexai.init(location="asia-northeast1")

# 初期化
PROJECT_ID = os.environ.get('PROJECT_ID')
REGION = os.environ.get('REGION')
LOCATION = os.environ.get("LOCATION")
INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME")
#REGION=os.environ.get('REGION')
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")
BUCKET_WEB = os.environ.get("BUCKET_WEB") # 画像用バケット (旧 BUCKET_NAME)
BUCKET_RAG = os.environ.get("BUCKET_RAG")

#vertexai.init(location=REGION, project=PROJECT_ID)
storage_client = storage.Client(project=PROJECT_ID)

vertexai.init(project=PROJECT_ID, location=REGION)
multimodal_model = GenerativeModel("gemini-1.5-flash")

#BUCKET_WEB = "rec-svn1" # 画像用バケット
bucket_name_rag = os.environ.get('BUCKET_WEB')

def upload_to_gcs(file, filename):
    """ファイルをGCSにアップロードし、公開URLを返す"""
    if not file:
        return None
    
    client = storage.Client()
    bucket = client.bucket(BUCKET_WEB)
    blob = bucket.blob(filename)
    
    blob.upload_from_file(file)
    # ❗️重要：バケットが一般公開設定になっている必要があります
    return blob.public_url

# お土産情報を生成する汎用関数
def get_souvenir_info(souvenir_name: str, item_name: str) -> str:
    """指定された項目について、お土産の情報を生成する汎用関数"""
    model = GenerativeModel("gemini-1.5-flash")
    tool = Tool.from_google_search_retrieval(grounding.GoogleSearchRetrieval())
    
    prompts = {
        "category": f"「{souvenir_name}」のカテゴリを、「お菓子」「雑貨」「飲み物」のように一言で教えて。見つからない時は、「不明」と返してください。",
        "price": f"""
            あなたは、お土産の「1箱あたりの税込価格」を計算するAIです。以下のルールに厳密に従って、最終的な計算結果の【数値のみ】を回答してください。

            # ルール
            - **最重要**: 必ず「1箱あたりの価格」を計算してください。複数個入りの商品を調査してください。
            - **価格帯**: 複数の価格帯（例: 5個入り、10個入り）が見つかった場合は、その平均値を出してください。
            - **単品**: その商品の価格を回答してください。
            - **不明な場合**: 価格が見つからない、または計算できない場合は、例外なく「0」と回答してください。

            # 回答例
            - 12枚入り1200円のお菓子A:1200
            - 1個1200円のキーホルダー:1200
            - 5個入り600円、10個入り1000円のお菓子B:800

            # 計算対象
            {souvenir_name}
        """,
        "purchase_location": f"""
            あなたはお土産の専門家です。お土産の名前が示されたら、そのお土産を購入できる最も代表的な場所を一つだけ回答してください。

            # 回答ルール
            -   まず、そのお土産を象徴する【都道府県名や地域名】（例：北海道、沖縄県）を最優先で考えてください。
            -   もし、特定の空港や駅（例：東京駅、博多駅）でしか買えない限定品であったり、その場所での購入が圧倒的に有名である場合に限り、例外的にその【施設名】を回答してください。
            -   回答は場所の名前のみとし、余計な説明は一切含めないでください。
            -   見つからない場合は「不明」と回答してください。

            # 回答例
            -   白い恋人 → 北海道
            -   東京ばな奈 → 東京駅
            -   萩の月 → 宮城県
            -   ちんすこう → 沖縄県
            -   赤福餅 → 三重県

            # 質問
            お土産の名前：{souvenir_name}
        """,
        "expiration_date": f"「{souvenir_name}」の日持ちを「賞味期限：約20日」「消費期限：製造日含む3日」「不明」のように一言で回答してください。見つからない時は「不明」とのみ回答してください。",
        "product_url": f"「{souvenir_name}」の公式サイトの商品ページのURLを「https://www.example.net」のようにただ一つのURLのみ出力してください。見つからない時は、「不明」と返してください。",
        # "rag_memo": f"「{souvenir_name}」について200文字程度で分かりやすく簡潔に説明して。説明には商品の特徴、保存方法（常温、冷蔵、冷凍など）、個数（10個入り、20個入りなどバリエーションがある場合はすべて記載）、個包装か否か、アレルゲン、販売期間、飛行機などでの制限を含めてください。見つからない時は、「特になし」と返してください。"
        "rag_memo": f"""
            あなたは、お土産情報の検索を専門とする優秀なアシスタントです。「{souvenir_name}」について、以下の情報を含めて200字以内で回答してください。
            #含めるべき情報
            ・商品の特徴
            ・保存方法（常温、冷蔵、冷凍など）
            ・個数（10個入り、20個入りなどバリエーションがある場合はすべて記載）
            ・個包装か否か
            ・アレルゲン
            ・販売期間
            ・飛行機等での制限
            #注意事項
            ・商品が見つからないときは「特になし」と返してください。
            ・具体的な商品名ではなく品目などがユーザーから入力された場合も、ユーザーに対して追加の質問はせずに一般的な情報で回答してください。
            ・必ず200字以内で回答してください。
        """
    }
    
    prompt = prompts.get(item_name, "")
    if not prompt: return ""

    response = model.generate_content(
        prompt,
        tools=[tool],
        generation_config=GenerationConfig(temperature=0.0),
    )
    return response.candidates[0].content.parts[0].text

souvenir_bp = Blueprint('souvenir', __name__, template_folder='templates')

@souvenir_bp.route('/souvenir/get_name_from_image', methods=['POST'])
def get_name_from_image():
    """アップロードされた画像から品名をAIで推定して返すAPI"""
    if 'image' not in request.files:
        return jsonify({"error": "No image file found"}), 400
    
    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({"error": "No image selected"}), 400

    try:
        # メモに書かれていた画像認識ロジックをここに入れる
        image_bytes = image_file.read()
        image_part = Part.from_data(data=image_bytes, mime_type=image_file.mimetype)
        
        # モデルの初期化（ファイル上部で定義済みのmultimodal_modelを使う）
        prompt = "この画像に写っているお土産の商品名を日本語で教えて下さい。特定できない場合は「不明」と答えてください。出力は商品名だけでお願いします。"
        
        response = multimodal_model.generate_content([image_part, prompt])
        item_name = response.text.strip()
        
        # 結果をJSON形式で返す
        return jsonify({"product_name": item_name})

    except Exception as e:
        logger.exception(f"画像からの品名推定エラー: {e}")
        return jsonify({"error": "Failed to get name from image"}), 500

@souvenir_bp.route('/souvenir/list')
def souvenir_list():
    # URLのクエリパラメータから検索キーワードを取得
    search_keyword = request.args.get('search_keyword', '')

    query = """
        SELECT
            souvenir_uid,
            name,
            image,
            category,
            purchase_location,
            price,
            expiration_date,
            product_url,
            memo,
            rag_memo,
            DATE_FORMAT(created_at, '%Y/%m/%d %H:%i:%s') AS created_at,
            DATE_FORMAT(updated_at, '%Y/%m/%d %H:%i:%s') AS updated_at
        FROM
            souvenir
    """

    parameters = {}
    
    # 検索キーワードがある場合、WHERE句を追加してLIKE検索を行う
    if search_keyword:
        query += " WHERE search_text LIKE :search_keyword"
        parameters['search_keyword'] = f"%{search_keyword}%"

    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            souvenirs = conn.execute(stmt, parameters).fetchall()
    except Exception as e:
        logger.error(e)
        return Response(
             status=500,
             response="transaction error!",
        )
    return render_template('souvenir/list.html', souvenirs=souvenirs, search_keyword=search_keyword)

@souvenir_bp.route('/souvenir/detail')
def souvenir_detail():
    souvenir_uid = request.args.get('souvenir_uid', type=int)

    query = """
        SELECT
            souvenir_uid,
            name,
            image,
            category,
            purchase_location,
            price,
            expiration_date,
            product_url,
            memo,
            rag_memo,
            search_text,
            search_file,
            DATE_FORMAT(created_at, '%Y/%m/%d %H:%i:%s') AS created_at,
            DATE_FORMAT(updated_at, '%Y/%m/%d %H:%i:%s') AS updated_at
        FROM
            souvenir
        WHERE
            souvenir_uid = :souvenir_uid;
    """

    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            res = conn.execute(stmt, parameters={"souvenir_uid": souvenir_uid})
            souvenir = res.fetchone()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    return render_template('souvenir/detail.html',souvenir=souvenir)

@souvenir_bp.route('/souvenir/create_input')
def souvenir_create_input():
    return render_template('souvenir/create_input.html')

@souvenir_bp.route('/souvenir/create_action', methods=['POST'])
def souvenir_create_action():
    name = request.form.get('name')
    image_file = request.files.get('image')
    category = request.form.get('category')
    purchase_location = request.form.get('purchase_location')
    price = request.form.get('price', type=int)
    expiration_date = request.form.get('expiration_date')
    product_url = request.form.get('product_url')
    memo = request.form.get('memo')
    rag_memo = request.form.get('rag_memo')

    # --- 変数を初期化 ---
    image_url = None
    search_file_path = None
    new_souvenir_id = None

    try:
        with db_conn.connect() as conn:
            # --- 2. まず画像とRAGファイルパスを「空」の状態でDBにINSERT ---
            search_text = f'{name},{category},{purchase_location},{memo},{rag_memo}'
            current_date = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y-%m-%d %H:%M:%S')

            query_insert = """
                INSERT INTO souvenir (name, category, purchase_location, price, expiration_date, product_url, memo, rag_memo, search_text, created_at, updated_at) 
                VALUES (:name, :category, :purchase_location, :price, :expiration_date, :product_url, :memo, :rag_memo, :search_text, :created_at, :updated_at)
            """
            stmt_insert = sqlalchemy.text(query_insert)
            
            result = conn.execute(
                stmt_insert, parameters={
                    "name": name, "category": category, "purchase_location": purchase_location, 
                    "price": price, "expiration_date": expiration_date, "product_url": product_url, 
                    "memo": memo, "rag_memo": rag_memo, "search_text": search_text,
                    "created_at": current_date, "updated_at": current_date
                }
            )
            
            # --- 3. 採番された新しいお土産IDを取得 ---
            new_souvenir_id = result.lastrowid
            conn.commit() # INSERTを確定

            # --- 4. 画像があれば、IDを使ってファイル名を決定し、GCSにアップロード ---
            if image_file and image_file.filename != '':
                ext = image_file.filename.rsplit('.', 1)[1].lower()
                filename = f"{new_souvenir_id}.{ext}"
                image_url = upload_to_gcs(image_file, filename)

            # --- 5. RAGテキストがあれば、IDを使ってファイル名を決定し、GCSにアップロード ---
            try:
                # 1. 全10項目のデータをリストにまとめる (順序が重要です)
                # ※変数名はご自身のプログラムに合わせて変更してください
                souvenir_data = [
                    new_souvenir_id,
                    name, 
                    image_url, 
                    category, 
                    purchase_location, 
                    price, 
                    expiration_date, 
                    product_url,
                    rag_memo,
                    memo
                ]

                # 2. 各項目内の「"」を「""」に変換し（CSVのエスケープ処理）、全体を「"」で囲む
                # formatted_dataを格納するための空のリストを準備
                formatted_data = []
                # souvenir_dataの各項目を順番に処理
                for item in souvenir_data:
                    # 1. データを文字列に変換し、中の「"」を「""」にエスケープ
                    escaped_item = str(item).replace('"', '""')
                    # 2. エスケープした文字列全体を「"」で囲む
                    quoted_item = f'"{escaped_item}"'
                    # 3. 完成した文字列をリストに追加
                    formatted_data.append(quoted_item)
                
                # 3. カンマで連結してCSVの一行を作成
                csv_line = ",".join(formatted_data)

                # 4. 作成したCSV行をGCSにアップロード
                rag_filename = f"{new_souvenir_id}.txt"
                bucket = storage_client.bucket(BUCKET_WEB)
                blob = bucket.blob(rag_filename)
                
                # 作成したcsv_lineをアップロードする
                blob.upload_from_string(csv_line, content_type="text/plain; charset=utf-8")
                
                search_file_path = f"gs://{BUCKET_WEB}/{rag_filename}"
                print(f"✅ RAGデータをCSV形式でGCSに保存しました: {search_file_path}")

            except Exception as e:
                print(f"🚨 RAGデータのGCSへの保存中にエラーが発生しました: {e}")


            # --- 6. GCSのパスをDBにUPDATEで保存 ---
            if image_url or search_file_path:
                query_update = sqlalchemy.text("""
                    UPDATE souvenir SET image = :image, search_file = :search_file
                    WHERE souvenir_uid = :souvenir_uid
                """)
                conn.execute(
                    query_update, parameters={
                        "image": image_url,
                        "search_file": search_file_path,
                        "souvenir_uid": new_souvenir_id
                    }
                )
                conn.commit() # UPDATEを確定

    except Exception as e:
        logger.exception(e)
        return Response("DB operation failed!", status=500)

    return render_template('souvenir/create_action.html')

@souvenir_bp.route('/souvenir/update_input')
def souvenir_update_input():
    souvenir_uid = request.args.get('souvenir_uid', type=int)

    query = """
        SELECT
            souvenir_uid,
            name,
            image,
            category,
            purchase_location,
            price,
            expiration_date,
            product_url,
            memo,
            rag_memo,
            search_text,
            search_file,
            DATE_FORMAT(created_at, '%Y/%m/%d %H:%i:%s') AS created_at,
            DATE_FORMAT(updated_at, '%Y/%m/%d %H:%i:%s') AS updated_at
        FROM
            souvenir
        WHERE
            souvenir_uid = :souvenir_uid;
    """

    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            res = conn.execute(stmt, parameters={"souvenir_uid": souvenir_uid})
            souvenir = res.fetchone()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )
    return render_template('souvenir/update_input.html', souvenir=souvenir)

@souvenir_bp.route('/souvenir/update_action', methods=['POST'])
def souvenir_update_action():
    souvenir_uid = request.form.get('souvenir_uid', type=int)
    name = request.form.get('name')
    category = request.form.get('category')
    purchase_location = request.form.get('purchase_location')
    price = request.form.get('price', type=int)
    expiration_date = request.form.get('expiration_date')    
    product_url = request.form.get('product_url')
    memo = request.form.get('memo')
    rag_memo = request.form.get('rag_memo')

    # 新しい画像ファイルと、既存の画像URLの両方を取得
    image_file = request.files.get('image')
    current_image_url = request.form.get('current_image', '')

    # --- 2. 画像のアップロード処理 ---
    # デフォルトでは既存のURLを使い、新しいファイルがあれば上書きする
    image_url_to_save = current_image_url

    if image_file and image_file.filename != '':
        # 新しい画像がアップロードされた場合の処理
        try:
            ext = image_file.filename.rsplit('.', 1)[1].lower()
            filename = f"{souvenir_uid}.{ext}"
            image_url_to_save = upload_to_gcs(image_file, filename)
        except Exception as e:
            logger.exception(f"GCSへの画像アップロード中にエラー: {e}")
            return Response("Image upload failed!", status=500)

        # --- 3. RAG用テキストファイルの更新処理 ---
    # (以前の回答を参考に、rag_memoをGCSにアップロードし、search_file_pathを取得する処理をここに追加)
    search_file_path = None
    try:
        # 1. 全10項目のデータをリストにまとめる (順序が重要です)
        # ※変数名はご自身のプログラムに合わせて変更してください
        souvenir_data = [
            souvenir_uid,
            name, 
            image_url_to_save, 
            category, 
            purchase_location, 
            price, 
            expiration_date, 
            product_url,
            rag_memo,
            memo
        ]

        # 2. 各項目内の「"」を「""」に変換し（CSVのエスケープ処理）、全体を「"」で囲む
        # formatted_dataを格納するための空のリストを準備
        formatted_data = []
        # souvenir_dataの各項目を順番に処理
        for item in souvenir_data:
            # 1. データを文字列に変換し、中の「"」を「""」にエスケープ
            escaped_item = str(item).replace('"', '""')
            # 2. エスケープした文字列全体を「"」で囲む
            quoted_item = f'"{escaped_item}"'
            # 3. 完成した文字列をリストに追加
            formatted_data.append(quoted_item)
        
        # 3. カンマで連結してCSVの一行を作成
        csv_line = ",".join(formatted_data)

        # 4. 作成したCSV行をGCSにアップロード
        rag_filename = f"{souvenir_uid}.txt"
        bucket = storage_client.bucket(BUCKET_WEB)
        blob = bucket.blob(rag_filename)
        
        # 作成したcsv_lineをアップロードする
        blob.upload_from_string(csv_line, content_type="text/plain; charset=utf-8")
        
        search_file_path = f"gs://{BUCKET_WEB}/{rag_filename}"
        print(f"✅ RAGデータをCSV形式でGCSに保存しました: {search_file_path}")

    except Exception as e:
        print(f"🚨 RAGデータのGCSへの保存中にエラーが発生しました: {e}")

            
    # --- 4. データベースを更新 ---
    search_text = f'{name},{category},{purchase_location},{memo},{rag_memo}'
    current_date = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).strftime('%Y-%m-%d %H:%M:%S')

    query = """
        UPDATE souvenir
        SET
            name = :name,
            image = :image,
            category = :category,
            purchase_location = :purchase_location,
            price = :price,
            expiration_date = :expiration_date,
            product_url = :product_url,
            memo = :memo, 
            rag_memo = :rag_memo,
            search_text = :search_text,
            search_file = :search_file,
            updated_at = :updated_at
        WHERE
            souvenir_uid = :souvenir_uid
    """
    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            conn.execute(
                stmt, parameters={
                    "souvenir_uid": souvenir_uid,
                    "name": name,
                    "image": image_url_to_save, # ← 保存する最終的な画像URL
                    "category": category,
                    "purchase_location": purchase_location,
                    "price": price,
                    "expiration_date": expiration_date,
                    "product_url": product_url,
                    "memo": memo,
                    "rag_memo": rag_memo,
                    "search_text": search_text,
                    "search_file": search_file_path,
                    "updated_at": current_date
                }
            )
            conn.commit()
    except Exception as e:
        logger.exception(e)
        return Response("DB update failed!", status=500)

    # --- 5. 更新後の詳細ページにリダイレクト ---
    souvenir = {
    'souvenir_uid': souvenir_uid
    }
    return render_template('souvenir/update_action.html', souvenir=souvenir)

@souvenir_bp.route('/souvenir/delete_input')
def souvenir_delete_input():
    souvenir_uid = request.args.get('souvenir_uid', type=int)

    query = """
        SELECT
            souvenir_uid,
            name,
            image,
            category,
            purchase_location,
            price,
            expiration_date,
            product_url,
            memo,
            rag_memo,
            search_text,
            search_file,
            DATE_FORMAT(created_at, '%Y/%m/%d %H:%i:%s') AS created_at,
            DATE_FORMAT(updated_at, '%Y/%m/%d %H:%i:%s') AS updated_at
        FROM
            souvenir
        WHERE
            souvenir_uid = :souvenir_uid;
    """

    stmt = sqlalchemy.text(query)
    try:
        with db_conn.connect() as conn:
            res = conn.execute(stmt, parameters={"souvenir_uid": souvenir_uid})
            souvenir = res.fetchone()
    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    return render_template('souvenir/delete_input.html', souvenir=souvenir)

@souvenir_bp.route('/souvenir/delete_action', methods=['POST'])
def souvenir_delete_action():
    souvenir_uid = request.form.get('souvenir_uid', type=int)

    try:
        with db_conn.connect() as conn:
            # --- ステップ1: 削除するファイルのパスをDBから取得 ---
            query_select = sqlalchemy.text("SELECT search_file FROM souvenir WHERE souvenir_uid = :souvenir_uid")
            res = conn.execute(query_select, parameters={"souvenir_uid": souvenir_uid})
            souvenir_data = res.fetchone()
            
            search_file_path = None
            if souvenir_data:
                search_file_path = souvenir_data[0]

            # --- ステップ2: Cloud Storage上のファイルを削除 ---
            if search_file_path:
                try:
                    # gs://bucket-name/file-name.txt の形式からファイル名だけを抽出
                    if search_file_path.startswith(f"gs://{BUCKET_WEB}/"):
                        filename_to_delete = search_file_path.replace(f"gs://{BUCKET_WEB}/", "")
                        
                        bucket = storage_client.bucket(BUCKET_WEB)
                        blob = bucket.blob(filename_to_delete)
                        if blob.exists():
                            blob.delete()
                            print(f"✅ GCSファイル {filename_to_delete} を削除しました。")
                except Exception as e:
                    print(f"❌ GCSファイルの削除に失敗しました: {e}")
                    # GCSファイルの削除に失敗しても、DBの削除は試みる
            
            # --- ステップ3: データベースのレコードを削除 ---
            query_delete = sqlalchemy.text("DELETE FROM souvenir WHERE souvenir_uid = :souvenir_uid")
            conn.execute(query_delete, parameters={"souvenir_uid": souvenir_uid})
            conn.commit()

    except Exception as e:
        logger.exception(e)
        return Response(
            status=500,
            response="transaction error!",
        )

    return render_template('souvenir/delete_action.html')

@souvenir_bp.route('/souvenir/autofill', methods=['POST'])
def souvenir_autofill():
    """お土産名をもとにAIで情報を生成し、JSONで返すAPI"""
    
    # JavaScriptから送られてきたJSONデータを取得
    data = request.get_json()
    name = data.get('name')

    if not name:
        return jsonify({"error": "souvenir name is required"}), 400

    # 各項目をAIで生成
    price_str = get_souvenir_info(name, "price").replace(',', '').replace('円', '')
    
    # 生成したデータを辞書にまとめる
    autofill_data = {
        "category": get_souvenir_info(name, "category"),
        "purchase_location": get_souvenir_info(name, "purchase_location"),
        "price": int(price_str) if price_str.isdigit() else 0,
        "expiration_date": get_souvenir_info(name, "expiration_date"),
        "product_url": get_souvenir_info(name, "product_url"),
        "rag_memo": get_souvenir_info(name, "rag_memo")
    }

    # 辞書をJSON形式でフロントエンドに返す
    return jsonify(autofill_data)