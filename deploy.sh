#/bin/sh
# set environment valiables
PROJECT_ID=silent-blend-470307-e6
BUCKET_WEB=rec-svn1
BUCKET_RAG=rec-svn-rag
DATA_STORE_ID=rag-datastore_1758014250191
REGION=asia-northeast1
AR_REPO=rec-svn
SERVICE_NAME=rec-svn
SA_NAME=sa-app
DB_USER=root
DB_PASS='1234Abcd!'
DB_NAME=rec_svn_db
INSTANCE_NAME=rec-svn-db

# プロジェクト設定の変更
gcloud config set project ${PROJECT_ID}

# PUSH to Artifact Registry
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
  --project=$PROJECT_ID

# deploy to ClouGOOGLE_API_KEY
gcloud run deploy $SERVICE_NAME --port 7860 \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
  --service-account=$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com \
  --region=$REGION \
  --project=$PROJECT_ID \
  --set-env-vars=PROJECT_ID=$PROJECT_ID,LOCATION=$REGION \
  --set-secrets=DB_PASS=db-password-secret:latest \
  --set-secrets=GOOGLE_API_KEY=google-api-key:latest \
  --allow-unauthenticated \
  --set-env-vars INSTANCE_CONNECTION_NAME=$PROJECT_ID:$REGION:$INSTANCE_NAME \
  --set-env-vars DB_USER=$DB_USER \
  --set-env-vars BUCKET_WEB=$BUCKET_WEB \
  --set-env-vars BUCKET_RAG=$BUCKET_RAG \
  --set-env-vars DB_NAME=$DB_NAME \
  --set-env-vars REGION=$REGION