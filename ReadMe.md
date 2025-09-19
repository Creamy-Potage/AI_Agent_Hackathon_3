# すうべに屋の環境構築について

## CloudSQL for MySQLの構築

以下のURLを参考に、DBインスタンスとデータベースを作成してください。
※ ユーザの作成以降は実施しなくて大丈夫です。

https://zenn.dev/hi_ka_ru/articles/cloudsql-20240602

- インスタンスの作成

| 項目 | 入力値 |
| ---- | ---- |
| インスタンスID | rec-svn-db |
| パスワード | {your PASSWORD} |
| データベースのバージョン | MySQL8.0 |
| CloudSQLのエディションの選択 | Enterprise |
| プリセット | サンドボックス |
| リージョン | asia-northeast1 |
| ゾーンの可用性 | シングルゾーン |
| プライマリゾーン | 任意 |
| マシン | 共有コア（1vCPU, 0.614GB） |
※ パスワードポリシーはデフォルトでOKです。

- データベースの作成

| 項目 | 入力値 |
| ---- | ---- |
| データベース名 | rec_svn_db |
| 文字セット | utf-8 |
| 照合 | デフォルト照合 |

### データベースの初期化

Cloud Shellを開き、以下のコマンドで、データベースにアクセスする。

```
gcloud sql connect rec-svn-db --user=root
```

パスワードを聞かれるので、インスタンス作成時に設定したパスワードを入力。

```
use rec_svn_db;
```

以下のSQLを実行する（ファイルを開いて、コピペでもOK）。

- rec-svn/database/create_table_and_insert.sql

## Cloud Storageのバケット作成

本アプリでは、以下の2つのバケットを使用するので、以下の2つのバケットをGUI画面にて作成する。

- お土産画像管理用バケット（Web表示用）
- お土産検索用バケット（RAG（VertexAISearch）用）

（バケット設定時の例を以下に示すので、参考にしてください。）
・バケット名：rec-svn
・ロケーションタイプ：Resion（asia-northeast1）
・データの保管方法：デフォルト→Standard
・オブジェクトへのアクセス制御：
　‐「公開アクセス禁止を適用」のチェックボックスを外す
　‐アクセス制御：均一

作成後、お土産画像管理用バケット（Web表示用）側のバケットに、Web画面で表示できるように、
以下のコマンドを用いて、公開設定を行う。※ BUCKET_WEBの修正を忘れずに実施してください。

```
gcloud storage buckets add-iam-policy-binding gs://${BUCKET_WEB} \
  --member="allUsers" \
  --role="roles/storage.objectViewer"
```

## お土産検索用RAG（VertexAISearch（AI Applications）の準備）
以下を参考に、Agent Builder（AI Applications）にて、VertexAISearch用のデータストアを作成し、
データストアのID（例：rec-svn-rag_1234567890xxx_gcs_store）を取得する。
  - データストア
    ‐ データソース：cloud storage
    - データの種類：非構造化ドキュメント（PDF、HTML、TXTなど）
    - 周期の頻度：定期的（1日ごと）
    - インポートするフォルダ：{上記で作成した、お土産検索用バケット（RAG（VertexAISearch）用）のバケット名}
    - データコネクタのロケーション：global
    - データコネクタ名：rec-svn-rag

## Webアプリ環境の構築
PROJECT_ID・BUCKET_WEB・BUCKET_RAG・DATA_STORE_ID・DB_PASSの値を修正した後、以下のコマンド実行する。
※ GitからソースをCloneしたら、フォルダ名を"AI_Agent_Hackathon_3"から、"rec-svn"に変更してください。

```
#/bin/sh
# set environment valiables
PROJECT_ID={your PROJECT_ID}
BUCKET_WEB={your BUCKET_WEB}
BUCKET_RAG={your BUCKET_RAG}
DATA_STORE_ID={your DATA_STORE_ID}
REGION=asia-northeast1
AR_REPO=rec-svn
SERVICE_NAME=rec-svn
SA_NAME=sa-app
DB_USER=root
DB_PASS={your DB_PASS}
DB_NAME=rec_svn_db
INSTANCE_NAME=rec-svn-db

# プロジェクト設定の変更
gcloud config set project ${PROJECT_ID}

# API有効化 
gcloud services enable --project=$PROJECT_ID run.googleapis.com \ 
artifactregistry.googleapis.com \ 
cloudbuild.googleapis.com \ 
compute.googleapis.com \ 
aiplatform.googleapis.com \ 
iap.googleapis.com 

# サービスアカウントの作成 
gcloud iam service-accounts create ${SA_NAME}  \ 
  --description="アプリのサービスアカウント" \ 
  --display-name="SA-APP" 

gcloud iam service-accounts keys create ~/sa-private-key.json \ 
    --iam-account=${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com 

gcloud projects add-iam-policy-binding ${PROJECT_ID} \ 
 --member "serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \ 
 --role "roles/run.invoker" 

gcloud projects add-iam-policy-binding ${PROJECT_ID} \ 
 --member "serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \ 
 --role "roles/aiplatform.user" 

gcloud projects add-iam-policy-binding ${PROJECT_ID} \ 
 --member "serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \ 
 --role "roles/discoveryengine.user" 

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
 --member "serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
 --role "roles/cloudsql.client"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
 --member "serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
 --role "roles/storage.objectAdmin"

# Artifacts repositories 作成(Webapp)
gcloud artifacts repositories create $AR_REPO \
 --location=$REGION \
 --repository-format=Docker \
 --project=$PROJECT_ID
  
# PUSH to Artifact Registry
cd
cd $SERVICE_NAME

# PUSH to Artifact Registry
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
  --project=$PROJECT_ID

# deploy to Cloud Run
gcloud run deploy $SERVICE_NAME --port 7860 \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
  --service-account=$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com \
  --region=$REGION \
  --project=$PROJECT_ID \
  --set-env-vars PROJECT_ID=$PROJECT_ID \
  --set-env-vars LOCATION=$REGION \
  --set-env-vars INSTANCE_CONNECTION_NAME=$PROJECT_ID:$REGION:$INSTANCE_NAME \
  --set-env-vars DB_USER=$DB_USER \
  --set-env-vars DB_PASS=$DB_PASS \
  --set-env-vars DB_NAME=$DB_NAME \
  --set-env-vars BUCKET_WEB=$BUCKET_WEB \
  --set-env-vars BUCKET_RAG=$BUCKET_RAG \
  --set-env-vars DATA_STORE_ID=$DATA_STORE_ID \
  --set-env-vars REGION=$REGION
```
