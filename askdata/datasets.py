"""内置数据集的中文说明。列的取值范围、可选值由 db.py 自动统计，这里只写人才知道的含义。"""

OLIST_META: dict[str, tuple[str, dict[str, str]]] = {
    "orders": ("订单表，一行一个订单", {
        "order_id": "订单 ID",
        "customer_id": "下单身份 ID，关联 customers.customer_id（每个订单一个，不能用来数用户）",
        "status": "订单状态：delivered 已送达、shipped 已发货、canceled 已取消、unavailable 缺货、"
                  "invoiced 已开票、processing 处理中、created 已创建、approved 已审核",
        "purchase_time": "下单时间",
        "approved_time": "付款审核通过时间",
        "shipped_time": "交给物流的时间",
        "delivered_time": "用户签收时间，未送达为空",
        "estimated_delivery_date": "平台承诺的送达日期",
    }),
    "order_items": ("订单明细，一行一件商品；一个订单买了几件就有几行", {
        "order_id": "订单 ID，关联 orders.order_id",
        "item_seq": "这件商品是订单里的第几件，从 1 开始",
        "product_id": "商品 ID，关联 products.product_id",
        "seller_id": "卖家 ID，关联 sellers.seller_id",
        "shipping_limit_time": "卖家最晚发货时间",
        "price": "商品价格，单位巴西雷亚尔（BRL）",
        "freight_value": "这件商品分摊的运费（BRL）",
    }),
    "payments": ("支付记录，一个订单可能分几笔支付（比如信用卡加代金券）", {
        "order_id": "订单 ID，关联 orders.order_id",
        "payment_seq": "这是订单的第几笔支付",
        "payment_type": "支付方式：credit_card 信用卡、boleto 银行票据、voucher 代金券、"
                        "debit_card 借记卡、not_defined 未知",
        "installments": "分期期数，1 表示不分期",
        "payment_value": "这笔支付的金额（BRL）",
    }),
    "reviews": ("订单评价", {
        "review_id": "评价 ID",
        "order_id": "订单 ID，关联 orders.order_id",
        "score": "评分 1 到 5，5 分最好",
        "comment_title": "评价标题，葡萄牙语，大多为空",
        "comment_message": "评价正文，葡萄牙语，大多为空",
        "created_time": "邀请用户评价的时间",
        "answered_time": "用户提交评价的时间",
    }),
    "customers": ("用户表。customer_id 每个订单一个；同一个真实用户用 customer_unique_id 识别", {
        "customer_id": "下单身份 ID，关联 orders.customer_id",
        "customer_unique_id": "真实用户 ID，数用户数、算复购都用它",
        "zip_prefix": "邮编前 5 位",
        "city": "城市，葡萄牙语小写",
        "state": "州缩写，关联 states.state",
    }),
    "products": ("商品表", {
        "product_id": "商品 ID",
        "category": "商品类目（中文）",
        "category_pt": "商品类目的葡萄牙语原名",
        "name_length": "商品标题字数",
        "description_length": "商品描述字数",
        "photos_qty": "商品图片数",
        "weight_g": "重量（克）",
        "length_cm": "长（厘米）",
        "height_cm": "高（厘米）",
        "width_cm": "宽（厘米）",
    }),
    "sellers": ("卖家表", {
        "seller_id": "卖家 ID",
        "zip_prefix": "邮编前 5 位",
        "city": "城市，葡萄牙语小写",
        "state": "州缩写，关联 states.state",
    }),
    "states": ("巴西各州", {
        "state": "州缩写",
        "state_name": "中文州名",
        "region": "所属大区",
    }),
}

OLIST_NOTES = [
    "表之间的关系：orders.customer_id = customers.customer_id；order_items.order_id = orders.order_id；"
    "order_items.product_id = products.product_id；order_items.seller_id = sellers.seller_id；"
    "payments.order_id = orders.order_id；reviews.order_id = orders.order_id；"
    "customers.state 和 sellers.state 都关联 states.state。",
    "数据时间：2016-09 到 2018-10，2017-01 到 2018-08 的数据是完整的。用户说“最近”时，以 2018-08 为最后一个完整月。",
    "销售额（GMV）默认用 order_items.price 求和，不含运费，只统计有效订单（排除 status 为 canceled 和 unavailable 的订单）；"
    "订单量、用户数、商品件数默认统计全部订单，用户另有说明时再排除。",
    "order_items 一个订单可能有多行（多件商品），reviews 也有少数订单有多条评价。按订单算订单数、评分、差评率时，"
    "先在子查询里按 order_id 聚合或用 count(DISTINCT order_id)，避免关联后重复计算。",
    "按类目统计时排除 category 为空的商品。",
    "金额单位是巴西雷亚尔（BRL）。",
    "数用户数用 customers.customer_unique_id 去重，不要用 customer_id。",
    "配送天数 = date_diff('day', purchase_time, delivered_time)，只看 delivered_time 不为空的订单。",
    "数据里没有退货记录。被问到退货率时要说明这一点，可以用取消率或 1–2 分差评率代替，并在结论里说清楚用的是哪个。",
]

# 取值太长、对写 SQL 帮助不大的列，只给几个例子。
OLIST_HIDE_VALUES = {"products.category_pt"}
