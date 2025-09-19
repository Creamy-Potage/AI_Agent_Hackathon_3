import os
from google.cloud import storage
import csv
import io

# --- ▼ 設定してください ▼ ---
# 1. あなたのバケット名に書き換えてください
BUCKET_NAME = "rec-svn1" 
# 2. ファイルが保存されているフォルダ名（プレフィックス）を指定してください
#    フォルダがない場合は "" (空文字) にしてください
FOLDER_PREFIX = "" 
# --- ▲ 設定はここまで ▲ ---

def correct_csv_format(content: str) -> str:
    """
    古い形式のCSV文字列を、各項目が引用符で囲まれた新しい形式に変換する。
    古い形式： 100001,"name,image,category,..."
    """
    try:
        # 最初のカンマでIDとそれ以外を分割
        parts = content.strip().split(',', 1)
        if len(parts) != 2:
            raise ValueError("CSV format does not have at least two parts.")

        item_id = parts[0]
        # 残りの部分から前後の「"」を削除
        other_items_str = parts[1].strip().strip('"')

        # カンマ区切りの文字列をリストに変換
        # io.StringIOを使って文字列をファイルのように扱う
        reader = csv.reader(io.StringIO(other_items_str))
        other_items_list = next(reader)

        # IDと結合して全10項目のリストを作成
        all_data = [item_id] + other_items_list

        if len(all_data) != 10:
            raise ValueError(f"Expected 10 columns, but found {len(all_data)}")

        # 各項目を正しく引用符で囲む
        formatted_data = [f'"{str(item).replace("\"", "\"\"")}"' for item in all_data]
        
        # 新しいCSV行を作成
        return ",".join(formatted_data)

    except Exception as e:
        print(f"  -> Error parsing content: {e}")
        return None


# --- メインの処理 ---
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)

print(f"Processing files in gs://{BUCKET_NAME}/{FOLDER_PREFIX} ...")

# 修正対象のファイルを取得
blobs_to_fix = list(bucket.list_blobs(prefix=FOLDER_PREFIX))
fixed_count = 0

for blob in blobs_to_fix:
    if blob.name.endswith('.txt'):
        print(f"Checking: {blob.name}")
        
        # オリジナルの内容をダウンロード
        original_content = blob.download_as_string().decode('utf-8')
        
        # 新しい形式に変換
        new_content = correct_csv_format(original_content)
        
        if new_content:
            # 新しい内容でファイルを上書き
            blob.upload_from_string(new_content, content_type="text/plain; charset=utf-8")
            print(f"  -> ✅ Corrected and overwritten.")
            fixed_count += 1
        else:
            print(f"  -> ⚠️ Skipped due to parsing error.")

print("\n--------------------")
print(f"Done! {fixed_count} files were corrected.")
