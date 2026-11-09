# 评测报告

> 由 `python -m evaluation.run` 在提交 4566c7f 上生成（DeepSeek 和 GLM-4-Flash 各跑 115 题 × 3 种配置）。只有最后一段 GLM 错题明细太长，改写成了摘要，其余是原文。

运行日期：2026-11-09；题目 115 道（有标准答案的按结果判分，另有 2 道考察拒答）。
实际调用的模型版本：deepseek-flash → deepseek-flash；glm-4-flash → glm-4-flash-250414。

## 总体准确率

| 模型 | 配置 | 准确率 | 95% 置信区间 | SQL 报过错 | 自动修正成功 | 平均调用次数 | 平均 tokens | 平均耗时 |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| deepseek-flash | 只给表名和列名，不纠错 | 87.6%（99/113） | 80.3% – 92.5% | 0 题 | 0 题 | 2.0 | 2,411 | 2.7 秒 |
| deepseek-flash | 加上中文字段说明和业务口径 | 96.5%（109/113） | 91.3% – 98.6% | 0 题 | 0 题 | 2.0 | 6,585 | 2.6 秒 |
| deepseek-flash | 再加报错自动修正（线上配置） | 96.5%（109/113） | 91.3% – 98.6% | 0 题 | 0 题 | 2.0 | 6,583 | 2.6 秒 |
| glm-4-flash | 只给表名和列名，不纠错 | 30.1%（34/113） | 22.4% – 39.1% | 46 题 | 0 题 | 1.6 | 1,462 | 3.2 秒 |
| glm-4-flash | 加上中文字段说明和业务口径 | 47.8%（54/113） | 38.8% – 56.9% | 39 题 | 0 题 | 1.7 | 5,146 | 4.7 秒 |
| glm-4-flash | 再加报错自动修正（线上配置） | 62.8%（71/113） | 53.6% – 71.2% | 41 题 | 22 题 | 2.5 | 7,801 | 7.8 秒 |

## 每一步带来多少提升

同一批题配对比较；p 值来自 McNemar 精确检验，小于 0.05 说明提升不太可能是偶然。

| 模型 | 变化 | 提升 | 改对 | 改错 | p 值 |
| --- | --- | ---: | ---: | ---: | ---: |
| deepseek-flash | 只给表名和列名，不纠错 → 加上中文字段说明和业务口径 | +8.8 个百分点 | 12 | 2 | 0.0129 |
| deepseek-flash | 加上中文字段说明和业务口径 → 再加报错自动修正（线上配置） | +0.0 个百分点 | 0 | 0 | 1 |
| glm-4-flash | 只给表名和列名，不纠错 → 加上中文字段说明和业务口径 | +17.7 个百分点 | 30 | 10 | 0.00222 |
| glm-4-flash | 加上中文字段说明和业务口径 → 再加报错自动修正（线上配置） | +15.0 个百分点 | 20 | 3 | 0.000488 |

注意：deepseek-flash 在“再加报错自动修正（线上配置）”配置下没有一题的 SQL 执行出错，自动修正没有机会起作用，这一行的差别来自模型输出本身的随机波动。

## 按难度（再加报错自动修正（线上配置））

| 模型 | 易 | 中 | 难 |
| --- | ---: | ---: | ---: |
| deepseek-flash | 100.0%（33/33） | 98.1%（53/54） | 88.5%（23/26） |
| glm-4-flash | 84.8%（28/33） | 59.3%（32/54） | 42.3%（11/26） |

## 数据里没有的问题：能否如实说明

| 模型 | 配置 | 正确拒答 |
| --- | --- | ---: |
| deepseek-flash | 只给表名和列名，不纠错 | 2/2 |
| deepseek-flash | 加上中文字段说明和业务口径 | 2/2 |
| deepseek-flash | 再加报错自动修正（线上配置） | 2/2 |
| glm-4-flash | 只给表名和列名，不纠错 | 2/2 |
| glm-4-flash | 加上中文字段说明和业务口径 | 2/2 |
| glm-4-flash | 再加报错自动修正（线上配置） | 2/2 |

## 答错的题（再加报错自动修正（线上配置））

- **deepseek-flash · h02** 2018 年 2 到 8 月里，销售额环比增长最多的是哪个月？　结果和标准答案不一致
  - 模型的 SQL：`WITH m AS ( SELECT strftime(o.purchase_time, '%Y-%m') AS ym, SUM(oi.price) AS gmv FROM orders o JOIN order_items oi ON oi.order_id = o.order_id WHERE o.status NOT IN ('canceled','unavailable') AND o.purchase_time >= TIMESTAMP '2018-01-01' AND o.purchase_time < TIMESTAMP '2018-09-01' GROUP BY 1 ) SEL`
- **deepseek-flash · p05** 用了不止一种支付方式的订单有多少个？　结果和标准答案不一致
  - 模型的 SQL：`SELECT count(*) AS "多笔支付订单数" FROM (SELECT order_id FROM payments GROUP BY order_id HAVING count(*) > 1) t`
- **deepseek-flash · r02** 差评（1 到 2 分）订单的平均配送天数，比好评（4 到 5 分）订单多几天？　结果和标准答案不一致
  - 模型的 SQL：`WITH r AS ( SELECT order_id, min(score) AS score FROM reviews GROUP BY order_id ), d AS ( SELECT o.order_id, date_diff('day', o.purchase_time, o.delivered_time) AS days FROM orders o WHERE o.delivered_time IS NOT NULL ) SELECT CASE WHEN r.score <= 2 THEN '差评(1-2分)' ELSE '好评(4-5分)' END AS "分组", count`
- **deepseek-flash · u06** 2017 年下过单的用户里，有多少人在 2018 年也下过单？　结果和标准答案不一致
  - 模型的 SQL：`WITH u AS ( SELECT DISTINCT c.customer_unique_id AS uid, strftime(o.purchase_time, '%Y') AS yr FROM orders o JOIN customers c ON o.customer_id = c.customer_id WHERE o.status NOT IN ('canceled','unavailable') ) SELECT (SELECT count(DISTINCT uid) FROM u WHERE yr='2017') AS "2017年下单用户数", (SELECT count(`
- glm-4-flash 答错 42 道，主要原因：把字段放错了表（比如在 orders 里找 customer_unique_id、state、seller_id）、别名未定义或缺少关联、没有遵守“订单量和用户数默认统计全部订单”的口径、BETWEEN 漏掉月底最后一天，另有 3 道服务端返回空回复。逐题明细保存在运行评测的电脑上（records.jsonl）。
