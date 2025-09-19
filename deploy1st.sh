#/bin/sh
# set environment valiables
PROJECT_ID=silent-blend-470307-e6
REGION=asia-northeast1
AR_REPO=rec-svn
SERVICE_NAME=rec-svn
SA_NAME=sa-app
DB_USER=root
DB_PASS=1234Abcd!
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

# サービスアカウントの付与
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
 --member "serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" --role "roles/cloudsql.client"

# Artifacts repositories 作成(Webapp)
gcloud artifacts repositories create $AR_REPO \
 --location=$REGION \
 --repository-format=Docker \
 --project=$PROJECT_ID
  
# PUSH to Artifact Registry
#cd
#cd $SERVICE_NAME

# PUSH to Artifact Registry
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
  --project=$PROJECT_ID

# deploy to ClouGOOGLE_API_KEY
gcloud run deploy $SERVICE_NAME --port 7860 \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$AR_REPO/$SERVICE_NAME \
  --service-account=$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com \
  --set-secrets=GOOGLE_API_KEY=google-api-key:latest \
  --region=$REGION \
  --project=$PROJECT_ID \
  --set-env-vars="PROJECT_ID=$PROJECT_ID,LOCATION=$REGION,INSTANCE_CONNECTION_NAME=$PROJECT_ID:$REGION:$INSTANCE_NAME,DB_USER=$DB_USER,DB_PASS=$DB_PASS,DB_NAME=$DB_NAME"