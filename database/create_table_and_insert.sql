CREATE TABLE giftee (
    giftee_uid MEDIUMINT NOT NULL AUTO_INCREMENT COMMENT 'UID',
    name VARCHAR(255) NOT NULL COMMENT '名前',
    relationship VARCHAR(100) COMMENT '関係',
    area VARCHAR(255) COMMENT '住所・所在地',
    gender VARCHAR(255) COMMENT '性別',
    number_of_people INT COMMENT '人数',
    favorite TEXT COMMENT '好きなもの',
    dislikes TEXT COMMENT '嫌いなもの',
    caution TEXT COMMENT '注意事項<br>例：持病、アレルギー、幼児・妊婦の有無、宗教上の規則',
    memo TEXT COMMENT 'メモ',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '登録日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    PRIMARY KEY (giftee_uid)
);

CREATE TABLE souvenir (
    souvenir_uid MEDIUMINT NOT NULL AUTO_INCREMENT COMMENT 'UID',
    name VARCHAR(255) NOT NULL COMMENT '品名',
    image VARCHAR(1000) COMMENT '画像',
    category VARCHAR(255) NOT NULL COMMENT 'カテゴリ',
    purchase_location VARCHAR(255) COMMENT '購入場所',
    price INT COMMENT 'ひとつあたりの価格 (円)',
    expiration_date VARCHAR(255) COMMENT '日持ち',
    product_url TEXT COMMENT '商品URL',
    memo TEXT COMMENT 'メモ',
    rag_memo TEXT COMMENT 'RAGメモ※少なくとも商品の特徴、保存方法、個数、個包装か否か、アレルゲン、発売期間、飛行機等での制限',
    search_text TEXT COMMENT 'キーワード検索用',
    search_file VARCHAR(1000) COMMENT 'RAGでのレコメンド用ファイルのパス',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '登録日',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日',
    PRIMARY KEY (souvenir_uid)
);
