"""下载巴西 Olist 电商公开数据集，清洗后存成 data/olist/*.parquet。

数据集：Brazilian E-Commerce Public Dataset by Olist（Kaggle，CC BY-NC-SA 4.0）。
Kaggle 下载需要登录，这里用 GitHub 上的公开镜像；每个文件都校验 sha256，
保证和 Kaggle 原版逐字节一致（行数：订单 99,441，订单明细 112,650）。

运行：python scripts/build_olist.py
仓库里已经提交了生成好的 parquet，一般不用重跑。
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "olist"

MIRROR_A = "https://raw.githubusercontent.com/xor9237/brazil_ecommerce/master/"
MIRROR_B = "https://raw.githubusercontent.com/dujiaying/olist/master/data/"
FILES = {
    # 文件名: (镜像地址, sha256)
    "olist_orders_dataset.csv": (MIRROR_B, "8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf"),
    "olist_order_items_dataset.csv": (MIRROR_A, "0bc4d068c4fe38cbb01bd90e8746e3c613fe7b4baef75fab7b0e329701c3e279"),
    "olist_order_payments_dataset.csv": (MIRROR_A, "4f713964f2815dbbaa40b9488268c55aac3627bfce5aa96cf58d1f3616de3cc0"),
    "olist_order_reviews_dataset.csv": (MIRROR_A, "0dff69f6fed33a13648020198ea94d7ae12afbdd4904186c6cd904e27a3e1ccd"),
    "olist_customers_dataset.csv": (MIRROR_A, "983a422239e1712ded753b3bf9ecf47dc73f144d306029dcfa99e70a226883d2"),
    "olist_products_dataset.csv": (MIRROR_A, "3e6569628a17fbc75fd206ee357b59e20364b9afa90f5b6cd5b4d624c58aa9cc"),
    "olist_sellers_dataset.csv": (MIRROR_A, "1f643d2b950373b85735e7794b20986f528d7a000432e7c6f9bcbb44d0846a0e"),
}

# 商品类目：葡萄牙语原名 -> 中文（自译）。原数据的英文翻译表少了最后两个类目。
CATEGORY_ZH = {
    "beleza_saude": "美妆健康", "informatica_acessorios": "电脑配件", "automotivo": "汽车用品",
    "cama_mesa_banho": "床品卫浴", "moveis_decoracao": "家具装饰", "esporte_lazer": "运动休闲",
    "perfumaria": "香水", "utilidades_domesticas": "家居日用", "telefonia": "手机通讯",
    "relogios_presentes": "手表礼品", "alimentos_bebidas": "食品饮料", "bebes": "母婴",
    "papelaria": "文具", "tablets_impressao_imagem": "平板与打印影像", "brinquedos": "玩具",
    "telefonia_fixa": "固定电话", "ferramentas_jardim": "园艺工具",
    "fashion_bolsas_e_acessorios": "时尚箱包配饰", "eletroportateis": "小家电",
    "consoles_games": "游戏机与游戏", "audio": "音频设备", "fashion_calcados": "鞋类",
    "cool_stuff": "潮流好物", "malas_acessorios": "行李箱包", "climatizacao": "空调制冷",
    "construcao_ferramentas_construcao": "建筑工具",
    "moveis_cozinha_area_de_servico_jantar_e_jardim": "厨房餐厅园林家具",
    "construcao_ferramentas_jardim": "建筑园艺工具", "fashion_roupa_masculina": "男装",
    "pet_shop": "宠物用品", "moveis_escritorio": "办公家具", "market_place": "平台综合",
    "eletronicos": "电子产品", "eletrodomesticos": "家用电器", "artigos_de_festas": "派对用品",
    "casa_conforto": "家居舒适", "construcao_ferramentas_ferramentas": "建筑五金工具",
    "agro_industria_e_comercio": "农业工商", "moveis_colchao_e_estofado": "床垫与软体家具",
    "livros_tecnicos": "专业书籍", "casa_construcao": "家装建材", "instrumentos_musicais": "乐器",
    "moveis_sala": "客厅家具", "construcao_ferramentas_iluminacao": "照明工具",
    "industria_comercio_e_negocios": "工业商业", "alimentos": "食品", "artes": "艺术品",
    "moveis_quarto": "卧室家具", "livros_interesse_geral": "大众图书",
    "construcao_ferramentas_seguranca": "安防工具", "fashion_underwear_e_moda_praia": "内衣泳装",
    "fashion_esporte": "运动服饰", "sinalizacao_e_seguranca": "标识与安全", "pcs": "电脑整机",
    "artigos_de_natal": "圣诞用品", "fashion_roupa_feminina": "女装",
    "eletrodomesticos_2": "家用电器2", "livros_importados": "进口图书", "bebidas": "饮料",
    "cine_foto": "摄影摄像", "la_cuisine": "厨具", "musica": "音乐", "casa_conforto_2": "家居舒适2",
    "portateis_casa_forno_e_cafe": "烤箱咖啡机", "cds_dvds_musicais": "音乐CD与DVD",
    "dvds_blu_ray": "DVD与蓝光", "flores": "鲜花", "artes_e_artesanato": "手工艺品",
    "fraldas_higiene": "纸尿裤与卫生用品", "fashion_roupa_infanto_juvenil": "童装",
    "seguros_e_servicos": "保险与服务", "pc_gamer": "游戏电脑",
    "portateis_cozinha_e_preparadores_de_alimentos": "厨房小电器",
}

# 巴西 27 个州：缩写, 中文名, 所属大区
STATES = [
    ("AC", "阿克里州", "北部"), ("AL", "阿拉戈斯州", "东北部"), ("AP", "阿马帕州", "北部"),
    ("AM", "亚马孙州", "北部"), ("BA", "巴伊亚州", "东北部"), ("CE", "塞阿拉州", "东北部"),
    ("DF", "联邦区", "中西部"), ("ES", "圣埃斯皮里图州", "东南部"), ("GO", "戈亚斯州", "中西部"),
    ("MA", "马拉尼昂州", "东北部"), ("MT", "马托格罗索州", "中西部"), ("MS", "南马托格罗索州", "中西部"),
    ("MG", "米纳斯吉拉斯州", "东南部"), ("PA", "帕拉州", "北部"), ("PB", "帕拉伊巴州", "东北部"),
    ("PR", "巴拉那州", "南部"), ("PE", "伯南布哥州", "东北部"), ("PI", "皮奥伊州", "东北部"),
    ("RJ", "里约热内卢州", "东南部"), ("RN", "北里奥格兰德州", "东北部"), ("RS", "南里奥格兰德州", "南部"),
    ("RO", "朗多尼亚州", "北部"), ("RR", "罗赖马州", "北部"), ("SC", "圣卡塔琳娜州", "南部"),
    ("SP", "圣保罗州", "东南部"), ("SE", "塞尔希培州", "东北部"), ("TO", "托坎廷斯州", "北部"),
]

# 清洗：统一列名、转时间类型、补中文类目。每张表一条 SQL。
# 原始 ID 是 32 位十六进制，这里只保留前 12 位：已验证每类 ID 截断后仍然唯一，
# 文件小一半，查询结果也更好读。
TABLES = {
    "orders": """
        SELECT left(order_id, 12) AS order_id, left(customer_id, 12) AS customer_id,
               order_status AS status,
               CAST(order_purchase_timestamp AS TIMESTAMP) AS purchase_time,
               CAST(order_approved_at AS TIMESTAMP) AS approved_time,
               CAST(order_delivered_carrier_date AS TIMESTAMP) AS shipped_time,
               CAST(order_delivered_customer_date AS TIMESTAMP) AS delivered_time,
               CAST(order_estimated_delivery_date AS DATE) AS estimated_delivery_date
        FROM read_csv('{raw}/olist_orders_dataset.csv', header=true, all_varchar=true)
        ORDER BY purchase_time, order_id""",
    "order_items": """
        SELECT left(order_id, 12) AS order_id, CAST(order_item_id AS INTEGER) AS item_seq,
               left(product_id, 12) AS product_id, left(seller_id, 12) AS seller_id,
               CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_time,
               CAST(price AS DECIMAL(10, 2)) AS price,
               CAST(freight_value AS DECIMAL(10, 2)) AS freight_value
        FROM read_csv('{raw}/olist_order_items_dataset.csv', header=true, all_varchar=true)
        ORDER BY order_id, item_seq""",
    "payments": """
        SELECT left(order_id, 12) AS order_id, CAST(payment_sequential AS INTEGER) AS payment_seq,
               payment_type,
               CAST(payment_installments AS INTEGER) AS installments,
               CAST(payment_value AS DECIMAL(10, 2)) AS payment_value
        FROM read_csv('{raw}/olist_order_payments_dataset.csv', header=true, all_varchar=true)
        ORDER BY order_id, payment_seq""",
    "reviews": """
        SELECT left(review_id, 12) AS review_id, left(order_id, 12) AS order_id,
               CAST(review_score AS INTEGER) AS score,
               review_comment_title AS comment_title, review_comment_message AS comment_message,
               CAST(review_creation_date AS TIMESTAMP) AS created_time,
               CAST(review_answer_timestamp AS TIMESTAMP) AS answered_time
        FROM read_csv('{raw}/olist_order_reviews_dataset.csv', header=true, all_varchar=true)
        ORDER BY created_time, review_id""",
    "customers": """
        SELECT left(customer_id, 12) AS customer_id, left(customer_unique_id, 12) AS customer_unique_id,
               customer_zip_code_prefix AS zip_prefix,
               customer_city AS city, customer_state AS state
        FROM read_csv('{raw}/olist_customers_dataset.csv', header=true, all_varchar=true)
        ORDER BY customer_id""",
    "products": """
        SELECT left(p.product_id, 12) AS product_id,
               cz.category_zh AS category,
               p.product_category_name AS category_pt,
               CAST(p.product_name_lenght AS INTEGER) AS name_length,
               CAST(p.product_description_lenght AS INTEGER) AS description_length,
               CAST(p.product_photos_qty AS INTEGER) AS photos_qty,
               CAST(p.product_weight_g AS INTEGER) AS weight_g,
               CAST(p.product_length_cm AS INTEGER) AS length_cm,
               CAST(p.product_height_cm AS INTEGER) AS height_cm,
               CAST(p.product_width_cm AS INTEGER) AS width_cm
        FROM read_csv('{raw}/olist_products_dataset.csv', header=true, all_varchar=true) p
        LEFT JOIN category_zh cz ON cz.category_pt = p.product_category_name
        ORDER BY p.product_id""",
    "sellers": """
        SELECT left(seller_id, 12) AS seller_id, seller_zip_code_prefix AS zip_prefix,
               seller_city AS city,
               seller_state AS state
        FROM read_csv('{raw}/olist_sellers_dataset.csv', header=true, all_varchar=true)
        ORDER BY seller_id""",
    "states": "SELECT * FROM states_src ORDER BY state",
}


def download() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, (base, sha) in FILES.items():
        path = RAW / name
        if not path.exists():
            print("下载", name)
            urllib.request.urlretrieve(base + name, path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != sha:
            sys.exit(f"{name} 的 sha256 不对：{digest}")


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("CREATE TABLE category_zh (category_pt VARCHAR, category_zh VARCHAR)")
    con.executemany("INSERT INTO category_zh VALUES (?, ?)", list(CATEGORY_ZH.items()))
    con.execute("CREATE TABLE states_src (state VARCHAR, state_name VARCHAR, region VARCHAR)")
    con.executemany("INSERT INTO states_src VALUES (?, ?, ?)", STATES)
    for table, sql in TABLES.items():
        out = OUT / f"{table}.parquet"
        con.execute(
            f"COPY ({sql.format(raw=RAW.as_posix())}) TO '{out.as_posix()}' "
            "(FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 19)"
        )
        n = con.execute(f"SELECT count(*) FROM '{out.as_posix()}'").fetchone()[0]
        print(f"{table:12s} {n:>8,} 行  {out.stat().st_size / 1e6:5.1f} MB")
    missing = con.execute(
        f"SELECT DISTINCT category_pt FROM '{(OUT / 'products.parquet').as_posix()}' "
        "WHERE category_pt IS NOT NULL AND category IS NULL"
    ).fetchall()
    if missing:
        sys.exit(f"这些类目没有中文名：{missing}")


if __name__ == "__main__":
    download()
    build()
