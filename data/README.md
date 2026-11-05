# 数据说明

`olist/` 里是处理好的 8 张表（parquet 格式，共约 10 MB），应用启动时整体载入内存。

| 表 | 行数 | 内容 |
| --- | ---: | --- |
| orders | 99,441 | 订单：状态、下单/发货/签收时间 |
| order_items | 112,650 | 订单明细：商品、卖家、价格、运费 |
| payments | 103,886 | 支付：方式、分期、金额 |
| reviews | 100,000 | 评价：1–5 分、评价时间 |
| customers | 99,441 | 用户：真实用户 ID、城市、州 |
| products | 32,951 | 商品：中文类目、尺寸重量 |
| sellers | 3,095 | 卖家：城市、州 |
| states | 27 | 巴西各州：中文州名、所属大区 |

## 来源与许可

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)，
许可为 CC BY-NC-SA 4.0（署名、非商业、相同方式共享）。本项目只用于学习和展示。

## 做了哪些处理

由 `scripts/build_olist.py` 生成，可以重跑复现：

- 从 GitHub 上的公开镜像下载原始 CSV，逐个校验 sha256，和 Kaggle 原版一致。
- 列名统一成简短的英文（如 `order_purchase_timestamp` → `purchase_time`），时间列转成时间类型，金额转成两位小数。
- 32 位十六进制 ID 只保留前 12 位：已验证每类 ID 截断后仍然唯一，文件小一半，结果也更好读。
- 商品类目和州名补上中文（本项目自译），方便直接用中文提问。
